"""
image_analyzer.py — orchestrates a single image through the full pipeline:

  EXIF GPS extraction (Phase 3)
    -> coordinate validation (Phase 3)
    -> boundary + watershed lookup (Phase 4)
    -> LULC raster query (Phase 5)
    -> GeoCodedResult (Phase 6 schema)
    -> teammate README compatibility fields (image_id, coordinate_status,
       study_area_status, capture_datetime, gps_source, gps_accuracy_m)

Per requirement: one image's failure must never raise past this function.
Every failure mode (missing GPS, malformed GPS, invalid coordinate, or any
unanticipated exception) is caught here and turned into a GeoCodedResult
with an appropriate status and error_reason, so pipeline.py can process a
batch without a single bad image aborting the rest.

`id_ledger` is OPT-IN (default None): if not supplied, image_id is simply
left as None and nothing is written to disk. This keeps every call site
that doesn't ask for persistent IDs (including all existing tests) free
of side effects. Pass an ImageIdLedger explicitly to get real, persistent
IDs -- see README.
"""

from __future__ import annotations

from datetime import datetime, timezone
from pathlib import Path
from typing import Optional

from . import config
from .coordinate_validator import InvalidCoordinateError, validate
from .exceptions import MalformedGPSError, NoGPSError
from .exif_reader import extract_gps, parse_capture_datetime
from .geo_lulc_analyzer import GeoLULCAnalyzer
from .image_id_ledger import ImageIdLedger
from .schema import (
    SCHEMA_VERSION,
    STATUS_ERROR,
    STATUS_INVALID_COORDINATE,
    STATUS_MALFORMED_GPS,
    STATUS_NO_GPS,
    GeoCodedResult,
)
from .status_translator import translate_status


def _now_iso() -> str:
    return datetime.now(timezone.utc).isoformat()


def _error_result(
    image_name: str,
    timestamp: str,
    status: str,
    error_reason: str,
    latitude: Optional[float] = None,
    longitude: Optional[float] = None,
    image_id: Optional[str] = None,
    file_path: Optional[str] = None,
    coordinate_status: Optional[str] = None,
    study_area_status: Optional[str] = None,
) -> GeoCodedResult:
    return GeoCodedResult(
        schema_version=SCHEMA_VERSION,
        image_name=image_name,
        processing_timestamp=timestamp,
        latitude=latitude,
        longitude=longitude,
        status=status,
        error_reason=error_reason,
        inside_study_area=None,
        micro_watershed_id=None,
        mws_code=None,
        lulc_value=None,
        lulc_class=None,
        raster_pixel_row=None,
        raster_pixel_col=None,
        lulc_neighborhood_window_size=None,
        lulc_neighborhood_class_purity_pct=None,
        lulc_neighborhood_nodata_pct=None,
        image_id=image_id,
        file_path=file_path,
        capture_datetime=None,
        gps_source=None,
        gps_accuracy_m=None,
        coordinate_status=coordinate_status,
        study_area_status=study_area_status,
    )


def analyze_image(
    image_path: str | Path,
    analyzer: GeoLULCAnalyzer,
    id_ledger: Optional[ImageIdLedger] = None,
) -> GeoCodedResult:
    """
    Run one image through the full pipeline. Never raises -- every failure
    mode is captured in the returned GeoCodedResult's status/error_reason.

    id_ledger: optional. If provided, a persistent image_id is assigned
    (or looked up, if this exact file content has been processed before).
    If omitted, image_id is left as None -- no ledger file is read or
    written. See module docstring.
    """
    image_path = Path(image_path)
    image_name = image_path.name
    file_path_str = str(image_path)
    timestamp = _now_iso()

    # image_id can be assigned even for a failing image -- the README
    # wants every processed photo (including missing/suspicious GPS) to
    # get a permanent id so it stays traceable. Only skipped if the file
    # itself can't be read at all (handled by the FileNotFoundError catch
    # below, where there's nothing to hash).
    image_id: Optional[str] = None
    if id_ledger is not None and image_path.exists():
        image_id = id_ledger.get_or_create(image_path)

    try:
        raw_gps = extract_gps(image_path)
    except NoGPSError as exc:
        coord_status, area_status = translate_status(STATUS_NO_GPS)
        return _error_result(
            image_name, timestamp, STATUS_NO_GPS, str(exc),
            image_id=image_id, file_path=file_path_str,
            coordinate_status=coord_status, study_area_status=area_status,
        )
    except MalformedGPSError as exc:
        coord_status, area_status = translate_status(STATUS_MALFORMED_GPS)
        return _error_result(
            image_name, timestamp, STATUS_MALFORMED_GPS, str(exc),
            image_id=image_id, file_path=file_path_str,
            coordinate_status=coord_status, study_area_status=area_status,
        )
    except FileNotFoundError as exc:
        return _error_result(
            image_name, timestamp, STATUS_ERROR, str(exc),
            image_id=image_id, file_path=file_path_str,
        )
    except Exception as exc:  # noqa: BLE001 - deliberate: one image must never crash the batch
        return _error_result(
            image_name, timestamp, STATUS_ERROR, f"Unexpected error reading EXIF: {exc}",
            image_id=image_id, file_path=file_path_str,
        )

    try:
        coord = validate(raw_gps)
    except InvalidCoordinateError as exc:
        coord_status, area_status = translate_status(STATUS_INVALID_COORDINATE)
        return _error_result(
            image_name, timestamp, STATUS_INVALID_COORDINATE, str(exc),
            image_id=image_id, file_path=file_path_str,
            coordinate_status=coord_status, study_area_status=area_status,
        )
    except Exception as exc:  # noqa: BLE001
        return _error_result(
            image_name, timestamp, STATUS_ERROR, f"Unexpected error validating coordinate: {exc}",
            image_id=image_id, file_path=file_path_str,
        )

    try:
        core = analyzer.analyze(latitude=coord.latitude, longitude=coord.longitude)
    except Exception as exc:  # noqa: BLE001
        return _error_result(
            image_name, timestamp, STATUS_ERROR,
            f"Unexpected error in spatial/LULC analysis: {exc}",
            latitude=coord.latitude, longitude=coord.longitude,
            image_id=image_id, file_path=file_path_str,
        )

    # Boundary-proximity distance -- used only to decide BOUNDARY_REVIEW.
    # Never affects core.status or core.inside_study_area (those are
    # unchanged from the existing, already-tested spatial analysis).
    try:
        distance_m = analyzer.boundary_checker.distance_to_boundary_m(coord.point)
    except Exception:  # noqa: BLE001 - this is a diagnostic extra, never fatal
        distance_m = None

    coordinate_status, study_area_status = translate_status(
        core.status,
        inside_study_area=core.inside_study_area,
        distance_to_boundary_m=distance_m,
        boundary_review_tolerance_m=config.BOUNDARY_REVIEW_TOLERANCE_M,
    )

    capture_datetime = parse_capture_datetime(raw_gps.capture_datetime_raw)
    gps_source = "EXIF"  # the only source this module supports; always EXIF when GPS extraction succeeded

    return GeoCodedResult(
        schema_version=SCHEMA_VERSION,
        image_name=image_name,
        processing_timestamp=timestamp,
        latitude=core.latitude,
        longitude=core.longitude,
        status=core.status,
        error_reason=None,
        inside_study_area=core.inside_study_area,
        micro_watershed_id=core.micro_watershed_id,
        mws_code=core.mws_code,
        lulc_value=core.lulc_value,
        lulc_class=core.lulc_class,
        raster_pixel_row=core.raster_pixel_row,
        raster_pixel_col=core.raster_pixel_col,
        lulc_neighborhood_window_size=core.lulc_neighborhood_window_size,
        lulc_neighborhood_class_purity_pct=core.lulc_neighborhood_class_purity_pct,
        lulc_neighborhood_nodata_pct=core.lulc_neighborhood_nodata_pct,
        image_id=image_id,
        file_path=file_path_str,
        capture_datetime=capture_datetime,
        gps_source=gps_source,
        gps_accuracy_m=raw_gps.gps_accuracy_m,
        coordinate_status=coordinate_status,
        study_area_status=study_area_status,
    )
