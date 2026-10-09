import geopandas as gpd
import pytest

from src.geo_lulc_analyzer import GeoLULCAnalyzer
from src.pipeline import find_images, run_pipeline
from src.schema import STATUS_ERROR, STATUS_MALFORMED_GPS, STATUS_NO_GPS
from src.spatial_analyzer import STATUS_OUTSIDE_STUDY_AREA
from tests.make_fixtures import (
    make_malformed_gps_image,
    make_no_gps_image,
    make_valid_gps_image,
)

_BOUNDARY_GDF = gpd.read_file("data/raw/study_area/shiggaon_boundary.gpkg")
_REAL_INSIDE_POINT = _BOUNDARY_GDF.geometry.iloc[0].representative_point()


@pytest.fixture(scope="module")
def analyzer():
    return GeoLULCAnalyzer()


class TestFindImages:
    def test_finds_jpg_and_jpeg_case_insensitively(self, tmp_path):
        (tmp_path / "a.jpg").write_bytes(b"x")
        (tmp_path / "b.JPG").write_bytes(b"x")
        (tmp_path / "c.jpeg").write_bytes(b"x")
        (tmp_path / "d.JPEG").write_bytes(b"x")
        (tmp_path / "notes.txt").write_bytes(b"x")
        (tmp_path / "e.png").write_bytes(b"x")

        found = find_images(tmp_path)
        names = {p.name for p in found}
        assert names == {"a.jpg", "b.JPG", "c.jpeg", "d.JPEG"}

    def test_empty_directory_returns_empty_list(self, tmp_path):
        assert find_images(tmp_path) == []


class TestRunPipeline:
    def test_mixed_batch_processes_all_images_despite_failures(self, tmp_path, analyzer):
        """
        Core requirement: one bad image must not stop the batch. Build a
        directory with a valid image, a no-GPS image, and a malformed-GPS
        image, and confirm the pipeline returns a result for ALL THREE --
        not just the ones before the first failure.
        """
        make_valid_gps_image(
            tmp_path / "valid.jpg", lat=_REAL_INSIDE_POINT.y, lon=_REAL_INSIDE_POINT.x
        )
        make_no_gps_image(tmp_path / "no_gps.jpg")
        make_malformed_gps_image(tmp_path / "malformed.jpg", "missing_field")

        results = run_pipeline(tmp_path, analyzer=analyzer)

        assert len(results) == 3
        by_name = {r.image_name: r for r in results}
        assert set(by_name.keys()) == {"valid.jpg", "no_gps.jpg", "malformed.jpg"}
        assert by_name["no_gps.jpg"].status == STATUS_NO_GPS
        assert by_name["malformed.jpg"].status == STATUS_MALFORMED_GPS
        assert by_name["valid.jpg"].status not in (STATUS_ERROR, STATUS_NO_GPS, STATUS_MALFORMED_GPS)

    def test_non_image_files_are_ignored(self, tmp_path, analyzer):
        make_valid_gps_image(
            tmp_path / "valid.jpg", lat=_REAL_INSIDE_POINT.y, lon=_REAL_INSIDE_POINT.x
        )
        (tmp_path / "readme.txt").write_text("not an image")
        (tmp_path / "data.csv").write_text("a,b,c")

        results = run_pipeline(tmp_path, analyzer=analyzer)
        assert len(results) == 1
        assert results[0].image_name == "valid.jpg"

    def test_empty_directory_returns_empty_result_list(self, tmp_path, analyzer):
        assert run_pipeline(tmp_path, analyzer=analyzer) == []

    def test_outside_study_area_image_included_in_batch(self, tmp_path, analyzer):
        make_valid_gps_image(tmp_path / "outside.jpg", lat=15.0, lon=65.0)
        results = run_pipeline(tmp_path, analyzer=analyzer)
        assert len(results) == 1
        assert results[0].status == STATUS_OUTSIDE_STUDY_AREA

    def test_reuses_single_analyzer_across_batch(self, tmp_path):
        """
        The datasets should be loaded once (via the shared `analyzer`
        fixture/argument) and reused, not reopened per image. This test
        doesn't measure timing (unreliable in CI) -- it just confirms
        passing a pre-built analyzer works and produces correct results
        for multiple images, proving the shared-instance code path.
        """
        analyzer_instance = GeoLULCAnalyzer()
        make_valid_gps_image(
            tmp_path / "a.jpg", lat=_REAL_INSIDE_POINT.y, lon=_REAL_INSIDE_POINT.x
        )
        make_valid_gps_image(
            tmp_path / "b.jpg", lat=_REAL_INSIDE_POINT.y, lon=_REAL_INSIDE_POINT.x
        )
        results = run_pipeline(tmp_path, analyzer=analyzer_instance)
        assert len(results) == 2
        assert results[0].status == results[1].status  # same point -> same outcome
