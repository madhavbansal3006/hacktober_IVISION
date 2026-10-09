"""
End-to-end and unit tests for JalDrishti Real ESP32 Live IoT Telemetry.
Validates:
- Validation and alias normalization of incoming telemetry
- Catchment and device identification
- Model 2 Isolation Forest ML anomaly inference
- Compound alert & hydrological risk computation
- GET /latest retrieval and filtering
- Rejection of malformed payloads
- Strict separation between Live and Simulation modes
- Staleness detection after timeout
"""

import pytest
import time
from datetime import datetime, timedelta
from fastapi.testclient import TestClient
from backend.model_2.api.main import app

@pytest.fixture(scope="module")
def client():
    with TestClient(app) as c:
        yield c

def test_01_telemetry_post_and_model2_inference(client):
    payload = {
        "device_id": "ESP32_SHIGGAON_NODE_01",
        "mws_code": "4D4F2m3",
        "rainfall_mm_hr": 15.5,
        "soil_moisture_pct": 68.0,
        "water_level_cm": 35.0,
        "turbidity_ntu": 25.0
    }
    response = client.post("/api/v1/telemetry", json=payload)
    assert response.status_code == 200, response.text
    data = response.json()

    # Field verification
    assert data["id"] == "g_mws.240575"
    assert data["MWS"] == "4D4F2m3"
    assert data["device_id"] == "ESP32_SHIGGAON_NODE_01"
    assert data["rainfall_mm_hr"] == 15.5
    assert data["soil_moisture_pct"] == 68.0
    assert data["water_level_cm"] == 35.0
    assert data["turbidity_ntu"] == 25.0

    # Model 2 ML & Risk calculations
    assert "live_ml_anomaly_score" in data
    assert isinstance(data["live_ml_anomaly_score"], (int, float))
    assert 0.0 <= data["live_ml_anomaly_score"] <= 100.0

    assert "live_risk_score" in data
    assert isinstance(data["live_risk_score"], (int, float))
    assert 0.0 <= data["live_risk_score"] <= 100.0

    assert "compound_alert_level" in data
    assert data["compound_alert_level"] in ["NORMAL", "WARNING", "HIGH ALERT", "EMERGENCY"]

    assert data["source"] == "live"
    assert data["is_stale"] is False
    assert data["connection_status"] == "CONNECTED"

def test_02_get_latest_telemetry(client):
    response = client.get("/api/v1/telemetry/latest")
    assert response.status_code == 200, response.text
    data = response.json()
    assert data["id"] == "g_mws.240575"
    assert data["MWS"] == "4D4F2m3"
    assert data["rainfall_mm_hr"] == 15.5
    assert data["is_stale"] is False

def test_03_get_latest_telemetry_with_filters(client):
    # Filter by watershed ID
    res1 = client.get("/api/v1/telemetry/latest?watershed_id=g_mws.240575")
    assert res1.status_code == 200
    assert res1.json()["id"] == "g_mws.240575"

    # Filter by MWS display code
    res2 = client.get("/api/v1/telemetry/latest?mws_code=4D4F2m3")
    assert res2.status_code == 200
    assert res2.json()["MWS"] == "4D4F2m3"

    # Filter by Device ID
    res3 = client.get("/api/v1/telemetry/latest?device_id=ESP32_SHIGGAON_NODE_01")
    assert res3.status_code == 200
    assert res3.json()["device_id"] == "ESP32_SHIGGAON_NODE_01"

    # Non-existent device
    res4 = client.get("/api/v1/telemetry/latest?device_id=NON_EXISTENT_DEVICE")
    assert res4.status_code == 404

def test_04_second_reading_updates_live_state(client):
    # Extreme weather event
    extreme_payload = {
        "device_id": "ESP32_SHIGGAON_NODE_01",
        "mws_code": "4D4F2m3",
        "rainfall_mm_hr": 310.0,
        "soil_moisture_pct": 96.0,
        "water_level_cm": 92.0,
        "turbidity_ntu": 920.0
    }
    response = client.post("/api/v1/telemetry", json=extreme_payload)
    assert response.status_code == 200
    data = response.json()
    assert data["rainfall_mm_hr"] == 310.0
    assert data["compound_alert_level"] == "EMERGENCY"
    assert data["compound_event_detected"] is True

    # Verify GET /latest returns updated state
    latest_res = client.get("/api/v1/telemetry/latest")
    assert latest_res.status_code == 200
    latest = latest_res.json()
    assert latest["rainfall_mm_hr"] == 310.0
    assert latest["compound_alert_level"] == "EMERGENCY"

def test_05_reject_malformed_telemetry(client):
    # Negative rainfall
    res1 = client.post("/api/v1/telemetry", json={
        "mws_code": "4D4F2m3",
        "rainfall_mm_hr": -10.0,
        "soil_moisture_pct": 50.0,
        "water_level_cm": 20.0,
        "turbidity_ntu": 10.0
    })
    assert res1.status_code == 422

    # Soil moisture > 100%
    res2 = client.post("/api/v1/telemetry", json={
        "mws_code": "4D4F2m3",
        "rainfall_mm_hr": 10.0,
        "soil_moisture_pct": 105.0,
        "water_level_cm": 20.0,
        "turbidity_ntu": 10.0
    })
    assert res2.status_code == 422

    # Missing mandatory sensor reading
    res3 = client.post("/api/v1/telemetry", json={
        "mws_code": "4D4F2m3",
        "rainfall_mm_hr": 10.0
    })
    assert res3.status_code == 422

def test_06_simulation_does_not_mutate_live_telemetry(client):
    # Live reading is at 310.0 mm/hr
    live_before = client.get("/api/v1/telemetry/latest").json()
    assert live_before["rainfall_mm_hr"] == 310.0

    # Run simulation inference with 5.0 mm/hr
    sim_payload = {
        "mws_code": "4D4F2m3",
        "rainfall_mm_hr": 5.0,
        "soil_moisture_pct": 20.0,
        "water_level_cm": 10.0,
        "turbidity_ntu": 5.0
    }
    sim_res = client.post("/api/v1/telemetry/infer", json=sim_payload)
    assert sim_res.status_code == 200
    sim_data = sim_res.json()
    assert sim_data["source"] == "simulation"
    assert sim_data["rainfall_mm_hr"] == 5.0

    # Ensure live telemetry endpoint was NOT mutated by the simulation
    live_after = client.get("/api/v1/telemetry/latest").json()
    assert live_after["rainfall_mm_hr"] == 310.0
    assert live_after["source"] == "live"

def test_07_staleness_detection(client):
    engine = app.state.adapters["iot_engine"]
    # Temporarily set last_received_at to 40 seconds in the past
    engine.last_received_at = datetime.now() - timedelta(seconds=40)

    stale_res = client.get("/api/v1/telemetry/latest")
    assert stale_res.status_code == 200
    stale_data = stale_res.json()
    assert stale_data["is_stale"] is True
    assert stale_data["connection_status"] == "OFFLINE / NO DATA"
    # Preserves last valid values and timestamp
    assert stale_data["rainfall_mm_hr"] == 310.0
    assert stale_data["timestamp"] is not None

    # Sending fresh telemetry restores active state
    fresh_payload = {
        "device_id": "ESP32_SHIGGAON_NODE_01",
        "mws_code": "4D4F2m3",
        "rainfall_mm_hr": 12.0,
        "soil_moisture_pct": 65.0,
        "water_level_cm": 30.0,
        "turbidity_ntu": 15.0
    }
    fresh_res = client.post("/api/v1/telemetry", json=fresh_payload)
    assert fresh_res.status_code == 200
    restored = client.get("/api/v1/telemetry/latest").json()
    assert restored["is_stale"] is False
    assert restored["connection_status"] == "CONNECTED"
    assert restored["rainfall_mm_hr"] == 12.0
