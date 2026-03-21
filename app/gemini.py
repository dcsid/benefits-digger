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


def _build_prompt(state_code: str, categories: list[str]) -> str:
    state_name = STATE_NAMES.get(state_code, state_code)
    cat_labels = [CATEGORY_LABELS.get(c, c) for c in categories]
    cat_str = ", ".join(cat_labels) if cat_labels else "all available categories"
    valid_categories = ", ".join(f'"{c}"' for c in categories) if categories else '"general"'

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
- Return ONLY the JSON array, no markdown, no explanation."""


def _call_gemini(prompt: str) -> list[dict[str, Any]]:
    """Call Gemini API and return parsed JSON."""
    from google import genai

    client = genai.Client(api_key=settings.gemini_api_key)

    response = client.models.generate_content(
        model="gemini-2.5-flash",
        contents=prompt,
        config={
            "response_mime_type": "application/json",
            "temperature": 0.2,
        },
    )

    text = response.text.strip()
    programs = json.loads(text)
    if isinstance(programs, dict) and "programs" in programs:
        programs = programs["programs"]
    if not isinstance(programs, list):
        raise ValueError(f"Expected a JSON array from Gemini, got {type(programs)}")
    return programs


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
        prompt = _build_prompt(state_code, categories)
        programs = _call_gemini(prompt)
        created = _ingest_gemini_programs(db, state_code, programs)
        db.commit()
        logger.info("Created %d state benefit programs for %s.", created, state_code)
        return created
    except Exception as exc:
        db.rollback()
        logger.error("Gemini state program generation failed for %s: %s", state_code, exc)
        return 0
