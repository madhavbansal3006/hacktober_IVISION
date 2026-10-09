import pytest
from fastapi.testclient import TestClient

from backend.model_2.api.main import app
from backend.model_2.api.adapters.crop_advisor_adapter import CropAdvisorAdapter, REGIONAL_CROPS

@pytest.fixture(scope="module")
def client():
    with TestClient(app) as c:
        yield c

@pytest.fixture(scope="module")
def crop_adapter():
    return CropAdvisorAdapter()

def test_crop_catalog_structure():
    """Verify regional crop catalog is populated with essential Karnataka Zone 8 crops."""
    assert len(REGIONAL_CROPS) >= 10
    crop_ids = [c["id"] for c in REGIONAL_CROPS]
    assert "byadgi_chilli" in crop_ids
    assert "sorghum_jowar" in crop_ids
    assert "pearl_millet_bajra" in crop_ids
    assert "chickpea_bengalgram" in crop_ids
    assert "cotton_bt" in crop_ids

def test_crop_advisory_golden_catchment(crop_adapter):
    """Verify crop advisory for golden catchment 4D4F2m3 / g_mws.240575."""
    advisory = crop_adapter.get_crop_advisory("4D4F2m3")
    assert advisory is not None
    assert advisory.MWS == "4D4F2m3"
    assert advisory.id == "g_mws.240575"

    # Water summary checks
    water = advisory.water_summary
    assert water.water_stress_score > 0
    assert water.water_stress_level in ("LOW", "MODERATE", "HIGH", "CRITICAL")
    assert water.flood_risk_score >= 0
    assert water.wqi is not None
    assert water.tds_mg_l is not None
    assert water.irrigation_advisory != ""

    # Recommendations checks
    assert len(advisory.recommended_crops) > 0
    top_crop = advisory.recommended_crops[0]
    assert top_crop.suitability_score >= advisory.recommended_crops[-1].suitability_score
    assert top_crop.water_tier in ("VERY_LOW", "LOW", "LOW_MODERATE", "MODERATE", "HIGH", "VERY_HIGH")
    assert len(top_crop.key_advantages) > 0

    # Caution crops checks
    if water.water_stress_score >= 42.0:
        assert len(advisory.caution_crops) > 0
        caution_names = [c.crop_name for c in advisory.caution_crops]
        assert any("Sugarcane" in name for name in caution_names)

    # Conservation practices
    assert len(advisory.conservation_practices) >= 2

def test_crop_advisory_id_resolution(crop_adapter):
    """Verify both canonical ID and display code return identical data."""
    adv_code = crop_adapter.get_crop_advisory("4D4F2m3")
    adv_id = crop_adapter.get_crop_advisory("g_mws.240575")
    assert adv_code is not None and adv_id is not None
    assert adv_code.id == adv_id.id
    assert adv_code.water_summary.water_stress_score == adv_id.water_summary.water_stress_score
    assert adv_code.recommended_crops[0].crop_name == adv_id.recommended_crops[0].crop_name

def test_api_crop_catalog(client):
    """Verify GET /api/v1/crops/catalog endpoint."""
    response = client.get("/api/v1/crops/catalog")
    assert response.status_code == 200
    data = response.json()
    assert "crops" in data
    assert data["total_crops"] >= 10

def test_api_crop_suggestions_endpoint(client):
    """Verify GET /api/v1/crops/{mws_identifier} endpoint."""
    response = client.get("/api/v1/crops/4D4F2m3")
    assert response.status_code == 200
    data = response.json()
    assert data["MWS"] == "4D4F2m3"
    assert data["id"] == "g_mws.240575"
    assert "water_summary" in data
    assert "recommended_crops" in data
    assert len(data["recommended_crops"]) > 0

def test_api_watershed_crops_endpoint(client):
    """Verify GET /api/v1/watersheds/{mws_id}/crops endpoint."""
    response = client.get("/api/v1/watersheds/4D4F2m3/crops")
    assert response.status_code == 200
    data = response.json()
    assert data["MWS"] == "4D4F2m3"

def test_api_crops_unknown_mws(client):
    """Verify 404 for nonexistent micro-watershed."""
    response = client.get("/api/v1/crops/nonexistent_mws_999")
    assert response.status_code == 404
