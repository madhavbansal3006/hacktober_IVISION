import dataclasses

import geopandas as gpd
import numpy as np
import pytest
import rasterio
from pyproj import Transformer
from affine import Affine
from shapely.geometry import box

from rasterio.transform import rowcol


def _from_origin(west, north, xsize, ysize):
    """Equivalent to rasterio.transform.from_origin, built directly to
    avoid that helper's internal PendingDeprecationWarning (matmul vs mul)."""
    return Affine(xsize, 0.0, west, 0.0, -ysize, north)

from src.boundary_checker import BoundaryChecker
from src.geo_lulc_analyzer import STATUS_OK, GeoCodedCoreResult, GeoLULCAnalyzer
from src.lulc_query import STATUS_NODATA_PIXEL, LULCQuery
from src.spatial_analyzer import STATUS_NO_WATERSHED_MATCH, STATUS_OUTSIDE_STUDY_AREA, SpatialAnalyzer
from src.watershed_locator import WatershedLocator

# Small-scale synthetic geometries anchored near REAL Shiggaon coordinates
# (~15N, 75E) so that reprojection into EPSG:32643 behaves sensibly --
# unlike the 0-10 degree grid in synthetic_geometries.py (fine for
# boundary/watershed-only tests, but meaningless once a real UTM zone
# reprojection is involved).
#
# Layout (lon=x, lat=y), degrees:
#   boundary: (75.000, 15.000) to (75.010, 15.010)
#   W1:       (75.000, 15.000) to (75.005, 15.005)         -- inside boundary
#   W2:       (75.005, 15.000) to (75.020, 15.010)         -- extends past boundary (lon > 75.010)
#   gap:      (75.000, 15.005) to (75.005, 15.010)         -- inside boundary, no watershed

_BOUNDARY_BOX = box(75.000, 15.000, 75.010, 15.010)
_W1_BOX = box(75.000, 15.000, 75.005, 15.005)
_W2_BOX = box(75.005, 15.000, 75.020, 15.010)

POINT_IN_W1 = (15.002, 75.002)                 # (lat, lon) -- gets an assigned LULC value
POINT_IN_W2_BEYOND_BOUNDARY_EDGE = (15.002, 75.008)  # inside boundary AND W2
POINT_OUTSIDE_BOUNDARY_IN_W2 = (15.002, 75.015)      # outside boundary, inside W2's extension
POINT_IN_GAP = (15.008, 75.002)                # inside boundary, no watershed
POINT_NODATA_IN_W1 = (15.001, 75.0015)         # inside boundary + W1, but raster left as NoData here
POINT_FAR_OUTSIDE = (0.0, 0.0)

_UTM43N_FROM_WGS84 = Transformer.from_crs("EPSG:4326", "EPSG:32643", always_xy=True)


def _make_boundary(path):
    gpd.GeoDataFrame({"name": ["b"]}, geometry=[_BOUNDARY_BOX], crs="EPSG:4326").to_file(
        path, driver="GPKG"
    )


def _make_watersheds(path):
    gpd.GeoDataFrame(
        {"id": ["W1", "W2"], "MWS": ["MWS-A", "MWS-B"]},
        geometry=[_W1_BOX, _W2_BOX],
        crs="EPSG:4326",
    ).to_file(path, driver="GPKG")


def _make_raster(path, assignments, pixel_size_m=10, pad_m=200, background=0):
    """
    assignments: dict of (lat, lon) -> raw class value to bake into the
    raster at that point's pixel. Everything else is left as background
    (default 0 == NoData).
    """
    utm_points = {ll: _UTM43N_FROM_WGS84.transform(ll[1], ll[0]) for ll in assignments}
    xs = [p[0] for p in utm_points.values()]
    ys = [p[1] for p in utm_points.values()]
    minx, maxx = min(xs) - pad_m, max(xs) + pad_m
    miny, maxy = min(ys) - pad_m, max(ys) + pad_m
    width = int((maxx - minx) / pixel_size_m) + 1
    height = int((maxy - miny) / pixel_size_m) + 1
    transform = _from_origin(minx, maxy, pixel_size_m, pixel_size_m)

    array = np.full((height, width), background, dtype=np.uint8)
    for ll, value in assignments.items():
        x, y = utm_points[ll]
        row, col = rowcol(transform, x, y)
        array[row, col] = value

    with rasterio.open(
        path, "w", driver="GTiff", height=height, width=width, count=1,
        dtype=array.dtype, crs="EPSG:32643", transform=transform, nodata=0,
    ) as dst:
        dst.write(array, 1)


def _build_analyzer(tmp_path):
    boundary_path = tmp_path / "boundary.gpkg"
    watershed_path = tmp_path / "watersheds.gpkg"
    raster_path = tmp_path / "lulc.tif"

    _make_boundary(boundary_path)
    _make_watersheds(watershed_path)
    _make_raster(
        raster_path,
        assignments={
            POINT_IN_W1: 2,                        # Agriculture
            POINT_IN_W2_BEYOND_BOUNDARY_EDGE: 4,    # Built-up
            POINT_OUTSIDE_BOUNDARY_IN_W2: 5,        # Barren -- should never surface (outside boundary)
            POINT_IN_GAP: 1,                        # Forest
            # POINT_NODATA_IN_W1 intentionally left unassigned -> background/NoData
        },
    )

    return GeoLULCAnalyzer(
        spatial_analyzer=SpatialAnalyzer(
            boundary_checker=BoundaryChecker(boundary_path),
            watershed_locator=WatershedLocator(watershed_path),
        ),
        lulc_query=LULCQuery(raster_path),
    )


class TestGeoLULCAnalyzer:
    def test_ok_status_full_resolution(self, tmp_path):
        analyzer = _build_analyzer(tmp_path)
        lat, lon = POINT_IN_W1
        result = analyzer.analyze(lat, lon)

        assert result.status == STATUS_OK
        assert result.inside_study_area is True
        assert result.micro_watershed_id == "W1"
        assert result.mws_code == "MWS-A"
        assert result.lulc_value == 2
        assert result.lulc_class == "Agriculture"
        assert result.raster_pixel_row is not None
        assert result.raster_pixel_col is not None

    def test_ok_status_watershed_extending_beyond_boundary(self, tmp_path):
        analyzer = _build_analyzer(tmp_path)
        lat, lon = POINT_IN_W2_BEYOND_BOUNDARY_EDGE
        result = analyzer.analyze(lat, lon)

        assert result.status == STATUS_OK
        assert result.micro_watershed_id == "W2"
        assert result.lulc_value == 4
        assert result.lulc_class == "Built-up"

    def test_outside_study_area_skips_lulc_query_entirely(self, tmp_path):
        """
        This point's raster pixel is deliberately set to 5 (Barren), and is
        inside watershed W2 -- but it's OUTSIDE the study boundary. The
        combined result must show OUTSIDE_STUDY_AREA with lulc_value=None,
        proving the analyzer short-circuits before ever querying the
        raster for this point, not merely that it discards the answer.
        """
        analyzer = _build_analyzer(tmp_path)
        lat, lon = POINT_OUTSIDE_BOUNDARY_IN_W2
        result = analyzer.analyze(lat, lon)

        assert result.status == STATUS_OUTSIDE_STUDY_AREA
        assert result.inside_study_area is False
        assert result.micro_watershed_id is None
        assert result.mws_code is None
        assert result.lulc_value is None
        assert result.lulc_class is None

    def test_no_watershed_match_but_lulc_still_resolved(self, tmp_path):
        analyzer = _build_analyzer(tmp_path)
        lat, lon = POINT_IN_GAP
        result = analyzer.analyze(lat, lon)

        assert result.status == STATUS_NO_WATERSHED_MATCH
        assert result.inside_study_area is True
        assert result.micro_watershed_id is None
        assert result.mws_code is None
        # LULC was still queried and resolved despite the watershed gap
        assert result.lulc_value == 1
        assert result.lulc_class == "Forest"

    def test_nodata_pixel_status(self, tmp_path):
        analyzer = _build_analyzer(tmp_path)
        lat, lon = POINT_NODATA_IN_W1
        result = analyzer.analyze(lat, lon)

        assert result.status == STATUS_NODATA_PIXEL
        assert result.inside_study_area is True
        assert result.micro_watershed_id == "W1"  # watershed lookup still succeeded
        assert result.lulc_value == 0
        assert result.lulc_class == "NODATA"

    def test_far_outside_everything(self, tmp_path):
        analyzer = _build_analyzer(tmp_path)
        lat, lon = POINT_FAR_OUTSIDE
        result = analyzer.analyze(lat, lon)
        assert result.status == STATUS_OUTSIDE_STUDY_AREA
        assert result.lulc_value is None


class TestStatusPriorityResolution:
    """
    Direct tests of `_resolve_status`, isolated from the full analyzer, so
    the priority ordering itself is independently verified and can be
    changed later (per STATUS_PRIORITY's docstring) with confidence these
    tests will catch any accidental behavior change.
    """

    def test_only_no_watershed_match_active(self):
        from src.geo_lulc_analyzer import STATUS_OK, _resolve_status
        from src.lulc_query import STATUS_OK as LULC_OK
        from src.spatial_analyzer import STATUS_NO_WATERSHED_MATCH

        assert _resolve_status(STATUS_NO_WATERSHED_MATCH, LULC_OK) == STATUS_NO_WATERSHED_MATCH

    def test_only_nodata_pixel_active(self):
        from src.geo_lulc_analyzer import _resolve_status
        from src.lulc_query import STATUS_NODATA_PIXEL
        from src.spatial_analyzer import STATUS_WATERSHED_MATCHED

        assert _resolve_status(STATUS_WATERSHED_MATCHED, STATUS_NODATA_PIXEL) == STATUS_NODATA_PIXEL

    def test_no_watershed_match_outranks_nodata_pixel(self):
        """Both conditions true at once -> NO_WATERSHED_MATCH wins per
        current STATUS_PRIORITY ordering."""
        from src.geo_lulc_analyzer import _resolve_status
        from src.lulc_query import STATUS_NODATA_PIXEL
        from src.spatial_analyzer import STATUS_NO_WATERSHED_MATCH

        assert (
            _resolve_status(STATUS_NO_WATERSHED_MATCH, STATUS_NODATA_PIXEL)
            == STATUS_NO_WATERSHED_MATCH
        )

    def test_outside_raster_extent_outranks_no_watershed_match(self):
        from src.geo_lulc_analyzer import _resolve_status
        from src.lulc_query import STATUS_OUTSIDE_RASTER_EXTENT
        from src.spatial_analyzer import STATUS_NO_WATERSHED_MATCH

        assert (
            _resolve_status(STATUS_NO_WATERSHED_MATCH, STATUS_OUTSIDE_RASTER_EXTENT)
            == STATUS_OUTSIDE_RASTER_EXTENT
        )

    def test_nothing_active_resolves_ok(self):
        from src.geo_lulc_analyzer import STATUS_OK, _resolve_status
        from src.lulc_query import STATUS_OK as LULC_OK
        from src.spatial_analyzer import STATUS_WATERSHED_MATCHED

        assert _resolve_status(STATUS_WATERSHED_MATCHED, LULC_OK) == STATUS_OK


class TestSchemaCompatibility:
    """
    Verifies GeoCodedCoreResult's field set matches what the Phase 2
    architecture doc's JSON schema specifies for the geospatial/LULC
    portion, so a teammate consuming this later isn't surprised by a
    missing or renamed key.
    """

    def test_core_schema_fields_present(self):
        expected_fields = {
            "latitude",
            "longitude",
            "status",
            "inside_study_area",
            "micro_watershed_id",
            "mws_code",
            "lulc_value",
            "lulc_class",
            "raster_pixel_row",
            "raster_pixel_col",
            # Phase 5 additions beyond the original Phase 2 schema:
            "lulc_neighborhood_window_size",
            "lulc_neighborhood_class_purity_pct",
            "lulc_neighborhood_nodata_pct",
        }
        actual_fields = {f.name for f in dataclasses.fields(GeoCodedCoreResult)}
        assert actual_fields == expected_fields

    def test_result_is_json_serializable(self, tmp_path):
        import json

        analyzer = _build_analyzer(tmp_path)
        result = analyzer.analyze(*POINT_IN_W1)
        # dataclasses.asdict + json.dumps must not raise -- this is what
        # Phase 6's CSV/JSON writer will rely on.
        payload = json.dumps(dataclasses.asdict(result))
        parsed = json.loads(payload)
        assert parsed["lulc_class"] == "Agriculture"
        assert parsed["micro_watershed_id"] == "W1"
