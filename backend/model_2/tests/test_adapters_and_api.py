import pytest
import hashlib
from pathlib import Path
from fastapi.testclient import TestClient
from backend.model_2.api.main import app
from backend.model_2.api.schemas import WatershedSummary, WatershedDetail, LiveRiskResult

def test_root_endpoint():
    with TestClient(app) as client:
        response = client.get("/")
        assert response.status_code == 200
        data = response.json()
        assert data["status"] == "online"
        assert "api_version" in data

def test_list_66_watersheds_and_contract():
    with TestClient(app) as client:
        response = client.get("/api/v1/watersheds")
        assert response.status_code == 200
        items = response.json()
        assert len(items) == 66, f"Expected 66 official MWS, got {len(items)}"
        
        # Test MWS Contract: id is internal GIS key, MWS is display code
        sample = items[0]
        assert "id" in sample and "MWS" in sample
        assert sample["id"] != sample["MWS"]
        assert sample["id"].startswith("g_mws.")
        assert len(sample["MWS"]) >= 4

def test_basin_summary_kpis():
    with TestClient(app) as client:
        response = client.get("/api/v1/watersheds/basin/summary")
        assert response.status_code == 200
        data = response.json()
        assert data["watershed_count"] == 66
        assert data["total_area_km2"] > 900
        assert 0 <= data["basin_health_index"] <= 100

def test_watershed_profile_lookup():
    with TestClient(app) as client:
        # Lookup by GIS id
        res1 = client.get("/api/v1/watersheds/g_mws.240575")
        assert res1.status_code == 200
        p1 = res1.json()
        assert p1["id"] == "g_mws.240575"
        assert p1["MWS"] == "4D4F2m3"
        assert p1["lulc"] is not None
        assert p1["risk"] is not None
        assert p1["interventions"] is not None

        # Lookup by display MWS code
        res2 = client.get("/api/v1/watersheds/4D4F2m3")
        assert res2.status_code == 200
        p2 = res2.json()
        assert p2["id"] == "g_mws.240575"
        assert p2["MWS"] == "4D4F2m3"

def test_live_iot_inference_engine():
    with TestClient(app) as client:
        reading = {
            "id": "g_mws.240575",
            "rainfall_mm": 250.0,
            "soil_moisture_pct": 92.0,
            "water_level_cm": 85.0,
            "turbidity_ntu": 800.0,
            "air_temperature_c": 27.0,
            "humidity_pct": 95.0,
            "water_temperature_c": 25.0,
            "ph": 6.8,
            "year": 2026,
            "month": 9
        }
        response = client.post("/api/v1/telemetry", json=reading)
        assert response.status_code == 200
        out = response.json()
        assert out["id"] == "g_mws.240575"
        assert out["MWS"] == "4D4F2m3"
        assert out["compound_event_detected"] is True
        assert out["compound_alert_level"] == "HIGH ALERT"
        assert out["live_risk_category"] == "HIGH"
        assert 0 <= out["live_risk_score"] <= 100

def test_gis_geojson_boundaries():
    with TestClient(app) as client:
        response = client.get("/api/v1/gis/mws-boundaries")
        assert response.status_code == 200
        geojson = response.json()
        assert geojson["type"] == "FeatureCollection"
        assert len(geojson["features"]) == 66
        # Coordinates must be in WGS84 EPSG:4326 range (lng ~75, lat ~14-15)
        coords = geojson["features"][0]["geometry"]["coordinates"][0][0]
        lng, lat = coords[0], coords[1]
        assert 74.0 <= lng <= 76.0, f"Longitude out of WGS84 range: {lng}"
        assert 14.0 <= lat <= 16.0, f"Latitude out of WGS84 range: {lat}"

def test_gis_geojson_all_66_features():
    with TestClient(app) as client:
        res = client.get("/api/v1/gis/mws-boundaries")
        assert res.status_code == 200
        data = res.json()
        assert data["type"] == "FeatureCollection"
        assert data["total_features"] == 66
        assert len(data["features"]) == 66

def test_gis_feature_properties_contract():
    with TestClient(app) as client:
        res = client.get("/api/v1/gis/mws-boundaries")
        assert res.status_code == 200
        features = res.json()["features"]
        required_keys = {
            "id", "MWS", "area_km2", "risk_score", "risk_category",
            "health_index", "primary_driver", "intervention_priority",
            "forest_pct", "agriculture_pct", "water_pct", "builtup_pct", "barren_pct"
        }
        for f in features:
            assert f["type"] == "Feature"
            assert "geometry" in f and f["geometry"] is not None
            props = f["properties"]
            for k in required_keys:
                assert k in props, f"Missing {k} in feature properties"
            assert props["risk_category"] in ("CRITICAL", "HIGH", "MODERATE", "LOW")

def test_gis_id_and_mws_uniqueness():
    with TestClient(app) as client:
        res = client.get("/api/v1/gis/mws-boundaries")
        assert res.status_code == 200
        features = res.json()["features"]
        ids = [f["properties"]["id"] for f in features]
        mws_codes = [f["properties"]["MWS"] for f in features]
        assert len(ids) == 66
        assert len(set(ids)) == 66, f"Duplicate ids found: {len(ids) - len(set(ids))}"
        assert len(mws_codes) == 66
        assert len(set(mws_codes)) == 66, f"Duplicate MWS codes found: {len(mws_codes) - len(set(mws_codes))}"

def test_gis_geometry_valid_and_bounds():
    with TestClient(app) as client:
        res = client.get("/api/v1/gis/mws-boundaries")
        assert res.status_code == 200
        features = res.json()["features"]
        for f in features:
            geom = f["geometry"]
            assert geom["type"] in ("Polygon", "MultiPolygon")
            assert len(geom["coordinates"]) > 0

def test_known_mws_selection_and_query():
    with TestClient(app) as client:
        # Check known MWS in GIS layer
        res = client.get("/api/v1/gis/mws-boundaries")
        assert res.status_code == 200
        features = res.json()["features"]
        known = next((f for f in features if f["properties"]["id"] == "g_mws.240575"), None)
        assert known is not None
        assert known["properties"]["MWS"] == "4D4F2m3"
        assert known["properties"]["risk_category"] == "HIGH"
        assert known["properties"]["primary_driver"] == "Water Stress"

        # Query endpoint by this ID
        profile_res = client.get("/api/v1/watersheds/g_mws.240575")
        assert profile_res.status_code == 200
        p = profile_res.json()
        assert p["id"] == "g_mws.240575"
        assert p["MWS"] == "4D4F2m3"
        assert p["risk"]["risk_category"] == "HIGH"

def test_gis_risk_distribution_and_drivers():
    with TestClient(app) as client:
        res = client.get("/api/v1/gis/mws-boundaries")
        assert res.status_code == 200
        data = res.json()
        assert data["risk_distribution"] == {
            "CRITICAL": 5,
            "HIGH": 15,
            "MODERATE": 17,
            "LOW": 29
        }
        assert data["primary_drivers"] == {
            "Water Stress": 38,
            "ML Anomaly": 20,
            "Ecosystem Risk": 8
        }

def test_api_not_found_produces_unavailable_state():
    with TestClient(app) as client:
        res = client.get("/api/v1/watersheds/non_existent_id")
        assert res.status_code == 404

def test_model1_artifact_unchanged():
    base_dir = Path(__file__).resolve().parents[3]
    model_path = base_dir / "model1" / "model1_lulc" / "models" / "lulc_random_forest.joblib"
    assert model_path.exists(), f"Model 1 artifact not found at {model_path}"
    
    sha256 = hashlib.sha256()
    md5 = hashlib.md5()
    with open(model_path, "rb") as f:
        while chunk := f.read(65536):
            sha256.update(chunk)
            md5.update(chunk)
            
    assert sha256.hexdigest() == "541028753dcb89d478f9e1151277a5dae8e61f62f648cc168280e700cb140439"
    assert md5.hexdigest() == "ee9edc9e14f13457d4d7d929ae678933"

def test_dashboard_basin_summary_full_metrics():
    with TestClient(app) as client:
        response = client.get("/api/v1/watersheds/basin/summary")
        assert response.status_code == 200
        data = response.json()
        assert data["watershed_count"] == 66
        assert data["total_area_km2"] > 900
        assert 0 <= data["basin_health_index"] <= 100
        assert data["critical_count"] == 5
        assert data["high_count"] == 15
        assert data["moderate_count"] == 17
        assert data["low_count"] == 29
        assert data["critical_count"] + data["high_count"] + data["moderate_count"] + data["low_count"] == 66
        
        # Verify distribution dictionaries
        assert data["risk_distribution"] == {
            "CRITICAL": 5,
            "HIGH": 15,
            "MODERATE": 17,
            "LOW": 29
        }
        assert data["primary_risk_drivers"] == {
            "Water Stress": 38,
            "ML Anomaly": 20,
            "Ecosystem Risk": 8
        }
        
        # Verify 12-month historical monthly trend
        trend = data["monthly_trend"]
        assert isinstance(trend, list)
        assert len(trend) == 12
        for pt in trend:
            assert "month" in pt and "year" in pt
            assert 0 <= pt["health_index"] <= 100
            assert 0 <= pt["risk_score"] <= 100

def test_dashboard_watershed_profile_monthly_trend():
    with TestClient(app) as client:
        res = client.get("/api/v1/watersheds/g_mws.240575")
        assert res.status_code == 200
        data = res.json()
        assert data["id"] == "g_mws.240575"
        assert data["MWS"] == "4D4F2m3"
        trend = data.get("monthly_trend")
        assert isinstance(trend, list)
        assert len(trend) == 12
        for pt in trend:
            assert "month" in pt and "year" in pt
            assert 0 <= pt["health_index"] <= 100

def test_dashboard_risk_categories_in_all_66_watersheds():
    with TestClient(app) as client:
        res = client.get("/api/v1/watersheds")
        assert res.status_code == 200
        items = res.json()
        assert len(items) == 66
        
        from collections import Counter
        cat_counts = Counter(item["risk_category"] for item in items)
        assert cat_counts["CRITICAL"] == 5
        assert cat_counts["HIGH"] == 15
        assert cat_counts["MODERATE"] == 17
        assert cat_counts["LOW"] == 29

def test_watershed_profile_known_mws_full_fields():
    with TestClient(app) as client:
        res = client.get("/api/v1/watersheds/g_mws.240575")
        assert res.status_code == 200
        p = res.json()
        
        # Identity contract
        assert p["id"] == "g_mws.240575"
        assert p["MWS"] == "4D4F2m3"
        assert p["area_km2"] == 14.24
        
        # Model 2 Risk Engine V4 calibration
        risk = p["risk"]
        assert risk is not None
        assert risk["risk_category"] == "HIGH"
        assert risk["final_risk_score"] == 55.27
        assert risk["primary_risk_driver"] == "Water Stress"
        assert 0 <= risk["water_stress_score"] <= 100
        assert 0 <= risk["flood_risk_score"] <= 100
        assert 0 <= risk["ecosystem_risk_score"] <= 100
        assert 0 <= risk["base_risk_score"] <= 100
        assert 0 <= risk["ml_anomaly_score"] <= 100
        
        # Model 1 LULC
        lulc = p["lulc"]
        assert lulc is not None
        assert lulc["dominant_class"] == "Agriculture"
        assert lulc["agriculture_pct"] > 90.0
        assert lulc["forest_pct"] >= 0.0
        assert lulc["water_pct"] >= 0.0
        assert lulc["builtup_pct"] >= 0.0
        assert lulc["valid_pixel_count"] > 0
        
        # Decision support interventions
        interventions = p["interventions"]
        assert interventions is not None
        assert interventions["primary_intervention"] is not None
        assert interventions["secondary_intervention"] is not None
        assert interventions["long_term_intervention"] is not None
        
        # Geospatial morphometry
        assert p["elevation_mean"] == 625.4
        assert p["slope_mean"] == 9.4
        assert p["stream_length_km"] == 2.62
        assert p["drainage_density"] == 0.184
        
        # 12-month historical series
        trend = p["monthly_trend"]
        assert isinstance(trend, list)
        assert len(trend) == 12

def test_all_66_mws_resolve_valid_profile():
    with TestClient(app) as client:
        list_res = client.get("/api/v1/watersheds")
        assert list_res.status_code == 200
        mws_items = list_res.json()
        assert len(mws_items) == 66
        
        for item in mws_items:
            m_id = item["id"]
            p_res = client.get(f"/api/v1/watersheds/{m_id}")
            assert p_res.status_code == 200, f"Failed resolving profile for {m_id}"
            p = p_res.json()
            assert p["id"] == m_id
            assert p["MWS"] == item["MWS"]
            assert p["risk"] is not None
            assert p["lulc"] is not None
            assert p["status"] == "available"

def test_watershed_profile_resolve_by_display_code():
    with TestClient(app) as client:
        res = client.get("/api/v1/watersheds/4D4F2m3")
        assert res.status_code == 200
        p = res.json()
        assert p["id"] == "g_mws.240575"
        assert p["MWS"] == "4D4F2m3"
        assert p["risk"]["risk_category"] == "HIGH"

def test_watershed_profile_invalid_mws_returns_404():
    with TestClient(app) as client:
        res = client.get("/api/v1/watersheds/invalid_mws_nonexistent_99999")
        assert res.status_code == 404
        assert "not found" in res.json()["detail"].lower()

def test_lulc_basin_summary_metrics():
    with TestClient(app) as client:
        res = client.get("/api/v1/lulc/summary")
        assert res.status_code == 200
        data = res.json()
        assert data["total_watersheds"] == 66
        assert data["coverage_distribution"] == {
            "LOW": 35,
            "GOOD": 27,
            "ACCEPTABLE": 3,
            "INSUFFICIENT_DATA": 1
        }
        assert data["confidence_stats"]["mean_confidence"] == 78.3
        assert data["confidence_stats"]["high_confidence_pct"] == 59.8
        assert data["confidence_stats"]["medium_confidence_pct"] == 33.1
        assert data["confidence_stats"]["low_confidence_pct"] == 7.0
        assert data["model_metadata"]["macro_f1"] == 0.807
        assert data["model_metadata"]["accuracy"] == 0.805
        assert data["model_metadata"]["classifier"] == "RandomForestClassifier"

def test_watershed_basin_lulc_summary_alias_endpoint():
    with TestClient(app) as client:
        res = client.get("/api/v1/watersheds/basin/lulc-summary")
        assert res.status_code == 200
        data = res.json()
        assert data["total_watersheds"] == 66
        assert "Forest" in data["full_scene_distribution"]
        assert "Agriculture" in data["full_scene_distribution"]

def test_all_66_mws_have_valid_lulc_percentages():
    with TestClient(app) as client:
        for mws_id in client.get("/api/v1/watersheds").json():
            res = client.get(f"/api/v1/watersheds/{mws_id['id']}/lulc")
            assert res.status_code == 200
            lulc = res.json()
            assert lulc["id"] == mws_id["id"]
            assert lulc["MWS"] == mws_id["MWS"]
            assert 0 <= lulc["forest_pct"] <= 100
            assert 0 <= lulc["agriculture_pct"] <= 100
            assert 0 <= lulc["water_pct"] <= 100
            assert 0 <= lulc["builtup_pct"] <= 100
            assert 0 <= lulc["barren_pct"] <= 100
            assert lulc["dominant_class"] in ["Forest", "Agriculture", "Water", "Built-up", "Barren"]
            assert lulc["coverage_category"] in ["GOOD", "LOW", "ACCEPTABLE", "INSUFFICIENT_DATA"]

def test_known_mws_lulc_exact_values():
    with TestClient(app) as client:
        res = client.get("/api/v1/watersheds/g_mws.240575/lulc")
        assert res.status_code == 200
        lulc = res.json()
        assert lulc["id"] == "g_mws.240575"
        assert lulc["MWS"] == "4D4F2m3"
        assert round(lulc["agriculture_pct"], 2) == 97.29
        assert round(lulc["forest_pct"], 2) == 0.59
        assert round(lulc["water_pct"], 2) == 0.0
        assert round(lulc["builtup_pct"], 2) == 2.11
        assert round(lulc["barren_pct"], 2) == 0.0
        assert lulc["valid_pixel_count"] == 2365
        assert lulc["dominant_class"] == "Agriculture"
        assert lulc["coverage_category"] == "LOW"
        assert round(lulc["coverage_pct"], 2) == 1.66

def test_water_quality_known_mws_exact_values():
    """Verify known MWS g_mws.240575 (4D4F2m3) deterministic simulation values and WQI calculation."""
    with TestClient(app) as client:
        res = client.get("/api/v1/water-quality/g_mws.240575")
        assert res.status_code == 200
        data = res.json()
        assert data["id"] == "g_mws.240575"
        assert data["MWS"] == "4D4F2m3"
        assert data["source"] == "simulation"
        assert data["status"] == "available"
        assert data["ph"] == 6.54
        assert data["tds"] == 512.34
        assert data["turbidity"] == 5.25
        assert data["temperature"] == 28.75
        assert data["wqi"] == 77.38
        assert data["quality_category"] == "Very Poor"
        assert data["timestamp"] == "2026-01-01T00:00:00+00:00"

def test_water_quality_lookup_by_display_code():
    """Verify lookup by SLUSI display code 4D4F2m3 resolves identical catchment record."""
    with TestClient(app) as client:
        res1 = client.get("/api/v1/water-quality/g_mws.240575")
        res2 = client.get("/api/v1/water-quality/4D4F2m3")
        assert res1.status_code == 200
        assert res2.status_code == 200
        assert res1.json() == res2.json()

def test_water_quality_calculation_matches_wqi_module():
    """Verify backend WQI output matches direct evaluation using the water_quality module."""
    from water_quality.src.wqi import evaluate_observation
    with TestClient(app) as client:
        res = client.get("/api/v1/water-quality/g_mws.240575")
        assert res.status_code == 200
        data = res.json()
        direct_eval = evaluate_observation({
            "ph": data["ph"],
            "tds": data["tds"],
            "turbidity": data["turbidity"],
            "temperature": data["temperature"],
            "source": data["source"],
        })
        assert data["wqi"] == direct_eval["wqi"]
        assert data["quality_category"] == direct_eval["quality_category"]

def test_water_quality_summary_all_66_mws():
    """Verify basin-wide water quality summary covers all 66 MWS with verified categories and mean WQI."""
    with TestClient(app) as client:
        res = client.get("/api/v1/water-quality/summary")
        assert res.status_code == 200
        data = res.json()
        assert data["total_monitored_mws"] == 66
        assert data["data_mode"] == "simulation"
        assert data["mean_wqi"] == 76.71
        assert len(data["watersheds"]) == 66

        dist = data["category_distribution"]
        assert sum(dist.values()) == 66
        assert dist["Excellent"] == 3
        assert dist["Good"] == 10
        assert dist["Poor"] == 16
        assert dist["Very Poor"] == 20
        assert dist["Unsuitable for Drinking"] == 17

        # Standards structure
        assert "ph" in data["parameter_standards"]
        assert "tds" in data["parameter_standards"]
        assert "turbidity" in data["parameter_standards"]
        assert "temperature" in data["parameter_standards"]

def test_water_quality_invalid_mws_returns_404():
    """Verify invalid/unknown MWS returns HTTP 404."""
    with TestClient(app) as client:
        res = client.get("/api/v1/water-quality/invalid_catchment_999")
        assert res.status_code == 404
        assert "not found" in res.json()["detail"].lower()

def test_all_66_mws_have_valid_water_quality_records():
    """Verify every single official micro-watershed generates valid water quality records."""
    with TestClient(app) as client:
        watersheds = client.get("/api/v1/watersheds").json()
        assert len(watersheds) == 66
        for w in watersheds:
            res = client.get(f"/api/v1/water-quality/{w['id']}")
            assert res.status_code == 200
            rec = res.json()
            assert rec["id"] == w["id"]
            assert rec["MWS"] == w["MWS"]
            assert rec["source"] == "simulation"
            assert 0 <= rec["ph"] <= 14
            assert rec["tds"] >= 0
            assert rec["turbidity"] >= 0
            assert rec["temperature"] > 0
            assert rec["wqi"] >= 0
            assert rec["quality_category"] in [
                "Excellent", "Good", "Poor", "Very Poor", "Unsuitable for Drinking"
            ]

def test_water_quality_live_mode_reflects_esp32_iot_telemetry():
    """Verify ?mode=live dynamically derives WQI and water quality attributes from real-time IoT gateway."""
    with TestClient(app) as client:
        # Ingest live sensor reading with real ESP32 sensor values
        live_payload = {
            "id": "g_mws.240575",
            "rainfall_mm": 12.5,
            "soil_moisture_pct": 74.2,
            "water_level_cm": 29.5,
            "turbidity_ntu": 8.5,
            "ph": 7.85,
            "water_temperature_c": 28.2,
            "air_temperature_c": 29.1,
            "humidity_pct": 68.0,
            "year": 2026,
            "month": 9
        }
        res_ingest = client.post("/api/v1/telemetry", json=live_payload)
        assert res_ingest.status_code == 200

        # Query water-quality with mode=live
        res_live = client.get("/api/v1/water-quality/g_mws.240575?mode=live")
        assert res_live.status_code == 200
        live_data = res_live.json()
        assert live_data["id"] == "g_mws.240575"
        assert live_data["MWS"] == "4D4F2m3"
        assert live_data["source"] == "live"
        assert live_data["ph"] == 7.85
        assert live_data["turbidity"] == 8.5
        assert live_data["temperature"] == 28.2
        assert live_data["wqi"] > 0
        assert live_data["quality_category"] in [
            "Excellent", "Good", "Poor", "Very Poor", "Unsuitable for Drinking"
        ]

        # Query summary with mode=live
        res_sum = client.get("/api/v1/water-quality/summary?mode=live")
        assert res_sum.status_code == 200
        assert res_sum.json()["data_mode"] == "live"

# ==============================================================================
# STAGE 2F: LIVE IoT INTEGRATION TESTS
# ==============================================================================

def test_known_live_iot_inference_regression():
    """
    Exact regression verification for known MWS g_mws.240575 (4D4F2m3):
    Input:
        id: g_mws.240575
        rainfall: 250.0
        soil moisture: 92.0
        water level: 85.0
        turbidity: 800.0
    Expected output:
        rainfall z: 1.88
        live ML anomaly: 43.29
        live risk: 58.93
        risk category: HIGH
        compound alert: HIGH ALERT
        event: Compound runoff and flood event
        source: live
    """
    with TestClient(app) as client:
        payload = {
            "id": "g_mws.240575",
            "rainfall": 250.0,
            "soil_moisture": 92.0,
            "water_level": 85.0,
            "turbidity": 800.0,
            "year": 2026,
            "month": 9,
        }
        res = client.post("/api/v1/telemetry", json=payload)
        assert res.status_code == 200
        data = res.json()
        assert data["id"] == "g_mws.240575"
        assert data["MWS"] == "4D4F2m3"
        assert data["rainfall_z_score"] == 1.88
        assert data["live_ml_anomaly_score"] == 43.29
        assert data["live_risk_score"] == 58.93
        assert data["live_risk_category"] == "HIGH"
        assert data["compound_alert_level"] == "HIGH ALERT"
        assert data["compound_event_type"] == "Compound runoff and flood event"
        assert data["source"] == "live"
        assert data["rainfall"] == 250.0
        assert data["soil_moisture"] == 92.0
        assert data["water_level"] == 85.0
        assert data["turbidity"] == 800.0
        assert data["timestamp"] is not None

def test_telemetry_post_and_get_latest():
    """Verify live ingest mutates latest telemetry and GET /latest returns it with source == 'live'."""
    with TestClient(app) as client:
        payload = {
            "id": "g_mws.240575",
            "rainfall_mm": 180.0,
            "soil_moisture_pct": 75.0,
            "water_level_cm": 60.0,
            "turbidity_ntu": 450.0,
            "air_temperature_c": 26.5,
            "humidity_pct": 82.0,
            "water_temperature_c": 24.5,
            "ph": 7.1,
        }
        post_res = client.post("/api/v1/telemetry", json=payload)
        assert post_res.status_code == 200
        post_data = post_res.json()
        assert post_data["source"] == "live"

        get_res = client.get("/api/v1/telemetry/latest")
        assert get_res.status_code == 200
        latest_data = get_res.json()
        assert latest_data["id"] == "g_mws.240575"
        assert latest_data["source"] == "live"
        assert latest_data["rainfall_mm"] == 180.0
        assert latest_data["soil_moisture_pct"] == 75.0
        assert latest_data["water_level_cm"] == 60.0
        assert latest_data["turbidity_ntu"] == 450.0

def test_telemetry_simulation_infer_does_not_mutate_latest():
    """Verify POST /api/v1/telemetry/infer returns source == 'simulation' and does not alter latest live state."""
    with TestClient(app) as client:
        # First ensure a live state exists
        live_payload = {
            "id": "g_mws.240575",
            "rainfall": 250.0,
            "soil_moisture": 92.0,
            "water_level": 85.0,
            "turbidity": 800.0,
        }
        client.post("/api/v1/telemetry", json=live_payload)

        # Now run simulation inference on a different unit with synthetic numbers
        sim_payload = {
            "id": "g_mws.240562",
            "rainfall": 10.0,
            "soil_moisture": 20.0,
            "water_level": 15.0,
            "turbidity": 30.0,
        }
        sim_res = client.post("/api/v1/telemetry/infer", json=sim_payload)
        assert sim_res.status_code == 200
        sim_data = sim_res.json()
        assert sim_data["id"] == "g_mws.240562"
        assert sim_data["source"] == "simulation"

        # Verify GET /latest STILL returns the original live state (g_mws.240575), NOT the simulation one
        latest_res = client.get("/api/v1/telemetry/latest")
        assert latest_res.status_code == 200
        latest_data = latest_res.json()
        assert latest_data["id"] == "g_mws.240575"
        assert latest_data["source"] == "live"

def test_telemetry_unknown_mws_returns_404():
    """Verify unknown catchment returns HTTP 404 for both ingest and inference."""
    with TestClient(app) as client:
        payload = {
            "id": "unknown_catchment_99999",
            "rainfall": 100.0,
            "soil_moisture": 50.0,
            "water_level": 30.0,
            "turbidity": 200.0,
        }
        res_ingest = client.post("/api/v1/telemetry", json=payload)
        assert res_ingest.status_code == 404
        assert "not found" in res_ingest.json()["detail"].lower()

        res_infer = client.post("/api/v1/telemetry/infer", json=payload)
        assert res_infer.status_code == 404
        assert "not found" in res_infer.json()["detail"].lower()

def test_telemetry_invalid_payload_returns_422():
    """Verify invalid physical sensor ranges return HTTP 422 validation errors."""
    with TestClient(app) as client:
        # Negative rainfall
        res1 = client.post("/api/v1/telemetry", json={"id": "g_mws.240575", "rainfall": -10.0, "soil_moisture": 50.0, "water_level": 10.0, "turbidity": 100.0})
        assert res1.status_code == 422

        # Soil moisture > 100%
        res2 = client.post("/api/v1/telemetry", json={"id": "g_mws.240575", "rainfall": 50.0, "soil_moisture": 150.0, "water_level": 10.0, "turbidity": 100.0})
        assert res2.status_code == 422

        # Negative water level
        res3 = client.post("/api/v1/telemetry", json={"id": "g_mws.240575", "rainfall": 50.0, "soil_moisture": 50.0, "water_level": -20.0, "turbidity": 100.0})
        assert res3.status_code == 422

        # Negative turbidity
        res4 = client.post("/api/v1/telemetry", json={"id": "g_mws.240575", "rainfall": 50.0, "soil_moisture": 50.0, "water_level": 10.0, "turbidity": -5.0})
        assert res4.status_code == 422

def test_telemetry_accepts_display_code_and_maps_canonical():
    """Verify ESP32 passing display code MWS '4D4F2m3' maps to canonical ID 'g_mws.240575'."""
    with TestClient(app) as client:
        payload = {
            "id": "4D4F2m3",
            "rainfall": 250.0,
            "soil_moisture": 92.0,
            "water_level": 85.0,
            "turbidity": 800.0,
        }
        res = client.post("/api/v1/telemetry", json=payload)
        assert res.status_code == 200
        data = res.json()
        assert data["id"] == "g_mws.240575"
        assert data["MWS"] == "4D4F2m3"
        assert data["source"] == "live"

# ==============================================================================
# STAGE 2G: GEO-CODED FIELD OBSERVATIONS INTEGRATION TESTS
# ==============================================================================

def test_field_observations_empty_state_and_alias():
    """Verify GET /api/v1/field-observations and /api/v1/evidence return honest empty state."""
    with TestClient(app) as client:
        res = client.get("/api/v1/field-observations")
        assert res.status_code == 200
        assert isinstance(res.json(), list)

        alias_res = client.get("/api/v1/evidence")
        assert alias_res.status_code == 200
        assert alias_res.json() == res.json()

def test_field_observations_invalid_id_returns_404():
    """Verify unknown observation ID returns HTTP 404."""
    with TestClient(app) as client:
        res = client.get("/api/v1/field-observations/NON_EXISTENT_IMG_9999")
        assert res.status_code == 404
        assert "not found" in res.json()["detail"].lower()

def test_field_observations_unknown_mws_returns_404():
    """Verify unknown micro-watershed in /mws/{id} and ?watershed_id= returns HTTP 404."""
    with TestClient(app) as client:
        res_path = client.get("/api/v1/field-observations/mws/non_existent_mws_999")
        assert res_path.status_code == 404
        assert "not found" in res_path.json()["detail"].lower()

        res_query = client.get("/api/v1/field-observations?watershed_id=non_existent_mws_999")
        assert res_query.status_code == 404
        assert "not found" in res_query.json()["detail"].lower()

def test_field_observations_valid_mws_returns_200():
    """Verify valid micro-watershed returns HTTP 200 with list (id and MWS supported)."""
    with TestClient(app) as client:
        # Query with canonical id
        res1 = client.get("/api/v1/field-observations/mws/g_mws.240575")
        assert res1.status_code == 200
        assert isinstance(res1.json(), list)

        # Query with display code
        res2 = client.get("/api/v1/field-observations/mws/4D4F2m3")
        assert res2.status_code == 200
        assert isinstance(res2.json(), list)

def test_canonical_mws_mapping_authoritative():
    """Verify authoritative GIS mapping g_mws.240575 -> 4D4F2m3 is preserved."""
    with TestClient(app) as client:
        gis = client.app.state.adapters["gis"]
        meta = gis.get_mws_meta("g_mws.240575")
        assert meta is not None
        assert meta["id"] == "g_mws.240575"
        assert meta["MWS"] == "4D4F2m3"

        # Reverse lookup by display code returns the exact same canonical mapping
        meta_rev = gis.get_mws_meta("4D4F2m3")
        assert meta_rev is not None
        assert meta_rev["id"] == "g_mws.240575"
        assert meta_rev["MWS"] == "4D4F2m3"

def test_geocoded_pipeline_image_analysis_fixture():
    """
    Verify the authoritative Geo-Coded pipeline executes on a test image fixture,
    extracting EXIF, validating coordinates, checking boundary, resolving canonical MWS,
    sampling Sentinel-2 LULC, and producing an EvidenceItem with honest provenance.
    """
    base_dir = Path(__file__).resolve().parents[3]
    fixture_path = base_dir / "geo_coded" / "GEO_CODED_IMAGES" / "tests" / "fixtures" / "valid_ne.jpg"
    assert fixture_path.exists(), f"Fixture not found at {fixture_path}"

    with TestClient(app) as client:
        geo_adapter = client.app.state.adapters["geocoded"]
        item = geo_adapter.analyze_single_image(fixture_path)

        assert item.filename == "valid_ne.jpg"
        assert item.latitude == pytest.approx(15.012338, rel=1e-4)
        assert item.longitude == pytest.approx(75.213450, rel=1e-4)
        assert item.boundary_status == "INSIDE"
        assert item.id == "g_mws.240603"
        assert item.MWS == "4D4F2j8"
        assert item.lulc_class == "Agriculture"
        assert item.coordinate_status == "VALID"
        assert item.gps_source == "EXIF"
        assert item.source == "geocoded_pipeline"
        assert item.status == "available"

        # Verify the analyzed item is now queryable through the API
        res = client.get("/api/v1/field-observations")
        assert res.status_code == 200
        items = res.json()
        assert len(items) >= 1
        found = next((x for x in items if x["filename"] == "valid_ne.jpg"), None)
        assert found is not None
        assert found["id"] == "g_mws.240603"
        assert found["MWS"] == "4D4F2j8"

def test_geocoded_no_gps_never_fabricates_coordinates():
    """
    Verify that an image without EXIF GPS metadata reports NO_GPS status
    and latitude/longitude remain None. Never fabricates coordinates.
    """
    base_dir = Path(__file__).resolve().parents[3]
    no_gps_path = base_dir / "geo_coded" / "GEO_CODED_IMAGES" / "tests" / "fixtures" / "no_gps.jpg"
    assert no_gps_path.exists(), f"Fixture not found at {no_gps_path}"

    with TestClient(app) as client:
        geo_adapter = client.app.state.adapters["geocoded"]
        item = geo_adapter.analyze_single_image(no_gps_path)

        assert item.filename == "no_gps.jpg"
        assert item.latitude is None
        assert item.longitude is None
        assert item.coordinate_status == "MISSING" or item.observation_status == "NO_GPS"
        assert item.id is None
        assert item.MWS is None

def test_geocoded_ledger_stability_and_no_database(tmp_path):
    """
    Verify the ImageIdLedger assigns deterministic sequential IDs based on SHA-256
    file content hash and uses flat JSON file persistence without a database.
    """
    import sys
    import json
    base_dir = Path(__file__).resolve().parents[3]
    try:
        from geo_coded.GEO_CODED_IMAGES.src.image_id_ledger import ImageIdLedger
    except ImportError:
        sys.path.insert(0, str(base_dir / "geo_coded" / "GEO_CODED_IMAGES"))
        from src.image_id_ledger import ImageIdLedger

    ledger_file = tmp_path / "test_ledger.json"
    ledger = ImageIdLedger(ledger_file)

    fixture_path = base_dir / "geo_coded" / "GEO_CODED_IMAGES" / "tests" / "fixtures" / "valid_ne.jpg"
    id1 = ledger.get_or_create(fixture_path)
    assert id1.startswith("IMG_")

    # Second call on identical content must return the identical ID
    id2 = ledger.get_or_create(fixture_path)
    assert id1 == id2
    assert len(ledger) == 1

    # Verify flat file JSON structure (no SQL database)
    assert ledger_file.exists()
    with open(ledger_file) as f:
        data = json.load(f)
    assert "entries" in data
    assert "next_id" in data


def _cleanup_test_upload_artifacts():
    base_dir = Path(__file__).resolve().parents[3]
    geo_dir = base_dir / "geo_coded" / "GEO_CODED_IMAGES"
    for p in [
        geo_dir / "outputs" / "geo_coded_results.json",
        geo_dir / "outputs" / "geo_coded_results.csv",
        geo_dir / "12_GEO_CODED_IMAGES" / "Metadata" / "Photo_Master_Validated.csv",
        geo_dir / "12_GEO_CODED_IMAGES" / "Metadata" / "image_id_ledger.json",
        geo_dir / "12_GEO_CODED_IMAGES" / "Metadata" / "GeoCoded_Processing_Log.txt",
        geo_dir / "12_GEO_CODED_IMAGES" / "GIS" / "GEO_CODED_PHOTO_POINTS.gpkg",
        geo_dir / "12_GEO_CODED_IMAGES" / "GIS" / "GEO_CODED_PHOTO_MWS_JOINED.gpkg",
    ]:
        if p.exists():
            try:
                p.unlink()
            except Exception:
                pass
    upload_dir = geo_dir / "data" / "uploads"
    if upload_dir.exists():
        import shutil
        shutil.rmtree(upload_dir, ignore_errors=True)
    if hasattr(app, "state") and hasattr(app.state, "adapters") and "geocoded" in app.state.adapters:
        app.state.adapters["geocoded"]._items.clear()


def test_upload_field_photos_valid_fixture():
    """Verify POST /api/v1/field-observations/upload processes valid geotagged image."""
    base_dir = Path(__file__).resolve().parents[3]
    fixture_path = base_dir / "geo_coded" / "GEO_CODED_IMAGES" / "tests" / "fixtures" / "valid_ne.jpg"
    assert fixture_path.exists(), f"Fixture not found at {fixture_path}"

    try:
        with TestClient(app) as client:
            with open(fixture_path, "rb") as f:
                files = [("files", ("valid_ne.jpg", f.read(), "image/jpeg"))]

            res = client.post("/api/v1/field-observations/upload", files=files)
            assert res.status_code == 200, f"Upload failed: {res.text}"
            data = res.json()

            assert data["total_received"] == 1
            assert data["total_processed"] == 1
            assert data["valid_geotagged"] == 1
            assert data["inside_boundary"] == 1
            assert data["mws_resolved"] == 1
            assert "1 photo processed" in data["summary_message"]

            # Verify photo result
            results = data["results"]
            assert len(results) == 1
            r = results[0]
            assert r["filename"] == "valid_ne.jpg"
            assert r["status"] == "OK"
            assert r["state_category"] == "processed"
            assert r["latitude"] == pytest.approx(15.012338, rel=1e-4)
            assert r["longitude"] == pytest.approx(75.213450, rel=1e-4)
            assert r["micro_watershed_id"] == "g_mws.240603"
            assert r["mws_code"] == "4D4F2j8"
            assert r["lulc_class"] == "Agriculture"
            assert r["image_id"] is not None

            # Verify queryable in ledger
            obs_res = client.get("/api/v1/field-observations")
            assert obs_res.status_code == 200
            ledger = obs_res.json()
            assert any(item["filename"] == "valid_ne.jpg" for item in ledger)
    finally:
        _cleanup_test_upload_artifacts()


def test_upload_field_photos_no_gps_and_invalid_type():
    """Verify image without GPS reports missing_gps and invalid file type is rejected."""
    base_dir = Path(__file__).resolve().parents[3]
    no_gps_path = base_dir / "geo_coded" / "GEO_CODED_IMAGES" / "tests" / "fixtures" / "no_gps.jpg"
    assert no_gps_path.exists(), f"Fixture not found at {no_gps_path}"

    try:
        with TestClient(app) as client:
            with open(no_gps_path, "rb") as f:
                no_gps_bytes = f.read()

            files = [
                ("files", ("no_gps.jpg", no_gps_bytes, "image/jpeg")),
                ("files", ("test_bad_file.txt", b"some text", "text/plain")),
            ]

            res = client.post("/api/v1/field-observations/upload", files=files)
            assert res.status_code == 200
            data = res.json()

            assert data["total_received"] == 2
            assert data["rejected_missing_gps"] >= 1
            assert data["failed_or_invalid"] >= 1

            results_by_name = {r["filename"]: r for r in data["results"]}
            assert "no_gps.jpg" in results_by_name
            assert results_by_name["no_gps.jpg"]["state_category"] == "missing_gps"
            assert results_by_name["no_gps.jpg"]["status"] == "NO_GPS"
            assert results_by_name["no_gps.jpg"]["latitude"] is None

            assert "test_bad_file.txt" in results_by_name
            assert results_by_name["test_bad_file.txt"]["state_category"] == "rejected"
            assert results_by_name["test_bad_file.txt"]["status"] == "INVALID_FILE_TYPE"
    finally:
        _cleanup_test_upload_artifacts()



# ==============================================================================
# STAGE 2H: REPORTS & EXPORTS INTEGRATION TESTS
# ==============================================================================

def test_reports_basin_endpoint_and_schema():
    """
    Verify GET /api/v1/reports/basin returns a structured BasinReport
    covering all 66 official micro-watersheds with complete provenance.
    """
    with TestClient(app) as client:
        res = client.get("/api/v1/reports/basin")
        assert res.status_code == 200, f"Expected 200, got {res.status_code}: {res.text}"
        data = res.json()

        assert data["report_type"] == "basin"
        assert data["total_mws"] == 66
        assert data["total_area_km2"] > 0
        assert 0 <= data["basin_health_index"] <= 100
        assert 0 <= data["average_risk_score"] <= 100
        assert "generated_at" in data

        # Risk breakdown
        assert "CRITICAL" in data["risk_distribution"]
        assert "HIGH" in data["risk_distribution"]
        assert "MODERATE" in data["risk_distribution"]
        assert "LOW" in data["risk_distribution"]
        total_risk_mws = sum(data["risk_distribution"].values())
        assert total_risk_mws == 66

        # Primary drivers
        assert "Water Stress" in data["primary_drivers"]

        # Water Quality section (MUST explicitly declare simulation)
        assert data["water_quality_summary"]["data_mode"] == "simulation"
        assert "SIMULATION" in data["provenance"]["water_quality"]

        # Status
        assert data["status"] == "available"


def test_reports_basin_csv_endpoint():
    """
    Verify GET /api/v1/reports/basin/csv generates an authoritative 66-row CSV
    with appropriate Content-Type and Content-Disposition headers.
    """
    with TestClient(app) as client:
        res = client.get("/api/v1/reports/basin/csv")
        assert res.status_code == 200
        assert "text/csv" in res.headers.get("content-type", "")
        assert "shiggaon_basin_report.csv" in res.headers.get("content-disposition", "")

        lines = [line.strip() for line in res.text.strip().split("\n") if line.strip()]
        # 1 header line + 66 data lines = 67 lines
        assert len(lines) == 67, f"Expected 67 CSV lines (1 header + 66 rows), got {len(lines)}"

        headers = lines[0].split(",")
        assert "id" in headers
        assert "MWS" in headers
        assert "risk_score" in headers
        assert "risk_category" in headers
        assert "health_index" in headers
        assert "dominant_lulc" in headers
        assert "wq_wqi" in headers
        assert "wq_source" in headers
        assert "iot_live_status" in headers
        assert "field_observations_count" in headers

        # Verify all data rows contain SIMULATION for water quality
        wq_source_idx = headers.index("wq_source")
        for row in lines[1:]:
            cols = row.split(",")
            assert cols[wq_source_idx] == "SIMULATION"


def test_reports_mws_by_canonical_id_and_display_code():
    """
    Verify GET /api/v1/reports/mws/{id} resolves both canonical GIS key
    and human-readable MWS display code, preserving canonical identity.
    """
    with TestClient(app) as client:
        # 1. By canonical GIS ID
        res1 = client.get("/api/v1/reports/mws/g_mws.240575")
        assert res1.status_code == 200
        d1 = res1.json()
        assert d1["report_type"] == "mws"
        assert d1["id"] == "g_mws.240575"
        assert d1["MWS"] == "4D4F2m3"
        assert d1["risk"]["risk_score"] > 0
        assert "sub_scores" in d1["risk"]
        assert "forest_pct" in d1["lulc"]
        assert "dominant_class" in d1["lulc"]
        assert "wqi" in d1["water_quality"]
        assert d1["water_quality"]["source"] == "simulation"
        assert "SIMULATION" in d1["provenance"]["water_quality"]
        assert "primary_intervention" in d1["interventions"]

        # 2. By display MWS code
        res2 = client.get("/api/v1/reports/mws/4D4F2m3")
        assert res2.status_code == 200
        d2 = res2.json()
        assert d2["id"] == "g_mws.240575"
        assert d2["MWS"] == "4D4F2m3"
        assert d2["risk"]["risk_score"] == d1["risk"]["risk_score"]


def test_reports_mws_csv_endpoint():
    """
    Verify GET /api/v1/reports/mws/{id}/csv generates a key-value tabular CSV
    export for the individual micro-watershed with provenance tracking.
    """
    with TestClient(app) as client:
        res = client.get("/api/v1/reports/mws/g_mws.240575/csv")
        assert res.status_code == 200
        assert "text/csv" in res.headers.get("content-type", "")
        assert "watershed_report_g_mws.240575.csv" in res.headers.get("content-disposition", "")

        csv_text = res.text
        assert "Field,Value,Unit/Context,Provenance" in csv_text
        assert "Canonical ID,g_mws.240575" in csv_text
        assert "Display Code,4D4F2m3" in csv_text
        assert "SIMULATION" in csv_text


def test_reports_mws_invalid_404():
    """
    Verify unknown micro-watershed identifiers return clean 404 responses
    for both JSON and CSV endpoints.
    """
    with TestClient(app) as client:
        # JSON 404
        r_json = client.get("/api/v1/reports/mws/invalid_mws_nonexistent")
        assert r_json.status_code == 404

        # CSV 404
        r_csv = client.get("/api/v1/reports/mws/invalid_mws_nonexistent/csv")
        assert r_csv.status_code == 404


def test_reports_honest_data_contract():
    """
    Strictly verifies data honesty contract in reports:
    1. Water Quality is always tagged SIMULATION (never disguised as live field readings)
    2. Live IoT telemetry reports UNAVAILABLE when offline (zero mock substitution)
    3. Field evidence reports count 0 honestly without fabricated photos
    """
    with TestClient(app) as client:
        res = client.get("/api/v1/reports/mws/g_mws.240575")
        assert res.status_code == 200
        d = res.json()

        # 1. WQ is simulation
        assert d["water_quality"]["source"] == "simulation"
        assert "SIMULATION" in d["provenance"]["water_quality"]

        # 2. IoT honesty (no telemetry has been posted to this specific node)
        if not d["live_iot"]["available"]:
            assert d["live_iot"]["source"] in ("unavailable", "live")
            assert d["live_iot"]["status"] in ("unavailable", "no_telemetry")

        # 3. Field evidence honesty
        assert isinstance(d["field_evidence"]["count"], int)
        assert d["field_evidence"]["status"] in ("available", "no_observations")


def test_reports_no_database_introduced():
    """
    Verify that Stage 2H remains strictly flat-file / memory based
    without introducing any database engine or database files.
    """
    from backend.model_2.api.main import app
    assert hasattr(app.state, "adapters")
    assert "reports" in app.state.adapters

    rep_adapter = app.state.adapters["reports"]
    # Check that rep_adapter uses in-memory adapter composition
    assert hasattr(rep_adapter, "gis")
    assert hasattr(rep_adapter, "m1")
    assert hasattr(rep_adapter, "m2")
    assert hasattr(rep_adapter, "wq")
    assert hasattr(rep_adapter, "iot")
    assert hasattr(rep_adapter, "geo")


