"""Run each synthetic user through the screening API and evaluate:

Level 1 — Are the generated questions relevant to the user's profile?
Level 2 — Do the resulting benefits match the pre-computed pairs?

Uses FastAPI TestClient (in-process) and Gemini as the LLM judge.

Outputs:
  data/screening_evaluation_v1.json
"""

from __future__ import annotations

import json
import os
import sys
import time
from datetime import datetime, timezone
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))

# Prevent remote catalog sync during evaluation
os.environ.setdefault("BENEFITS_DIGGER_AUTO_SYNC_REMOTE", "false")

from fastapi.testclient import TestClient  # noqa: E402

from app.main import app  # noqa: E402
from app.config import get_settings  # noqa: E402

def _default_answer(question: dict) -> object:
    """Return a safe default for questions we can't answer from user data."""
    input_type = question.get("input_type", "")
    options = question.get("options")
    if input_type == "radio":
        return "No"
    if input_type == "select" and options:
        return options[0]["value"]
    if input_type == "date":
        return "1980-01-01"
    if input_type in ("number", "currency"):
        return "0"
    return "No"


DATA_DIR = ROOT / "data"
USERS_PATH = DATA_DIR / "synthetic_users_v1.json"
PAIRS_PATH = DATA_DIR / "synthetic_user_benefit_pairs_v1.json"
EVAL_OUT = DATA_DIR / "screening_evaluation_v1.json"

API = "/api/v1"


def load_users() -> list[dict]:
    with open(USERS_PATH, encoding="utf-8") as f:
        return json.load(f)["users"]


def load_pairs() -> dict[str, list[dict]]:
    """Return paired benefits keyed by user_id."""
    with open(PAIRS_PATH, encoding="utf-8") as f:
        data = json.load(f)
    return {u["user_id"]: u["benefits"] for u in data["users"]}


def build_answer_lookup(user: dict) -> dict[str, object]:
    """Build a flat lookup from question key to answer value."""
    lookup: dict[str, object] = {}
    for key, val in (user.get("current_app_answers") or {}).items():
        if val is not None:
            lookup[key] = val
    for key, val in (user.get("expanded_answers") or {}).items():
        if val is not None:
            lookup[key] = val
    # state_code is answered via the special key
    if user.get("selected_state_code"):
        lookup["state_code"] = user["selected_state_code"]
    return lookup


# ---------------------------------------------------------------------------
# Level 1: LLM relevance judge
# ---------------------------------------------------------------------------

def judge_question_relevance(
    gemini_client,
    user: dict,
    questions_asked: list[dict],
) -> dict:
    """Ask Gemini to judge whether each question is relevant to the user."""
    q_list = "\n".join(
        f"  {i+1}. key={q['key']}  prompt=\"{q['prompt']}\"  (answer_source={q.get('answer_source', 'unknown')})"
        for i, q in enumerate(questions_asked)
    )

    prompt = f"""You are evaluating a benefits screening tool. A user with the following profile went through a screening session and was asked a series of questions.

USER PROFILE:
- Background: {user.get('background_summary', 'N/A')}
- Scenario: {user.get('scenario_key', 'N/A')}
- Selected benefit categories: {', '.join(user.get('selected_categories', []))}
- Scope: {user.get('selected_scope', 'N/A')}
- State: {user.get('selected_state_code', 'N/A')}

QUESTIONS ASKED (in order):
{q_list}

For each question, determine if it is RELEVANT to this user's profile and needs. A question is relevant if:
- It relates to the user's selected benefit categories
- It helps determine eligibility for programs matching the user's scenario
- It gathers information pertinent to the user's demographic or economic situation

A question is IRRELEVANT if:
- It asks about topics completely unrelated to the user's needs (e.g., asking about military service for a student with no military background)
- It gathers information that would not help narrow down benefits for this user's scenario

Return a JSON object with this exact structure:
{{
  "overall_score": <integer 0-100, percentage of questions that are relevant>,
  "questions": [
    {{
      "key": "<question_key>",
      "relevant": <true or false>,
      "reason": "<brief explanation, 1 sentence>"
    }}
  ]
}}"""

    try:
        response = gemini_client.models.generate_content(
            model="gemini-2.5-flash",
            contents=prompt,
            config={
                "response_mime_type": "application/json",
                "temperature": 0.1,
            },
        )
        return json.loads(response.text.strip())
    except Exception as exc:
        print(f"    LLM judge failed: {exc}")
        return {
            "overall_score": -1,
            "questions": [],
            "error": str(exc),
        }


# ---------------------------------------------------------------------------
# Level 2: Benefit comparison
# ---------------------------------------------------------------------------

def compare_benefits(api_results: list[dict], paired: list[dict]) -> dict:
    """Compare API results against pre-computed pairs by program_slug."""
    api_by_slug = {r["program_slug"]: r for r in api_results}
    pair_by_slug = {p["program_slug"]: p for p in paired}

    all_slugs = set(api_by_slug) | set(pair_by_slug)
    matches = 0
    status_mismatches = []
    missing_from_api = []
    extra_in_api = []

    for slug in all_slugs:
        in_api = slug in api_by_slug
        in_pair = slug in pair_by_slug

        if in_api and in_pair:
            api_status = api_by_slug[slug]["eligibility_status"]
            pair_status = pair_by_slug[slug]["eligibility_status"]
            if api_status == pair_status:
                matches += 1
            else:
                status_mismatches.append({
                    "program_slug": slug,
                    "api_status": api_status,
                    "paired_status": pair_status,
                })
        elif in_pair and not in_api:
            missing_from_api.append({
                "program_slug": slug,
                "paired_status": pair_by_slug[slug]["eligibility_status"],
            })
        else:
            extra_in_api.append({
                "program_slug": slug,
                "api_status": api_by_slug[slug]["eligibility_status"],
            })

    total_paired = len(pair_by_slug)
    return {
        "api_results_count": len(api_by_slug),
        "paired_count": total_paired,
        "matches": matches,
        "status_mismatches": status_mismatches,
        "missing_from_api": missing_from_api,
        "extra_in_api": extra_in_api,
        "match_rate": round(matches / total_paired, 3) if total_paired else 1.0,
    }


# ---------------------------------------------------------------------------
# Main
# ---------------------------------------------------------------------------

def main() -> None:
    users = load_users()
    pairs = load_pairs()
    print(f"Loaded {len(users)} synthetic users, {len(pairs)} paired result sets")

    # Init Gemini
    settings = get_settings()
    gemini_client = None
    if settings.gemini_api_key:
        from google import genai
        gemini_client = genai.Client(api_key=settings.gemini_api_key)
        print("Gemini LLM judge initialized")
    else:
        print("WARNING: No Gemini API key — Level 1 (question relevance) will be skipped")

    client = TestClient(app)
    user_reports: list[dict] = []
    relevance_scores: list[int] = []
    match_rates: list[float] = []

    for user in users:
        uid = user["synthetic_user_id"]
        print(f"\n{'='*60}")
        print(f"Processing {uid}: {user.get('persona_title', '')} ({user.get('scenario_key', '')})")

        answer_lookup = build_answer_lookup(user)

        # --- Step 1: Create session ---
        payload = {
            "scope": user.get("selected_scope", "both"),
            "state_code": user.get("selected_state_code"),
            "categories": user.get("selected_categories", []),
            "breadth_value": user.get("breadth_value", 0.5),
            "depth_value": user.get("depth_value", 0.5),
        }
        resp = client.post(f"{API}/sessions", json=payload)
        if resp.status_code != 200:
            print(f"  ERROR creating session: {resp.status_code} {resp.text}")
            user_reports.append({
                "user_id": uid,
                "error": f"Session creation failed: {resp.status_code}",
            })
            continue

        envelope = resp.json()
        session_id = envelope["session_id"]
        next_q = envelope.get("next_question")

        # --- Step 2: Walk the full question loop ---
        # Answer each question as it's asked. For questions we have a real
        # answer for, use it.  For questions not in the synthetic user's
        # data, provide a safe default ("No" for radio, first option for
        # select, etc.) so the loop continues and we capture the full
        # question sequence for Level 1 evaluation.
        questions_asked: list[dict] = []
        seen_keys: set[str] = set()
        max_iterations = 30  # safety limit

        while next_q and max_iterations > 0:
            max_iterations -= 1
            q_key = next_q["key"]

            if q_key in seen_keys:
                break
            seen_keys.add(q_key)

            real_answer = answer_lookup.get(q_key)
            if real_answer is not None:
                answer_to_submit = real_answer
                answer_source = "user"
            else:
                answer_to_submit = _default_answer(next_q)
                answer_source = "default"

            questions_asked.append({
                "key": q_key,
                "prompt": next_q["prompt"],
                "input_type": next_q.get("input_type", ""),
                "answer_given": real_answer if real_answer is not None else "(default)",
                "answer_source": answer_source,
            })

            ans_resp = client.post(
                f"{API}/sessions/{session_id}/answers",
                json={"answers": {q_key: answer_to_submit}},
            )
            if ans_resp.status_code != 200:
                break
            next_q = ans_resp.json().get("next_question")

        # Bulk-submit any remaining known answers not yet asked
        remaining = {k: v for k, v in answer_lookup.items() if k not in seen_keys}
        if remaining:
            client.post(
                f"{API}/sessions/{session_id}/answers",
                json={"answers": remaining},
            )

        user_count = sum(1 for q in questions_asked if q["answer_source"] == "user")
        default_count = sum(1 for q in questions_asked if q["answer_source"] == "default")
        print(f"  Questions asked: {len(questions_asked)} ({user_count} from user data, {default_count} defaulted)")
        for qa in questions_asked:
            tag = "USER" if qa["answer_source"] == "user" else "DFLT"
            print(f"    [{tag}] {qa['key']}: {qa['prompt'][:60]}...")

        # --- Step 3: Get results ---
        results_resp = client.get(f"{API}/sessions/{session_id}/results")
        if results_resp.status_code != 200:
            print(f"  ERROR getting results: {results_resp.status_code}")
            user_reports.append({
                "user_id": uid,
                "error": f"Results failed: {results_resp.status_code}",
            })
            continue

        results = results_resp.json()
        api_benefits = results.get("federal_results", []) + results.get("state_results", [])

        # --- Step 4: Level 1 — LLM judge ---
        llm_judgment = None
        if gemini_client and questions_asked:
            llm_judgment = judge_question_relevance(gemini_client, user, questions_asked)
            score = llm_judgment.get("overall_score", -1)
            if score >= 0:
                relevance_scores.append(score)
                print(f"  Level 1 relevance score: {score}/100")
            time.sleep(0.5)  # gentle rate limiting

        # --- Step 5: Level 2 — Compare benefits ---
        paired_benefits = pairs.get(uid, [])
        level_2 = compare_benefits(api_benefits, paired_benefits)
        match_rates.append(level_2["match_rate"])
        print(f"  Level 2: {level_2['matches']}/{level_2['paired_count']} exact matches "
              f"({level_2['match_rate']*100:.1f}%), "
              f"{len(level_2['status_mismatches'])} mismatches, "
              f"{len(level_2['missing_from_api'])} missing, "
              f"{len(level_2['extra_in_api'])} extra")

        user_reports.append({
            "user_id": uid,
            "user_name": user["full_name"],
            "persona_title": user.get("persona_title", ""),
            "scenario_key": user.get("scenario_key", ""),
            "background_summary": user.get("background_summary", ""),
            "level_1": {
                "questions_asked": questions_asked,
                "llm_judgment": llm_judgment,
            },
            "level_2": level_2,
        })

    # --- Write report ---
    avg_relevance = round(sum(relevance_scores) / len(relevance_scores), 1) if relevance_scores else None
    avg_match_rate = round(sum(match_rates) / len(match_rates), 3) if match_rates else None

    summary = {
        "level_1": {
            "avg_relevance_score": avg_relevance,
            "users_evaluated": len(relevance_scores),
            "users_above_70": sum(1 for s in relevance_scores if s >= 70),
            "users_below_50": sum(1 for s in relevance_scores if s < 50),
        },
        "level_2": {
            "avg_match_rate": avg_match_rate,
            "perfect_matches": sum(1 for r in match_rates if r == 1.0),
            "users_evaluated": len(match_rates),
        },
    }

    report = {
        "meta": {
            "generated_at": datetime.now(timezone.utc).isoformat(),
            "user_count": len(users),
        },
        "summary": summary,
        "users": user_reports,
    }

    with open(EVAL_OUT, "w", encoding="utf-8") as f:
        json.dump(report, f, indent=2, ensure_ascii=False)

    print(f"\n{'='*60}")
    print("EVALUATION COMPLETE")
    print(f"{'='*60}")
    print(f"Users processed: {len(user_reports)}")
    if avg_relevance is not None:
        print(f"\nLevel 1 (Question Relevance):")
        print(f"  Average score: {avg_relevance}/100")
        print(f"  Users >= 70: {summary['level_1']['users_above_70']}/{len(relevance_scores)}")
        print(f"  Users < 50:  {summary['level_1']['users_below_50']}/{len(relevance_scores)}")
    if avg_match_rate is not None:
        print(f"\nLevel 2 (Benefit Accuracy):")
        print(f"  Average match rate: {avg_match_rate*100:.1f}%")
        print(f"  Perfect matches: {summary['level_2']['perfect_matches']}/{len(match_rates)}")
    print(f"\nWrote {EVAL_OUT}")


if __name__ == "__main__":
    main()
