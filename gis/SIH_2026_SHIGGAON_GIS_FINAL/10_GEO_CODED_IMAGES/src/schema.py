"""
schema.py — the final per-image result shape, matching the Phase 2
architecture doc's JSON schema (image_name, processing_timestamp, etc.)
plus the Phase 5 diagnostic additions. Every other module (image_analyzer,
pipeline, io_writer) imports GeoCodedResult from here rather than building
a result dict/dataclass independently.
"""

from __future__ import annotations

from dataclasses import dataclass
from typing import Optional

SCHEMA_VERSION = "1.0"

# Failure-mode statuses specific to the EXIF/coordinate stage (Phase 3).
# Spatial/LULC statuses (OUTSIDE_STUDY_AREA, NO_WATERSHED_MATCH,
# NODATA_PIXEL, OK) are defined in spatial_analyzer.py / lulc_query.py /
# geo_lulc_analyzer.py and reused as-is -- not redefined here.
STATUS_NO_GPS = "NO_GPS"
STATUS_MALFORMED_GPS = "MALFORMED_GPS"
STATUS_INVALID_COORDINATE = "INVALID_COORDINATE"
STATUS_ERROR = "ERROR"

# --------------------------------------------------------------------------
# Teammate README compatibility: the two-field status vocabulary required
# by SIH_2026_Shiggaon_GeoCoded_Imagery_Teammate_README.docx. These are
# ADDITIONAL to `status` above -- the internal status system is unchanged
# and still the source of truth; these are a translation, computed once
# by src/status_translator.py and stored on GeoCodedResult alongside it.
# --------------------------------------------------------------------------
COORD_STATUS_VALID = "VALID"
COORD_STATUS_MISSING = "MISSING"
COORD_STATUS_SUSPICIOUS = "SUSPICIOUS"
COORD_STATUS_OUTSIDE_STUDY_AREA = "OUTSIDE_STUDY_AREA"

STUDY_AREA_STATUS_INSIDE = "INSIDE"
STUDY_AREA_STATUS_BOUNDARY_REVIEW = "BOUNDARY_REVIEW"
STUDY_AREA_STATUS_OUTSIDE = "OUTSIDE"


@dataclass(frozen=True)
class GeoCodedResult:
    """
    One row of the final output. All fields are present on every result
    (never a partial dict) -- fields that don't apply for a given status
    are explicitly None, not omitted. This keeps CSV output columns
    consistent across every row regardless of status.
    """

    schema_version: str
    image_name: str
    processing_timestamp: str  # ISO 8601 UTC

    latitude: Optional[float]
    longitude: Optional[float]

    status: str
    error_reason: Optional[str]

    inside_study_area: Optional[bool]
    micro_watershed_id: Optional[str]
    mws_code: Optional[str]

    lulc_value: Optional[int]
    lulc_class: Optional[str]
    raster_pixel_row: Optional[int]
    raster_pixel_col: Optional[int]

    lulc_neighborhood_window_size: Optional[int]
    lulc_neighborhood_class_purity_pct: Optional[float]
    lulc_neighborhood_nodata_pct: Optional[float]

    # --- Teammate README compatibility fields, all additive/defaulted so
    # every existing construction of this dataclass (tests included)
    # keeps working unchanged. Populated by image_analyzer.py; consumed
    # by the new teammate export writers (src/teammate_metadata_writer.py,
    # src/teammate_gis_writer.py) as well as the existing CSV/JSON writer,
    # which picks them up automatically since it derives its column list
    # from dataclasses.fields(GeoCodedResult). ---
    image_id: Optional[str] = None
    file_path: Optional[str] = None
    capture_datetime: Optional[str] = None   # from EXIF DateTimeOriginal; LOCAL time, no TZ -- see exif_reader.parse_capture_datetime
    gps_source: Optional[str] = None          # "EXIF" when coordinates came from EXIF GPS
    gps_accuracy_m: Optional[float] = None    # from EXIF GPSHPositioningError, when present; never fabricated
    coordinate_status: Optional[str] = None   # VALID / MISSING / SUSPICIOUS / OUTSIDE_STUDY_AREA
    study_area_status: Optional[str] = None   # INSIDE / BOUNDARY_REVIEW / OUTSIDE
