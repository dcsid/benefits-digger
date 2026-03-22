"""Pair each synthetic user with benefits from the eligibility engine.

Outputs:
  data/synthetic_user_benefit_pairs_v1.csv
  data/synthetic_user_benefit_pairs_v1.json
"""

from __future__ import annotations

import csv
import json
import sys
from collections import Counter
from datetime import datetime, timezone
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))

from sqlalchemy import select  # noqa: E402

from app.db import SessionLocal  # noqa: E402
from app.models import Program  # noqa: E402
from app.services import (  # noqa: E402
    evaluate_program,
    expand_category_filters,
    get_latest_version,
    program_matches_categories,
)

DATA_DIR = ROOT / "data"
USERS_PATH = DATA_DIR / "synthetic_users_v1.json"
CSV_OUT = DATA_DIR / "synthetic_user_benefit_pairs_v1.csv"
JSON_OUT = DATA_DIR / "synthetic_user_benefit_pairs_v1.json"

CSV_COLUMNS = [
    "user_id",
    "user_name",
    "persona_title",
    "scenario_key",
    "program_slug",
    "program_name",
    "program_category",
    "jurisdiction_level",
    "jurisdiction_code",
    "eligibility_status",
    "decision_certainty",
    "matched_reasons",
    "failed_reasons",
    "missing_facts",
]


def load_users() -> list[dict]:
    with open(USERS_PATH, encoding="utf-8") as f:
        return json.load(f)["users"]


def build_answers(user: dict) -> dict:
    """Merge screening answers and inject state_code."""
    answers: dict = {}
    for key, val in (user.get("current_app_answers") or {}).items():
        if val is not None:
            answers[key] = val
    for key, val in (user.get("expanded_answers") or {}).items():
        if val is not None:
            answers[key] = val
    if user.get("selected_state_code"):
        answers["state_code"] = user["selected_state_code"]
    return answers


def get_candidate_programs_for_user(db, user: dict) -> list:
    """Filter active programs by user scope, state, and categories."""
    programs = db.scalars(select(Program).where(Program.status == "active")).all()
    scope = user.get("selected_scope", "both")
    state_code = user.get("selected_state_code")
    categories = {c for c in (user.get("selected_categories") or []) if c and c != "all"}
    expanded = expand_category_filters(categories)

    filtered = []
    for program in programs:
        if scope == "federal" and program.jurisdiction.level != "federal":
            continue
        if scope == "state" and program.jurisdiction.level != "state":
            continue
        if program.jurisdiction.level == "state":
            if not state_code or program.jurisdiction.code != state_code:
                continue
        if expanded and program.kind != "referral":
            if not program_matches_categories(program, expanded):
                continue
        filtered.append(program)
    return filtered


def main() -> None:
    users = load_users()
    print(f"Loaded {len(users)} synthetic users")

    db = SessionLocal()
    try:
        # Collect results grouped by user
        all_users_output: list[dict] = []
        csv_rows: list[dict] = []
        status_counter: Counter = Counter()

        for user in users:
            uid = user["synthetic_user_id"]
            answers = build_answers(user)
            candidates = get_candidate_programs_for_user(db, user)

            benefits: list[dict] = []
            for program in candidates:
                version = get_latest_version(db, program.id)
                if version is None:
                    continue
                evaluation = evaluate_program(db, program, version, answers)
                status = evaluation["eligibility_status"]
                status_counter[status] += 1

                benefit = {
                    "program_slug": evaluation["program_slug"],
                    "program_name": evaluation["program_name"],
                    "program_category": evaluation["category"],
                    "jurisdiction_level": evaluation["jurisdiction"]["level"],
                    "jurisdiction_code": evaluation["jurisdiction"]["code"],
                    "eligibility_status": status,
                    "decision_certainty": evaluation["decision_certainty"],
                    "matched_reasons": evaluation["matched_reasons"],
                    "failed_reasons": evaluation["failed_reasons"],
                    "missing_facts": evaluation["missing_facts"],
                }
                benefits.append(benefit)

                csv_rows.append({
                    "user_id": uid,
                    "user_name": user["full_name"],
                    "persona_title": user.get("persona_title", ""),
                    "scenario_key": user.get("scenario_key", ""),
                    "program_slug": benefit["program_slug"],
                    "program_name": benefit["program_name"],
                    "program_category": benefit["program_category"],
                    "jurisdiction_level": benefit["jurisdiction_level"],
                    "jurisdiction_code": benefit["jurisdiction_code"],
                    "eligibility_status": status,
                    "decision_certainty": benefit["decision_certainty"],
                    "matched_reasons": "; ".join(benefit["matched_reasons"]),
                    "failed_reasons": "; ".join(benefit["failed_reasons"]),
                    "missing_facts": "; ".join(benefit["missing_facts"]),
                })

            all_users_output.append({
                "user_id": uid,
                "user_name": user["full_name"],
                "persona_title": user.get("persona_title", ""),
                "scenario_key": user.get("scenario_key", ""),
                "benefits": benefits,
            })
            print(f"  {uid}: {len(benefits)} programs evaluated")

    finally:
        db.close()

    # Write CSV
    with open(CSV_OUT, "w", newline="", encoding="utf-8") as f:
        writer = csv.DictWriter(f, fieldnames=CSV_COLUMNS)
        writer.writeheader()
        writer.writerows(csv_rows)

    # Write JSON
    json_output = {
        "meta": {
            "generated_at": datetime.now(timezone.utc).isoformat(),
            "source_file": "synthetic_users_v1.json",
            "user_count": len(users),
            "total_evaluations": len(csv_rows),
            "status_breakdown": dict(status_counter),
        },
        "users": all_users_output,
    }
    with open(JSON_OUT, "w", encoding="utf-8") as f:
        json.dump(json_output, f, indent=2, ensure_ascii=False)

    # Summary
    print(f"\nUsers processed: {len(users)}")
    print(f"Total evaluations: {len(csv_rows)}")
    for status, count in status_counter.most_common():
        print(f"  {status}: {count}")
    print(f"\nWrote {CSV_OUT}")
    print(f"Wrote {JSON_OUT}")


if __name__ == "__main__":
    main()
