from __future__ import annotations

import re
from typing import Any, Optional

from sqlalchemy.orm import Session

from app.hybrid_explorer import interpret_hybrid_explorer_request
from app.services import CATEGORY_LABELS


BOOL_TRUE = {"yes", "y", "yeah", "yep", "correct", "i do", "i am", "true"}
BOOL_FALSE = {"no", "n", "nope", "not", "false", "i do not", "i'm not", "im not"}

AGE_RE = re.compile(r"\b(?:i am|i'm|im|age|turned|turning)\s+(\d{2})\b", re.IGNORECASE)
MONEY_RE = re.compile(r"\$?\s?(\d{1,3}(?:,\d{3})+|\d{4,6})")

FACT_LABELS = {
    "state_code": "State selected",
    "applicant_income": "Limited income and resources",
    "applicant_disability": "Disability or qualifying illness",
    "applicant_ability_to_work": "Unable to work for a year or more",
    "applicant_served_in_active_military": "Active-duty military service",
    "applicant_service_disability": "Service-connected disability",
    "applicant_dolo": "Recent family death",
    "deceased_died_of_COVID": "COVID-related death",
    "deceased_death_location_is_US": "Death occurred in the U.S.",
    "applicant_paid_into_SS": "Worked and paid Social Security taxes",
    "recent_job_loss": "Recent job loss or reduced hours",
    "housing_urgency": "Urgent housing or utility pressure",
    "food_insecurity": "Food or grocery hardship",
    "current_student": "Currently in school or job training",
    "has_children": "Children or dependents in household",
    "is_62_or_older": "Age 62 or older",
    "recent_disaster_impact": "Recent disaster impact",
    "needs_health_coverage": "Needs health coverage or medical help",
    "annual_income_amount": "Approximate annual income",
}

FACT_ORDER = [
    "state_code",
    "recent_job_loss",
    "housing_urgency",
    "food_insecurity",
    "current_student",
    "has_children",
    "applicant_income",
    "applicant_disability",
    "applicant_ability_to_work",
    "applicant_served_in_active_military",
    "applicant_service_disability",
    "applicant_paid_into_SS",
    "applicant_dolo",
    "deceased_died_of_COVID",
    "deceased_death_location_is_US",
    "recent_disaster_impact",
    "needs_health_coverage",
    "is_62_or_older",
    "annual_income_amount",
]

YES_NO_PROBE_OPTIONS = [
    {"value": "Yes", "label": "Yes"},
    {"value": "No", "label": "No"},
]

PROBE_QUESTIONS = {
    "state_code": {
        "prompt": "What state do you live in or want help in right now?",
        "reason": "State benefits and agencies are different in every state.",
        "input_type": "state",
    },
    "applicant_income": {
        "prompt": "Are your income and resources limited right now?",
        "reason": "Many food, cash, and health programs use an income screen.",
        "input_type": "yes_no",
        "options": YES_NO_PROBE_OPTIONS,
    },
    "recent_job_loss": {
        "prompt": "Did you recently lose a job, lose hours, or have work become unstable?",
        "reason": "That helps identify unemployment and emergency support paths.",
        "input_type": "yes_no",
        "options": YES_NO_PROBE_OPTIONS,
    },
    "housing_urgency": {
        "prompt": "Are you behind on rent or utilities, facing eviction, or worried about losing housing?",
        "reason": "Housing programs depend on whether the situation is urgent.",
        "input_type": "yes_no",
        "options": YES_NO_PROBE_OPTIONS,
    },
    "current_student": {
        "prompt": "Are you currently in school, college, or a job-training program?",
        "reason": "That changes which education benefits and grants make sense.",
        "input_type": "yes_no",
        "options": YES_NO_PROBE_OPTIONS,
    },
    "has_children": {
        "prompt": "Do you have children or dependents in your household?",
        "reason": "Family and child-related programs depend on household makeup.",
        "input_type": "yes_no",
        "options": YES_NO_PROBE_OPTIONS,
    },
    "applicant_disability": {
        "prompt": "Do you have a disability or health condition that significantly affects daily life or work?",
        "reason": "That can open disability and health-related benefit pathways.",
        "input_type": "yes_no",
        "options": YES_NO_PROBE_OPTIONS,
    },
    "applicant_ability_to_work": {
        "prompt": "Has that condition kept you from working, or is it expected to keep you from working, for a year or more?",
        "reason": "Longer work limitations matter for disability screening.",
        "input_type": "yes_no",
        "options": YES_NO_PROBE_OPTIONS,
    },
    "applicant_served_in_active_military": {
        "prompt": "Did you serve in active-duty military service?",
        "reason": "That is the main gateway to veteran benefit programs.",
        "input_type": "yes_no",
        "options": YES_NO_PROBE_OPTIONS,
    },
    "applicant_service_disability": {
        "prompt": "If you served, was your disability or condition caused or worsened by that service?",
        "reason": "That affects service-connected VA disability screening.",
        "input_type": "yes_no",
        "options": YES_NO_PROBE_OPTIONS,
    },
    "applicant_dolo": {
        "prompt": "Did you recently lose an immediate family member?",
        "reason": "That helps screen survivor and funeral-related programs.",
        "input_type": "yes_no",
        "options": YES_NO_PROBE_OPTIONS,
    },
    "deceased_died_of_COVID": {
        "prompt": "Was the death related to COVID-19?",
        "reason": "That matters for funeral assistance screening.",
        "input_type": "yes_no",
        "options": YES_NO_PROBE_OPTIONS,
    },
    "deceased_death_location_is_US": {
        "prompt": "Did the person die in the United States or a U.S. territory?",
        "reason": "Some death-related programs depend on where the death occurred.",
        "input_type": "yes_no",
        "options": YES_NO_PROBE_OPTIONS,
    },
    "is_62_or_older": {
        "prompt": "Are you age 62 or older?",
        "reason": "Retirement programs use age as a key first screen.",
        "input_type": "yes_no",
        "options": YES_NO_PROBE_OPTIONS,
    },
    "applicant_paid_into_SS": {
        "prompt": "Have you worked and paid U.S. Social Security taxes?",
        "reason": "That affects retirement and disability pathways.",
        "input_type": "yes_no",
        "options": YES_NO_PROBE_OPTIONS,
    },
    "recent_disaster_impact": {
        "prompt": "Has a recent disaster like a fire, flood, storm, or emergency directly affected your household?",
        "reason": "That can open disaster recovery programs.",
        "input_type": "yes_no",
        "options": YES_NO_PROBE_OPTIONS,
    },
}

CATEGORY_PROBE_ORDER = {
    "children_families": ["has_children", "applicant_income", "state_code"],
    "death": ["applicant_dolo", "deceased_died_of_COVID", "deceased_death_location_is_US", "state_code"],
    "disabilities": ["applicant_disability", "applicant_ability_to_work", "applicant_income", "state_code"],
    "disasters": ["recent_disaster_impact", "housing_urgency", "state_code"],
    "education": ["current_student", "applicant_income", "state_code"],
    "food": ["applicant_income", "has_children", "state_code"],
    "health": ["applicant_disability", "applicant_income", "applicant_served_in_active_military", "is_62_or_older", "state_code"],
    "housing_utilities": ["housing_urgency", "applicant_income", "state_code"],
    "jobs_unemployment": ["recent_job_loss", "applicant_income", "state_code"],
    "military_veterans": ["applicant_served_in_active_military", "applicant_service_disability", "state_code"],
    "retirement_seniors": ["is_62_or_older", "applicant_paid_into_SS", "state_code"],
    "welfare_cash_assistance": ["applicant_income", "has_children", "state_code"],
}


def _normalize_text(value: Any) -> str:
    if value is None:
        return ""
    return re.sub(r"\s+", " ", str(value).strip().lower())


def _dedupe_preserve_order(values: list[str]) -> list[str]:
    seen: set[str] = set()
    ordered: list[str] = []
    for value in values:
        normalized = _normalize_text(value)
        if not normalized or normalized in seen:
            continue
        seen.add(normalized)
        ordered.append(value)
    return ordered


def _merge_categories(*category_lists: list[str]) -> list[str]:
    merged: list[str] = []
    for category_list in category_lists:
        merged.extend(category_list or [])
    return _dedupe_preserve_order(merged)


def _boolish_from_message(message: str) -> Optional[bool]:
    normalized = _normalize_text(message)
    if not normalized:
        return None
    if any(token == normalized or token in normalized.split() for token in BOOL_TRUE):
        return True
    if any(token == normalized or token in normalized.split() for token in BOOL_FALSE):
        return False
    return None


def _extract_age_value(text: str) -> Optional[int]:
    match = AGE_RE.search(text or "")
    if not match:
        return None
    age = int(match.group(1))
    if 0 < age < 120:
        return age
    return None


def _extract_money_value(text: str) -> Optional[int]:
    for match in MONEY_RE.finditer(text or ""):
        raw = match.group(1).replace(",", "")
        try:
            value = int(raw)
        except ValueError:
            continue
        if 500 <= value <= 1_000_000:
            return value
    return None


def _collect_story_text(description: str, messages: list[dict[str, str]]) -> str:
    parts = [description or ""]
    parts.extend(message.get("content", "") for message in messages if message.get("role") == "user")
    return " ".join(part for part in parts if part).strip()


def _extract_story_facts(text: str, state_code: Optional[str]) -> dict[str, Any]:
    normalized = _normalize_text(text)
    facts: dict[str, Any] = {}

    if state_code:
        facts["state_code"] = state_code

    if any(term in normalized for term in ("lost my job", "laid off", "lost work", "hours cut", "unemployed", "work dried up")):
        facts["recent_job_loss"] = True
    if any(term in normalized for term in ("behind on rent", "eviction", "homeless", "rent", "utilities", "utility shutoff", "shutoff", "housing")):
        facts["housing_urgency"] = True
    if any(term in normalized for term in ("hungry", "groceries", "food", "meal", "snap", "wic")):
        facts["food_insecurity"] = True
    if any(term in normalized for term in ("school", "college", "student", "tuition", "job training", "training program", "certificate program")):
        facts["current_student"] = True
    if any(term in normalized for term in ("child", "children", "kids", "dependent", "pregnant", "newborn", "baby")):
        facts["has_children"] = True
    if any(term in normalized for term in ("disability", "disabled", "illness", "condition", "medical condition", "chronic illness")):
        facts["applicant_disability"] = True
    if any(term in normalized for term in ("can't work", "cannot work", "unable to work", "stopped working because", "too sick to work")):
        facts["applicant_disability"] = True
        facts["applicant_ability_to_work"] = True
    if any(term in normalized for term in ("veteran", "active duty", "served in the military", "army", "navy", "air force", "marines", "coast guard")):
        facts["applicant_served_in_active_military"] = True
    if any(term in normalized for term in ("service connected", "caused by my service", "injured in the military", "worsened by my service")):
        facts["applicant_served_in_active_military"] = True
        facts["applicant_service_disability"] = True
    if any(term in normalized for term in ("died", "passed away", "funeral", "burial", "widow", "widower", "survivor")):
        facts["applicant_dolo"] = True
    if "covid" in normalized and facts.get("applicant_dolo"):
        facts["deceased_died_of_COVID"] = True
    if any(term in normalized for term in ("u.s.", "united states", "california", "new york", "texas", "florida")) and facts.get("applicant_dolo"):
        facts["deceased_death_location_is_US"] = True
    if any(term in normalized for term in ("flood", "fire", "hurricane", "earthquake", "disaster", "storm", "emergency")):
        facts["recent_disaster_impact"] = True
    if any(term in normalized for term in ("doctor", "hospital", "insurance", "medical bills", "medicine", "medicaid", "medicare", "therapy")):
        facts["needs_health_coverage"] = True
    if any(term in normalized for term in ("low income", "limited income", "can't afford", "cannot afford", "behind on bills", "money is tight", "struggling to pay")):
        facts["applicant_income"] = True
    if any(term in normalized for term in ("social security", "worked for years", "worked and paid", "retired")):
        facts["applicant_paid_into_SS"] = True

    age = _extract_age_value(text)
    if age is not None:
        facts["is_62_or_older"] = age >= 62

    income = _extract_money_value(text)
    if income is not None:
        facts["annual_income_amount"] = income
        if income <= 35_000:
            facts.setdefault("applicant_income", True)

    return facts


def _parse_probe_answer(db: Session, question_key: str, message: str) -> dict[str, Any]:
    normalized = _normalize_text(message)
    updates: dict[str, Any] = {}

    if question_key == "state_code":
        interpretation = interpret_hybrid_explorer_request(
            db,
            description=message,
            query="",
            scope="both",
            state_code=None,
            categories=[],
            use_llm=False,
        )
        if interpretation.get("applied_state_code"):
            updates["state_code"] = interpretation["applied_state_code"]
        return updates

    if question_key == "is_62_or_older":
        boolish = _boolish_from_message(message)
        if boolish is not None:
            updates[question_key] = boolish
            return updates
        age = _extract_age_value(message)
        if age is not None:
            updates[question_key] = age >= 62
        return updates

    if question_key == "annual_income_amount":
        income = _extract_money_value(message)
        if income is not None:
            updates["annual_income_amount"] = income
            updates["applicant_income"] = income <= 35_000
        return updates

    boolish = _boolish_from_message(message)
    if boolish is None:
        return updates

    updates[question_key] = boolish
    if question_key == "applicant_disability" and not boolish:
        updates["applicant_ability_to_work"] = False
    if question_key == "applicant_served_in_active_military" and not boolish:
        updates["applicant_service_disability"] = False
    if question_key == "applicant_dolo" and not boolish:
        updates["deceased_died_of_COVID"] = False
        updates["deceased_death_location_is_US"] = False
    return updates


def _prefill_answers_from_facts(facts: dict[str, Any]) -> dict[str, Any]:
    prefill: dict[str, Any] = {}
    for key in (
        "state_code",
        "applicant_income",
        "applicant_disability",
        "applicant_ability_to_work",
        "applicant_served_in_active_military",
        "applicant_service_disability",
        "applicant_dolo",
        "deceased_died_of_COVID",
        "deceased_death_location_is_US",
        "applicant_paid_into_SS",
    ):
        value = facts.get(key)
        if isinstance(value, bool):
            prefill[key] = "Yes" if value else "No"
        elif isinstance(value, str):
            prefill[key] = value
    return prefill


def _fact_to_chip(key: str, value: Any) -> Optional[dict[str, Any]]:
    if value is None:
        return None
    if isinstance(value, bool):
        value_label = "Yes" if value else "No"
    elif isinstance(value, (int, float)):
        if key == "annual_income_amount":
            value_label = f"${value:,.0f}/year"
        else:
            value_label = str(value)
    else:
        value_label = str(value)
    return {
        "key": key,
        "label": FACT_LABELS.get(key, key.replace("_", " ").title()),
        "value": value,
        "value_label": value_label,
    }


def _fact_chips(facts: dict[str, Any]) -> list[dict[str, Any]]:
    chips: list[dict[str, Any]] = []
    for key in FACT_ORDER:
        chip = _fact_to_chip(key, facts.get(key))
        if chip:
            chips.append(chip)
    return chips


def _suggested_scope(explicit_scope: Optional[str], state_code: Optional[str]) -> str:
    if explicit_scope == "state":
        return "state" if state_code else "federal"
    if state_code:
        return "both"
    return explicit_scope or "federal"


def _follow_up_queue(categories: list[str], facts: dict[str, Any]) -> list[str]:
    queue: list[str] = []
    if "state_code" not in facts:
        queue.append("state_code")
    for category in categories:
        queue.extend(CATEGORY_PROBE_ORDER.get(category, []))
    queue.extend(["applicant_income", "has_children", "state_code"])
    deduped: list[str] = []
    seen: set[str] = set()
    for key in queue:
        if key in seen or facts.get(key) is not None:
            continue
        if key not in PROBE_QUESTIONS:
            continue
        seen.add(key)
        deduped.append(key)
    return deduped


def _follow_up_payload(queue: list[str]) -> tuple[Optional[dict[str, Any]], list[dict[str, Any]]]:
    payload = []
    for key in queue[:4]:
        spec = PROBE_QUESTIONS[key]
        payload.append(
            {
                "key": key,
                "prompt": spec["prompt"],
                "reason": spec["reason"],
                "input_type": spec.get("input_type", "yes_no"),
                "options": spec.get("options"),
            }
        )
    return (payload[0] if payload else None), payload


def _build_summary(categories: list[str], facts: dict[str, Any], state_code: Optional[str]) -> str:
    if not categories:
        category_text = "general support"
    else:
        category_text = ", ".join(CATEGORY_LABELS.get(cat, cat.replace("_", " ").title()) for cat in categories[:3])

    known = []
    for key in ("recent_job_loss", "housing_urgency", "food_insecurity", "applicant_disability", "applicant_dolo", "current_student"):
        if facts.get(key):
            known.append(FACT_LABELS[key].lower())
    summary = f"This sounds most connected to {category_text}."
    if state_code:
        summary += f" I also picked up state context for {state_code}."
    if known:
        summary += " So far I have: " + ", ".join(known[:3]) + "."
    return summary


def _build_chat_reply(summary: str, next_probe: Optional[dict[str, Any]]) -> str:
    if next_probe is None:
        return summary + " I have enough to hand these suggestions to the screener."
    return summary + " " + next_probe["prompt"]


def _merge_fact_dicts(*fact_dicts: dict[str, Any]) -> dict[str, Any]:
    merged: dict[str, Any] = {}
    for fact_dict in fact_dicts:
        for key, value in (fact_dict or {}).items():
            if value is not None:
                merged[key] = value
    return merged


def interpret_life_event_intake(
    db: Session,
    *,
    description: str,
    scope: Optional[str] = None,
    state_code: Optional[str] = None,
    categories: Optional[list[str]] = None,
    current_facts: Optional[dict[str, Any]] = None,
    messages: Optional[list[dict[str, str]]] = None,
    pending_question_key: Optional[str] = None,
    use_llm: bool = True,
) -> dict[str, Any]:
    messages = messages or []
    story_text = _collect_story_text(description, messages)
    interpretation = interpret_hybrid_explorer_request(
        db,
        description=story_text,
        query="",
        scope=scope or "both",
        state_code=state_code.upper() if state_code else None,
        categories=categories or [],
        use_llm=use_llm,
    )

    facts = dict(current_facts or {})
    if pending_question_key and messages:
        latest_user_message = next((msg.get("content", "") for msg in reversed(messages) if msg.get("role") == "user"), "")
        facts = _merge_fact_dicts(facts, _parse_probe_answer(db, pending_question_key, latest_user_message))

    story_facts = _extract_story_facts(story_text, interpretation.get("applied_state_code"))
    facts = _merge_fact_dicts(story_facts, facts)

    applied_categories = _merge_categories(
        [item["key"] for item in interpretation.get("applied_categories", [])],
        categories or [],
    )
    if facts.get("recent_job_loss"):
        applied_categories = _merge_categories(applied_categories, ["jobs_unemployment"])
    if facts.get("housing_urgency"):
        applied_categories = _merge_categories(applied_categories, ["housing_utilities"])
    if facts.get("food_insecurity"):
        applied_categories = _merge_categories(applied_categories, ["food"])
    if facts.get("current_student"):
        applied_categories = _merge_categories(applied_categories, ["education"])
    if facts.get("has_children"):
        applied_categories = _merge_categories(applied_categories, ["children_families"])
    if facts.get("applicant_disability"):
        applied_categories = _merge_categories(applied_categories, ["disabilities", "health"])
    if facts.get("applicant_served_in_active_military"):
        applied_categories = _merge_categories(applied_categories, ["military_veterans"])
    if facts.get("applicant_dolo"):
        applied_categories = _merge_categories(applied_categories, ["death"])
    if facts.get("recent_disaster_impact"):
        applied_categories = _merge_categories(applied_categories, ["disasters"])
    if facts.get("needs_health_coverage"):
        applied_categories = _merge_categories(applied_categories, ["health"])
    if facts.get("is_62_or_older"):
        applied_categories = _merge_categories(applied_categories, ["retirement_seniors"])
    if facts.get("applicant_income"):
        applied_categories = _merge_categories(applied_categories, ["food", "welfare_cash_assistance"])

    inferred_state_code = facts.get("state_code") or interpretation.get("applied_state_code")
    suggested_scope = _suggested_scope(scope, inferred_state_code)
    queue = _follow_up_queue(applied_categories, facts)
    next_probe, follow_up_questions = _follow_up_payload(queue)
    summary = _build_summary(applied_categories, facts, inferred_state_code)
    prefill_answers = _prefill_answers_from_facts(facts)

    return {
        "summary": summary,
        "chat_reply": _build_chat_reply(summary, next_probe),
        "suggested_scope": suggested_scope,
        "applied_state_code": inferred_state_code,
        "suggested_categories": [
            {"key": category, "label": CATEGORY_LABELS.get(category, category.replace("_", " ").title())}
            for category in applied_categories
        ],
        "structured_facts": _fact_chips(facts),
        "current_facts": facts,
        "prefill_answers": prefill_answers,
        "follow_up_questions": follow_up_questions,
        "next_probe": next_probe,
        "interpretation_method": interpretation.get("method", "heuristic"),
        "llm_used": interpretation.get("llm_used", False),
    }
