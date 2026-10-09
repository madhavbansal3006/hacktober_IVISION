import geopandas as gpd
from shapely.geometry import Point

from src.boundary_checker import BoundaryChecker
from src.spatial_analyzer import (
    STATUS_NO_WATERSHED_MATCH,
    STATUS_OUTSIDE_STUDY_AREA,
    STATUS_WATERSHED_MATCHED,
    SpatialAnalyzer,
)
from src.watershed_locator import WatershedLocator
from tests.synthetic_geometries import (
    POINT_FAR_OUTSIDE,
    POINT_IN_GAP,
    POINT_INSIDE_W1,
    POINT_INSIDE_W2,
    POINT_OUTSIDE_BOUNDARY_IN_W2,
    make_boundary_gpkg,
    make_watersheds_gpkg,
)


def _build_analyzer(tmp_path):
    boundary_path = tmp_path / "boundary.gpkg"
    watershed_path = tmp_path / "watersheds.gpkg"
    make_boundary_gpkg(boundary_path)
    make_watersheds_gpkg(watershed_path)
    return SpatialAnalyzer(
        boundary_checker=BoundaryChecker(boundary_path),
        watershed_locator=WatershedLocator(watershed_path),
    )


class TestSpatialAnalyzerSynthetic:
    def test_inside_boundary_and_watershed(self, tmp_path):
        analyzer = _build_analyzer(tmp_path)
        result = analyzer.analyze(latitude=POINT_INSIDE_W1.y, longitude=POINT_INSIDE_W1.x)
        assert result.inside_study_area is True
        assert result.status == STATUS_WATERSHED_MATCHED
        assert result.micro_watershed_id == "W1"
        assert result.mws_code == "MWS-A"

    def test_inside_boundary_and_watershed_that_extends_beyond(self, tmp_path):
        analyzer = _build_analyzer(tmp_path)
        result = analyzer.analyze(latitude=POINT_INSIDE_W2.y, longitude=POINT_INSIDE_W2.x)
        assert result.inside_study_area is True
        assert result.status == STATUS_WATERSHED_MATCHED
        assert result.micro_watershed_id == "W2"

    def test_outside_boundary_short_circuits_before_watershed_lookup(self, tmp_path):
        """
        This point IS inside watershed W2's extended footprint, but is
        OUTSIDE the study boundary. Boundary must be checked first --
        result must be OUTSIDE_STUDY_AREA with no watershed id returned,
        even though a watershed lookup would technically succeed.
        """
        analyzer = _build_analyzer(tmp_path)
        result = analyzer.analyze(
            latitude=POINT_OUTSIDE_BOUNDARY_IN_W2.y,
            longitude=POINT_OUTSIDE_BOUNDARY_IN_W2.x,
        )
        assert result.inside_study_area is False
        assert result.status == STATUS_OUTSIDE_STUDY_AREA
        assert result.micro_watershed_id is None
        assert result.mws_code is None

    def test_far_outside_everything(self, tmp_path):
        analyzer = _build_analyzer(tmp_path)
        result = analyzer.analyze(
            latitude=POINT_FAR_OUTSIDE.y, longitude=POINT_FAR_OUTSIDE.x
        )
        assert result.inside_study_area is False
        assert result.status == STATUS_OUTSIDE_STUDY_AREA

    def test_inside_boundary_but_in_watershed_gap(self, tmp_path):
        analyzer = _build_analyzer(tmp_path)
        result = analyzer.analyze(latitude=POINT_IN_GAP.y, longitude=POINT_IN_GAP.x)
        assert result.inside_study_area is True
        assert result.status == STATUS_NO_WATERSHED_MATCH
        assert result.micro_watershed_id is None
        assert result.mws_code is None

    def test_result_echoes_input_coordinates(self, tmp_path):
        analyzer = _build_analyzer(tmp_path)
        result = analyzer.analyze(latitude=2.5, longitude=3.5)
        assert result.latitude == 2.5
        assert result.longitude == 3.5


class TestSpatialAnalyzerRealData:
    """Integration test against actual Shiggaon datasets, default paths."""

    def test_representative_point_end_to_end(self):
        analyzer = SpatialAnalyzer()
        boundary_gdf = gpd.read_file(
            "data/raw/study_area/shiggaon_boundary.gpkg"
        )
        rep_point = boundary_gdf.geometry.iloc[0].representative_point()
        result = analyzer.analyze(latitude=rep_point.y, longitude=rep_point.x)
        assert result.inside_study_area is True
        assert result.status in (STATUS_WATERSHED_MATCHED, STATUS_NO_WATERSHED_MATCH)

    def test_arabian_sea_point_is_outside(self):
        analyzer = SpatialAnalyzer()
        result = analyzer.analyze(latitude=15.0, longitude=65.0)
        assert result.inside_study_area is False
        assert result.status == STATUS_OUTSIDE_STUDY_AREA
        assert result.micro_watershed_id is None
