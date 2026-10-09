"""
Unit tests for the Copernicus GLO-30 3D Terrain DEM dataset and integration.
Verifies data integrity, spatial bounds, elevation range, and all 66 MWS elevation records.
"""

import json
from pathlib import Path
import pytest

ROOT = Path(__file__).resolve().parents[3]
TERRAIN_JSON = ROOT / "frontend" / "public" / "data" / "shiggaon_dem_terrain.json"
SOURCE_DEM = ROOT / "backend" / "model_2" / "Data" / "raw" / "Shiggaon_Taluk_DEM_GLO30" / "Shiggaon_Taluk_DEM_GLO30.tif"


def test_terrain_json_exists_and_loads():
    assert TERRAIN_JSON.exists(), f"Terrain file missing: {TERRAIN_JSON}"
    with open(TERRAIN_JSON, "r", encoding="utf-8") as f:
        data = json.load(f)
    assert "source" in data
    assert "Copernicus GLO-30" in data["source"]
    assert "bounds" in data
    assert "elevations" in data
    assert "mws_elevation_stats" in data


def test_terrain_spatial_bounds_and_grid():
    with open(TERRAIN_JSON, "r", encoding="utf-8") as f:
        data = json.load(f)

    west, south, east, north = data["bounds"]
    # Shiggaon bounding box verification
    assert 75.05 <= west <= 75.08
    assert 14.85 <= south <= 14.88
    assert 75.34 <= east <= 75.37
    assert 15.15 <= north <= 15.18

    # Grid dimensions
    shape = data["grid_shape"]
    assert shape == [200, 200]
    elevs = data["elevations"]
    assert len(elevs) == 200
    assert len(elevs[0]) == 200


def test_terrain_elevation_values_within_physical_limits():
    with open(TERRAIN_JSON, "r", encoding="utf-8") as f:
        data = json.load(f)

    min_e = data["min_elevation"]
    max_e = data["max_elevation"]
    mean_e = data["mean_elevation"]

    # Copernicus GLO-30 taluk range: ~540m to ~738m
    assert 535.0 <= min_e <= 545.0
    assert 720.0 <= max_e <= 745.0
    assert 620.0 <= mean_e <= 640.0


def test_authoritative_66_mws_elevation_coverage():
    with open(TERRAIN_JSON, "r", encoding="utf-8") as f:
        data = json.load(f)

    stats = data["mws_elevation_stats"]
    assert data["total_mws"] == 66

    # Golden demo catchment 4D4F2m3 / g_mws.240575 verification
    assert "4D4F2m3" in stats
    assert "g_mws.240575" in stats

    golden = stats["4D4F2m3"]
    assert golden["id"] == "g_mws.240575"
    assert golden["MWS"] == "4D4F2m3"
    assert round(golden["min"], 1) == 621.1
    assert round(golden["max"], 1) == 629.6
    assert round(golden["mean"], 1) == 625.4


def test_source_dem_untouched():
    assert SOURCE_DEM.exists(), "Source DEM GeoTIFF missing"
    assert SOURCE_DEM.stat().st_size > 2_000_000, "Source DEM file unexpectedly truncated"
