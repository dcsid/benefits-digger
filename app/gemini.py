"""Gemini-powered state benefit program generation."""

from __future__ import annotations

import json
import logging
from datetime import datetime
from typing import Any, Optional

from sqlalchemy import select
from sqlalchemy.orm import Session

from app.catalog import hash_content, slugify
from app.config import get_settings
from app.gov_crawl import category_keyword_hints, crawl_official_site, filter_relevant_pages
from app.llm import build_gemini_config, get_gemini_client, get_gemini_model
from app.models import (
    AmountRule,
    EligibilityRule,
    Jurisdiction,
    Program,
    ProgramVersion,
    Question,
    QuestionVariant,
)
from app.services import (
    CATEGORY_LABELS,
    get_or_create_agency,
    get_or_create_jurisdiction,
    is_redundant_state_residency_signal,
    upsert_questions,
    upsert_question_variants,
)

logger = logging.getLogger(__name__)

settings = get_settings()

STATE_NAMES = {
    "AL": "Alabama", "AK": "Alaska", "AZ": "Arizona", "AR": "Arkansas",
    "CA": "California", "CO": "Colorado", "CT": "Connecticut", "DE": "Delaware",
    "FL": "Florida", "GA": "Georgia", "HI": "Hawaii", "ID": "Idaho",
    "IL": "Illinois", "IN": "Indiana", "IA": "Iowa", "KS": "Kansas",
    "KY": "Kentucky", "LA": "Louisiana", "ME": "Maine", "MD": "Maryland",
    "MA": "Massachusetts", "MI": "Michigan", "MN": "Minnesota", "MS": "Mississippi",
    "MO": "Missouri", "MT": "Montana", "NE": "Nebraska", "NV": "Nevada",
    "NH": "New Hampshire", "NJ": "New Jersey", "NM": "New Mexico", "NY": "New York",
    "NC": "North Carolina", "ND": "North Dakota", "OH": "Ohio", "OK": "Oklahoma",
    "OR": "Oregon", "PA": "Pennsylvania", "RI": "Rhode Island", "SC": "South Carolina",
    "SD": "South Dakota", "TN": "Tennessee", "TX": "Texas", "UT": "Utah",
    "VT": "Vermont", "VA": "Virginia", "WA": "Washington", "WV": "West Virginia",
    "WI": "Wisconsin", "WY": "Wyoming", "DC": "District of Columbia",
    "AS": "American Samoa", "GU": "Guam", "PR": "Puerto Rico", "VI": "US Virgin Islands",
}

INTAKE_NAVIGATION_ACTIONS = {
    "use_screener": {
        "key": "use_screener",
        "label": "Use the screener",
        "href": "#start-screening-panel",
        "kind": "inline_action",
    },
    "start_screening": {
        "key": "start_screening",
        "label": "Start screening",
        "href": "action:start_screening",
        "kind": "inline_action",
    },
    "open_explorer": {
        "key": "open_explorer",
        "label": "Open Program Explorer",
        "href": "/explorer",
        "kind": "route",
    },
    "open_results": {
        "key": "open_results",
        "label": "Open Results",
        "href": "/results",
        "kind": "route",
    },
    "open_dashboard": {
        "key": "open_dashboard",
        "label": "Open Dashboard",
        "href": "/dashboard",
        "kind": "route",
    },
}


def _has_state_benefits(db: Session, state_code: str, categories: list[str]) -> bool:
    """Check if we already have generated benefit programs for this state."""
    jurisdiction = db.scalar(
        select(Jurisdiction).where(Jurisdiction.code == state_code, Jurisdiction.level == "state")
    )
    if jurisdiction is None:
        return False
    programs = db.scalars(
        select(Program).where(
            Program.jurisdiction_id == jurisdiction.id,
            Program.kind == "benefit",
            Program.status == "active",
        )
    ).all()
    if not programs:
        return False
    if not categories:
        return True
    existing_cats = {p.category for p in programs}
    return all(cat in existing_cats for cat in categories)


def _build_prompt(state_code: str, categories: list[str], crawled_pages: Optional[list[dict[str, Any]]] = None) -> str:
    state_name = STATE_NAMES.get(state_code, state_code)
    cat_labels = [CATEGORY_LABELS.get(c, c) for c in categories]
    cat_str = ", ".join(cat_labels) if cat_labels else "all available categories"
    valid_categories = ", ".join(f'"{c}"' for c in categories) if categories else '"general"'
    grounded_pages = crawled_pages or []
    grounded_section = ""
    if grounded_pages:
        grounded_section = f"""

Use ONLY the following crawled official government pages as evidence. Do not invent programs beyond what is grounded in these pages.

Official crawled pages:
{json.dumps([{"url": page["url"], "title": page["title"], "excerpt": page["excerpt"]} for page in grounded_pages], ensure_ascii=True)}

Additional grounding rules:
- Every program must clearly correspond to one or more of the crawled pages.
- apply_url MUST be one of the provided crawled URLs.
- If the crawled pages are too weak to support a program, omit that program.
"""

    return f"""You are a US government benefits expert. For the state of {state_name} ({state_code}), generate a JSON array of REAL state-level benefit programs in these categories: {cat_str}.

For each program return an object with these exact fields:
- "title": official program name (string)
- "agency_title": the state agency that administers it (string)
- "summary": 1-2 sentence description (string)
- "apply_url": official .gov URL to apply or learn more — must be a real URL ending in .gov (string)
- "category": one of [{valid_categories}] (string)
- "amount_description": what the benefit provides, e.g. "Up to $234/month per person" (string)
- "documents": array of 2-5 objects listing documents needed to apply, each with:
  - "name": document name (string)
  - "type": "required" or "recommended" (string)
  - "description": brief description of the document (string)
- "eligibility_criteria": array of 2-5 objects, each with:
  - "question_key": snake_case identifier prefixed with "{state_code.lower()}_", e.g. "{state_code.lower()}_household_income" (string)
  - "prompt": the eligibility question to ask the applicant (string)
  - "hint": short helper text (string or null)
  - "input_type": one of "radio", "select", "number", "currency", "date", "text" (string)
  - "options": array of {{"value": "...", "label": "..."}} objects (required for radio and select, null otherwise)
  - "sensitivity_level": one of "low", "medium", "high" (string)
  - "operator": one of "matches_any", "gte", "lte", "equals" (string)
  - "expected_values": array of acceptable values that indicate eligibility (array)
  - "label": human-readable description of this rule, e.g. "Household income below 130% FPL" (string)

IMPORTANT:
- Only include REAL programs that actually exist in {state_name}.
- apply_url MUST be a real .gov website URL.
- Include 2-5 programs per category.
- Every radio/select question MUST have options.
- Question keys must be unique across all programs (use descriptive names).
- Do NOT include state residency or "do you live in {state_name}" questions, because the applicant already selected {state_name} in the product.
- If a program needs county, ZIP code, city, or another sub-state location, ask for that specific detail instead of general residency.
{grounded_section}
- Return ONLY the JSON array, no markdown, no explanation."""


def _call_gemini(prompt: str) -> list[dict[str, Any]]:
    """Call Gemini API and return parsed JSON."""
    client = get_gemini_client()

    response = client.models.generate_content(
        model=get_gemini_model(),
        contents=prompt,
        config=build_gemini_config(
            response_mime_type="application/json",
            temperature=0.35,
            structured=True,
        ),
    )

    text = response.text.strip()
    programs = json.loads(text)
    if isinstance(programs, dict) and "programs" in programs:
        programs = programs["programs"]
    if not isinstance(programs, list):
        raise ValueError(f"Expected a JSON array from Gemini, got {type(programs)}")
    return programs


def generate_intake_assistant_guidance(
    *,
    description: str,
    messages: list[dict[str, str]],
    summary: str,
    suggested_scope: str,
    state_code: Optional[str],
    categories: list[str],
    facts: dict[str, Any],
    available_probes: list[dict[str, Any]],
    available_navigation_actions: list[str],
) -> Optional[dict[str, Any]]:
    """Use Gemini to draft a grounded assistant reply and choose the best next navigation step."""
    if not settings.gemini_api_key or not description.strip():
        return None

    try:
        from google import genai
    except Exception as exc:  # pragma: no cover - import guard
        logger.warning("Gemini library unavailable for intake assistant: %s", exc)
        return None

    available_actions = {
        key: INTAKE_NAVIGATION_ACTIONS[key]
        for key in available_navigation_actions
        if key in INTAKE_NAVIGATION_ACTIONS
    }
    allowed_probe_keys = [probe["key"] for probe in available_probes if probe.get("key")]
    compact_messages = [
        {"role": message.get("role", "user"), "content": message.get("content", "")[:500]}
        for message in messages[-6:]
    ]
    fact_labels = {
        key: value
        for key, value in facts.items()
        if value not in (None, "", [], {})
    }

    prompt = f"""You are Zobo, the in-product assistant inside a benefits screening web app.

Your job is to help the user navigate the product and refine their situation.
You must stay grounded in the supplied context. Do not invent programs, pages, questions, or eligibility decisions.

Return ONLY a JSON object with these exact keys:
- "summary": 1 to 2 short sentences summarizing the situation
- "chat_reply": 1 to 3 short sentences in a helpful assistant tone
- "next_probe_key": one of {json.dumps(allowed_probe_keys)} or null
- "navigation_actions": array containing up to 3 values from {json.dumps(list(available_actions.keys()))}

Rules:
- Use the provided summary, categories, facts, and available probes.
- If more detail would clearly help, choose exactly one next_probe_key from the allowlist.
- If the user already has enough detail to move forward, set next_probe_key to null.
- Prefer concluding once the user has given a usable situation plus at least one concrete follow-up detail, instead of continuing to fish for more.
- Keep the chat reply concise, practical, and conversational.
- Sound like a calm personal assistant, not a classifier or rules engine.
- Be flexible about tone and wording so the reply feels natural instead of templated.
- Do not start the chat reply with phrases like "This sounds most connected to".
- Do not repeat the summary verbatim in the chat reply.
- If the user's message is only a greeting, vague opener, or too thin to classify confidently, respond warmly, invite them to describe what is going on in a sentence or two, and set next_probe_key to null.
- When you ask a follow-up, connect it to why it matters instead of abruptly dropping the raw question.
- Navigation actions must reflect the current best next steps in the product.
- Never mention a page or feature that is not in the available navigation actions.

Examples of the tone to follow:
- If the user says "hi", a good chat_reply is: "Hi. I’m Zobo. Tell me a little about what’s going on, and I can help you sort through the next steps."
- If the user says they lost a job and are behind on rent, a good chat_reply is: "I’m sorry you’re dealing with that. We should look at housing and unemployment options. A quick question so I can narrow the right programs: what state are you in?"
- If the user says they cannot work because of a disability, a good chat_reply is: "That sounds really hard. We should look at disability and health-related options. To point you in the right direction, are you in a specific state right now?"
- If the user has already answered the key follow-up, a good chat_reply is: "Thanks, that gives me enough to work with. We should look at housing and food options. I have enough to line up the next steps for California."

Product surfaces available in this app:
{json.dumps(available_actions, ensure_ascii=True)}

Current grounded context:
- Existing summary: {summary}
- Suggested scope: {suggested_scope}
- Suggested state: {state_code or "null"}
- Suggested categories: {json.dumps(categories)}
- Structured facts: {json.dumps(fact_labels, ensure_ascii=True)}
- Available follow-up probes: {json.dumps(available_probes, ensure_ascii=True)}
- Recent conversation: {json.dumps(compact_messages, ensure_ascii=True)}

Original user situation:
{description}
"""

    try:
        client = get_gemini_client()
        response = client.models.generate_content(
            model=get_gemini_model(),
            contents=prompt,
            config=build_gemini_config(
                response_mime_type="application/json",
                temperature=0.8,
                structured=False,
            ),
        )
        payload = json.loads(response.text.strip())
        if not isinstance(payload, dict):
            return None

        next_probe_key = payload.get("next_probe_key")
        if next_probe_key not in allowed_probe_keys:
            next_probe_key = None

        navigation_actions = [
            action for action in payload.get("navigation_actions", [])
            if action in available_actions
        ][:3]

        summary_text = payload.get("summary")
        if not isinstance(summary_text, str) or not summary_text.strip():
            summary_text = None

        chat_reply = payload.get("chat_reply")
        if not isinstance(chat_reply, str) or not chat_reply.strip():
            chat_reply = None

        return {
            "summary": summary_text,
            "chat_reply": chat_reply,
            "next_probe_key": next_probe_key,
            "navigation_actions": navigation_actions,
        }
    except Exception as exc:  # pragma: no cover - external API fallback
        logger.warning("Gemini intake assistant generation failed, falling back to deterministic guidance: %s", exc)
        return None


def _ingest_gemini_programs(db: Session, state_code: str, programs: list[dict[str, Any]]) -> int:
    """Insert Gemini-generated programs into the database."""
    state_name = STATE_NAMES.get(state_code, state_code)
    jurisdiction = get_or_create_jurisdiction(
        db, code=state_code, level="state", name=state_name, parent_code="federal"
    )

    created = 0
    all_questions: list[dict[str, Any]] = []
    all_variants: list[dict[str, Any]] = []

    for prog_data in programs:
        title = prog_data.get("title", "").strip()
        if not title:
            continue

        slug = slugify(f"{state_code}-{title}")
        existing = db.scalar(select(Program).where(Program.slug == slug))
        if existing is not None:
            continue

        agency = get_or_create_agency(
            db, jurisdiction.id, prog_data.get("agency_title", f"{state_name} State Agency"),
            prog_data.get("apply_url"),
        )

        program = Program(
            slug=slug,
            name=title,
            kind="benefit",
            category=prog_data.get("category", "general"),
            summary=prog_data.get("summary", ""),
            apply_url=prog_data.get("apply_url", ""),
            documents_json=prog_data.get("documents"),
            status="active",
            jurisdiction_id=jurisdiction.id,
            agency_id=agency.id,
        )
        db.add(program)
        db.flush()

        signature = hash_content(prog_data)
        version = ProgramVersion(
            program_id=program.id,
            version_label=f"gemini-{datetime.utcnow().strftime('%Y%m%d')}",
            signature=signature,
            publication_state="published",
            published_at=datetime.utcnow(),
            change_summary=f"Generated by Gemini for {state_name}.",
            source_freshness_days=0,
        )
        db.add(version)
        db.flush()

        db.add(AmountRule(
            program_version_id=version.id,
            amount_type="estimated",
            display_text=prog_data.get("amount_description", "Contact the agency for details."),
            source_key=f"gemini-{state_code}-{slug}",
        ))

        # Always add a state_code rule so the program is scoped to this state
        db.add(EligibilityRule(
            program_version_id=version.id,
            question_key="state_code",
            operator="matches_any",
            expected_values_json=[state_code],
            label=f"Available in {state_name}.",
            priority=100,
            source_key=f"gemini-{state_code}-{slug}",
            source_citation=prog_data.get("apply_url", ""),
        ))

        for criterion in prog_data.get("eligibility_criteria", []):
            qkey = criterion.get("question_key", "").strip()
            if not qkey:
                continue
            if is_redundant_state_residency_signal(
                state_code=state_code,
                state_name=state_name,
                question_key=qkey,
                prompt=criterion.get("prompt"),
                hint=criterion.get("hint"),
                label=criterion.get("label"),
                options=criterion.get("options"),
                expected_values=criterion.get("expected_values"),
            ):
                continue

            all_questions.append({
                "key": qkey,
                "prompt": criterion.get("prompt", qkey),
                "hint": criterion.get("hint"),
                "input_type": criterion.get("input_type", "radio"),
                "sensitivity_level": criterion.get("sensitivity_level", "low"),
                "options": criterion.get("options"),
            })

            for tier in ("simple", "standard", "detailed"):
                all_variants.append({
                    "question_key": qkey,
                    "depth_tier": tier,
                    "prompt": criterion.get("prompt", qkey),
                    "hint": criterion.get("hint"),
                    "input_type": criterion.get("input_type", "radio"),
                    "options_json": criterion.get("options"),
                    "normalizer": None,
                })

            db.add(EligibilityRule(
                program_version_id=version.id,
                question_key=qkey,
                operator=criterion.get("operator", "matches_any"),
                expected_values_json=criterion.get("expected_values", []),
                label=criterion.get("label", qkey),
                priority=80,
                source_key=f"gemini-{state_code}-{slug}",
                source_citation=prog_data.get("apply_url", ""),
            ))

        created += 1

    if all_questions:
        upsert_questions(db, all_questions)
        upsert_question_variants(db, all_variants)

    db.flush()
    return created


def _get_state_seed_url(db: Session, state_code: str) -> Optional[str]:
    slug = f"state-social-services-{state_code.lower()}"
    referral = db.scalar(select(Program).where(Program.slug == slug))
    if referral and referral.apply_url:
        return referral.apply_url

    jurisdiction = db.scalar(
        select(Jurisdiction).where(Jurisdiction.code == state_code, Jurisdiction.level == "state")
    )
    if jurisdiction is None:
        return None

    agency = db.scalar(select(Program).where(Program.jurisdiction_id == jurisdiction.id, Program.kind == "referral"))
    if agency and agency.apply_url:
        return agency.apply_url
    return None


def ensure_state_programs(db: Session, state_code: str, categories: list[str]) -> int:
    """Ensure state benefit programs exist for the given state and categories.

    If programs already exist in the DB, returns 0 (cached).
    Otherwise calls Gemini to generate them and inserts into DB.
    """
    if not settings.gemini_api_key:
        logger.warning("No Gemini API key configured, skipping state program generation.")
        return 0

    if not state_code:
        return 0

    state_code = state_code.upper()

    if _has_state_benefits(db, state_code, categories):
        logger.info("State benefits for %s already cached, skipping Gemini call.", state_code)
        return 0

    logger.info("Generating state benefits for %s via Gemini...", state_code)
    try:
        crawled_pages: list[dict[str, Any]] = []
        seed_url = _get_state_seed_url(db, state_code)
        if seed_url:
            crawled_pages = crawl_official_site(
                seed_url,
                timeout_seconds=settings.request_timeout_seconds,
                max_pages=settings.crawl_max_pages_per_site,
                max_depth=settings.crawl_max_depth,
                keyword_hints=category_keyword_hints(categories),
            )
            crawled_pages = filter_relevant_pages(
                crawled_pages,
                context_title=f"{STATE_NAMES.get(state_code, state_code)} benefits",
                jurisdiction_name=STATE_NAMES.get(state_code, state_code),
                categories=categories,
                max_results=settings.crawl_relevant_page_limit,
            )

        prompt = _build_prompt(state_code, categories, crawled_pages=crawled_pages)
        programs = _call_gemini(prompt)
        created = _ingest_gemini_programs(db, state_code, programs)
        db.commit()
        logger.info("Created %d state benefit programs for %s.", created, state_code)
        return created
    except Exception as exc:
        db.rollback()
        logger.error("Gemini state program generation failed for %s: %s", state_code, exc)
        return 0
