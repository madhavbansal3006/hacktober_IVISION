from datetime import datetime

import geopandas as gpd
import pytest

from src.geo_lulc_analyzer import GeoLULCAnalyzer
from src.image_analyzer import analyze_image
from src.schema import (
    STATUS_ERROR,
    STATUS_INVALID_COORDINATE,
    STATUS_MALFORMED_GPS,
    STATUS_NO_GPS,
)
from src.spatial_analyzer import STATUS_OUTSIDE_STUDY_AREA
from tests.make_fixtures import make_valid_gps_image

# Real Shiggaon boundary representative point (guaranteed interior),
# computed fresh from the actual dataset rather than hardcoded.
_BOUNDARY_GDF = gpd.read_file("data/raw/study_area/shiggaon_boundary.gpkg")
_REAL_INSIDE_POINT = _BOUNDARY_GDF.geometry.iloc[0].representative_point()

_ARABIAN_SEA_LAT, _ARABIAN_SEA_LON = 15.0, 65.0  # clearly outside Shiggaon


@pytest.fixture(scope="module")
def analyzer():
    return GeoLULCAnalyzer()


class TestValidImages:
    def test_image_inside_study_area_end_to_end(self, tmp_path, analyzer):
        path = tmp_path / "inside.jpg"
        make_valid_gps_image(path, lat=_REAL_INSIDE_POINT.y, lon=_REAL_INSIDE_POINT.x)

        result = analyze_image(path, analyzer)

        assert result.image_name == "inside.jpg"
        assert result.error_reason is None
        assert result.inside_study_area is True
        assert result.latitude == pytest.approx(_REAL_INSIDE_POINT.y, abs=1e-3)
        assert result.longitude == pytest.approx(_REAL_INSIDE_POINT.x, abs=1e-3)
        # exact status depends on real watershed/raster coverage at this
        # point, which we don't hardcode -- just assert it's one of the
        # "inside boundary" statuses, not a failure status.
        assert result.status not in (
            STATUS_NO_GPS,
            STATUS_MALFORMED_GPS,
            STATUS_INVALID_COORDINATE,
            STATUS_ERROR,
            STATUS_OUTSIDE_STUDY_AREA,
        )

    def test_processing_timestamp_is_valid_iso8601(self, tmp_path, analyzer):
        path = tmp_path / "inside.jpg"
        make_valid_gps_image(path, lat=_REAL_INSIDE_POINT.y, lon=_REAL_INSIDE_POINT.x)
        result = analyze_image(path, analyzer)
        # must not raise
        datetime.fromisoformat(result.processing_timestamp)

    def test_image_outside_study_area(self, tmp_path, analyzer):
        path = tmp_path / "outside.jpg"
        make_valid_gps_image(path, lat=_ARABIAN_SEA_LAT, lon=_ARABIAN_SEA_LON)

        result = analyze_image(path, analyzer)

        assert result.status == STATUS_OUTSIDE_STUDY_AREA
        assert result.inside_study_area is False
        assert result.error_reason is None
        assert result.micro_watershed_id is None
        assert result.lulc_value is None


class TestFailureModes:
    def test_no_gps_image(self, tmp_path, analyzer):
        from tests.make_fixtures import make_no_gps_image

        path = tmp_path / "no_gps.jpg"
        make_no_gps_image(path)

        result = analyze_image(path, analyzer)

        assert result.status == STATUS_NO_GPS
        assert result.error_reason is not None
        assert result.latitude is None
        assert result.inside_study_area is None

    def test_malformed_gps_image(self, tmp_path, analyzer):
        from tests.make_fixtures import make_malformed_gps_image

        path = tmp_path / "malformed.jpg"
        make_malformed_gps_image(path, "bad_ref")

        result = analyze_image(path, analyzer)

        assert result.status == STATUS_MALFORMED_GPS
        assert result.error_reason is not None

    def test_out_of_range_coordinate_image(self, tmp_path, analyzer):
        from tests.make_fixtures import make_out_of_range_image

        path = tmp_path / "out_of_range.jpg"
        make_out_of_range_image(path)

        result = analyze_image(path, analyzer)

        assert result.status == STATUS_INVALID_COORDINATE
        assert result.error_reason is not None

    def test_nonexistent_file(self, tmp_path, analyzer):
        path = tmp_path / "does_not_exist.jpg"
        result = analyze_image(path, analyzer)

        assert result.status == STATUS_ERROR
        assert result.error_reason is not None
        assert result.image_name == "does_not_exist.jpg"

    def test_failure_result_does_not_raise(self, tmp_path, analyzer):
        """The core contract: analyze_image must NEVER raise, even for a
        completely broken input."""
        path = tmp_path / "not_an_image.jpg"
        path.write_bytes(b"this is not a jpeg at all")

        result = analyze_image(path, analyzer)  # must not raise
        assert result.status == STATUS_ERROR
        assert result.error_reason is not None
