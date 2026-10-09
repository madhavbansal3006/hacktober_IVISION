"""
Unit and Integration Tests for Ask JalDrishti (Gemma 4 Q&A with Real Watershed Evidence).
Covers:
1. Normal watershed question (end-to-end verified with evidence references)
2. Unknown watershed ID (404 Not Found)
3. Missing evidence handling (disclosures preserved, no fake numbers)
4. Fabricated numerical claim (rejected, deterministic fallback returned)
5. Incorrect risk category (rejected, deterministic fallback returned)
6. Invalid model output (malformed JSON handled gracefully)
7. Model API failure (timeout / HTTP error handled with safe fallback)
8. Empty question rejection (400 Bad Request)
9. Non-existent evidence ID rejection (rejected, fallback used)
"""

import pytest
from unittest.mock import patch, MagicMock
from fastapi.testclient import TestClient

from backend.model_2.api.main import app
from backend.model_2.api.schemas import AskResponse
from backend.model_2.api.services.gemma_client import (
    GemmaTimeoutError,
    GemmaAPIError,
    GemmaMalformedResponseError,
)

# ---------------------------------------------------------------------------
# Test 1: Normal Watershed Question
# ---------------------------------------------------------------------------
def test_ask_normal_watershed_question():
    """
    Verifies that a valid question for an existing micro-watershed with grounded
    Gemma 4 claims passes deterministic validation and returns a verified answer.
    """
    mock_llm_response = {
        "answer": (
            "Micro-watershed 4D4F2m3 has an official final risk score of 55.27/100, placing it in the "
            "HIGH risk category. Its primary risk driver is Water Stress (component score 78.78/100). "
            "The dominant land cover is Agriculture (97.29%)."
        ),
        "claims": [
            {
                "claim_text": "Official risk score is 55.27",
                "evidence_id": "ev_final_risk",
                "claimed_value": 55.27
            },
            {
                "claim_text": "Risk category is HIGH",
                "evidence_id": "ev_risk_category",
                "claimed_value": "HIGH"
            },
            {
                "claim_text": "Primary driver is Water Stress",
                "evidence_id": "ev_primary_driver",
                "claimed_value": "Water Stress"
            },
            {
                "claim_text": "Water Stress score is 78.78",
                "evidence_id": "ev_water_stress",
                "claimed_value": 78.78
            },
            {
                "claim_text": "Agriculture land cover is 97.29%",
                "evidence_id": "ev_lulc_agri",
                "claimed_value": 97.29
            }
        ],
        "disclosed_gaps": [
            "Water Quality is simulation only and does not reflect in-situ telemetry."
        ]
    }

    with patch("backend.model_2.api.routes.ai.GemmaClient.generate_answer", return_value=mock_llm_response):
        with TestClient(app) as client:
            payload = {
                "mws_code": "4D4F2m3",
                "question": "What are the main risk factors for this watershed?"
            }
            response = client.post("/api/v1/ai/ask", json=payload)
            assert response.status_code == 200, response.text
            data = response.json()

            assert data["status"] == "available"
            assert data["mws_code"] == "4D4F2m3"
            assert data["mws_id"] == "g_mws.240575"
            assert data["validation_passed"] is True
            assert data["fallback_used"] is False
            assert "55.27" in data["answer"]
            assert len(data["evidence_used"]) >= 10
            assert len(data["claims"]) == 5
            for claim in data["claims"]:
                assert claim["verified"] is True
            assert data["validation_details"]["schema_valid"] is True
            assert data["validation_details"]["numerical_claims_valid"] is True
            assert data["validation_details"]["risk_category_valid"] is True
            assert data["validation_details"]["evidence_ids_valid"] is True


# ---------------------------------------------------------------------------
# Test 2: Unknown Watershed ID
# ---------------------------------------------------------------------------
def test_ask_unknown_watershed_id():
    """
    Verifies that querying a non-existent watershed ID returns 404 with
    a clear message referencing the official 66 GIS catalog.
    """
    with TestClient(app) as client:
        payload = {
            "mws_code": "INVALID_MWS_9999",
            "question": "What is the slope of this watershed?"
        }
        response = client.post("/api/v1/ai/ask", json=payload)
        assert response.status_code == 404
        data = response.json()
        assert "not found among official 66 units" in data["detail"]


# ---------------------------------------------------------------------------
# Test 3: Missing Evidence Handling
# ---------------------------------------------------------------------------
def test_ask_missing_evidence():
    """
    Verifies that the evidence retriever preserves missing values honestly
    without inventing fake numbers or zeroing out metrics. Disclosures are retained.
    """
    with TestClient(app) as client:
        adapters = app.state.adapters
        from backend.model_2.api.services.watershed_evidence import WatershedEvidenceService

        svc = WatershedEvidenceService(adapters)
        bundle = svc.retrieve_evidence("4D4F2m3")
        assert bundle is not None
        assert bundle.mws_code == "4D4F2m3"

        # Check that disclosed gaps accurately record real limitations
        gap_texts = " ".join(bundle.disclosed_gaps)
        assert "simulation" in gap_texts.lower()
        assert "field survey photos" in gap_texts.lower() or "field observations" in gap_texts.lower()

        # Check all evidence items: none should have invented nulls
        for item in bundle.items:
            assert item.value is not None


# ---------------------------------------------------------------------------
# Test 4: Fabricated Numerical Claim (Rejected & Fallback Used)
# ---------------------------------------------------------------------------
def test_ask_fabricated_numerical_claim():
    """
    Verifies that when Gemma claims an ungrounded or fabricated numerical value
    (e.g. risk score 95.0 instead of actual 55.27), the deterministic validator
    rejects the unverified answer and returns the safe deterministic fallback.
    """
    hallucinated_response = {
        "answer": "Micro-watershed 4D4F2m3 is extremely dangerous with a risk score of 95.0/100.",
        "claims": [
            {
                "claim_text": "Risk score is 95.0",
                "evidence_id": "ev_final_risk",
                "claimed_value": 95.0  # Real is 55.27
            }
        ],
        "disclosed_gaps": []
    }

    with patch("backend.model_2.api.routes.ai.GemmaClient.generate_answer", return_value=hallucinated_response):
        with TestClient(app) as client:
            payload = {
                "mws_code": "4D4F2m3",
                "question": "What is the risk score?"
            }
            response = client.post("/api/v1/ai/ask", json=payload)
            assert response.status_code == 200
            data = response.json()

            assert data["validation_passed"] is False
            assert data["fallback_used"] is True
            assert data["validation_details"]["numerical_claims_valid"] is False

            # The unverified answer containing "95.0" must NOT be displayed
            assert "95.0" not in data["answer"]
            # The safe fallback constructed from real data must be present
            assert "55.27" in data["answer"]
            assert "Authoritative Profile" in data["answer"]


# ---------------------------------------------------------------------------
# Test 5: Incorrect Risk Category (Rejected & Fallback Used)
# ---------------------------------------------------------------------------
def test_ask_incorrect_risk_category():
    """
    Verifies that when Gemma asserts an incorrect risk category that conflicts
    with official thresholds (e.g. claiming LOW when official is HIGH),
    the validator catches the discrepancy, rejects the answer, and falls back.
    """
    incorrect_cat_response = {
        "answer": "This watershed is in safe condition and is classified as LOW risk.",
        "claims": [
            {
                "claim_text": "Risk category is LOW",
                "evidence_id": "ev_risk_category",
                "claimed_value": "LOW"  # Official is HIGH
            }
        ],
        "disclosed_gaps": []
    }

    with patch("backend.model_2.api.routes.ai.GemmaClient.generate_answer", return_value=incorrect_cat_response):
        with TestClient(app) as client:
            payload = {
                "mws_code": "4D4F2m3",
                "question": "Is this watershed high risk?"
            }
            response = client.post("/api/v1/ai/ask", json=payload)
            assert response.status_code == 200
            data = response.json()

            assert data["validation_passed"] is False
            assert data["fallback_used"] is True
            assert data["validation_details"]["risk_category_valid"] is False
            assert "HIGH" in data["answer"]


# ---------------------------------------------------------------------------
# Test 6: Invalid Model Output (Malformed JSON Handled Safely)
# ---------------------------------------------------------------------------
def test_ask_invalid_model_output():
    """
    Verifies that malformed or non-JSON model output is caught gracefully
    and triggers the safe deterministic fallback without an unhandled server error.
    """
    with patch(
        "backend.model_2.api.routes.ai.GemmaClient.generate_answer",
        side_effect=GemmaMalformedResponseError("Model returned invalid JSON syntax")
    ):
        with TestClient(app) as client:
            payload = {
                "mws_code": "4D4F2m3",
                "question": "Describe the watershed topography."
            }
            response = client.post("/api/v1/ai/ask", json=payload)
            assert response.status_code == 200
            data = response.json()

            assert data["validation_passed"] is False
            assert data["fallback_used"] is True
            assert "Authoritative Profile" in data["answer"]
            assert data["mws_code"] == "4D4F2m3"


# ---------------------------------------------------------------------------
# Test 7: Model API Failure (Timeout / Network Error Handled Safely)
# ---------------------------------------------------------------------------
def test_ask_model_api_failure():
    """
    Verifies that model timeouts or API HTTP errors are handled gracefully,
    delivering deterministic explanations constructed from trusted project data.
    """
    # 7a. Timeout test
    with patch(
        "backend.model_2.api.routes.ai.GemmaClient.generate_answer",
        side_effect=GemmaTimeoutError("Request timed out after 30 seconds")
    ):
        with TestClient(app) as client:
            payload = {
                "mws_code": "4D4F2m3",
                "question": "What is the vegetation index?"
            }
            response = client.post("/api/v1/ai/ask", json=payload)
            assert response.status_code == 200
            data = response.json()
            assert data["fallback_used"] is True
            assert "timed out" in " ".join(data["validation_details"]["reasons"]).lower()

    # 7b. API 500 error test
    with patch(
        "backend.model_2.api.routes.ai.GemmaClient.generate_answer",
        side_effect=GemmaAPIError(500, "Gemini internal server failure")
    ):
        with TestClient(app) as client:
            payload = {
                "mws_code": "4D4F2m3",
                "question": "What is the stream length?"
            }
            response = client.post("/api/v1/ai/ask", json=payload)
            assert response.status_code == 200
            data = response.json()
            assert data["fallback_used"] is True


# ---------------------------------------------------------------------------
# Test 8: Empty / Blank Question Rejected
# ---------------------------------------------------------------------------
def test_ask_empty_question_rejected():
    """
    Verifies that an empty or whitespace-only question is rejected with 400 Bad Request.
    """
    with TestClient(app) as client:
        payload = {
            "mws_code": "4D4F2m3",
            "question": "   "
        }
        response = client.post("/api/v1/ai/ask", json=payload)
        assert response.status_code == 400
        assert "Question cannot be empty" in response.json()["detail"]


# ---------------------------------------------------------------------------
# Test 9: Non-existent Evidence ID Rejected
# ---------------------------------------------------------------------------
def test_ask_non_existent_evidence_id_rejected():
    """
    Verifies that a claim citing an ungrounded or invented evidence ID
    is detected by the validator and rejected.
    """
    hallucinated_id_response = {
        "answer": "Sensor reading indicates temperature is 45C.",
        "claims": [
            {
                "claim_text": "Temperature is 45C",
                "evidence_id": "ev_invented_satellite_radar",  # Non-existent
                "claimed_value": 45.0
            }
        ],
        "disclosed_gaps": []
    }

    with patch("backend.model_2.api.routes.ai.GemmaClient.generate_answer", return_value=hallucinated_id_response):
        with TestClient(app) as client:
            payload = {
                "mws_code": "4D4F2m3",
                "question": "What is the radar temperature?"
            }
            response = client.post("/api/v1/ai/ask", json=payload)
            assert response.status_code == 200
            data = response.json()
            assert data["validation_passed"] is False
            assert data["fallback_used"] is True
            assert data["validation_details"]["evidence_ids_valid"] is False
