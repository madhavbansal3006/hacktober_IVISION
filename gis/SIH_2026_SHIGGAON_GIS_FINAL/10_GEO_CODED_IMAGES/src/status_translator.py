"""
status_translator.py — translates this module's internal `status` values
into the two-field vocabulary required by
SIH_2026_Shiggaon_GeoCoded_Imagery_Teammate_README.docx:

    coordinate_status: VALID / MISSING / SUSPICIOUS / OUTSIDE_STUDY_AREA
    study_area_status: INSIDE / BOUNDARY_REVIEW / OUTSIDE

This is a pure, additional OUTPUT-layer translation. The internal status
system (schema.STATUS_*, spatial_analyzer.STATUS_*, lulc_query.STATUS_*,
geo_lulc_analyzer.STATUS_OK) is not changed, removed, or bypassed by
this -- `status` remains the single source of truth for the detailed
internal pipeline outcome; these two fields are derived from it once per
image and stored alongside it.
"""

from __future__ import annotations

from typing import Optional

from . import schema


def translate_status(
    internal_status: str,
    *,
    inside_study_area: Optional[bool] = None,
    distance_to_boundary_m: Optional[float] = None,
    boundary_review_tolerance_m: Optional[float] = None,
) -> tuple[Optional[str], Optional[str]]:
    """
    Returns (coordinate_status, study_area_status). Either may be None
    when not determinable from the given inputs.

    Mapping, per the teammate README + explicit user decisions:
      NO_GPS                          -> (MISSING, None)
      MALFORMED_GPS/INVALID_COORDINATE -> (SUSPICIOUS, None)
      ERROR (unanticipated failure)    -> (None, None)
      valid coordinate, near boundary  -> (VALID, BOUNDARY_REVIEW)
      valid coordinate, inside         -> (VALID, INSIDE)
      valid coordinate, outside        -> (OUTSIDE_STUDY_AREA, OUTSIDE)

    "Near boundary" means distance_to_boundary_m <= boundary_review_tolerance_m
    (config.BOUNDARY_REVIEW_TOLERANCE_M) -- it overrides INSIDE/OUTSIDE
    regardless of which side of the boundary the point falls on, matching
    the README's framing of BOUNDARY_REVIEW as "needs review" rather than
    a third spatial category.
    """
    if internal_status == schema.STATUS_NO_GPS:
        return schema.COORD_STATUS_MISSING, None

    if internal_status in (schema.STATUS_MALFORMED_GPS, schema.STATUS_INVALID_COORDINATE):
        return schema.COORD_STATUS_SUSPICIOUS, None

    if internal_status == schema.STATUS_ERROR:
        return None, None

    # From here on, the coordinate itself was valid (internal_status is
    # one of OUTSIDE_STUDY_AREA / NO_WATERSHED_MATCH / NODATA_PIXEL /
    # OUTSIDE_RASTER_EXTENT / OK) -- inside_study_area must be known.
    if inside_study_area is None:
        return None, None

    if (
        distance_to_boundary_m is not None
        and boundary_review_tolerance_m is not None
        and distance_to_boundary_m <= boundary_review_tolerance_m
    ):
        return schema.COORD_STATUS_VALID, schema.STUDY_AREA_STATUS_BOUNDARY_REVIEW

    if inside_study_area:
        return schema.COORD_STATUS_VALID, schema.STUDY_AREA_STATUS_INSIDE

    return schema.COORD_STATUS_OUTSIDE_STUDY_AREA, schema.STUDY_AREA_STATUS_OUTSIDE
