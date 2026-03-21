import os
import sys
from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))

from app.rules import evaluate_matches_any


def test_evaluate_matches_any_handles_dates_and_unknowns() -> None:
    assert evaluate_matches_any("2021-05-21", [">=2020-05-20"]) == "pass"
    assert evaluate_matches_any("2020-05-19", [">=2020-05-20"]) == "fail"
    assert evaluate_matches_any(None, [">=2020-05-20"]) == "unknown"

