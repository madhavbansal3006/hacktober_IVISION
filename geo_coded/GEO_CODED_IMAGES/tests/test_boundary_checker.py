import geopandas as gpd
import pytest
from shapely.geometry import Point, box

from src.boundary_checker import BoundaryChecker
from tests.synthetic_geometries import (
    POINT_FAR_OUTSIDE,
    POINT_INSIDE_W1,
    make_boundary_gpkg,
    make_wrong_crs_gpkg,
)


class TestSyntheticBoundary:
    def test_point_inside_boundary(self, tmp_path):
        path = tmp_path / "boundary.gpkg"
        make_boundary_gpkg(path)
        checker = BoundaryChecker(path)
        assert checker.is_inside(POINT_INSIDE_W1) is True

    def test_point_outside_boundary(self, tmp_path):
        path = tmp_path / "boundary.gpkg"
        make_boundary_gpkg(path)
        checker = BoundaryChecker(path)
        assert checker.is_inside(POINT_FAR_OUTSIDE) is False

    def test_point_exactly_on_edge_counts_as_inside(self, tmp_path):
        path = tmp_path / "boundary.gpkg"
        make_boundary_gpkg(path)
        checker = BoundaryChecker(path)
        edge_point = Point(0, 5)  # on the left edge of the (0,0)-(10,10) square
        assert checker.is_inside(edge_point) is True

    def test_wrong_crs_raises(self, tmp_path):
        path = tmp_path / "boundary_bad_crs.gpkg"
        make_wrong_crs_gpkg(path, box(0, 0, 10, 10))
        with pytest.raises(ValueError, match="CRS"):
            BoundaryChecker(path)

    def test_multiple_features_raises(self, tmp_path):
        path = tmp_path / "multi_boundary.gpkg"
        gdf = gpd.GeoDataFrame(
            {"name": ["a", "b"]},
            geometry=[box(0, 0, 5, 5), box(5, 5, 10, 10)],
            crs="EPSG:4326",
        )
        gdf.to_file(path, driver="GPKG")
        with pytest.raises(ValueError, match="Expected exactly 1"):
            BoundaryChecker(path)


class TestDistanceToBoundary:
    """
    Uses a boundary anchored near REAL Shiggaon coordinates (~15N, 75E),
    not the far-away 0-10 degree synthetic square used elsewhere in this
    file -- EPSG:32643 (UTM zone 43N) reprojection is only meaningful
    near its actual zone; reusing the 0-10 degree square here produced
    wildly distorted (~300km) "distances" the first time this was tried.
    """

    @staticmethod
    def _make_local_boundary(path):
        gdf = gpd.GeoDataFrame(
            {"name": ["local"]},
            geometry=[box(75.000, 15.000, 75.010, 15.010)],
            crs="EPSG:4326",
        )
        gdf.to_file(path, driver="GPKG")

    def test_point_far_inside_has_large_distance(self, tmp_path):
        path = tmp_path / "boundary.gpkg"
        self._make_local_boundary(path)
        checker = BoundaryChecker(path)
        center = Point(75.005, 15.005)
        distance = checker.distance_to_boundary_m(center)
        assert distance > 0

    def test_point_exactly_on_edge_has_near_zero_distance(self, tmp_path):
        path = tmp_path / "boundary.gpkg"
        self._make_local_boundary(path)
        checker = BoundaryChecker(path)
        edge_point = Point(75.000, 15.005)  # exactly on the left edge
        distance = checker.distance_to_boundary_m(edge_point)
        assert distance == pytest.approx(0.0, abs=1.0)

    def test_point_just_outside_is_close_to_zero(self, tmp_path):
        path = tmp_path / "boundary.gpkg"
        self._make_local_boundary(path)
        checker = BoundaryChecker(path)
        just_outside = Point(74.9999, 15.005)  # ~11m past the left edge
        distance = checker.distance_to_boundary_m(just_outside)
        assert 0 < distance < 100

    def test_distance_increases_further_from_edge(self, tmp_path):
        path = tmp_path / "boundary.gpkg"
        self._make_local_boundary(path)
        checker = BoundaryChecker(path)
        near = Point(75.001, 15.005)   # near the left edge
        far = Point(75.005, 15.005)    # center
        assert checker.distance_to_boundary_m(far) > checker.distance_to_boundary_m(near)

    def test_works_on_real_shiggaon_boundary(self):
        """Integration check against the actual dataset -- just confirms
        it runs and returns a sane positive number, not a specific value."""
        checker = BoundaryChecker()  # default real Shiggaon boundary
        far_outside = Point(65.0, 15.0)  # Arabian Sea
        distance = checker.distance_to_boundary_m(far_outside)
        assert distance > 100_000  # definitely far, in meters


class TestRealShiggaonBoundary:
    """Integration tests against the actual audited dataset."""

    def test_representative_point_is_inside(self):
        checker = BoundaryChecker()
        gdf = gpd.read_file(
            "data/raw/study_area/shiggaon_boundary.gpkg"
        )
        rep_point = gdf.geometry.iloc[0].representative_point()
        assert checker.is_inside(rep_point) is True

    def test_point_far_outside_shiggaon_is_outside(self):
        checker = BoundaryChecker()
        # Point in the Arabian Sea, nowhere near Karnataka
        far_point = Point(65.0, 15.0)
        assert checker.is_inside(far_point) is False
