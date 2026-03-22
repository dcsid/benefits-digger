from __future__ import annotations

import logging
import re
from datetime import date, datetime
from typing import Any, Optional, Tuple

from sqlalchemy import desc, func, select
from sqlalchemy.orm import Session

from app.catalog import (
    FEDERAL_FEED_PAGE_URL,
    build_fallback_federal_catalog,
    build_fallback_state_directory,
    fetch_remote_federal_catalog,
    fetch_remote_state_directory,
    hash_content,
    is_official_government_url,
    slugify,
)
from app.config import get_settings
from app.gov_crawl import category_keyword_hints, crawl_official_site, filter_relevant_pages
from app.models import (
    Agency,
    AmountRule,
    ChangeEvent,
    EligibilityRule,
    Jurisdiction,
    Program,
    ProgramVersion,
    Question,
    QuestionVariant,
    ReviewTask,
    ScreeningSession,
    SessionAnswer,
    Source,
    SourceSnapshot,
)
from app.normalizers import normalize_answer
from app.rules import evaluate_matches_any, score_status


logger = logging.getLogger(__name__)
settings = get_settings()
BREADTH_ANCHORS: list[tuple[float, dict[str, Any]]] = [
    (0.0, {
        "max_answers": 4,
        "weights": {"low": 1.0, "medium": 0.25, "high": 0.05},
        "bonuses": {"low": 25, "medium": -20, "high": -160},
        "unlock_after": {"low": 0, "medium": 1, "high": 99},
    }),
    (0.5, {
        "max_answers": 10,
        "weights": {"low": 1.0, "medium": 0.95, "high": 0.45},
        "bonuses": {"low": 10, "medium": 10, "high": -15},
        "unlock_after": {"low": 0, "medium": 0, "high": 3},
    }),
    (1.0, {
        "max_answers": 24,
        "weights": {"low": 1.0, "medium": 1.35, "high": 1.9},
        "bonuses": {"low": 0, "medium": 35, "high": 90},
        "unlock_after": {"low": 0, "medium": 0, "high": 1},
    }),
]

LEGACY_CONTROL_MODE_TO_VALUE = {"quick": 0.0, "standard": 0.5, "deep": 1.0}
STATE_RESIDENCY_TERMS = (
    "resident",
    "residency",
    "live in",
    "lives in",
    "lived in",
    "living in",
    "currently live",
    "currently resides",
    "reside in",
    "household in",
    "address in",
    "domiciled",
)
SUBSTATE_LOCATION_TERMS = (
    "county",
    "zip",
    "zip code",
    "zipcode",
    "postal code",
    "city",
    "town",
    "municipality",
    "address",
)


def _lerp(a: float, b: float, t: float) -> float:
    return a + (b - a) * t


def _lerp_dict(a: dict[str, float], b: dict[str, float], t: float, *, round_int: bool = False) -> dict[str, float]:
    result = {}
    for key in a:
        val = _lerp(a[key], b[key], t)
        result[key] = round(val) if round_int else val
    return result


def interpolate_breadth_policy(breadth_value: float) -> dict[str, Any]:
    breadth_value = max(0.0, min(1.0, breadth_value))
    lo_val, lo_pol = BREADTH_ANCHORS[0]
    for anchor_val, anchor_pol in BREADTH_ANCHORS:
        if anchor_val <= breadth_value:
            lo_val, lo_pol = anchor_val, anchor_pol
        else:
            break
    hi_val, hi_pol = BREADTH_ANCHORS[-1]
    for anchor_val, anchor_pol in reversed(BREADTH_ANCHORS):
        if anchor_val >= breadth_value:
            hi_val, hi_pol = anchor_val, anchor_pol
        else:
            break
    if lo_val == hi_val:
        t = 0.0
    else:
        t = (breadth_value - lo_val) / (hi_val - lo_val)
    return {
        "max_answers": round(_lerp(lo_pol["max_answers"], hi_pol["max_answers"], t)),
        "weights": _lerp_dict(lo_pol["weights"], hi_pol["weights"], t),
        "bonuses": _lerp_dict(lo_pol["bonuses"], hi_pol["bonuses"], t),
        "unlock_after": _lerp_dict(lo_pol["unlock_after"], hi_pol["unlock_after"], t, round_int=True),
    }


def depth_value_to_tier(depth_value: float) -> str:
    if depth_value < 0.33:
        return "simple"
    if depth_value < 0.67:
        return "standard"
    return "detailed"


def normalize_match_text(value: Any) -> str:
    if value is None:
        return ""
    return re.sub(r"\s+", " ", str(value).replace("_", " ").strip().lower())


def values_are_booleanish(values: Optional[list[Any]]) -> bool:
    if not values:
        return False
    normalized = {normalize_match_text(value) for value in values if value is not None}
    return bool(normalized) and normalized.issubset({"yes", "no", "true", "false", "1", "0"})


def options_are_booleanish(options: Optional[list[dict[str, Any]]]) -> bool:
    if not options:
        return False
    values = []
    for option in options:
        if not isinstance(option, dict):
            continue
        values.append(option.get("value", option.get("label")))
    return values_are_booleanish(values)


def is_redundant_state_residency_signal(
    *,
    state_code: str,
    state_name: str,
    question_key: Optional[str] = None,
    prompt: Optional[str] = None,
    hint: Optional[str] = None,
    label: Optional[str] = None,
    options: Optional[list[dict[str, Any]]] = None,
    expected_values: Optional[list[Any]] = None,
) -> bool:
    normalized_state_code = normalize_match_text(state_code)
    normalized_state_name = normalize_match_text(state_name)
    normalized_texts = [
        normalize_match_text(question_key),
        normalize_match_text(prompt),
        normalize_match_text(hint),
        normalize_match_text(label),
    ]

    residency_signal = False
    for text in normalized_texts:
        if not text:
            continue
        mentions_state = bool(
            normalized_state_name and normalized_state_name in text
            or normalized_state_code and normalized_state_code in set(text.split())
        )
        mentions_residency = any(term in text for term in STATE_RESIDENCY_TERMS)
        if mentions_state and mentions_residency:
            residency_signal = True
            break

    if not residency_signal:
        return False

    asks_substate_location = any(
        term in text
        for text in normalized_texts
        for term in SUBSTATE_LOCATION_TERMS
    )
    if asks_substate_location:
        return False

    return True


def is_redundant_state_residency_rule(
    *,
    session_state_code: Optional[str],
    program: Program,
    rule: EligibilityRule,
    question: Optional[Question] = None,
) -> bool:
    if not session_state_code or program.jurisdiction.level != "state":
        return False
    if session_state_code.upper() != program.jurisdiction.code.upper():
        return False
    if rule.question_key == "state_code":
        return False
    return is_redundant_state_residency_signal(
        state_code=program.jurisdiction.code,
        state_name=program.jurisdiction.name,
        question_key=rule.question_key,
        prompt=question.prompt if question else None,
        hint=question.hint if question else None,
        label=rule.label,
        options=question.options_json if question else None,
        expected_values=rule.expected_values_json if isinstance(rule.expected_values_json, list) else None,
    )


CATEGORY_FILTER_MAP = {
    "children_families": {"children_families", "family"},
    "death": {"death", "survivor", "funeral_assistance"},
    "disabilities": {"disability", "ssdi", "ssi"},
    "disasters": {"disaster", "funeral_assistance"},
    "education": {"education"},
    "food": {"food"},
    "health": {"health"},
    "housing_utilities": {"housing", "utility"},
    "jobs_unemployment": {"jobs", "unemployment"},
    "military_veterans": {"veteran", "va_disability"},
    "retirement_seniors": {"retirement", "social_security"},
    "welfare_cash_assistance": {"cash", "ssi"},
    "retirement": {"retirement", "social_security"},
    "disability": {"disability", "ssdi", "ssi"},
    "survivor": {"survivor", "funeral_assistance"},
    "veteran": {"veteran", "va_disability"},
    "cash": {"cash", "ssi"},
    "all": set(),
}
CATEGORY_LABELS = {
    "children_families": "Children and families",
    "death": "Death",
    "disabilities": "Disabilities",
    "disasters": "Disasters",
    "education": "Education",
    "food": "Food",
    "health": "Health",
    "housing_utilities": "Housing and utilities",
    "jobs_unemployment": "Jobs and unemployment",
    "military_veterans": "Military and veterans",
    "retirement_seniors": "Retirement and seniors",
    "welfare_cash_assistance": "Welfare and cash assistance",
}
QUESTION_CATEGORY_HINTS = {
    "children_families": {"child", "children", "childcare", "dependent", "family", "parent", "pregnancy"},
    "family": {"child", "children", "childcare", "dependent", "family", "parent", "pregnancy"},
    "death": {"burial", "death", "funeral", "survivor"},
    "survivor": {"burial", "death", "funeral", "survivor"},
    "disabilities": {"accessible", "disability", "disabled", "impairment", "medical", "ssi", "ssdi"},
    "disability": {"accessible", "disability", "disabled", "impairment", "medical", "ssi", "ssdi"},
    "ssdi": {"disability", "disabled", "ssdi", "work credits"},
    "ssi": {"disabled", "income", "resources", "ssi"},
    "disasters": {"disaster", "emergency", "evacuation", "fema", "fire", "flood", "storm"},
    "funeral_assistance": {"burial", "death", "funeral"},
    "education": {"college", "education", "grant", "school", "scholarship", "student", "training", "tuition", "university"},
    "food": {"food", "meal", "nutrition", "snap", "wic"},
    "health": {"coverage", "health", "insurance", "medical", "medicaid", "medicare", "prescription"},
    "housing_utilities": {"electric", "energy", "heating", "home", "housing", "internet", "mortgage", "rent", "rental", "shelter", "utility", "voucher", "water"},
    "housing": {"electric", "energy", "heating", "home", "housing", "internet", "mortgage", "rent", "rental", "shelter", "utility", "voucher", "water"},
    "utility": {"electric", "energy", "heating", "internet", "utility", "water"},
    "jobs_unemployment": {"employment", "job", "laid off", "training", "unemployment", "wage", "worker", "workforce"},
    "jobs": {"employment", "job", "laid off", "training", "unemployment", "wage", "worker", "workforce"},
    "unemployment": {"employment", "job", "laid off", "unemployment", "wage", "worker", "workforce"},
    "military_veterans": {"military", "service", "va", "veteran"},
    "veteran": {"military", "service", "va", "veteran"},
    "va_disability": {"military", "service", "va", "veteran"},
    "retirement_seniors": {"older adult", "pension", "retire", "retirement", "senior", "social security"},
    "retirement": {"older adult", "pension", "retire", "retirement", "senior", "social security"},
    "social_security": {"older adult", "retire", "retirement", "social security"},
    "welfare_cash_assistance": {"assistance", "benefit amount", "cash", "income", "resources", "tanf", "welfare"},
    "cash": {"assistance", "benefit amount", "cash", "income", "resources", "tanf", "welfare"},
}


def bootstrap_catalog(db: Session, use_remote: bool = True) -> None:
    if _table_is_empty(db, Program):
        sync_federal_catalog(db, build_fallback_federal_catalog(), source_mode="seed")
        sync_state_directory(db, build_fallback_state_directory(), source_mode="seed")
        db.commit()

    if use_remote:
        try:
            sync_remote_sources(db)
        except Exception as exc:  # pragma: no cover - defensive logging
            db.rollback()
            logger.warning("Remote sync failed, continuing with seeded catalog: %s", exc)


def sync_remote_sources(db: Session) -> dict[str, Any]:
    summary = {
        "federal": "skipped",
        "states": "skipped",
        "review_tasks_created": 0,
        "crawled_programs": 0,
        "crawl_sources_added": 0,
    }
    federal_catalog = fetch_remote_federal_catalog(settings.request_timeout_seconds)
    state_catalog = fetch_remote_state_directory(settings.request_timeout_seconds)
    try:
        summary["review_tasks_created"] += sync_federal_catalog(db, federal_catalog, source_mode="remote")
        summary["federal"] = "synced"
        summary["review_tasks_created"] += sync_state_directory(db, state_catalog, source_mode="remote")
        summary["states"] = "synced"
        crawl_summary = enrich_catalog_with_crawled_sources(db)
        summary["crawled_programs"] = crawl_summary["crawled_programs"]
        summary["crawl_sources_added"] = crawl_summary["crawl_sources_added"]
        summary["review_tasks_created"] += crawl_summary["review_tasks_created"]
        db.commit()
    except Exception:
        db.rollback()
        raise
    return summary


def sync_federal_catalog(db: Session, catalog: dict[str, Any], source_mode: str) -> int:
    federal = get_or_create_jurisdiction(db, code="federal", level="federal", name="Federal")
    source = upsert_source(
        db,
        key="usagov-benefit-finder-feed",
        title="USA.gov benefit finder feed",
        url="https://www.usa.gov/benefit-finder/all-benefits",
        source_type="api_json",
        authority_rank=85,
        parser_type="api_json",
        fetch_cadence="daily",
        jurisdiction_id=federal.id,
    )
    snapshot, changed, previous_snapshot = create_snapshot(
        db,
        source=source,
        content_hash=catalog["content_hash"],
        content_type=catalog["content_type"],
        raw_excerpt=catalog["raw_excerpt"],
    )
    review_tasks_created = 0
    if changed and previous_snapshot is not None and source_mode == "remote":
        review_tasks_created += create_review_task(
            db,
            source=source,
            previous_snapshot=previous_snapshot,
            current_snapshot=snapshot,
            diff_type="eligibility",
            materiality_score=85,
            notes="Federal benefit feed changed.",
        )

    ensure_base_questions(db)
    upsert_questions(db, catalog["questions"])

    from app.seed_data import QUESTION_VARIANTS
    upsert_question_variants(db, QUESTION_VARIANTS)

    seen_slugs: set[str] = set()
    for benefit in catalog["benefits"]:
        slug = slugify(benefit["title"])
        seen_slugs.add(slug)
        agency = get_or_create_agency(db, federal.id, benefit["agency_title"], benefit.get("source_link"))
        official_program_url = benefit.get("source_link") if is_official_government_url(benefit.get("source_link")) else FEDERAL_FEED_PAGE_URL
        program = db.scalar(select(Program).where(Program.slug == slug))
        if program is None:
            program = Program(
                slug=slug,
                name=benefit["title"],
                kind="benefit",
                category=benefit["category"],
                family=benefit["family"],
                summary=benefit["summary"],
                apply_url=official_program_url,
                documents_json=benefit.get("documents"),
                status="active",
                jurisdiction_id=federal.id,
                agency_id=agency.id,
            )
            db.add(program)
            db.flush()
        else:
            program.name = benefit["title"]
            program.kind = "benefit"
            program.category = benefit["category"]
            program.family = benefit["family"]
            program.summary = benefit["summary"]
            program.apply_url = official_program_url
            program.documents_json = benefit.get("documents") or program.documents_json
            program.status = "active"
            program.agency_id = agency.id

        upsert_source(
            db,
            key=f"program-source:{slug}",
            title=benefit["title"],
            url=official_program_url,
            source_type="program_page",
            authority_rank=80,
            parser_type="link",
            fetch_cadence="weekly",
            program_id=program.id,
            jurisdiction_id=federal.id,
        )

        signature = hash_content(
            {
                "summary": benefit["summary"],
                "apply_url": official_program_url,
                "eligibility": benefit["eligibility"],
                "amount_display": benefit.get("amount_display"),
            }
        )
        latest_version = get_latest_version(db, program.id)
        if latest_version is None or latest_version.signature != signature:
            supersede_published_versions(db, program.id)
            version = ProgramVersion(
                program_id=program.id,
                version_label=f"{source_mode}-{snapshot.content_hash[:8]}",
                signature=signature,
                publication_state="published",
                published_at=datetime.utcnow(),
                change_summary=f"{source_mode.title()} sync from USA.gov benefit feed.",
                source_freshness_days=0,
            )
            db.add(version)
            db.flush()

            for row in benefit["eligibility"]:
                db.add(
                    EligibilityRule(
                        program_version_id=version.id,
                        question_key=row["criteria_key"],
                        operator="matches_any",
                        expected_values_json=row["acceptable_values"],
                        label=row["label"],
                        priority=100,
                        source_key=source.key,
                        source_citation=official_program_url,
                    )
                )

            db.add(
                AmountRule(
                    program_version_id=version.id,
                    amount_type="formula" if benefit.get("amount_formula") else "range",
                    display_text=benefit.get("amount_display"),
                    formula_json=benefit.get("amount_formula"),
                    input_keys=list(benefit["amount_formula"].get("inputs", {}).values()) if benefit.get("amount_formula") and benefit["amount_formula"].get("inputs") else None,
                    min_amount=benefit.get("amount_min"),
                    max_amount=benefit.get("amount_max"),
                    period=benefit.get("amount_period"),
                    source_key=source.key,
                )
            )

    federal_programs = db.scalars(
        select(Program).join(Jurisdiction, Program.jurisdiction_id == Jurisdiction.id).where(
            Jurisdiction.code == "federal",
            Program.kind == "benefit",
        )
    ).all()
    for program in federal_programs:
        if program.slug not in seen_slugs:
            program.status = "paused"

    db.flush()
    return review_tasks_created


def sync_state_directory(db: Session, catalog: dict[str, Any], source_mode: str) -> int:
    federal = get_or_create_jurisdiction(db, code="federal", level="federal", name="Federal")
    source = upsert_source(
        db,
        key="usagov-state-social-services-directory",
        title="USA.gov state social service agencies directory",
        url="https://www.usa.gov/state-social-services",
        source_type="html_page",
        authority_rank=75,
        parser_type="html",
        fetch_cadence="weekly",
        jurisdiction_id=federal.id,
    )
    snapshot, changed, previous_snapshot = create_snapshot(
        db,
        source=source,
        content_hash=catalog["content_hash"],
        content_type=catalog["content_type"],
        raw_excerpt=catalog["raw_excerpt"],
    )
    review_tasks_created = 0
    if changed and previous_snapshot is not None and source_mode == "remote":
        review_tasks_created += create_review_task(
            db,
            source=source,
            previous_snapshot=previous_snapshot,
            current_snapshot=snapshot,
            diff_type="structural",
            materiality_score=60,
            notes="State directory changed.",
        )

    ensure_base_questions(db)

    for agency_row in catalog["agencies"]:
        jurisdiction = get_or_create_jurisdiction(
            db,
            code=agency_row["code"],
            level="state",
            name=agency_row["name"],
            parent_code="federal",
        )
        agency = get_or_create_agency(db, jurisdiction.id, f"{agency_row['name']} social services", agency_row["url"])
        slug = f"state-social-services-{agency_row['code'].lower()}"
        program = db.scalar(select(Program).where(Program.slug == slug))
        summary = f"Official {agency_row['name']} social service agency entry point for state-administered benefits."
        if program is None:
            program = Program(
                slug=slug,
                name=f"{agency_row['name']} state social services",
                kind="referral",
                category="general",
                family="state_entry",
                summary=summary,
                apply_url=agency_row["url"],
                status="active",
                jurisdiction_id=jurisdiction.id,
                agency_id=agency.id,
            )
            db.add(program)
            db.flush()
        else:
            program.name = f"{agency_row['name']} state social services"
            program.kind = "referral"
            program.summary = summary
            program.apply_url = agency_row["url"]
            program.status = "active"
            program.agency_id = agency.id

        upsert_source(
            db,
            key=f"state-program-source:{agency_row['code']}",
            title=f"{agency_row['name']} social services agency",
            url=agency_row["url"],
            source_type="program_page",
            authority_rank=75,
            parser_type="link",
            fetch_cadence="weekly",
            program_id=program.id,
            jurisdiction_id=jurisdiction.id,
        )

        signature = hash_content({"summary": summary, "apply_url": agency_row["url"], "state_code": agency_row["code"]})
        latest_version = get_latest_version(db, program.id)
        if latest_version is None or latest_version.signature != signature:
            supersede_published_versions(db, program.id)
            version = ProgramVersion(
                program_id=program.id,
                version_label=f"{source_mode}-{snapshot.content_hash[:8]}",
                signature=signature,
                publication_state="published",
                published_at=datetime.utcnow(),
                change_summary=f"{source_mode.title()} sync from USA.gov state directory.",
                source_freshness_days=0,
            )
            db.add(version)
            db.flush()
            db.add(
                EligibilityRule(
                    program_version_id=version.id,
                    question_key="state_code",
                    operator="matches_any",
                    expected_values_json=[agency_row["code"]],
                    label=f"You selected {agency_row['name']} for state benefits.",
                    priority=100,
                    source_key=source.key,
                    source_citation=agency_row["url"],
                )
            )
            db.add(
                AmountRule(
                    program_version_id=version.id,
                    amount_type="unknown",
                    display_text="This result is an official state entry point rather than a single benefit amount.",
                    source_key=source.key,
                )
            )

    db.flush()
    return review_tasks_created


def enrich_catalog_with_crawled_sources(db: Session) -> dict[str, int]:
    programs = db.scalars(
        select(Program)
        .where(Program.status == "active")
        .order_by(Program.updated_at.desc(), Program.name.asc())
    ).all()
    programs = [program for program in programs if is_official_government_url(program.apply_url)]
    programs.sort(
        key=lambda program: (
            any(source.source_type == "crawled_page" for source in program.sources),
            program.name.lower(),
        )
    )

    summary = {"crawled_programs": 0, "crawl_sources_added": 0, "review_tasks_created": 0}
    for program in programs[: settings.crawl_max_programs_per_sync]:
        pages = crawl_official_site(
            program.apply_url,
            timeout_seconds=settings.request_timeout_seconds,
            max_pages=settings.crawl_max_pages_per_site,
            max_depth=settings.crawl_max_depth,
            keyword_hints=category_keyword_hints([program.category, program.family or "general"]),
        )
        if not pages:
            continue

        summary["crawled_programs"] += 1
        relevant_pages = filter_relevant_pages(
            pages,
            context_title=program.name,
            jurisdiction_name=program.jurisdiction.name,
            categories=[program.category],
            max_results=settings.crawl_relevant_page_limit,
        )
        for page in relevant_pages:
            source_key = f"crawl:{program.slug}:{hash_content(page['url'])[:12]}"
            existing_source = db.scalar(select(Source).where(Source.key == source_key))
            source = upsert_source(
                db,
                key=source_key,
                title=page["title"],
                url=page["url"],
                source_type="crawled_page",
                authority_rank=78,
                parser_type="html_crawl",
                fetch_cadence="weekly",
                program_id=program.id,
                jurisdiction_id=program.jurisdiction_id,
            )
            if existing_source is None:
                summary["crawl_sources_added"] += 1

            snapshot, changed, previous_snapshot = create_snapshot(
                db,
                source=source,
                content_hash=page["content_hash"],
                content_type=page["content_type"],
                raw_excerpt=page["raw_excerpt"],
            )
            if changed and previous_snapshot is not None:
                summary["review_tasks_created"] += create_review_task(
                    db,
                    source=source,
                    previous_snapshot=previous_snapshot,
                    current_snapshot=snapshot,
                    diff_type="content",
                    materiality_score=45,
                    notes=f"Crawled official page changed for {program.name}.",
                )

    db.flush()
    return summary


def create_session(
    db: Session,
    scope: str,
    state_code: Optional[str],
    categories: list[str],
    depth_mode: str = "standard",
    breadth_value: Optional[float] = None,
    depth_value: Optional[float] = None,
) -> ScreeningSession:
    legacy_value = LEGACY_CONTROL_MODE_TO_VALUE.get(depth_mode, 0.5)
    if breadth_value is None:
        breadth_value = depth_value if depth_value is not None else legacy_value
    if depth_value is None:
        depth_value = legacy_value
    session = ScreeningSession(
        scope=scope,
        state_code=state_code.upper() if state_code else None,
        categories_json=sorted({item for item in categories if item}),
        depth_mode=depth_mode,
        breadth_value=breadth_value,
        depth_value=depth_value,
    )
    db.add(session)
    db.commit()
    db.refresh(session)

    if scope in {"state", "both"} and session.state_code:
        from app.gemini import ensure_state_programs
        ensure_state_programs(db, session.state_code, categories)

    return session


def get_session_or_404(db: Session, public_id: str) -> ScreeningSession:
    session = db.scalar(select(ScreeningSession).where(ScreeningSession.public_id == public_id))
    if session is None:
        raise ValueError("Session not found")
    return session


def upsert_answers(db: Session, session: ScreeningSession, answers: dict[str, Any]) -> None:
    for key, value in answers.items():
        variant = resolve_question_variant(db, key, session.depth_value)
        if variant and variant.normalizer:
            value = normalize_answer(value, key, variant.normalizer)
        answer = db.scalar(
            select(SessionAnswer).where(
                SessionAnswer.session_id == session.id,
                SessionAnswer.question_key == key,
            )
        )
        if answer is None:
            answer = SessionAnswer(session_id=session.id, question_key=key, value_json=value)
            db.add(answer)
        else:
            answer.value_json = value
        if key == "state_code" and isinstance(value, str):
            session.state_code = value.upper()
    db.commit()


def get_answers_map(db: Session, session: ScreeningSession) -> dict[str, Any]:
    rows = db.scalars(select(SessionAnswer).where(SessionAnswer.session_id == session.id)).all()
    answers = {row.question_key: row.value_json for row in rows}
    if session.state_code and "state_code" not in answers:
        answers["state_code"] = session.state_code
    return answers


def get_next_question(db: Session, session: ScreeningSession, answers: dict[str, Any]) -> Optional[Question]:
    policy = get_breadth_policy(session)
    if session.scope in {"state", "both"} and not session.state_code and "state_code" not in answers:
        return db.scalar(select(Question).where(Question.key == "state_code"))

    if len(answers) >= policy["max_answers"]:
        return None

    scores = score_unanswered_questions(db, session, answers, enforce_depth_unlocks=True)
    if not scores:
        scores = score_unanswered_questions(db, session, answers, enforce_depth_unlocks=False)

    if not scores:
        return None

    next_key = max(scores.items(), key=lambda item: item[1])[0]
    return db.scalar(select(Question).where(Question.key == next_key))


def compute_results(db: Session, session: ScreeningSession) -> dict[str, Any]:
    answers = get_answers_map(db, session)
    return compute_results_for_answers(db, session, answers)


def compute_results_for_answers(db: Session, session: ScreeningSession, answers: dict[str, Any]) -> dict[str, Any]:
    federal_results = []
    state_results = []
    for program in get_candidate_programs(db, session):
        version = get_latest_version(db, program.id)
        if version is None:
            continue
        evaluation = evaluate_program(db, program, version, answers)
        if program.kind == "referral" or program.jurisdiction.level == "state":
            state_results.append(evaluation)
        else:
            federal_results.append(evaluation)

    federal_results.sort(key=result_sort_key, reverse=True)
    state_results.sort(key=result_sort_key, reverse=True)

    return {
        "session_id": session.public_id,
        "federal_results": federal_results[: settings.max_results_per_section],
        "state_results": state_results[: settings.max_results_per_section],
    }


def provisional_result_count(db: Session, session: ScreeningSession) -> int:
    results = compute_results(db, session)
    count = 0
    for bucket in ("federal_results", "state_results"):
        count += sum(1 for item in results[bucket] if item["eligibility_status"] != "likely_ineligible")
    return count


def compute_plan(db: Session, session: ScreeningSession) -> dict[str, Any]:
    answers = get_answers_map(db, session)
    results = compute_results_for_answers(db, session, answers)
    all_results = results["federal_results"] + results["state_results"]
    likely = [item for item in all_results if item["eligibility_status"] == "likely_eligible"]
    possible = [item for item in all_results if item["eligibility_status"] == "possibly_eligible"]
    positive_results = [item for item in all_results if item["eligibility_status"] != "likely_ineligible"]

    top_missing_facts = rank_missing_facts(positive_results)
    action_plan = build_action_plan(positive_results)
    official_source_hub = dedupe_link_payload(
        link
        for result in positive_results
        for link in (
            [{"label": source["title"], "url": source["url"]} for source in result["data_gathered_from"]]
            + result["how_to_get_benefit"]
        )
    )

    likely_federal = sum(1 for item in results["federal_results"] if item["eligibility_status"] == "likely_eligible")
    likely_state = sum(1 for item in results["state_results"] if item["eligibility_status"] == "likely_eligible")
    average_coverage = round(
        sum(item["certainty_breakdown"]["rule_coverage"] for item in positive_results) / len(positive_results)
    ) if positive_results else 0
    next_question = get_next_question(db, session, answers)

    estimated_monthly = sum(
        item["estimated_amount"].get("amount", 0)
        for item in likely
        if item["estimated_amount"].get("calculated") and item["estimated_amount"].get("period") == "monthly"
    )

    return {
        "profile": build_profile_summary(session, answers),
        "overview": {
            "likely_programs": len(likely),
            "possible_programs": len(possible),
            "likely_federal_programs": likely_federal,
            "likely_state_programs": likely_state,
            "average_rule_coverage": average_coverage,
            "answered_questions": len(answers),
            "next_question_key": next_question.key if next_question else None,
            "estimated_monthly_total": round(estimated_monthly),
        },
        "benefit_stack": build_benefit_stack(positive_results),
        "top_missing_facts": top_missing_facts,
        "action_plan": action_plan,
        "official_source_hub": official_source_hub[:10],
        "planning_notes": build_planning_notes(session, likely, possible, top_missing_facts),
        "document_checklist": _aggregate_documents(likely + possible),
    }


def _aggregate_documents(results: list[dict[str, Any]]) -> list[dict[str, Any]]:
    """Deduplicate documents across eligible programs into a master checklist."""
    seen: dict[str, dict[str, Any]] = {}
    for result in results:
        for doc in result.get("documents") or []:
            name = doc.get("name", "")
            if not name:
                continue
            key = name.lower().strip()
            if key not in seen:
                seen[key] = {
                    "name": name,
                    "type": doc.get("type", "recommended"),
                    "description": doc.get("description", ""),
                    "programs": [],
                }
            seen[key]["programs"].append(result["program_name"])
            if doc.get("type") == "required":
                seen[key]["type"] = "required"
    required = [d for d in seen.values() if d["type"] == "required"]
    recommended = [d for d in seen.values() if d["type"] != "required"]
    return required + recommended


def get_program_detail(db: Session, slug: str) -> Optional[dict[str, Any]]:
    program = db.scalar(select(Program).where(Program.slug == slug))
    if program is None:
        return None
    version = get_latest_version(db, program.id)
    if version is None:
        return None
    source_rows = get_program_sources(db, program)
    how_to_get_benefit = build_application_guidance(program, source_rows)
    return {
        "slug": program.slug,
        "name": program.name,
        "kind": program.kind,
        "category": program.category,
        "family": program.family,
        "summary": program.summary,
        "apply_url": program.apply_url,
        "documents": program.documents_json or [],
        "jurisdiction": {
            "code": program.jurisdiction.code,
            "level": program.jurisdiction.level,
            "name": program.jurisdiction.name,
        },
        "agency": program.agency.name if program.agency else None,
        "version_label": version.version_label,
        "rules": [
            {
                "question_key": rule.question_key,
                "label": rule.label,
                "expected_values": rule.expected_values_json,
            }
            for rule in db.scalars(select(EligibilityRule).where(EligibilityRule.program_version_id == version.id)).all()
        ],
        "data_gathered_from": source_rows,
        "how_to_get_benefit": how_to_get_benefit,
        "sources": source_rows,
    }


def list_states(db: Session) -> list[dict[str, str]]:
    rows = db.scalars(
        select(Jurisdiction).where(Jurisdiction.level == "state").order_by(Jurisdiction.name.asc())
    ).all()
    return [{"code": row.code, "name": row.name} for row in rows]


def list_review_tasks(db: Session) -> list[dict[str, Any]]:
    tasks = db.scalars(select(ReviewTask).order_by(ReviewTask.created_at.desc())).all()
    payload = []
    for task in tasks:
        event = task.change_event
        source = db.get(Source, event.source_id)
        payload.append(
            {
                "id": task.id,
                "status": task.status,
                "created_at": task.created_at.isoformat(),
                "notes": task.reviewer_notes,
                "diff_type": event.diff_type,
                "materiality_score": event.materiality_score,
                "source_title": source.title if source else None,
                "source_url": source.url if source else None,
            }
        )
    return payload


def compare_scenarios(
    db: Session,
    session: ScreeningSession,
    scenarios: list[dict[str, Any]],
) -> dict[str, Any]:
    base_answers = get_answers_map(db, session)
    baseline = compute_results_for_answers(db, session, base_answers)
    baseline_index = index_results(baseline)

    comparisons = []
    for scenario in scenarios:
        scenario_answers = dict(base_answers)
        scenario_answers.update(scenario.get("answers", {}))
        scenario_results = compute_results_for_answers(db, session, scenario_answers)
        scenario_index = index_results(scenario_results)
        comparisons.append(
            {
                "name": scenario.get("name", "Scenario"),
                "description": scenario.get("description"),
                "answer_overrides": scenario.get("answers", {}),
                "summary": summarize_comparison(baseline_index, scenario_index),
                "gained_programs": list_changed_programs(baseline_index, scenario_index, direction="gain"),
                "improved_programs": list_changed_programs(baseline_index, scenario_index, direction="improve"),
                "lost_programs": list_changed_programs(baseline_index, scenario_index, direction="loss"),
            }
        )

    return {
        "session_id": session.public_id,
        "baseline": {
            "overview": build_comparison_overview(baseline),
        },
        "comparisons": comparisons,
    }


def list_program_catalog(
    db: Session,
    *,
    query: str = "",
    scope: str = "both",
    state_code: Optional[str] = None,
    categories: Optional[list[str]] = None,
    limit: int = 40,
) -> list[dict[str, Any]]:
    programs = db.scalars(select(Program).where(Program.status == "active").order_by(Program.name.asc())).all()
    filtered: list[Program] = []
    query_lower = query.lower().strip()
    expanded_categories = expand_category_filters(set(categories or []))

    for program in programs:
        if scope == "federal" and program.jurisdiction.level != "federal":
            continue
        if scope == "state" and program.jurisdiction.level != "state":
            continue
        if state_code and program.jurisdiction.level == "state" and program.jurisdiction.code != state_code.upper():
            continue
        if expanded_categories and program.kind != "referral" and not program_matches_categories(program, expanded_categories):
            continue
        if query_lower:
            haystack = " ".join(
                [
                    program.name.lower(),
                    (program.summary or "").lower(),
                    (program.category or "").lower(),
                    (program.family or "").lower(),
                    (program.agency.name.lower() if program.agency else ""),
                ]
            )
            if query_lower not in haystack:
                continue
        filtered.append(program)

    payload = []
    for program in filtered[:limit]:
        sources = get_program_sources(db, program)
        payload.append(
            {
                "slug": program.slug,
                "name": program.name,
                "kind": program.kind,
                "category": program.category,
                "family": program.family,
                "summary": program.summary,
                "jurisdiction": {
                    "code": program.jurisdiction.code,
                    "level": program.jurisdiction.level,
                    "name": program.jurisdiction.name,
                },
                "agency": program.agency.name if program.agency else None,
                "apply_url": get_official_application_url(program, sources),
                "data_gathered_from": sources[:3],
            }
        )
    return payload


def estimate_amount(amount_rule: Optional[AmountRule], answers: dict[str, Any]) -> dict[str, Any]:
    """Compute an estimated benefit amount using formula if available, else static text."""
    if not amount_rule:
        return {"certainty": "unknown", "display": "Amount not available in the current source set.", "calculated": False}

    if not amount_rule.formula_json:
        return {
            "certainty": "unknown" if amount_rule.amount_type == "unknown" else amount_rule.amount_type,
            "display": amount_rule.display_text or "Amount not available.",
            "calculated": False,
        }

    formula = amount_rule.formula_json
    formula_type = formula.get("type", "")
    period = amount_rule.period or "monthly"

    try:
        if formula_type == "table_lookup":
            lookup_key = formula.get("lookup_key", "")
            result_field = formula.get("result_field", "max_benefit")
            user_val = answers.get(lookup_key)
            if user_val is None:
                return {
                    "certainty": "range" if amount_rule.min_amount and amount_rule.max_amount else amount_rule.amount_type,
                    "display": amount_rule.display_text or "Answer more questions for an estimate.",
                    "calculated": False,
                    "period": period,
                    "min": amount_rule.min_amount,
                    "max": amount_rule.max_amount,
                }
            try:
                user_val = int(float(str(user_val)))
            except (ValueError, TypeError):
                user_val = 1
            table = formula.get("table", [])
            best_row = None
            for row in table:
                if row.get(lookup_key) is not None and int(row[lookup_key]) <= user_val:
                    best_row = row
            if best_row is None and table:
                best_row = table[0]
            if best_row:
                amount = best_row.get(result_field, 0)
                return {
                    "certainty": "estimated",
                    "display": f"Up to ${amount:,.0f}/{period}",
                    "calculated": True,
                    "period": period,
                    "amount": amount,
                }

        elif formula_type == "fixed":
            amount = formula.get("amount", 0)
            return {
                "certainty": "exact",
                "display": f"${amount:,.0f}/{period}",
                "calculated": True,
                "period": period,
                "amount": amount,
            }

        elif formula_type == "linear":
            base = formula.get("base", 0)
            inputs = formula.get("inputs", {})
            total = base
            for coeff_name, question_key in inputs.items():
                val = answers.get(question_key)
                if val is not None:
                    try:
                        total += formula.get(coeff_name, 0) * float(str(val))
                    except (ValueError, TypeError):
                        pass
            total = max(0, total)
            if amount_rule.max_amount:
                total = min(total, amount_rule.max_amount)
            return {
                "certainty": "estimated",
                "display": f"~${total:,.0f}/{period}",
                "calculated": True,
                "period": period,
                "amount": total,
            }
    except Exception:
        pass

    return {
        "certainty": amount_rule.amount_type,
        "display": amount_rule.display_text or "Amount not available.",
        "calculated": False,
    }


def evaluate_program(db: Session, program: Program, version: ProgramVersion, answers: dict[str, Any]) -> dict[str, Any]:
    rules = db.scalars(
        select(EligibilityRule)
        .where(EligibilityRule.program_version_id == version.id)
        .order_by(desc(EligibilityRule.priority))
    ).all()
    amount_rule = db.scalar(select(AmountRule).where(AmountRule.program_version_id == version.id))

    outcomes: list[str] = []
    matched_reasons: list[str] = []
    missing_facts: list[str] = []
    failed_reasons: list[str] = []
    source_keys = {rule.source_key for rule in rules}

    for rule in rules:
        question = db.scalar(select(Question).where(Question.key == rule.question_key))
        if is_redundant_state_residency_rule(
            session_state_code=answers.get("state_code"),
            program=program,
            rule=rule,
            question=question,
        ):
            continue
        if not isinstance(rule.expected_values_json, list):
            continue
        answer_value = answers.get(rule.question_key)
        outcome = evaluate_matches_any(answer_value, rule.expected_values_json)
        outcomes.append(outcome)
        if outcome == "pass":
            matched_reasons.append(rule.label)
        elif outcome == "unknown":
            missing_facts.append(question.prompt if question else rule.question_key)
        else:
            failed_reasons.append(rule.label)

    if program.kind == "referral":
        state_code = answers.get("state_code")
        if state_code and state_code == program.jurisdiction.code:
            eligibility_status = "likely_eligible"
            matched_reasons = [f"This is the official {program.jurisdiction.name} state entry point for benefits."]
            failed_reasons = []
            missing_facts = []
        else:
            eligibility_status = "likely_ineligible"
    else:
        eligibility_status = score_status(outcomes)

    freshness_score = compute_source_freshness_score(db, source_keys)
    authority_score = compute_source_authority_score(db, source_keys)
    rule_coverage = 100 if not rules else round((sum(1 for item in outcomes if item != "unknown") / len(rules)) * 100)
    program_determinism = compute_program_determinism(program, rules)
    amount_determinism = 0 if program.kind == "referral" else compute_amount_determinism(amount_rule)
    decision_certainty = round(
        0.35 * rule_coverage
        + 0.20 * authority_score
        + 0.20 * freshness_score
        + 0.15 * program_determinism
        + 0.10 * amount_determinism
    )
    data_sources = get_program_sources(db, program)
    how_to_get_benefit = build_application_guidance(program, data_sources)

    return {
        "program_slug": program.slug,
        "program_name": program.name,
        "kind": program.kind,
        "category": program.category,
        "family": program.family,
        "eligibility_status": eligibility_status,
        "decision_certainty": decision_certainty,
        "certainty_breakdown": {
            "rule_coverage": rule_coverage,
            "source_authority": authority_score,
            "source_freshness": freshness_score,
            "program_determinism": program_determinism,
            "amount_determinism": amount_determinism,
        },
        "estimated_amount": estimate_amount(amount_rule, answers),
        "summary": program.summary,
        "jurisdiction": {
            "level": program.jurisdiction.level,
            "code": program.jurisdiction.code,
            "name": program.jurisdiction.name,
        },
        "agency": program.agency.name if program.agency else None,
        "apply_url": program.apply_url,
        "matched_reasons": matched_reasons[:4],
        "missing_facts": missing_facts[:4],
        "failed_reasons": failed_reasons[:4],
        "documents": program.documents_json or [],
        "data_gathered_from": data_sources,
        "how_to_get_benefit": how_to_get_benefit,
        "sources": data_sources,
    }


def get_candidate_programs(db: Session, session: ScreeningSession) -> list[Program]:
    programs = db.scalars(select(Program).where(Program.status == "active")).all()
    categories = {category for category in session.categories_json or [] if category and category != "all"}
    expanded_categories = expand_category_filters(categories)
    filtered = []
    for program in programs:
        if session.scope == "federal" and program.jurisdiction.level != "federal":
            continue
        if session.scope == "state" and program.jurisdiction.level != "state":
            continue
        if program.jurisdiction.level == "state":
            if not session.state_code or program.jurisdiction.code != session.state_code:
                continue
        if expanded_categories and program.kind != "referral":
            if not program_matches_categories(program, expanded_categories):
                continue
        filtered.append(program)
    return filtered


def result_sort_key(result: dict[str, Any]) -> tuple[int, int]:
    status_rank = {
        "likely_eligible": 3,
        "possibly_eligible": 2,
        "unclear": 1,
        "likely_ineligible": 0,
    }
    return status_rank.get(result["eligibility_status"], 0), result["decision_certainty"]


def status_rank(status: str) -> int:
    ranking = {
        "likely_eligible": 3,
        "possibly_eligible": 2,
        "unclear": 1,
        "likely_ineligible": 0,
    }
    return ranking.get(status, 0)


def get_breadth_policy(session: ScreeningSession) -> dict[str, Any]:
    value = getattr(session, "breadth_value", None)
    if value is None:
        value = getattr(session, "depth_value", None)
    if value is None:
        value = LEGACY_CONTROL_MODE_TO_VALUE.get(session.depth_mode, 0.5)
    return interpolate_breadth_policy(value)


def resolve_question_variant(
    db: Session,
    question_key: str,
    depth_value: float,
) -> Optional[QuestionVariant]:
    tier = depth_value_to_tier(depth_value)
    return db.scalar(
        select(QuestionVariant).where(
            QuestionVariant.question_key == question_key,
            QuestionVariant.depth_tier == tier,
        )
    )


def question_is_unlocked(question: Question, answers_count: int, policy: dict[str, Any]) -> bool:
    unlock_after = policy["unlock_after"].get(question.sensitivity_level, 0)
    return answers_count >= unlock_after


def score_unanswered_questions(
    db: Session,
    session: ScreeningSession,
    answers: dict[str, Any],
    *,
    enforce_depth_unlocks: bool,
) -> dict[str, float]:
    policy = get_breadth_policy(session)
    scores: dict[str, float] = {}
    focused_scores: dict[str, float] = {}
    non_referral_scores: dict[str, float] = {}
    candidate_programs = get_candidate_programs(db, session)
    answers_count = len(answers)
    selected_categories = {
        category for category in session.categories_json or [] if category and category != "all"
    }
    expanded_categories = expand_category_filters(selected_categories)
    for program in candidate_programs:
        version = get_latest_version(db, program.id)
        if version is None:
            continue
        rules = db.scalars(
            select(EligibilityRule)
            .where(EligibilityRule.program_version_id == version.id)
            .order_by(desc(EligibilityRule.priority))
        ).all()
        for rule in rules:
            if rule.question_key in answers:
                continue
            question = db.scalar(select(Question).where(Question.key == rule.question_key))
            if question is None:
                continue
            if is_redundant_state_residency_rule(
                session_state_code=session.state_code,
                program=program,
                rule=rule,
                question=question,
            ):
                continue
            if enforce_depth_unlocks and not question_is_unlocked(question, answers_count, policy):
                continue
            depth_weight = policy["weights"].get(question.sensitivity_level, 1.0)
            sensitivity_bonus = policy["bonuses"].get(question.sensitivity_level, 0)
            score_increment = (
                rule.priority * depth_weight
                + question.sort_weight
                + sensitivity_bonus
            )
            scores[rule.question_key] = scores.get(rule.question_key, 0.0) + score_increment

            if program.kind != "referral":
                non_referral_scores[rule.question_key] = non_referral_scores.get(rule.question_key, 0.0) + score_increment

            focus_score = question_category_focus_score(question, rule, program, expanded_categories)
            if focus_score > 0:
                focused_scores[rule.question_key] = focused_scores.get(rule.question_key, 0.0) + score_increment + focus_score

    if focused_scores:
        return focused_scores
    if selected_categories and non_referral_scores:
        return non_referral_scores
    return scores


def expand_category_filters(categories: set[str]) -> set[str]:
    expanded: set[str] = set()
    for category in categories:
        expanded.add(category)
        expanded.update(CATEGORY_FILTER_MAP.get(category, {category}))
    return expanded


def program_matches_categories(program: Program, expanded_categories: set[str]) -> bool:
    tokens = {
        (program.category or "").lower(),
        (program.family or "").lower(),
        slugify(program.name),
    }
    haystack = " ".join(
        [
            program.name.lower(),
            (program.summary or "").lower(),
            (program.category or "").lower(),
            (program.family or "").lower(),
        ]
    )
    if tokens.intersection(expanded_categories):
        return True
    keyword_map = {
        "death": ("death", "survivor", "funeral"),
        "survivor": ("death", "survivor", "funeral"),
        "disasters": ("disaster", "fema", "emergency", "funeral"),
        "military_veterans": ("veteran", "military", "va "),
        "retirement_seniors": ("retirement", "senior", "social security"),
        "housing_utilities": ("housing", "utility", "internet", "energy"),
        "welfare_cash_assistance": ("cash", "income", "assistance"),
        "children_families": ("child", "children", "family"),
        "jobs_unemployment": ("job", "employment", "unemployment"),
    }
    for category, keywords in keyword_map.items():
        if category in expanded_categories and any(keyword in haystack for keyword in keywords):
            return True
    return False


def category_focus_hints(categories: set[str]) -> set[str]:
    hints: set[str] = set()
    for category in categories:
        hints.update(QUESTION_CATEGORY_HINTS.get(category, set()))
        if category not in QUESTION_CATEGORY_HINTS:
            hints.update(token for token in normalize_match_text(category).split() if token)
    return {hint for hint in hints if hint}


def question_category_focus_score(
    question: Question,
    rule: EligibilityRule,
    program: Program,
    selected_categories: set[str],
) -> int:
    if not selected_categories or program.kind == "referral":
        return 0

    hints = category_focus_hints(selected_categories)
    if not hints:
        return 0

    question_text = " ".join(
        [
            normalize_match_text(question.prompt),
            normalize_match_text(question.hint),
            normalize_match_text(rule.label),
        ]
    )
    focus = sum(1 for hint in hints if hint in question_text)
    if focus == 0:
        return 0

    # Reward truly category-specific prompts more than generic program metadata.
    focus_score = focus * 70
    if program.category in selected_categories or program.family in selected_categories:
        focus_score += 20
    return focus_score


def supersede_published_versions(db: Session, program_id: int) -> None:
    versions = db.scalars(
        select(ProgramVersion).where(
            ProgramVersion.program_id == program_id,
            ProgramVersion.publication_state == "published",
        )
    ).all()
    for version in versions:
        version.publication_state = "superseded"


def get_latest_version(db: Session, program_id: int) -> Optional[ProgramVersion]:
    return db.scalar(
        select(ProgramVersion)
        .where(
            ProgramVersion.program_id == program_id,
            ProgramVersion.publication_state == "published",
        )
        .order_by(desc(ProgramVersion.published_at), desc(ProgramVersion.id))
    )


def compute_source_authority_score(db: Session, source_keys: set[str]) -> int:
    if not source_keys:
        return 50
    sources = db.scalars(select(Source).where(Source.key.in_(source_keys))).all()
    if not sources:
        return 50
    return round(sum(source.authority_rank for source in sources) / len(sources))


def compute_source_freshness_score(db: Session, source_keys: set[str]) -> int:
    if not source_keys:
        return 40
    from sqlalchemy import func as sa_func
    latest_subq = (
        select(SourceSnapshot.source_id, sa_func.max(SourceSnapshot.fetched_at).label("latest"))
        .group_by(SourceSnapshot.source_id)
        .subquery()
    )
    rows = db.execute(
        select(latest_subq.c.latest)
        .join(Source, Source.id == latest_subq.c.source_id)
        .where(Source.key.in_(source_keys))
    ).all()
    latest_dates = [row[0] for row in rows if row[0]]
    if not latest_dates:
        return 60
    days_old = (datetime.utcnow() - max(latest_dates)).days
    if days_old <= 7:
        return 100
    if days_old <= 30:
        return 85
    if days_old <= 90:
        return 70
    return 50


def compute_program_determinism(program: Program, rules: list[EligibilityRule]) -> int:
    if program.kind == "referral":
        return 35
    if not rules:
        return 20
    if any(any(str(value).startswith(("<", ">")) for value in (rule.expected_values_json or [])) for rule in rules):
        return 75
    return 85


def compute_amount_determinism(amount_rule: Optional[AmountRule]) -> int:
    if amount_rule is None:
        return 10
    if amount_rule.amount_type == "exact":
        return 90
    if amount_rule.amount_type == "formula":
        return 75
    if amount_rule.amount_type == "range":
        return 45
    return 20


def get_program_sources(db: Session, program: Program) -> list[dict[str, Any]]:
    from sqlalchemy import func as sa_func

    sources = db.scalars(select(Source).where(Source.program_id == program.id)).all()

    all_source_ids = [s.id for s in sources]
    shared_keys = []
    if program.jurisdiction.level == "federal":
        shared_keys.append("usagov-benefit-finder-feed")
    elif program.jurisdiction.level == "state":
        shared_keys.append("usagov-state-social-services-directory")
    shared_sources = db.scalars(select(Source).where(Source.key.in_(shared_keys))).all() if shared_keys else []
    all_source_ids.extend(s.id for s in shared_sources)

    latest_subq = (
        select(SourceSnapshot.source_id, sa_func.max(SourceSnapshot.fetched_at).label("latest"))
        .where(SourceSnapshot.source_id.in_(all_source_ids))
        .group_by(SourceSnapshot.source_id)
        .subquery()
    )
    snapshot_map = {
        row[0]: row[1]
        for row in db.execute(select(latest_subq.c.source_id, latest_subq.c.latest)).all()
    }

    payload = []
    for source in sources:
        if not is_official_government_url(source.url):
            continue
        fetched = snapshot_map.get(source.id)
        payload.append(
            {
                "title": source.title,
                "url": source.url,
                "kind": "application_page",
                "authority_rank": source.authority_rank,
                "last_verified_at": fetched.date().isoformat() if fetched else None,
            }
        )
    for shared_source in shared_sources:
        if not is_official_government_url(shared_source.url):
            continue
        fetched = snapshot_map.get(shared_source.id)
        payload.append(
            {
                "title": shared_source.title,
                "url": shared_source.url,
                "kind": "data_source",
                "authority_rank": shared_source.authority_rank,
                "last_verified_at": fetched.date().isoformat() if fetched else None,
            }
        )
    return payload


def build_profile_summary(session: ScreeningSession, answers: dict[str, Any]) -> dict[str, Any]:
    birth_date = parse_answer_date(answers.get("applicant_date_of_birth"))
    age_years = compute_age_years(birth_date) if birth_date else None
    return {
        "scope": session.scope,
        "state_code": session.state_code,
        "depth_mode": session.depth_mode,
        "breadth_value": getattr(session, "breadth_value", session.depth_value),
        "depth_value": session.depth_value,
        "selected_categories": [
            {"key": category, "label": CATEGORY_LABELS.get(category, category.replace("_", " ").title())}
            for category in session.categories_json or []
        ],
        "derived_facts": {
            "age_years": age_years,
            "is_retirement_age": bool(age_years is not None and age_years >= 62),
            "has_income_constraint": normalize_boolish(answers.get("applicant_income")) == "yes",
            "has_disability": normalize_boolish(answers.get("applicant_disability")) == "yes",
            "has_military_service": normalize_boolish(answers.get("applicant_served_in_active_military")) == "yes",
            "reported_family_death": normalize_boolish(answers.get("applicant_dolo")) == "yes",
        },
    }


def build_benefit_stack(results: list[dict[str, Any]]) -> list[dict[str, Any]]:
    buckets: dict[str, dict[str, Any]] = {}
    for item in results:
        category = item.get("category") or infer_result_category(item)
        bucket = buckets.setdefault(
            category,
            {
                "category": category,
                "label": CATEGORY_LABELS.get(category, category.replace("_", " ").title()),
                "likely_programs": 0,
                "possible_programs": 0,
                "top_programs": [],
            },
        )
        if item["eligibility_status"] == "likely_eligible":
            bucket["likely_programs"] += 1
        elif item["eligibility_status"] == "possibly_eligible":
            bucket["possible_programs"] += 1
        if len(bucket["top_programs"]) < 3:
            bucket["top_programs"].append(item["program_name"])

    return sorted(
        buckets.values(),
        key=lambda item: (item["likely_programs"], item["possible_programs"], len(item["top_programs"])),
        reverse=True,
    )


def build_action_plan(results: list[dict[str, Any]]) -> list[dict[str, Any]]:
    plan: list[dict[str, Any]] = []
    ordered_results = sorted(results, key=result_sort_key, reverse=True)
    for result in ordered_results[:6]:
        if not result["how_to_get_benefit"]:
            continue
        primary_step = result["how_to_get_benefit"][0]
        plan.append(
            {
                "program_name": result["program_name"],
                "eligibility_status": result["eligibility_status"],
                "confidence": result["decision_certainty"],
                "step_label": primary_step["label"],
                "url": primary_step["url"],
                "jurisdiction": result["jurisdiction"]["name"],
            }
        )
    return plan


def build_planning_notes(
    session: ScreeningSession,
    likely: list[dict[str, Any]],
    possible: list[dict[str, Any]],
    top_missing_facts: list[dict[str, Any]],
) -> list[str]:
    notes: list[str] = []
    if likely:
        notes.append(
            f"You already have {len(likely)} strong match{'es' if len(likely) != 1 else ''} to pursue on official government sites."
        )
    if possible and not likely:
        notes.append(
            f"You have {len(possible)} possible match{'es' if len(possible) != 1 else ''}; answering a few more questions should tighten these."
        )
    if top_missing_facts:
        notes.append(f"The biggest information gap right now is: {top_missing_facts[0]['label']}.")
    if session.scope in {"state", "both"} and not session.state_code:
        notes.append("Choose a state to unlock official state benefit pathways.")
    return notes


def rank_missing_facts(results: list[dict[str, Any]]) -> list[dict[str, Any]]:
    counts: dict[str, int] = {}
    for result in results:
        for fact in result["missing_facts"]:
            counts[fact] = counts.get(fact, 0) + 1
    ranked = sorted(counts.items(), key=lambda item: (-item[1], item[0]))
    return [{"label": label, "program_count": count} for label, count in ranked[:8]]


def dedupe_link_payload(links) -> list[dict[str, str]]:
    seen: set[str] = set()
    payload: list[dict[str, str]] = []
    for link in links:
        url = link.get("url")
        if not url or url in seen:
            continue
        payload.append({"label": link.get("label") or url, "url": url})
        seen.add(url)
    return payload


def parse_answer_date(value: Any) -> Optional[date]:
    if not isinstance(value, str):
        return None
    try:
        return datetime.strptime(value, "%Y-%m-%d").date()
    except ValueError:
        return None


def compute_age_years(birth_date: date) -> int:
    today = date.today()
    return today.year - birth_date.year - ((today.month, today.day) < (birth_date.month, birth_date.day))


def normalize_boolish(value: Any) -> str:
    if value is None:
        return ""
    normalized = str(value).strip().lower()
    if normalized in {"yes", "true", "1"}:
        return "yes"
    if normalized in {"no", "false", "0"}:
        return "no"
    return normalized


def infer_result_category(result: dict[str, Any]) -> str:
    haystack = " ".join(
        [
            result.get("program_name", "").lower(),
            result.get("summary", "").lower(),
        ]
    )
    if "veteran" in haystack or "military" in haystack:
        return "military_veterans"
    if "retirement" in haystack or "social security" in haystack:
        return "retirement_seniors"
    if "disability" in haystack:
        return "disabilities"
    if "death" in haystack or "funeral" in haystack or "survivor" in haystack:
        return "death"
    return "welfare_cash_assistance"


def index_results(results: dict[str, Any]) -> dict[str, dict[str, Any]]:
    return {
        item["program_slug"]: item
        for item in results["federal_results"] + results["state_results"]
    }


def build_comparison_overview(results: dict[str, Any]) -> dict[str, int]:
    all_results = results["federal_results"] + results["state_results"]
    return {
        "likely_programs": sum(1 for item in all_results if item["eligibility_status"] == "likely_eligible"),
        "possible_programs": sum(1 for item in all_results if item["eligibility_status"] == "possibly_eligible"),
        "state_programs": len(results["state_results"]),
        "federal_programs": len(results["federal_results"]),
    }


def summarize_comparison(
    baseline_index: dict[str, dict[str, Any]],
    scenario_index: dict[str, dict[str, Any]],
) -> dict[str, int]:
    baseline_overview = build_comparison_overview(
        {
            "federal_results": [item for item in baseline_index.values() if item["jurisdiction"]["level"] == "federal"],
            "state_results": [item for item in baseline_index.values() if item["jurisdiction"]["level"] == "state"],
        }
    )
    scenario_overview = build_comparison_overview(
        {
            "federal_results": [item for item in scenario_index.values() if item["jurisdiction"]["level"] == "federal"],
            "state_results": [item for item in scenario_index.values() if item["jurisdiction"]["level"] == "state"],
        }
    )
    return {
        "likely_delta": scenario_overview["likely_programs"] - baseline_overview["likely_programs"],
        "possible_delta": scenario_overview["possible_programs"] - baseline_overview["possible_programs"],
        "federal_delta": scenario_overview["federal_programs"] - baseline_overview["federal_programs"],
        "state_delta": scenario_overview["state_programs"] - baseline_overview["state_programs"],
    }


def list_changed_programs(
    baseline_index: dict[str, dict[str, Any]],
    scenario_index: dict[str, dict[str, Any]],
    *,
    direction: str,
) -> list[dict[str, Any]]:
    changes: list[dict[str, Any]] = []
    all_slugs = sorted(set(baseline_index) | set(scenario_index))
    for slug in all_slugs:
        baseline = baseline_index.get(slug)
        scenario = scenario_index.get(slug)
        if scenario is None:
            continue
        baseline_rank = status_rank(baseline["eligibility_status"]) if baseline else -1
        scenario_rank = status_rank(scenario["eligibility_status"])
        if direction == "gain" and baseline_rank < 2 <= scenario_rank:
            changes.append(build_change_payload(slug, baseline, scenario))
        elif direction == "improve" and baseline and scenario_rank > baseline_rank:
            changes.append(build_change_payload(slug, baseline, scenario))
        elif direction == "loss" and baseline and baseline_rank >= 2 > scenario_rank:
            changes.append(build_change_payload(slug, baseline, scenario))
    return changes[:6]


def build_change_payload(
    slug: str,
    baseline: Optional[dict[str, Any]],
    scenario: dict[str, Any],
) -> dict[str, Any]:
    return {
        "program_slug": slug,
        "program_name": scenario["program_name"],
        "before_status": baseline["eligibility_status"] if baseline else "not_present",
        "after_status": scenario["eligibility_status"],
        "after_confidence": scenario["decision_certainty"],
        "apply_url": scenario["apply_url"],
    }


def build_application_guidance(program: Program, data_sources: list[dict[str, Any]]) -> list[dict[str, str]]:
    application_url = get_official_application_url(program, data_sources)
    steps: list[dict[str, str]] = []

    if program.kind == "referral":
        if application_url:
            steps.append(
                {
                    "label": "Start on the official state social services website.",
                    "url": application_url,
                }
            )
            steps.append(
                {
                    "label": "Use the state's official benefit tools or program pages to choose the benefit you need.",
                    "url": application_url,
                }
            )
            steps.append(
                {
                    "label": "Follow the state's official instructions for documents, local office contact, or online submission.",
                    "url": application_url,
                }
            )
        return steps

    overview_source = next((source for source in data_sources if source.get("kind") == "data_source"), None)
    if overview_source:
        steps.append(
            {
                "label": "Review the official government eligibility source used for this match.",
                "url": overview_source["url"],
            }
        )
    if application_url:
        steps.append(
            {
                "label": "Open the official government page to start or continue the application.",
                "url": application_url,
            }
        )
        steps.append(
            {
                "label": "Use the same official page for required documents, status checks, or agency contact details.",
                "url": application_url,
            }
        )
    return steps


def get_official_application_url(program: Program, data_sources: list[dict[str, Any]]) -> Optional[str]:
    if is_official_government_url(program.apply_url):
        return program.apply_url
    application_source = next((source for source in data_sources if source.get("kind") == "application_page"), None)
    if application_source:
        return application_source["url"]
    data_source = next((source for source in data_sources if source.get("kind") == "data_source"), None)
    if data_source:
        return data_source["url"]
    return None


def ensure_base_questions(db: Session) -> None:
    question = db.scalar(select(Question).where(Question.key == "state_code"))
    if question is None:
        db.add(
            Question(
                key="state_code",
                prompt="Which state or territory do you want state benefits for?",
                hint="State benefits vary by state and are kept separate from federal matches.",
                input_type="select",
                sensitivity_level="low",
                options_json=None,
                sort_weight=1000,
            )
        )
        db.flush()


def upsert_questions(db: Session, questions: list[dict[str, Any]]) -> None:
    frequency: dict[str, int] = {}
    for row in questions:
        frequency[row["key"]] = frequency.get(row["key"], 0) + 1

    for row in questions:
        question = db.scalar(select(Question).where(Question.key == row["key"]))
        if question is None:
            question = Question(
                key=row["key"],
                prompt=row["prompt"],
                hint=row.get("hint"),
                input_type=row["input_type"],
                sensitivity_level=row["sensitivity_level"],
                options_json=row.get("options"),
                sort_weight=float(frequency[row["key"]]),
            )
            db.add(question)
        else:
            question.prompt = row["prompt"]
            question.hint = row.get("hint")
            question.input_type = row["input_type"]
            question.sensitivity_level = row["sensitivity_level"]
            question.options_json = row.get("options")
            question.sort_weight = float(frequency[row["key"]])
    db.flush()


def upsert_question_variants(db: Session, variants: list[dict[str, Any]]) -> None:
    for row in variants:
        variant = db.scalar(
            select(QuestionVariant).where(
                QuestionVariant.question_key == row["question_key"],
                QuestionVariant.depth_tier == row["depth_tier"],
            )
        )
        if variant is None:
            variant = QuestionVariant(
                question_key=row["question_key"],
                depth_tier=row["depth_tier"],
                prompt=row["prompt"],
                hint=row.get("hint"),
                input_type=row["input_type"],
                options_json=row.get("options"),
                normalizer=row.get("normalizer"),
            )
            db.add(variant)
        else:
            variant.prompt = row["prompt"]
            variant.hint = row.get("hint")
            variant.input_type = row["input_type"]
            variant.options_json = row.get("options")
            variant.normalizer = row.get("normalizer")
    db.flush()


def serialize_question(
    db: Session,
    question: Optional[Question],
    depth_value: float = 0.5,
) -> Optional[dict[str, Any]]:
    if question is None:
        return None
    prompt = question.prompt
    hint = question.hint
    input_type = question.input_type
    options = question.options_json

    variant = resolve_question_variant(db, question.key, depth_value)
    if variant is not None:
        prompt = variant.prompt
        hint = variant.hint
        input_type = variant.input_type
        options = variant.options_json

    if question.key == "state_code":
        options = [{"label": item["name"], "value": item["code"]} for item in list_states(db)]
    return {
        "key": question.key,
        "prompt": prompt,
        "hint": hint,
        "input_type": input_type,
        "sensitivity_level": question.sensitivity_level,
        "options": options,
    }


def get_or_create_jurisdiction(
    db: Session,
    *,
    code: str,
    level: str,
    name: str,
    parent_code: Optional[str] = None,
) -> Jurisdiction:
    jurisdiction = db.scalar(select(Jurisdiction).where(Jurisdiction.code == code))
    if jurisdiction is None:
        jurisdiction = Jurisdiction(code=code, level=level, name=name, parent_code=parent_code)
        db.add(jurisdiction)
        db.flush()
    else:
        jurisdiction.level = level
        jurisdiction.name = name
        jurisdiction.parent_code = parent_code
    return jurisdiction


def get_or_create_agency(db: Session, jurisdiction_id: int, name: str, homepage_url: Optional[str]) -> Agency:
    agency = db.scalar(
        select(Agency).where(
            Agency.jurisdiction_id == jurisdiction_id,
            Agency.name == name,
        )
    )
    if agency is None:
        agency = Agency(jurisdiction_id=jurisdiction_id, name=name, homepage_url=homepage_url)
        db.add(agency)
        db.flush()
    else:
        agency.homepage_url = homepage_url
    return agency


def upsert_source(
    db: Session,
    *,
    key: str,
    title: str,
    url: str,
    source_type: str,
    authority_rank: int,
    parser_type: str,
    fetch_cadence: str,
    program_id: Optional[int] = None,
    jurisdiction_id: Optional[int] = None,
) -> Source:
    source = db.scalar(select(Source).where(Source.key == key))
    if source is None:
        source = Source(
            key=key,
            title=title,
            url=url,
            source_type=source_type,
            authority_rank=authority_rank,
            parser_type=parser_type,
            fetch_cadence=fetch_cadence,
            program_id=program_id,
            jurisdiction_id=jurisdiction_id,
        )
        db.add(source)
        db.flush()
    else:
        source.title = title
        source.url = url
        source.source_type = source_type
        source.authority_rank = authority_rank
        source.parser_type = parser_type
        source.fetch_cadence = fetch_cadence
        source.program_id = program_id
        source.jurisdiction_id = jurisdiction_id
    return source


def create_snapshot(
    db: Session,
    *,
    source: Source,
    content_hash: str,
    content_type: str,
    raw_excerpt: str,
) -> Tuple[SourceSnapshot, bool, Optional[SourceSnapshot]]:
    previous_snapshot = db.scalar(
        select(SourceSnapshot)
        .where(SourceSnapshot.source_id == source.id)
        .order_by(desc(SourceSnapshot.fetched_at), desc(SourceSnapshot.id))
    )
    if previous_snapshot and previous_snapshot.content_hash == content_hash:
        return previous_snapshot, False, previous_snapshot

    snapshot = SourceSnapshot(
        source_id=source.id,
        content_hash=content_hash,
        content_type=content_type,
        raw_excerpt=raw_excerpt,
        extraction_status="parsed",
    )
    db.add(snapshot)
    db.flush()
    return snapshot, True, previous_snapshot


def create_review_task(
    db: Session,
    *,
    source: Source,
    previous_snapshot: Optional[SourceSnapshot],
    current_snapshot: SourceSnapshot,
    diff_type: str,
    materiality_score: int,
    notes: str,
) -> int:
    change_event = ChangeEvent(
        source_id=source.id,
        previous_snapshot_id=previous_snapshot.id if previous_snapshot else None,
        current_snapshot_id=current_snapshot.id,
        diff_type=diff_type,
        materiality_score=materiality_score,
        review_required=True,
        review_status="pending",
        notes=notes,
    )
    db.add(change_event)
    db.flush()
    db.add(ReviewTask(change_event_id=change_event.id, status="open"))
    db.flush()
    return 1


def _table_is_empty(db: Session, model: type) -> bool:
    return db.scalar(select(func.count()).select_from(model)) == 0
