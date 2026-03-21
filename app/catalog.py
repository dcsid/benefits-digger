from __future__ import annotations

import hashlib
import html
import json
import re
from typing import Any, Optional

import httpx

from app.seed_data import FEDERAL_SAMPLE_BENEFITS, FEDERAL_SAMPLE_QUESTIONS, STATE_DIRECTORY_SAMPLE


FEDERAL_FEED_URL = "https://www.usa.gov/s3/files/benefit-finder/api/life-event/all_benefits.json"
STATE_DIRECTORY_URL = "https://www.usa.gov/state-social-services"
TAG_RE = re.compile(r"<[^>]+>")
WHITESPACE_RE = re.compile(r"\s+")
STATE_LINK_RE = re.compile(
    r'<a[^>]+href="(?P<href>https?://[^"]+)"[^>]*>(?P<label>[^<]+?)\s*\((?P<code>[A-Z]{2})\)</a>',
    re.IGNORECASE,
)


def strip_html(text: Optional[str]) -> str:
    if not text:
        return ""
    cleaned = TAG_RE.sub(" ", text)
    return WHITESPACE_RE.sub(" ", html.unescape(cleaned)).strip()


def slugify(text: str) -> str:
    slug = re.sub(r"[^a-z0-9]+", "-", text.lower()).strip("-")
    return slug or "item"


def hash_content(content: Any) -> str:
    if not isinstance(content, str):
        content = json.dumps(content, sort_keys=True)
    return hashlib.sha256(content.encode("utf-8")).hexdigest()


def infer_category(text: str) -> str:
    normalized = text.lower()
    if any(keyword in normalized for keyword in ("retirement", "retire")):
        return "retirement"
    if any(keyword in normalized for keyword in ("survivor", "death", "funeral")):
        return "survivor"
    if any(keyword in normalized for keyword in ("disability", "impairment", "illness")):
        return "disability"
    if any(keyword in normalized for keyword in ("veteran", "military", "va ")):
        return "veteran"
    if any(keyword in normalized for keyword in ("health", "medical", "medicare", "medicaid")):
        return "health"
    if any(keyword in normalized for keyword in ("housing", "rental", "home")):
        return "housing"
    if any(keyword in normalized for keyword in ("food", "nutrition", "snap")):
        return "food"
    if any(keyword in normalized for keyword in ("utility", "energy", "internet", "phone")):
        return "utility"
    return "cash"


def infer_sensitivity(question_key: str, input_type: str) -> str:
    normalized = question_key.lower()
    if any(token in normalized for token in ("income", "asset", "resource")):
        return "high"
    if input_type in {"date", "currency", "number"} or any(
        token in normalized for token in ("birth", "death", "disability")
    ):
        return "medium"
    return "low"


def normalize_input_type(source_type: str) -> str:
    mapping = {
        "date": "date",
        "radio": "radio",
        "select": "select",
        "number": "number",
        "currency": "currency",
    }
    return mapping.get(source_type.lower(), "text")


def _flatten_fieldsets(fieldsets: list[dict], bucket: dict[str, dict]) -> None:
    for wrapper in fieldsets:
        fieldset = wrapper.get("fieldset", {})
        criteria_key = fieldset.get("criteriaKey")
        inputs = fieldset.get("inputs", [])
        if criteria_key and inputs:
            input_criteria = inputs[0].get("inputCriteria", {})
            options = []
            for option in input_criteria.get("values", []):
                if "option" in option:
                    options.append(
                        {
                            "label": str(option["option"]),
                            "value": option.get("value", option["option"]),
                        }
                    )
            input_type = normalize_input_type(input_criteria.get("type", "text"))
            bucket[criteria_key] = {
                "key": criteria_key,
                "prompt": fieldset.get("legend") or input_criteria.get("label") or criteria_key.replace("_", " ").title(),
                "hint": fieldset.get("hint") or None,
                "input_type": input_type,
                "sensitivity_level": infer_sensitivity(criteria_key, input_type),
                "options": options or None,
            }

        for child_group in fieldset.get("children", []):
            child_fieldsets = child_group.get("fieldsets", [])
            _flatten_fieldsets(child_fieldsets, bucket)


def normalize_remote_federal_payload(payload_text: str) -> dict[str, Any]:
    payload = json.loads(payload_text)
    data = payload["data"]
    questions_by_key: dict[str, dict] = {}
    for section in data["lifeEventForm"]["sectionsEligibilityCriteria"]:
        _flatten_fieldsets(section["section"]["fieldsets"], questions_by_key)

    normalized_benefits = []
    for item in data["benefits"]:
        benefit = item["benefit"]
        summary = strip_html(benefit.get("summary"))
        title = strip_html(benefit.get("title"))
        normalized_benefits.append(
            {
                "title": title,
                "summary": summary,
                "agency_title": strip_html(benefit.get("agency", {}).get("title")),
                "source_link": benefit.get("SourceLink"),
                "category": infer_category(f"{title} {summary}"),
                "family": slugify(title),
                "eligibility": [
                    {
                        "criteria_key": row["criteriaKey"],
                        "label": strip_html(row["label"]),
                        "acceptable_values": row.get("acceptableValues", []),
                    }
                    for row in benefit.get("eligibility", [])
                ],
                "amount_display": "Amount varies by agency formula or case details.",
            }
        )

    return {
        "questions": list(questions_by_key.values()),
        "benefits": normalized_benefits,
        "content_hash": hash_content(payload_text),
        "content_type": "application/json",
        "raw_excerpt": payload_text[:5000],
    }


def parse_state_directory_html(payload_text: str) -> dict[str, Any]:
    agencies: list[dict[str, str]] = []
    seen_codes: set[str] = set()
    for match in STATE_LINK_RE.finditer(payload_text):
        code = match.group("code").upper()
        if code in seen_codes:
            continue
        name = html.unescape(match.group("label")).strip()
        agencies.append(
            {
                "code": code,
                "name": name,
                "url": match.group("href"),
            }
        )
        seen_codes.add(code)
    agencies.sort(key=lambda item: item["name"])
    return {
        "agencies": agencies,
        "content_hash": hash_content(payload_text),
        "content_type": "text/html",
        "raw_excerpt": payload_text[:5000],
    }


def build_fallback_federal_catalog() -> dict[str, Any]:
    payload = {
        "questions": FEDERAL_SAMPLE_QUESTIONS,
        "benefits": FEDERAL_SAMPLE_BENEFITS,
    }
    return {
        **payload,
        "content_hash": hash_content(payload),
        "content_type": "application/json",
        "raw_excerpt": json.dumps(payload, sort_keys=True)[:5000],
    }


def build_fallback_state_directory() -> dict[str, Any]:
    payload = {"agencies": STATE_DIRECTORY_SAMPLE}
    return {
        **payload,
        "content_hash": hash_content(payload),
        "content_type": "application/json",
        "raw_excerpt": json.dumps(payload, sort_keys=True)[:5000],
    }


def fetch_remote_federal_catalog(timeout_seconds: float) -> dict[str, Any]:
    with httpx.Client(timeout=timeout_seconds, follow_redirects=True) as client:
        response = client.get(FEDERAL_FEED_URL)
        response.raise_for_status()
        return normalize_remote_federal_payload(response.text)


def fetch_remote_state_directory(timeout_seconds: float) -> dict[str, Any]:
    with httpx.Client(timeout=timeout_seconds, follow_redirects=True) as client:
        response = client.get(STATE_DIRECTORY_URL)
        response.raise_for_status()
        return parse_state_directory_html(response.text)
