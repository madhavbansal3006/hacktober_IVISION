import geopandas as gpd
import pytest
from shapely.geometry import box

from src.watershed_locator import WatershedLocator
from tests.synthetic_geometries import (
    POINT_FAR_OUTSIDE,
    POINT_IN_GAP,
    POINT_INSIDE_W1,
    POINT_INSIDE_W2,
    POINT_OUTSIDE_BOUNDARY_IN_W2,
    make_duplicate_id_watersheds_gpkg,
    make_watersheds_gpkg,
    make_wrong_crs_gpkg,
)


class TestSyntheticWatersheds:
    def test_point_in_w1(self, tmp_path):
        path = tmp_path / "watersheds.gpkg"
        make_watersheds_gpkg(path)
        locator = WatershedLocator(path)
        match = locator.locate(POINT_INSIDE_W1)
        assert match is not None
        assert match.micro_watershed_id == "W1"
        assert match.mws_code == "MWS-A"
        assert match.match_type == "unique"

    def test_point_in_w2_which_extends_beyond_boundary(self, tmp_path):
        """
        W2 extends beyond the study-area boundary (x up to 15 vs boundary's
        x=10). The watershed locator has no concept of the boundary at all
        -- it should match correctly regardless, since containment is
        evaluated purely against the watershed polygon.
        """
        path = tmp_path / "watersheds.gpkg"
        make_watersheds_gpkg(path)
        locator = WatershedLocator(path)
        match = locator.locate(POINT_INSIDE_W2)
        assert match is not None
        assert match.micro_watershed_id == "W2"
        assert match.mws_code == "MWS-B"

    def test_point_in_w2_extended_area_still_matches_even_outside_boundary(self, tmp_path):
        """
        A point that is OUTSIDE the study boundary but inside W2's extended
        footprint still resolves to a watershed match at the locator level
        -- it is the caller's (SpatialAnalyzer's) job to have already
        excluded this point via the boundary check first.
        """
        path = tmp_path / "watersheds.gpkg"
        make_watersheds_gpkg(path)
        locator = WatershedLocator(path)
        match = locator.locate(POINT_OUTSIDE_BOUNDARY_IN_W2)
        assert match is not None
        assert match.micro_watershed_id == "W2"

    def test_point_in_gap_returns_none(self, tmp_path):
        path = tmp_path / "watersheds.gpkg"
        make_watersheds_gpkg(path)
        locator = WatershedLocator(path)
        assert locator.locate(POINT_IN_GAP) is None

    def test_point_far_outside_returns_none(self, tmp_path):
        path = tmp_path / "watersheds.gpkg"
        make_watersheds_gpkg(path)
        locator = WatershedLocator(path)
        assert locator.locate(POINT_FAR_OUTSIDE) is None

    def test_shared_edge_point_resolves_deterministically(self, tmp_path):
        """Point exactly on the shared edge between W1 and W2 (x=5) should
        intersect both and resolve via the smallest-area tiebreak, not error."""
        path = tmp_path / "watersheds.gpkg"
        make_watersheds_gpkg(path)
        locator = WatershedLocator(path)
        from shapely.geometry import Point

        shared_edge_point = Point(5, 2)  # on the boundary between W1 (0-5) and W2 (5-15)
        match = locator.locate(shared_edge_point)
        assert match is not None
        assert match.match_type == "multiple_candidates_smallest_area_selected"
        assert match.candidate_count == 2
        # W1 (5x5=25 area) is smaller than W2 (10x10=100 area) -> W1 wins
        assert match.micro_watershed_id == "W1"

    def test_duplicate_id_raises(self, tmp_path):
        path = tmp_path / "dup_watersheds.gpkg"
        make_duplicate_id_watersheds_gpkg(path)
        with pytest.raises(ValueError, match="not unique"):
            WatershedLocator(path)

    def test_wrong_crs_raises(self, tmp_path):
        path = tmp_path / "watersheds_bad_crs.gpkg"
        make_wrong_crs_gpkg(path, box(0, 0, 5, 5))
        with pytest.raises(ValueError, match="CRS"):
            WatershedLocator(path)

    def test_missing_required_field_raises(self, tmp_path):
        path = tmp_path / "missing_field_watersheds.gpkg"
        gdf = gpd.GeoDataFrame(
            {"id": ["W1"]},  # MWS field missing entirely
            geometry=[box(0, 0, 5, 5)],
            crs="EPSG:4326",
        )
        gdf.to_file(path, driver="GPKG")
        with pytest.raises(ValueError, match="MWS"):
            WatershedLocator(path)


class TestRealShiggaonWatersheds:
    """Integration tests against the actual audited dataset (66 features)."""

    def test_loads_all_66_watersheds(self):
        locator = WatershedLocator()
        assert len(locator._gdf) == 66

    def test_representative_point_of_boundary_matches_some_watershed(self):
        boundary_gdf = gpd.read_file(
            "data/raw/study_area/shiggaon_boundary.gpkg"
        )
        rep_point = boundary_gdf.geometry.iloc[0].representative_point()
        locator = WatershedLocator()
        match = locator.locate(rep_point)
        assert match is not None
        assert match.micro_watershed_id  # non-empty
        assert match.mws_code
