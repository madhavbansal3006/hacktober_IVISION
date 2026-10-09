"""
Unit tests for the 3D Terrain Slope Analysis feature in Shiggaon Watershed Intelligence.
Verifies DEM-derived slope calculations, physical bounds, monotonic consistency,
catchment-level slope statistics across all 66 micro-watersheds, and freeze integrity.
"""

import json
from pathlib import Path
import pytest

ROOT = Path(__file__).resolve().parents[3]
TERRAIN_JSON = ROOT / "frontend" / "public" / "data" / "shiggaon_dem_terrain.json"
SOURCE_DEM = ROOT / "backend" / "model_2" / "Data" / "raw" / "Shiggaon_Taluk_DEM_GLO30" / "Shiggaon_Taluk_DEM_GLO30.tif"
MODEL1_PATH = ROOT / "model1" / "model1_lulc" / "models" / "lulc_random_forest.joblib"
MODEL2_PATH = ROOT / "backend" / "model_2" / "models" / "model2_live_iot_isolation_forest.joblib"


@pytest.fixture
def dem_payload():
    assert TERRAIN_JSON.exists(), f"Missing terrain json: {TERRAIN_JSON}"
    with open(TERRAIN_JSON, "r", encoding="utf-8") as f:
        return json.load(f)


def test_terrain_json_contains_all_66_mws_slope_statistics(dem_payload):
    stats = dem_payload["mws_elevation_stats"]
    # Filter out g_mws alias keys to get exact unique MWS units
    unique_mws = {k: v for k, v in stats.items() if not k.startswith("g_mws")}
    assert len(unique_mws) == 66, f"Expected 66 MWS units, got {len(unique_mws)}"

    for mws_code, data in unique_mws.items():
        assert "slope_min" in data, f"{mws_code} missing slope_min"
        assert "slope_max" in data, f"{mws_code} missing slope_max"
        assert "slope_mean" in data, f"{mws_code} missing slope_mean"


def test_slope_values_physical_bounds(dem_payload):
    stats = dem_payload["mws_elevation_stats"]
    unique_mws = {k: v for k, v in stats.items() if not k.startswith("g_mws")}

    for mws_code, data in unique_mws.items():
        s_min = data["slope_min"]
        s_max = data["slope_max"]
        s_mean = data["slope_mean"]

        # Slopes in degrees must be non-negative and physically plausible (<90 deg)
        assert 0.0 <= s_min <= 10.0, f"{mws_code}: slope_min {s_min} out of bounds"
        assert 0.5 <= s_max <= 60.0, f"{mws_code}: slope_max {s_max} out of bounds"
        assert 0.4 <= s_mean <= 25.0, f"{mws_code}: slope_mean {s_mean} out of bounds"


def test_slope_monotonic_order(dem_payload):
    stats = dem_payload["mws_elevation_stats"]
    unique_mws = {k: v for k, v in stats.items() if not k.startswith("g_mws")}

    for mws_code, data in unique_mws.items():
        s_min = data["slope_min"]
        s_max = data["slope_max"]
        s_mean = data["slope_mean"]
        assert s_min <= s_mean <= s_max, (
            f"{mws_code}: Slope values violated monotonic order: min={s_min}, mean={s_mean}, max={s_max}"
        )


def test_golden_catchment_4D4F2m3_slope_statistics(dem_payload):
    stats = dem_payload["mws_elevation_stats"]
    assert "4D4F2m3" in stats
    golden = stats["4D4F2m3"]

    # Valley/agricultural catchment in lowlands
    assert golden["id"] == "g_mws.240575"
    assert golden["MWS"] == "4D4F2m3"
    assert golden["slope_min"] == 0.0
    assert golden["slope_max"] == 2.7
    assert golden["slope_mean"] == 0.7


def test_steep_catchment_slope_statistics(dem_payload):
    stats = dem_payload["mws_elevation_stats"]
    assert "5B1A6p3" in stats
    steep = stats["5B1A6p3"]

    # Highest relief catchment in Shiggaon (169.4m relief)
    assert steep["slope_min"] == 0.1
    assert steep["slope_max"] >= 30.0, f"Expected steep slope >= 30.0 deg, got {steep['slope_max']}"
    assert steep["slope_mean"] >= 4.5, f"Expected mean slope >= 4.5 deg, got {steep['slope_mean']}"


def test_source_dem_and_production_models_untouched():
    assert SOURCE_DEM.exists()
    assert SOURCE_DEM.stat().st_size == 2_068_713, "Source DEM file was unexpectedly modified"

    if MODEL1_PATH.exists():
        assert MODEL1_PATH.stat().st_size == 55_677_825, "Model 1 production joblib was unexpectedly modified"

    if MODEL2_PATH.exists():
        assert MODEL2_PATH.stat().st_size == 4_183_475, "Model 2 production joblib was unexpectedly modified"
