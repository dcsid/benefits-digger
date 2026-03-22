from __future__ import annotations

import re
from typing import Any, Optional

from sqlalchemy.orm import Session

from app.gemini import INTAKE_NAVIGATION_ACTIONS, STATE_NAMES, generate_intake_assistant_guidance
from app.hybrid_explorer import interpret_hybrid_explorer_request
from app.services import CATEGORY_LABELS


BOOL_TRUE = {"yes", "y", "yeah", "yep", "correct", "i do", "i am", "true"}
BOOL_FALSE = {"no", "n", "nope", "not", "false", "i do not", "i'm not", "im not"}
LOW_SIGNAL_OPENERS = {
    "hello",
    "hello there",
    "hey",
    "hey there",
    "hi",
    "hi there",
    "hola",
    "good morning",
    "good afternoon",
    "good evening",
}
LOW_SIGNAL_GENERIC = {
    "help",
    "help me",
    "i need help",
    "need help",
    "not sure",
    "unsure",
    "can you help",
}

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


def _resolve_state_code_from_message(message: str) -> Optional[str]:
    normalized = _normalize_text(message)
    if not normalized:
        return None

    collapsed = re.sub(r"[^a-z]", "", normalized)
    if len(collapsed) == 2:
        candidate = collapsed.upper()
        if candidate in STATE_NAMES:
            return candidate

    for code, name in STATE_NAMES.items():
        normalized_name = _normalize_text(name)
        collapsed_name = re.sub(r"[^a-z]", "", normalized_name)
        if normalized == normalized_name or collapsed == collapsed_name:
            return code
    return None


def _is_low_signal_opening(text: str, categories: list[str], facts: dict[str, Any]) -> bool:
    normalized = _normalize_text(text)
    if not normalized:
        return True
    if categories:
        return False
    meaningful_fact_keys = {key for key, value in facts.items() if value not in (None, False, "", [], {})}
    if meaningful_fact_keys:
        return False
    if normalized in LOW_SIGNAL_OPENERS or normalized in LOW_SIGNAL_GENERIC:
        return True
    tokens = re.findall(r"[a-z0-9']+", normalized)
    if len(tokens) <= 2:
        return True
    return False


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
        resolved_state_code = _resolve_state_code_from_message(message)
        if resolved_state_code:
            updates["state_code"] = resolved_state_code
            return updates
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


def _follow_up_payload(
    queue: list[str],
    *,
    preferred_key: Optional[str] = None,
) -> tuple[Optional[dict[str, Any]], list[dict[str, Any]]]:
    ordered_queue = list(queue)
    if preferred_key and preferred_key in ordered_queue:
        ordered_queue.remove(preferred_key)
        ordered_queue.insert(0, preferred_key)
    payload = []
    for key in ordered_queue[:4]:
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


def _build_low_signal_chat_reply() -> str:
    return (
        "Hi. I’m Zobo, and I’m here to help you sort through things like rent, food, health coverage, disability, unemployment, school costs, "
        "or family loss. Tell me a little about what’s going on, and we’ll figure out the best next step together."
    )


def _friendly_probe_bridge(next_probe: Optional[dict[str, Any]]) -> Optional[str]:
    if not next_probe:
        return None
    key = next_probe.get("key")
    prompt = next_probe.get("prompt", "").strip()
    if not prompt:
        return None
    if key == "state_code":
        return "To narrow this to the right federal and state options, what state do you live in or want help in right now?"
    if key == "applicant_income":
        return "A quick question so I can narrow the right programs: are your income and resources limited right now?"
    if key == "housing_urgency":
        return "To tell apart longer-term housing help from urgent options, are you behind on rent or utilities, facing eviction, or worried about losing housing?"
    if key == "recent_job_loss":
        return "A quick check that helps with unemployment support: did you recently lose a job, lose hours, or have work become unstable?"
    if key == "applicant_disability":
        return "To see whether disability-related help may fit, do you have a disability or health condition that significantly affects daily life or work?"
    prompt = prompt[0].lower() + prompt[1:] if len(prompt) > 1 else prompt.lower()
    return f"A quick next question: {prompt}"


def _build_empathy_acknowledgment(facts: dict[str, Any]) -> Optional[str]:
    if facts.get("applicant_dolo"):
        return "I’m sorry you’re going through that."
    if facts.get("housing_urgency") and facts.get("food_insecurity"):
        return "That sounds like a lot to carry at once."
    if facts.get("recent_job_loss"):
        return "I’m sorry things feel unstable right now."
    if facts.get("housing_urgency"):
        return "I’m sorry housing is feeling so stressful right now."
    if facts.get("food_insecurity"):
        return "I’m sorry things are this tight right now."
    if facts.get("applicant_disability"):
        return "That sounds really hard."
    if facts.get("recent_disaster_impact"):
        return "I’m sorry you’re dealing with that."
    return None


def _build_topic_phrase(categories: list[str]) -> Optional[str]:
    labels = [CATEGORY_LABELS.get(category, category.replace("_", " ").title()).lower() for category in categories[:2]]
    if not labels:
        return None
    if len(labels) == 1:
        return f"We should look at {labels[0]} options."
    return f"We should look at {labels[0]} and {labels[1]} options."


def _build_conversational_chat_reply(
    *,
    categories: list[str],
    facts: dict[str, Any],
    next_probe: Optional[dict[str, Any]],
) -> str:
    parts: list[str] = []
    empathy = _build_empathy_acknowledgment(facts)
    topic_phrase = _build_topic_phrase(categories)
    if empathy:
        parts.append(empathy)
    elif facts:
        parts.append("Thanks for sharing that with me.")
    else:
        parts.append("Thanks for sharing that.")
    if topic_phrase:
        parts.append(topic_phrase)
    bridge = _friendly_probe_bridge(next_probe)
    if bridge:
        parts.append(bridge)
        return " ".join(parts)
    parts.append("I have enough to line up the next steps whenever you want to keep going.")
    return " ".join(parts)


def _has_enough_context_to_conclude(
    *,
    categories: list[str],
    facts: dict[str, Any],
    state_code: Optional[str],
    messages: list[dict[str, str]],
) -> bool:
    if not categories:
        return False
    user_turns = sum(1 for message in messages if message.get("role") == "user")
    if user_turns < 1:
        return False
    known_fact_keys = {
        key
        for key, value in facts.items()
        if value not in (None, False, "", [], {}) and key != "state_code"
    }
    if state_code and len(known_fact_keys) >= 2:
        return True
    if len(known_fact_keys) >= 3:
        return True
    return False


def _build_conclusion_chat_reply(
    *,
    categories: list[str],
    facts: dict[str, Any],
    state_code: Optional[str],
) -> str:
    parts: list[str] = []
    empathy = _build_empathy_acknowledgment(facts)
    topic_phrase = _build_topic_phrase(categories)
    if empathy:
        parts.append(empathy)
    else:
        parts.append("Thanks, that gives me enough to work with.")
    if topic_phrase:
        parts.append(topic_phrase)
    if state_code:
        parts.append(f"I have enough to line up the next steps for {state_code}.")
    else:
        parts.append("I have enough to line up the next steps.")
    parts.append("I’ll stop here unless you want to add anything else.")
    return " ".join(parts)


def _default_navigation_actions(next_probe: Optional[dict[str, Any]]) -> list[str]:
    if next_probe is None:
        return ["start_screening", "use_screener", "open_explorer"]
    return ["use_screener", "open_explorer", "open_dashboard"]


def _navigation_action_payload(action_keys: list[str]) -> list[dict[str, Any]]:
    actions: list[dict[str, Any]] = []
    seen: set[str] = set()
    for key in action_keys:
        if key in seen or key not in INTAKE_NAVIGATION_ACTIONS:
            continue
        seen.add(key)
        actions.append(INTAKE_NAVIGATION_ACTIONS[key])
    return actions


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
    low_signal = _is_low_signal_opening(story_text, applied_categories, facts)
    if low_signal:
        low_signal_actions = _navigation_action_payload(["use_screener", "open_explorer"])
        assistant_guidance = None
        if use_llm:
            assistant_guidance = generate_intake_assistant_guidance(
                description=description,
                messages=messages,
                summary="",
                suggested_scope=suggested_scope,
                state_code=inferred_state_code,
                categories=applied_categories,
                facts=facts,
                available_probes=[],
                available_navigation_actions=["use_screener", "open_explorer"],
            )
        return {
            "summary": assistant_guidance.get("summary") if assistant_guidance and assistant_guidance.get("summary") else "",
            "chat_reply": assistant_guidance.get("chat_reply") if assistant_guidance and assistant_guidance.get("chat_reply") else _build_low_signal_chat_reply(),
            "suggested_scope": suggested_scope,
            "applied_state_code": inferred_state_code,
            "suggested_categories": [],
            "structured_facts": _fact_chips(facts),
            "current_facts": facts,
            "prefill_answers": _prefill_answers_from_facts(facts),
            "follow_up_questions": [],
            "next_probe": None,
            "navigation_actions": _navigation_action_payload(
                assistant_guidance.get("navigation_actions") if assistant_guidance else [action["key"] for action in low_signal_actions]
            ),
            "interpretation_method": interpretation.get("method", "heuristic"),
            "llm_used": interpretation.get("llm_used", False) or bool(assistant_guidance),
            "assistant_method": "gemini+grounded" if assistant_guidance else "deterministic",
        }

    should_conclude = _has_enough_context_to_conclude(
        categories=applied_categories,
        facts=facts,
        state_code=inferred_state_code,
        messages=messages,
    )
    queue = [] if should_conclude else _follow_up_queue(applied_categories, facts)
    summary = _build_summary(applied_categories, facts, inferred_state_code)
    provisional_next_probe, provisional_follow_up_questions = _follow_up_payload(queue)
    navigation_action_keys = _default_navigation_actions(provisional_next_probe)
    assistant_guidance = None
    if use_llm:
        assistant_guidance = generate_intake_assistant_guidance(
            description=description,
            messages=messages,
            summary=summary,
            suggested_scope=suggested_scope,
            state_code=inferred_state_code,
            categories=applied_categories,
            facts=facts,
            available_probes=provisional_follow_up_questions,
            available_navigation_actions=navigation_action_keys,
        )

    preferred_probe_key = assistant_guidance.get("next_probe_key") if assistant_guidance else None
    next_probe, follow_up_questions = _follow_up_payload(queue, preferred_key=preferred_probe_key)
    if assistant_guidance and assistant_guidance.get("summary"):
        summary = assistant_guidance["summary"]
    prefill_answers = _prefill_answers_from_facts(facts)
    chat_reply = (
        assistant_guidance.get("chat_reply")
        if assistant_guidance and assistant_guidance.get("chat_reply")
        else (
            _build_conclusion_chat_reply(
                categories=applied_categories,
                facts=facts,
                state_code=inferred_state_code,
            )
            if next_probe is None
            else _build_conversational_chat_reply(
                categories=applied_categories,
                facts=facts,
                next_probe=next_probe,
            )
        )
    )
    navigation_actions = _navigation_action_payload(
        assistant_guidance.get("navigation_actions") if assistant_guidance else navigation_action_keys
    )
    assistant_llm_used = bool(assistant_guidance)

    return {
        "summary": summary,
        "chat_reply": chat_reply,
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
        "navigation_actions": navigation_actions,
        "interpretation_method": interpretation.get("method", "heuristic"),
        "llm_used": interpretation.get("llm_used", False) or assistant_llm_used,
        "assistant_method": "gemini+grounded" if assistant_llm_used else "deterministic",
    }
