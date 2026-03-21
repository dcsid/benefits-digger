from __future__ import annotations

import logging
from datetime import datetime
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
from app.models import (
    Agency,
    AmountRule,
    ChangeEvent,
    EligibilityRule,
    Jurisdiction,
    Program,
    ProgramVersion,
    Question,
    ReviewTask,
    ScreeningSession,
    SessionAnswer,
    Source,
    SourceSnapshot,
)
from app.rules import evaluate_matches_any, score_status


logger = logging.getLogger(__name__)
settings = get_settings()
DEPTH_POLICIES = {
    "quick": {
        "max_answers": 4,
        "weights": {"low": 1.0, "medium": 0.25, "high": 0.05},
        "bonuses": {"low": 25, "medium": -20, "high": -160},
        "unlock_after": {"low": 0, "medium": 1, "high": 99},
    },
    "standard": {
        "max_answers": 10,
        "weights": {"low": 1.0, "medium": 0.95, "high": 0.45},
        "bonuses": {"low": 10, "medium": 10, "high": -15},
        "unlock_after": {"low": 0, "medium": 0, "high": 3},
    },
    "deep": {
        "max_answers": 24,
        "weights": {"low": 1.0, "medium": 1.35, "high": 1.9},
        "bonuses": {"low": 0, "medium": 35, "high": 90},
        "unlock_after": {"low": 0, "medium": 0, "high": 1},
    },
}
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
    summary = {"federal": "skipped", "states": "skipped", "review_tasks_created": 0}
    federal_catalog = fetch_remote_federal_catalog(settings.request_timeout_seconds)
    state_catalog = fetch_remote_state_directory(settings.request_timeout_seconds)
    summary["review_tasks_created"] += sync_federal_catalog(db, federal_catalog, source_mode="remote")
    summary["federal"] = "synced"
    summary["review_tasks_created"] += sync_state_directory(db, state_catalog, source_mode="remote")
    summary["states"] = "synced"
    db.commit()
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
                    amount_type="range",
                    display_text=benefit.get("amount_display"),
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


def create_session(db: Session, scope: str, state_code: Optional[str], categories: list[str], depth_mode: str) -> ScreeningSession:
    session = ScreeningSession(
        scope=scope,
        state_code=state_code.upper() if state_code else None,
        categories_json=sorted({item for item in categories if item}),
        depth_mode=depth_mode,
    )
    db.add(session)
    db.commit()
    db.refresh(session)
    return session


def get_session_or_404(db: Session, public_id: str) -> ScreeningSession:
    session = db.scalar(select(ScreeningSession).where(ScreeningSession.public_id == public_id))
    if session is None:
        raise ValueError("Session not found")
    return session


def upsert_answers(db: Session, session: ScreeningSession, answers: dict[str, Any]) -> None:
    for key, value in answers.items():
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
    policy = get_depth_policy(session.depth_mode)
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
        answer_value = answers.get(rule.question_key)
        outcome = evaluate_matches_any(answer_value, rule.expected_values_json)
        outcomes.append(outcome)
        if outcome == "pass":
            matched_reasons.append(rule.label)
        elif outcome == "unknown":
            question = db.scalar(select(Question).where(Question.key == rule.question_key))
            missing_facts.append(question.prompt if question else rule.question_key)
        else:
            failed_reasons.append(rule.label)

    if program.kind == "referral":
        state_code = answers.get("state_code")
        if state_code and state_code == program.jurisdiction.code:
            eligibility_status = "possibly_eligible"
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
        "eligibility_status": eligibility_status,
        "decision_certainty": decision_certainty,
        "certainty_breakdown": {
            "rule_coverage": rule_coverage,
            "source_authority": authority_score,
            "source_freshness": freshness_score,
            "program_determinism": program_determinism,
            "amount_determinism": amount_determinism,
        },
        "estimated_amount": {
            "certainty": "unknown" if not amount_rule or amount_rule.amount_type == "unknown" else amount_rule.amount_type,
            "display": amount_rule.display_text if amount_rule else "Amount not available in the current source set.",
        },
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


def get_depth_policy(depth_mode: str) -> dict[str, Any]:
    return DEPTH_POLICIES.get(depth_mode, DEPTH_POLICIES["standard"])


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
    policy = get_depth_policy(session.depth_mode)
    scores: dict[str, float] = {}
    candidate_programs = get_candidate_programs(db, session)
    answers_count = len(answers)
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
            if enforce_depth_unlocks and not question_is_unlocked(question, answers_count, policy):
                continue
            depth_weight = policy["weights"].get(question.sensitivity_level, 1.0)
            sensitivity_bonus = policy["bonuses"].get(question.sensitivity_level, 0)
            scores[rule.question_key] = (
                scores.get(rule.question_key, 0.0)
                + rule.priority * depth_weight
                + question.sort_weight
                + sensitivity_bonus
            )
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
    latest_dates: list[datetime] = []
    for source in db.scalars(select(Source).where(Source.key.in_(source_keys))).all():
        snapshot = db.scalar(
            select(SourceSnapshot)
            .where(SourceSnapshot.source_id == source.id)
            .order_by(desc(SourceSnapshot.fetched_at))
        )
        if snapshot:
            latest_dates.append(snapshot.fetched_at)
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
    sources = db.scalars(select(Source).where(Source.program_id == program.id)).all()
    payload = []
    for source in sources:
        if not is_official_government_url(source.url):
            continue
        snapshot = db.scalar(
            select(SourceSnapshot)
            .where(SourceSnapshot.source_id == source.id)
            .order_by(desc(SourceSnapshot.fetched_at))
        )
        payload.append(
            {
                "title": source.title,
                "url": source.url,
                "kind": "application_page",
                "authority_rank": source.authority_rank,
                "last_verified_at": snapshot.fetched_at.date().isoformat() if snapshot else None,
            }
        )
    for shared_key in {"usagov-benefit-finder-feed", "usagov-state-social-services-directory"}:
        shared_source = db.scalar(select(Source).where(Source.key == shared_key))
        if shared_source and (
            (program.jurisdiction.level == "federal" and shared_key == "usagov-benefit-finder-feed")
            or (program.jurisdiction.level == "state" and shared_key == "usagov-state-social-services-directory")
        ):
            if not is_official_government_url(shared_source.url):
                continue
            snapshot = db.scalar(
                select(SourceSnapshot)
                .where(SourceSnapshot.source_id == shared_source.id)
                .order_by(desc(SourceSnapshot.fetched_at))
            )
            payload.append(
                {
                    "title": shared_source.title,
                    "url": shared_source.url,
                    "kind": "data_source",
                    "authority_rank": shared_source.authority_rank,
                    "last_verified_at": snapshot.fetched_at.date().isoformat() if snapshot else None,
                }
            )
    return payload


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


def serialize_question(db: Session, question: Optional[Question]) -> Optional[dict[str, Any]]:
    if question is None:
        return None
    options = question.options_json
    if question.key == "state_code":
        options = [{"label": item["name"], "value": item["code"]} for item in list_states(db)]
    return {
        "key": question.key,
        "prompt": question.prompt,
        "hint": question.hint,
        "input_type": question.input_type,
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
