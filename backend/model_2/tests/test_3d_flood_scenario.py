"""
Unit tests for the 3D Flood Scenario feature in the Shiggaon Watershed Intelligence System.
Validates terrain-based threshold logic, MWS intersection calculations, and data integrity.
"""

import json
from pathlib import Path
import numpy as np
import pytest

ROOT = Path(__file__).resolve().parents[3]
TERRAIN_JSON = ROOT / "frontend" / "public" / "data" / "shiggaon_dem_terrain.json"
SOURCE_DEM = ROOT / "backend" / "model_2" / "Data" / "raw" / "Shiggaon_Taluk_DEM_GLO30" / "Shiggaon_Taluk_DEM_GLO30.tif"
MODEL1_JOB = ROOT / "model1" / "model1_lulc" / "models" / "lulc_random_forest.joblib"
MODEL2_JOB = ROOT / "backend" / "model_2" / "models" / "model2_live_iot_isolation_forest.joblib"


@pytest.fixture
def dem_payload():
    assert TERRAIN_JSON.exists(), f"Terrain file missing: {TERRAIN_JSON}"
    with open(TERRAIN_JSON, "r", encoding="utf-8") as f:
        return json.load(f)


def test_flood_scenario_elevation_bounds(dem_payload):
    min_elev = dem_payload["min_elevation"]
    max_elev = dem_payload["max_elevation"]

    # Authentic Copernicus GLO-30 DEM range
    assert 535.0 <= min_elev <= 545.0
    assert 720.0 <= max_elev <= 745.0


def test_terrain_threshold_flood_extent_monotonicity(dem_payload):
    elevs = np.array(dem_payload["elevations"])
    min_elev = dem_payload["min_elevation"]
    taluk_cells = elevs[elevs >= min_elev]
    total_taluk = taluk_cells.size

    # Evaluate flood cell count at progressive water levels
    levels = [550.0, 570.0, 600.0, 630.0, 660.0]
    flooded_counts = [np.sum((elevs >= min_elev) & (elevs <= lvl)) for lvl in levels]

    # Monotonicity check: higher water level must strictly increase or equal flooded cells
    for i in range(len(flooded_counts) - 1):
        assert flooded_counts[i] <= flooded_counts[i + 1], "Flood extent must grow monotonically with water level"

    # Percentage flooded at baseline (550m) should be small (deepest valley outlet only, < 2%)
    assert flooded_counts[0] / total_taluk < 0.02
    # Percentage at 660m should be significant (> 70%)
    assert flooded_counts[-1] / total_taluk > 0.70


def test_mws_intersection_deterministic_calculation(dem_payload):
    stats = {k: v for k, v in dem_payload["mws_elevation_stats"].items() if not k.startswith("g_mws")}
    assert len(stats) == 66, "Must contain all 66 authoritative MWS units"

    def count_affected(water_level):
        return sum(1 for mws, s in stats.items() if s["min"] <= water_level)

    # Specific calibrated thresholds
    assert count_affected(550.0) == 6
    assert count_affected(570.0) == 13
    assert count_affected(600.0) == 29
    assert count_affected(620.0) == 43
    assert count_affected(640.0) == 56


def test_golden_catchment_4D4F2m3_threshold_behavior(dem_payload):
    stats = dem_payload["mws_elevation_stats"]
    golden = stats["4D4F2m3"]

    assert golden["id"] == "g_mws.240575"
    assert golden["MWS"] == "4D4F2m3"
    assert round(golden["min"], 1) == 621.1

    # At default scenario level (570m), 4D4F2m3 is upland (unaffected)
    assert golden["min"] > 570.0, "4D4F2m3 must remain unaffected at 570m"

    # At 625m water level, 4D4F2m3 lowlands intersect the scenario extent
    assert golden["min"] <= 625.0, "4D4F2m3 must be affected when water level reaches 625m"


def test_reset_scenario_baseline(dem_payload):
    baseline_level = 540.0
    stats = {k: v for k, v in dem_payload["mws_elevation_stats"].items() if not k.startswith("g_mws")}
    # At 540m, only the lowest outlet MWS are at the threshold
    affected_at_baseline = sum(1 for mws, s in stats.items() if s["min"] <= baseline_level)
    assert affected_at_baseline <= 2


def test_production_models_and_source_dem_unchanged():
    assert SOURCE_DEM.stat().st_size == 2_068_713, "Source DEM file was unexpectedly modified"
    assert MODEL1_JOB.stat().st_size == 55_677_825, "Model 1 production artifact was unexpectedly modified"
    assert MODEL2_JOB.stat().st_size == 4_183_475, "Model 2 artifact was unexpectedly modified"
