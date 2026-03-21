import os
import sys
from pathlib import Path

from fastapi.testclient import TestClient


ROOT = Path(__file__).resolve().parents[1]
TEST_DB = ROOT / "test_benefits_digger.db"
if TEST_DB.exists():
    TEST_DB.unlink()

os.environ["BENEFITS_DIGGER_DATABASE_URL"] = f"sqlite:///{TEST_DB.as_posix()}"
os.environ["BENEFITS_DIGGER_AUTO_SYNC_REMOTE"] = "false"
sys.path.insert(0, str(ROOT))

from app.main import app


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
