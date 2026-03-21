from __future__ import annotations

import json
import logging
import re
from typing import Any, Optional

from sqlalchemy import select
from sqlalchemy.orm import Session

from app.config import get_settings
from app.models import Jurisdiction, Program
from app.services import (
    CATEGORY_LABELS,
    expand_category_filters,
    get_official_application_url,
    get_program_sources,
    program_matches_categories,
)


logger = logging.getLogger(__name__)
settings = get_settings()

STOPWORDS = {
    "a",
    "an",
    "and",
    "are",
    "as",
    "at",
    "be",
    "because",
    "for",
    "from",
    "help",
    "i",
    "if",
    "in",
    "into",
    "is",
    "it",
    "just",
    "me",
    "my",
    "need",
    "of",
    "on",
    "or",
    "that",
    "the",
    "their",
    "them",
    "they",
    "to",
    "with",
}

CATEGORY_KEYWORDS = {
    "children_families": [
        "baby",
        "child",
        "children",
        "dependent",
        "family",
        "parent",
        "pregnant",
        "newborn",
        "child care",
    ],
    "death": [
        "death",
        "died",
        "died of covid",
        "funeral",
        "survivor",
        "passed away",
        "widow",
        "widower",
        "burial",
    ],
    "disabilities": [
        "disability",
        "disabled",
        "illness",
        "impairment",
        "cannot work",
        "can't work",
        "unable to work",
        "ssdi",
        "ssi",
    ],
    "disasters": [
        "disaster",
        "flood",
        "fire",
        "hurricane",
        "earthquake",
        "emergency",
        "covid",
    ],
    "education": [
        "college",
        "education",
        "school",
        "student",
        "training",
        "tuition",
    ],
    "food": [
        "food",
        "groceries",
        "hungry",
        "meal",
        "nutrition",
        "snap",
        "wic",
    ],
    "health": [
        "doctor",
        "health",
        "healthcare",
        "hospital",
        "insurance",
        "medical",
        "medicaid",
        "medicare",
        "medicine",
        "therapy",
    ],
    "housing_utilities": [
        "electric",
        "eviction",
        "gas bill",
        "heating",
        "home",
        "homeless",
        "housing",
        "internet",
        "phone",
        "rent",
        "shelter",
        "utility",
        "utilities",
        "voucher",
        "water bill",
    ],
    "jobs_unemployment": [
        "employment",
        "job",
        "laid off",
        "lost my job",
        "lost work",
        "paycheck",
        "unemployment",
        "work search",
    ],
    "military_veterans": [
        "active duty",
        "military",
        "service-connected",
        "served",
        "veteran",
        "va",
    ],
    "retirement_seniors": [
        "retire",
        "retirement",
        "senior",
        "social security",
        "turning 62",
        "turning 65",
        "older adult",
    ],
    "welfare_cash_assistance": [
        "assistance",
        "basic needs",
        "cash",
        "income support",
        "money",
        "tanf",
        "temporary assistance",
    ],
}

CATEGORY_SEARCH_TERMS = {
    "children_families": ["family", "child", "children"],
    "death": ["death", "survivor", "funeral"],
    "disabilities": ["disability", "disabled", "ssdi", "ssi"],
    "disasters": ["disaster", "emergency", "covid"],
    "education": ["education", "student", "school"],
    "food": ["food", "nutrition", "snap", "wic"],
    "health": ["health", "medical", "medicaid", "medicare"],
    "housing_utilities": ["housing", "utility", "rent", "voucher"],
    "jobs_unemployment": ["job", "employment", "unemployment"],
    "military_veterans": ["military", "veteran", "va"],
    "retirement_seniors": ["retirement", "social security", "senior"],
    "welfare_cash_assistance": ["cash", "assistance", "support"],
}


def _normalize_text(value: Any) -> str:
    if value is None:
        return ""
    return re.sub(r"\s+", " ", str(value).strip().lower())


def _tokenize(text: str) -> list[str]:
    return [
        token
        for token in re.findall(r"[a-z0-9']+", _normalize_text(text))
        if len(token) > 2 and token not in STOPWORDS
    ]


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


def _available_states(db: Session) -> list[Jurisdiction]:
    return db.scalars(
        select(Jurisdiction).where(Jurisdiction.level == "state").order_by(Jurisdiction.name.asc())
    ).all()


def _extract_state_code(db: Session, description: str) -> Optional[str]:
    normalized = _normalize_text(description)
    if not normalized:
        return None
    states = sorted(_available_states(db), key=lambda row: len(row.name), reverse=True)
    for state in states:
        state_name = _normalize_text(state.name)
        if state_name and re.search(rf"\b{re.escape(state_name)}\b", normalized):
            return state.code
    return None


def _infer_categories(description: str) -> tuple[list[str], list[str]]:
    normalized = _normalize_text(description)
    matched_categories: list[str] = []
    matched_keywords: list[str] = []
    for category, keywords in CATEGORY_KEYWORDS.items():
        hits = [keyword for keyword in keywords if keyword in normalized]
        if hits:
            matched_categories.append(category)
            matched_keywords.extend(hits[:2])
    return _dedupe_preserve_order(matched_categories), _dedupe_preserve_order(matched_keywords)


def _build_search_terms(query: str, description: str, categories: list[str], matched_keywords: list[str]) -> list[str]:
    terms: list[str] = []
    if query.strip():
        terms.append(query.strip())
    terms.extend(matched_keywords)
    for category in categories:
        terms.extend(CATEGORY_SEARCH_TERMS.get(category, []))
    terms.extend(_tokenize(description)[:8])
    return _dedupe_preserve_order(terms)[:12]


def _try_llm_interpretation(
    db: Session,
    description: str,
    *,
    scope: str,
    state_code: Optional[str],
    categories: list[str],
) -> Optional[dict[str, Any]]:
    if not settings.gemini_api_key or not description.strip():
        return None

    try:
        from google import genai
    except Exception as exc:  # pragma: no cover - import guard
        logger.warning("Gemini library unavailable for explorer interpretation: %s", exc)
        return None

    available_states = [row.code for row in _available_states(db)]
    valid_categories = list(CATEGORY_LABELS.keys())
    prompt = f"""You are helping an official government benefits catalog search.

Convert the user's description into a compact JSON object with these exact keys:
- "summary": one-sentence plain-English summary
- "state_code": one of {json.dumps(available_states)} or null
- "scope": one of ["federal", "state", "both"] or null
- "categories": array containing zero or more of {json.dumps(valid_categories)}
- "search_terms": array of up to 8 short search terms

Rules:
- Do not invent programs or benefits.
- Keep categories broad and grounded in the user's actual need.
- If the user mentions a state, extract it.
- If the explicit product filters already specify a scope/state/categories, you may reinforce them but do not contradict them.
- Return ONLY JSON.

Current explicit filters:
- scope: {scope}
- state_code: {state_code or "null"}
- categories: {json.dumps(categories)}

User description:
{description}
"""

    try:
        client = genai.Client(api_key=settings.gemini_api_key)
        response = client.models.generate_content(
            model="gemini-2.5-flash",
            contents=prompt,
            config={
                "response_mime_type": "application/json",
                "temperature": 0.1,
            },
        )
        payload = json.loads(response.text.strip())
        if not isinstance(payload, dict):
            return None
        llm_categories = [
            category for category in payload.get("categories", [])
            if category in CATEGORY_LABELS
        ]
        llm_terms = [term for term in payload.get("search_terms", []) if isinstance(term, str)]
        llm_state_code = payload.get("state_code")
        if llm_state_code and llm_state_code not in available_states:
            llm_state_code = None
        llm_scope = payload.get("scope")
        if llm_scope not in {"federal", "state", "both", None}:
            llm_scope = None
        return {
            "summary": payload.get("summary"),
            "state_code": llm_state_code,
            "scope": llm_scope,
            "categories": llm_categories,
            "search_terms": llm_terms,
        }
    except Exception as exc:  # pragma: no cover - external API fallback
        logger.warning("Gemini explorer interpretation failed, falling back to heuristics: %s", exc)
        return None


def _merge_interpretations(
    heuristic: dict[str, Any],
    llm_payload: Optional[dict[str, Any]],
) -> dict[str, Any]:
    if not llm_payload:
        heuristic["method"] = "heuristic"
        heuristic["llm_used"] = False
        return heuristic

    merged_categories = _dedupe_preserve_order(
        list(heuristic["applied_category_keys"]) + list(llm_payload.get("categories", []))
    )
    merged_terms = _dedupe_preserve_order(
        list(heuristic["search_terms"]) + list(llm_payload.get("search_terms", []))
    )[:12]

    state_code = heuristic["applied_state_code"] or llm_payload.get("state_code")
    scope = heuristic["applied_scope"] or llm_payload.get("scope") or "both"
    summary = llm_payload.get("summary") or heuristic["summary"]

    return {
        **heuristic,
        "method": "gemini+heuristic",
        "llm_used": True,
        "summary": summary,
        "applied_scope": scope,
        "applied_state_code": state_code,
        "applied_category_keys": merged_categories,
        "applied_categories": [
            {"key": category, "label": CATEGORY_LABELS.get(category, category.replace("_", " ").title())}
            for category in merged_categories
        ],
        "search_terms": merged_terms,
    }


def interpret_hybrid_explorer_request(
    db: Session,
    *,
    description: str,
    query: str,
    scope: str,
    state_code: Optional[str],
    categories: Optional[list[str]] = None,
    use_llm: bool = True,
) -> dict[str, Any]:
    explicit_categories = _dedupe_preserve_order(categories or [])
    inferred_categories, matched_keywords = _infer_categories(description)
    inferred_state_code = state_code.upper() if state_code else _extract_state_code(db, description)
    applied_categories = _dedupe_preserve_order(explicit_categories + inferred_categories)
    search_terms = _build_search_terms(query, description, applied_categories, matched_keywords)

    summary_parts: list[str] = []
    if applied_categories:
        summary_parts.append(
            "categories " + ", ".join(CATEGORY_LABELS.get(cat, cat.replace("_", " ").title()) for cat in applied_categories[:3])
        )
    if inferred_state_code:
        summary_parts.append(f"state {inferred_state_code}")
    if query.strip():
        summary_parts.append(f'exact search "{query.strip()}"')
    if not summary_parts:
        summary = "Browsing the official program catalog."
    else:
        summary = "Interpreted your need as " + ", ".join(summary_parts) + "."

    heuristic = {
        "method": "heuristic",
        "llm_used": False,
        "original_description": description,
        "original_query": query,
        "summary": summary,
        "applied_scope": scope or "both",
        "applied_state_code": inferred_state_code,
        "applied_category_keys": applied_categories,
        "applied_categories": [
            {"key": category, "label": CATEGORY_LABELS.get(category, category.replace("_", " ").title())}
            for category in applied_categories
        ],
        "matched_keywords": matched_keywords,
        "search_terms": search_terms,
    }

    llm_payload = None
    if use_llm and description.strip():
        llm_payload = _try_llm_interpretation(
            db,
            description,
            scope=scope,
            state_code=inferred_state_code,
            categories=applied_categories,
        )

    return _merge_interpretations(heuristic, llm_payload)


def _candidate_programs(
    db: Session,
    *,
    scope: str,
    state_code: Optional[str],
    categories: list[str],
) -> list[Program]:
    programs = db.scalars(select(Program).where(Program.status == "active").order_by(Program.name.asc())).all()
    expanded_categories = expand_category_filters(set(categories))
    filtered: list[Program] = []
    for program in programs:
        if scope == "federal" and program.jurisdiction.level != "federal":
            continue
        if scope == "state" and program.jurisdiction.level != "state":
            continue
        if state_code and program.jurisdiction.level == "state" and program.jurisdiction.code != state_code:
            continue
        if expanded_categories and program.kind != "referral" and not program_matches_categories(program, expanded_categories):
            continue
        filtered.append(program)
    return filtered


def _score_program(program: Program, interpretation: dict[str, Any], query: str) -> tuple[int, list[str]]:
    haystack = " ".join(
        [
            program.name.lower(),
            (program.summary or "").lower(),
            (program.category or "").lower(),
            (program.family or "").lower(),
            (program.agency.name.lower() if program.agency else ""),
            program.jurisdiction.name.lower(),
        ]
    )
    score = 0
    reasons: list[str] = []

    query_lower = _normalize_text(query)
    if query_lower:
        if query_lower in program.name.lower():
            score += 90
            reasons.append(f'Matches exact search "{query.strip()}".')
        elif query_lower in haystack:
            score += 55
            reasons.append(f'Appears in the catalog details for "{query.strip()}".')

    matched_terms: list[str] = []
    for term in interpretation.get("search_terms", []):
        term_lower = _normalize_text(term)
        if len(term_lower) < 3:
            continue
        if term_lower in program.name.lower():
            score += 18
            matched_terms.append(term)
        elif term_lower in haystack:
            score += 8
            matched_terms.append(term)

    if matched_terms:
        reasons.append("Matches your need description: " + ", ".join(_dedupe_preserve_order(matched_terms)[:4]) + ".")

    category_keys = [item["key"] for item in interpretation.get("applied_categories", [])]
    expanded_categories = expand_category_filters(set(category_keys))
    if expanded_categories and program.kind != "referral" and program_matches_categories(program, expanded_categories):
        score += 35
        label = CATEGORY_LABELS.get(category_keys[0], category_keys[0].replace("_", " ").title()) if category_keys else "selected need"
        reasons.append(f"Matches inferred need area: {label}.")

    state_code = interpretation.get("applied_state_code")
    if state_code and program.jurisdiction.level == "state" and program.jurisdiction.code == state_code:
        score += 24
        reasons.append(f"Applies in {program.jurisdiction.name}.")
    elif program.jurisdiction.level == "federal":
        score += 4

    if program.kind == "referral" and state_code and program.jurisdiction.code == state_code:
        score += 14
        reasons.append("Useful as the official state starting point.")

    return score, _dedupe_preserve_order(reasons)


def hybrid_explorer_search(
    db: Session,
    *,
    query: str = "",
    description: str = "",
    scope: str = "both",
    state_code: Optional[str] = None,
    categories: Optional[list[str]] = None,
    limit: int = 20,
    use_llm: bool = True,
) -> dict[str, Any]:
    interpretation = interpret_hybrid_explorer_request(
        db,
        description=description,
        query=query,
        scope=scope,
        state_code=state_code.upper() if state_code else None,
        categories=categories,
        use_llm=use_llm,
    )

    candidate_programs = _candidate_programs(
        db,
        scope=interpretation["applied_scope"],
        state_code=interpretation["applied_state_code"],
        categories=interpretation["applied_category_keys"],
    )

    scored_programs: list[tuple[int, Program, list[str]]] = []
    for program in candidate_programs:
        score, reasons = _score_program(program, interpretation, query)
        if query.strip() or description.strip():
            if score <= 0:
                continue
        scored_programs.append((score, program, reasons))

    scored_programs.sort(key=lambda item: (item[0], item[1].name.lower()), reverse=True)

    payload = []
    for score, program, reasons in scored_programs[:limit]:
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
                "match_reasons": reasons,
                "search_score": score,
            }
        )

    return {
        "mode": "hybrid",
        "interpretation": interpretation,
        "programs": payload,
    }
