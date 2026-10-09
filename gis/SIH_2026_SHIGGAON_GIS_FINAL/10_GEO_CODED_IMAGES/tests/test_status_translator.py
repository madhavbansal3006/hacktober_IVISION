import pytest

from src import schema
from src.status_translator import translate_status


class TestFailureModeTranslation:
    def test_no_gps_maps_to_missing(self):
        coord, area = translate_status(schema.STATUS_NO_GPS)
        assert coord == schema.COORD_STATUS_MISSING
        assert area is None

    def test_malformed_gps_maps_to_suspicious(self):
        coord, area = translate_status(schema.STATUS_MALFORMED_GPS)
        assert coord == schema.COORD_STATUS_SUSPICIOUS
        assert area is None

    def test_invalid_coordinate_maps_to_suspicious(self):
        coord, area = translate_status(schema.STATUS_INVALID_COORDINATE)
        assert coord == schema.COORD_STATUS_SUSPICIOUS
        assert area is None

    def test_error_maps_to_both_none(self):
        coord, area = translate_status(schema.STATUS_ERROR)
        assert coord is None
        assert area is None


class TestValidCoordinateTranslation:
    def test_inside_boundary_far_from_edge_is_valid_inside(self):
        coord, area = translate_status(
            "OK",
            inside_study_area=True,
            distance_to_boundary_m=5000.0,
            boundary_review_tolerance_m=15.0,
        )
        assert coord == schema.COORD_STATUS_VALID
        assert area == schema.STUDY_AREA_STATUS_INSIDE

    def test_outside_boundary_far_from_edge_is_outside(self):
        coord, area = translate_status(
            "OUTSIDE_STUDY_AREA",
            inside_study_area=False,
            distance_to_boundary_m=5000.0,
            boundary_review_tolerance_m=15.0,
        )
        assert coord == schema.COORD_STATUS_OUTSIDE_STUDY_AREA
        assert area == schema.STUDY_AREA_STATUS_OUTSIDE

    def test_inside_but_within_tolerance_is_boundary_review(self):
        coord, area = translate_status(
            "OK",
            inside_study_area=True,
            distance_to_boundary_m=10.0,
            boundary_review_tolerance_m=15.0,
        )
        assert coord == schema.COORD_STATUS_VALID
        assert area == schema.STUDY_AREA_STATUS_BOUNDARY_REVIEW

    def test_outside_but_within_tolerance_is_also_boundary_review(self):
        """BOUNDARY_REVIEW overrides INSIDE/OUTSIDE regardless of which
        side of the boundary the point falls on -- it's a 'needs review'
        flag, not a third spatial category."""
        coord, area = translate_status(
            "OUTSIDE_STUDY_AREA",
            inside_study_area=False,
            distance_to_boundary_m=10.0,
            boundary_review_tolerance_m=15.0,
        )
        assert coord == schema.COORD_STATUS_VALID
        assert area == schema.STUDY_AREA_STATUS_BOUNDARY_REVIEW

    def test_distance_exactly_at_tolerance_boundary_is_review(self):
        coord, area = translate_status(
            "OK", inside_study_area=True, distance_to_boundary_m=15.0,
            boundary_review_tolerance_m=15.0,
        )
        assert area == schema.STUDY_AREA_STATUS_BOUNDARY_REVIEW

    def test_distance_just_beyond_tolerance_is_not_review(self):
        coord, area = translate_status(
            "OK", inside_study_area=True, distance_to_boundary_m=15.01,
            boundary_review_tolerance_m=15.0,
        )
        assert area == schema.STUDY_AREA_STATUS_INSIDE

    def test_no_watershed_match_still_valid_inside(self):
        """A watershed-layer gap doesn't affect coordinate/study-area
        status at all -- those are about the coordinate and the boundary,
        not the watershed match."""
        coord, area = translate_status(
            "NO_WATERSHED_MATCH", inside_study_area=True,
            distance_to_boundary_m=5000.0, boundary_review_tolerance_m=15.0,
        )
        assert coord == schema.COORD_STATUS_VALID
        assert area == schema.STUDY_AREA_STATUS_INSIDE

    def test_missing_inside_study_area_returns_both_none(self):
        """Safety fallback: if inside_study_area wasn't determined at all
        (shouldn't normally happen), don't guess."""
        coord, area = translate_status("OK", inside_study_area=None)
        assert coord is None
        assert area is None

    def test_missing_distance_falls_back_to_inside_outside_only(self):
        """If distance couldn't be computed (e.g. boundary distance calc
        failed), BOUNDARY_REVIEW is simply never triggered -- falls back
        to plain INSIDE/OUTSIDE rather than erroring."""
        coord, area = translate_status(
            "OK", inside_study_area=True, distance_to_boundary_m=None,
            boundary_review_tolerance_m=15.0,
        )
        assert coord == schema.COORD_STATUS_VALID
        assert area == schema.STUDY_AREA_STATUS_INSIDE
