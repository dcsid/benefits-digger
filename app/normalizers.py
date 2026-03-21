"""Answer normalizers for depth-dependent question variants.

Each normalizer converts a detailed answer (e.g. a dollar amount) into the
canonical format that eligibility rules already expect (e.g. "Yes" / "No").
Normalization happens at answer-write time so rules never need to change.
"""

from __future__ import annotations

from typing import Any, Callable, Optional

# 2024 Federal Poverty Level for a single-person household (48 contiguous states).
FPL_SINGLE_2024 = 15_060


def _parse_number(value: Any) -> Optional[float]:
    if isinstance(value, (int, float)):
        return float(value)
    if isinstance(value, str):
        cleaned = value.replace(",", "").replace("$", "").strip()
        try:
            return float(cleaned)
        except (ValueError, TypeError):
            return None
    return None


def _identity(value: Any, question_key: str) -> Any:
    return value


def _yes_if_below_fpl(value: Any, question_key: str) -> str:
    num = _parse_number(value)
    if num is not None and num < FPL_SINGLE_2024:
        return "Yes"
    return "No"


def _yes_if_gte_12(value: Any, question_key: str) -> str:
    num = _parse_number(value)
    if num is not None and num >= 12:
        return "Yes"
    return "No"


def _yes_if_any_selected(value: Any, question_key: str) -> str:
    if isinstance(value, list):
        meaningful = [v for v in value if v != "none"]
        return "Yes" if meaningful else "No"
    if isinstance(value, str) and value.strip() and value.strip() != "none":
        return "Yes"
    return "No"


NormalizerFunc = Callable[[Any, str], Any]

NORMALIZER_REGISTRY: dict[str, NormalizerFunc] = {
    "identity": _identity,
    "yes_if_below_fpl": _yes_if_below_fpl,
    "yes_if_gte_12": _yes_if_gte_12,
    "yes_if_any_selected": _yes_if_any_selected,
}


def normalize_answer(
    value: Any,
    question_key: str,
    normalizer_key: Optional[str],
) -> Any:
    if not normalizer_key or normalizer_key == "identity":
        return value
    func = NORMALIZER_REGISTRY.get(normalizer_key)
    if func is None:
        return value
    return func(value, question_key)
