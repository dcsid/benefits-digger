import os
import sys
from datetime import datetime
from pathlib import Path

from fastapi.testclient import TestClient
from sqlalchemy import select


ROOT = Path(__file__).resolve().parents[1]
TEST_DB = ROOT / "test_benefits_digger.db"
if TEST_DB.exists():
    TEST_DB.unlink()

os.environ["BENEFITS_DIGGER_DATABASE_URL"] = f"sqlite:///{TEST_DB.as_posix()}"
os.environ["BENEFITS_DIGGER_AUTO_SYNC_REMOTE"] = "false"
sys.path.insert(0, str(ROOT))

from app.main import app
from app.db import SessionLocal
from app.models import Agency, AmountRule, EligibilityRule, Program, ProgramVersion, Question, Jurisdiction


def seed_state_program_with_redundant_residency_rule() -> None:
    with SessionLocal() as db:
        california = db.scalar(select(Jurisdiction).where(Jurisdiction.code == "CA", Jurisdiction.level == "state"))
        assert california is not None

        agency = db.scalar(
            select(Agency).where(
                Agency.jurisdiction_id == california.id,
                Agency.name == "California Test Benefits Agency",
            )
        )
        if agency is None:
            agency = Agency(
                jurisdiction_id=california.id,
                name="California Test Benefits Agency",
                homepage_url="https://www.ca.gov/",
            )
            db.add(agency)
            db.flush()

        redundant_questions = [
            (
                "ca_resident",
                "Are you a resident of California?",
                [
                    {"label": "Yes", "value": "Yes"},
                    {"label": "No", "value": "No"},
                ],
                500.0,
            ),
            (
                "ca_residency_status",
                "What is your California residency status?",
                [
                    {"label": "Resident", "value": "resident"},
                    {"label": "Non-resident", "value": "non_resident"},
                ],
                490.0,
            ),
            (
                "ca_currently_live",
                "Do you currently live in California?",
                [
                    {"label": "Yes", "value": "Yes"},
                    {"label": "No", "value": "No"},
                ],
                480.0,
            ),
        ]
        for key, prompt, options, weight in redundant_questions:
            question = db.scalar(select(Question).where(Question.key == key))
            if question is None:
                db.add(
                    Question(
                        key=key,
                        prompt=prompt,
                        hint=None,
                        input_type="radio",
                        sensitivity_level="low",
                        options_json=options,
                        sort_weight=weight,
                    )
                )

        income_question = db.scalar(select(Question).where(Question.key == "ca_low_income"))
        if income_question is None:
            db.add(
                Question(
                    key="ca_low_income",
                    prompt="Do you have low income?",
                    hint=None,
                    input_type="radio",
                    sensitivity_level="low",
                    options_json=[
                        {"label": "Yes", "value": "Yes"},
                        {"label": "No", "value": "No"},
                    ],
                    sort_weight=100.0,
                )
            )
            db.flush()

        program = db.scalar(select(Program).where(Program.slug == "ca-test-cash-support"))
        if program is None:
            program = Program(
                slug="ca-test-cash-support",
                name="California Test Cash Support",
                kind="benefit",
                category="cash",
                family="ca_test_cash_support",
                summary="Regression test program for redundant state residency questions.",
                apply_url="https://www.ca.gov/",
                status="active",
                jurisdiction_id=california.id,
                agency_id=agency.id,
            )
            db.add(program)
            db.flush()

        version = db.scalar(
            select(ProgramVersion).where(
                ProgramVersion.program_id == program.id,
                ProgramVersion.publication_state == "published",
            )
        )
        if version is None:
            version = ProgramVersion(
                program_id=program.id,
                version_label="test-regression",
                signature="ca-test-cash-support-v1",
                publication_state="published",
                published_at=datetime.utcnow(),
                change_summary="Regression fixture for state residency filtering.",
                source_freshness_days=0,
            )
            db.add(version)
            db.flush()

            db.add_all(
                [
                    EligibilityRule(
                        program_version_id=version.id,
                        question_key="state_code",
                        operator="matches_any",
                        expected_values_json=["CA"],
                        label="Available in California.",
                        priority=100,
                        source_key="test-ca-source",
                        source_citation="https://www.ca.gov/",
                    ),
                    EligibilityRule(
                        program_version_id=version.id,
                        question_key="ca_resident",
                        operator="matches_any",
                        expected_values_json=["Yes"],
                        label="You are a resident of California.",
                        priority=99,
                        source_key="test-ca-source",
                        source_citation="https://www.ca.gov/",
                    ),
                    EligibilityRule(
                        program_version_id=version.id,
                        question_key="ca_residency_status",
                        operator="matches_any",
                        expected_values_json=["resident"],
                        label="You have California residency.",
                        priority=98,
                        source_key="test-ca-source",
                        source_citation="https://www.ca.gov/",
                    ),
                    EligibilityRule(
                        program_version_id=version.id,
                        question_key="ca_currently_live",
                        operator="matches_any",
                        expected_values_json=["Yes"],
                        label="You currently live in California.",
                        priority=97,
                        source_key="test-ca-source",
                        source_citation="https://www.ca.gov/",
                    ),
                    EligibilityRule(
                        program_version_id=version.id,
                        question_key="ca_low_income",
                        operator="matches_any",
                        expected_values_json=["Yes"],
                        label="You have low income.",
                        priority=80,
                        source_key="test-ca-source",
                        source_citation="https://www.ca.gov/",
                    ),
                    AmountRule(
                        program_version_id=version.id,
                        amount_type="range",
                        display_text="Test support amount.",
                        source_key="test-ca-source",
                    ),
                ]
            )

        db.commit()


def test_session_flow_returns_federal_and_state_results() -> None:
    with TestClient(app) as client:
        states = client.get("/api/v1/jurisdictions/states")
        assert states.status_code == 200
        assert any(row["code"] == "NY" for row in states.json())

        create_response = client.post(
            "/api/v1/sessions",
            json={
                "scope": "both",
                "state_code": "NY",
                "categories": ["retirement"],
                "depth_mode": "standard",
            },
        )
        assert create_response.status_code == 200
        session = create_response.json()
        assert session["session_id"]
        assert session["next_question"]["key"] in {"applicant_date_of_birth", "applicant_paid_into_SS"}

        answer_response = client.post(
            f"/api/v1/sessions/{session['session_id']}/answers",
            json={
                "answers": {
                    "applicant_paid_into_SS": "Yes",
                    "applicant_date_of_birth": "1950-01-01",
                }
            },
        )
        assert answer_response.status_code == 200

        results_response = client.get(f"/api/v1/sessions/{session['session_id']}/results")
        assert results_response.status_code == 200
        payload = results_response.json()

        assert payload["federal_results"]
        assert payload["state_results"]
        retirement = next(
            item for item in payload["federal_results"] if item["program_slug"] == "social-security-retirement-benefits"
        )
        assert retirement["eligibility_status"] in {"likely_eligible", "possibly_eligible"}
        assert retirement["data_gathered_from"]
        assert retirement["how_to_get_benefit"]
        assert all(".gov" in source["url"] or ".us" in source["url"] for source in retirement["data_gathered_from"])
        assert all(".gov" in step["url"] or ".us" in step["url"] for step in retirement["how_to_get_benefit"])
        assert payload["state_results"][0]["jurisdiction"]["code"] == "NY"


def test_deep_mode_is_more_aggressive_than_quick() -> None:
    with TestClient(app) as client:
        quick_response = client.post(
            "/api/v1/sessions",
            json={
                "scope": "federal",
                "categories": ["all"],
                "depth_mode": "quick",
            },
        )
        deep_response = client.post(
            "/api/v1/sessions",
            json={
                "scope": "federal",
                "categories": ["all"],
                "depth_mode": "deep",
            },
        )

        assert quick_response.status_code == 200
        assert deep_response.status_code == 200

        seeded_answers = {
            "applicant_paid_into_SS": "Yes",
            "applicant_disability": "No",
            "applicant_served_in_active_military": "No",
            "applicant_dolo": "No",
        }

        quick_follow_up = client.post(
            f"/api/v1/sessions/{quick_response.json()['session_id']}/answers",
            json={"answers": seeded_answers},
        )
        deep_follow_up = client.post(
            f"/api/v1/sessions/{deep_response.json()['session_id']}/answers",
            json={"answers": seeded_answers},
        )

        assert quick_follow_up.status_code == 200
        assert deep_follow_up.status_code == 200
        assert quick_follow_up.json()["next_question"] is None
        assert deep_follow_up.json()["next_question"] is not None


def test_plan_compare_and_catalog_endpoints_work() -> None:
    with TestClient(app) as client:
        session_response = client.post(
            "/api/v1/sessions",
            json={
                "scope": "both",
                "state_code": "NY",
                "categories": ["retirement_seniors"],
                "depth_mode": "deep",
            },
        )
        assert session_response.status_code == 200
        session_id = session_response.json()["session_id"]

        client.post(
            f"/api/v1/sessions/{session_id}/answers",
            json={
                "answers": {
                    "applicant_paid_into_SS": "Yes",
                    "applicant_date_of_birth": "1950-01-01",
                }
            },
        )

        plan_response = client.get(f"/api/v1/sessions/{session_id}/plan")
        assert plan_response.status_code == 200
        plan = plan_response.json()
        assert plan["overview"]["likely_programs"] >= 1
        assert plan["official_source_hub"]

        compare_response = client.post(
            f"/api/v1/sessions/{session_id}/compare",
            json={
                "scenarios": [
                    {
                        "name": "Limited income scenario",
                        "answers": {"applicant_income": "Yes"},
                    }
                ]
            },
        )
        assert compare_response.status_code == 200
        comparison = compare_response.json()
        assert comparison["comparisons"]
        assert "summary" in comparison["comparisons"][0]

        catalog_response = client.get(
            "/api/v1/programs",
            params={"query": "retirement", "scope": "federal"},
        )
        assert catalog_response.status_code == 200
        catalog = catalog_response.json()
        assert catalog
        assert all(".gov" in item["apply_url"] or ".us" in item["apply_url"] for item in catalog if item["apply_url"])


def test_hybrid_explorer_supports_plain_english_description_without_llm() -> None:
    with TestClient(app) as client:
        response = client.post(
            "/api/v1/explorer/search",
            json={
                "description": "My family member died of COVID in California and I need help with funeral costs and survivor benefits.",
                "scope": "both",
                "limit": 10,
                "use_llm": True,
            },
        )
        assert response.status_code == 200
        payload = response.json()

        assert payload["mode"] == "hybrid"
        assert payload["interpretation"]["method"] == "heuristic"
        assert payload["interpretation"]["applied_state_code"] == "CA"
        assert any(item["key"] == "death" for item in payload["interpretation"]["applied_categories"])
        assert payload["programs"]
        assert any(program["jurisdiction"]["code"] == "CA" for program in payload["programs"])
        assert any(program["match_reasons"] for program in payload["programs"])
        assert any(
            "funeral" in (program["name"] or "").lower() or "survivor" in (program["summary"] or "").lower()
            for program in payload["programs"]
        )


def test_selected_state_suppresses_redundant_residency_questions_across_depths() -> None:
    seed_state_program_with_redundant_residency_rule()

    with TestClient(app) as client:
        for depth_mode in ("quick", "standard", "deep"):
            session_response = client.post(
                "/api/v1/sessions",
                json={
                    "scope": "state",
                    "state_code": "CA",
                    "categories": ["welfare_cash_assistance"],
                    "depth_mode": depth_mode,
                },
            )
            assert session_response.status_code == 200
            session = session_response.json()
            assert session["next_question"]["key"] == "ca_low_income"

            answer_response = client.post(
                f"/api/v1/sessions/{session['session_id']}/answers",
                json={"answers": {"ca_low_income": "Yes"}},
            )
            assert answer_response.status_code == 200
            next_question = answer_response.json()["next_question"]
            assert next_question is None or next_question["key"] != "ca_resident"

            results_response = client.get(f"/api/v1/sessions/{session['session_id']}/results")
            assert results_response.status_code == 200
            payload = results_response.json()
            program = next(item for item in payload["state_results"] if item["program_slug"] == "ca-test-cash-support")
            assert program["eligibility_status"] == "likely_eligible"
            assert all("resident of california" not in fact.lower() for fact in program["missing_facts"])
            assert all("california residency" not in fact.lower() for fact in program["missing_facts"])
            assert all("currently live in california" not in fact.lower() for fact in program["missing_facts"])
