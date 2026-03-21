from __future__ import annotations

from datetime import date, datetime
from typing import Any, Optional


COMPARATORS = (">=", "<=", ">", "<")


def parse_date(value: Any) -> Optional[date]:
    if isinstance(value, date) and not isinstance(value, datetime):
        return value
    if isinstance(value, datetime):
        return value.date()
    if not isinstance(value, str):
        return None
    normalized = value.strip()
    for fmt in ("%Y-%m-%d", "%m-%d-%Y", "%m/%d/%Y", "%Y/%m/%d"):
        try:
            return datetime.strptime(normalized, fmt).date()
        except ValueError:
            continue
    return None


def parse_number(value: Any) -> Optional[float]:
    if isinstance(value, (int, float)):
        return float(value)
    if not isinstance(value, str):
        return None
    try:
        return float(value.replace(",", "").strip())
    except ValueError:
        return None


def normalize_text(value: Any) -> str:
    if value is None:
        return ""
    return str(value).strip().lower()


def compare_scalar(answer: Any, expected: Any) -> bool:
    if isinstance(expected, bool):
        return bool(answer) is expected

    if isinstance(expected, (int, float)):
        parsed = parse_number(answer)
        return parsed is not None and parsed == float(expected)

    if not isinstance(expected, str):
        return answer == expected

    token = expected.strip()
    for comparator in COMPARATORS:
        if token.startswith(comparator):
            threshold = token[len(comparator) :].strip()
            answer_date = parse_date(answer)
            threshold_date = parse_date(threshold)
            if answer_date and threshold_date:
                if comparator == ">=":
                    return answer_date >= threshold_date
                if comparator == "<=":
                    return answer_date <= threshold_date
                if comparator == ">":
                    return answer_date > threshold_date
                return answer_date < threshold_date

            answer_number = parse_number(answer)
            threshold_number = parse_number(threshold)
            if answer_number is not None and threshold_number is not None:
                if comparator == ">=":
                    return answer_number >= threshold_number
                if comparator == "<=":
                    return answer_number <= threshold_number
                if comparator == ">":
                    return answer_number > threshold_number
                return answer_number < threshold_number

    return normalize_text(answer) == normalize_text(token)


def evaluate_matches_any(answer: Any, expected_values: Optional[list[Any]]) -> str:
    if answer in (None, ""):
        return "unknown"
    for expected in expected_values or []:
        if compare_scalar(answer, expected):
            return "pass"
    return "fail"


def score_status(outcomes: list[str]) -> str:
    if not outcomes:
        return "unclear"
    if "fail" in outcomes:
        return "likely_ineligible"
    if all(outcome == "pass" for outcome in outcomes):
        return "likely_eligible"
    if "pass" in outcomes or "unknown" in outcomes:
        return "possibly_eligible"
    return "unclear"
