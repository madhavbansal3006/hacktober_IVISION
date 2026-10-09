"""
teammate_metadata_writer.py — writes the tabular/log outputs required by
SIH_2026_Shiggaon_GeoCoded_Imagery_Teammate_README.docx:

  - Photo_Master_Validated.csv  (README section 7/21)
  - QA_Log.xlsx                  (README section 21)
  - GeoCoded_Processing_Log.txt  (README sections 21/22)

These are ADDITIONAL outputs alongside the existing outputs/*.csv/json
(io_writer.py) -- this module does not replace or modify that writer.

Human-review fields (observation_type, description, photo_quality,
evidence_relevance, intervention_type, remarks, review_status, reviewer)
are ALWAYS written blank -- this module never invents values for them,
per explicit instruction. They exist as columns so the CSV matches the
teammate's schema and a human reviewer can fill them in afterward.
"""

from __future__ import annotations

import csv
from pathlib import Path
from typing import Optional

import openpyxl

from . import config
from .schema import GeoCodedResult

# Column order matches the teammate README's field table exactly.
PHOTO_MASTER_FIELDNAMES = [
    "image_id",
    "file_name",
    "file_path",
    "latitude",
    "longitude",
    "capture_datetime",
    "gps_source",
    "gps_accuracy_m",
    "coordinate_status",
    "mws_id",
    "study_area_status",
    "observation_type",
    "description",
    "photo_quality",
    "evidence_relevance",
    "intervention_type",
    "remarks",
    "review_status",
    "reviewer",
]

# Human-review fields: always blank, never populated by this module.
_HUMAN_REVIEW_FIELDS = (
    "observation_type",
    "description",
    "photo_quality",
    "evidence_relevance",
    "intervention_type",
    "remarks",
    "review_status",
    "reviewer",
)

QA_LOG_FIELDNAMES = [
    "image_id",
    "file_name",
    "coordinate_status",
    "study_area_status",
    "mws_id",
    "lulc_class",
    "status",
    "review_status",
    "remarks",
]


def _to_photo_master_row(result: GeoCodedResult) -> dict:
    row = {
        "image_id": result.image_id,
        "file_name": result.image_name,
        "file_path": result.file_path,
        "latitude": result.latitude,
        "longitude": result.longitude,
        "capture_datetime": result.capture_datetime,
        "gps_source": result.gps_source,
        "gps_accuracy_m": result.gps_accuracy_m,
        "coordinate_status": result.coordinate_status,
        # mws_id per the user's explicit integration-key decision: this is
        # `id`, exposed under the README's expected column name. The
        # internal `micro_watershed_id` field/meaning is NOT changed --
        # this is a rename at the export layer only.
        "mws_id": result.micro_watershed_id,
        "study_area_status": result.study_area_status,
    }
    for field in _HUMAN_REVIEW_FIELDS:
        row[field] = None  # always blank -- never invented
    return row


def write_photo_master_validated_csv(
    results: list[GeoCodedResult], path: str | Path | None = None
) -> Path:
    path = Path(path) if path is not None else config.PHOTO_MASTER_VALIDATED_CSV
    path.parent.mkdir(parents=True, exist_ok=True)

    with open(path, "w", newline="") as f:
        writer = csv.DictWriter(f, fieldnames=PHOTO_MASTER_FIELDNAMES)
        writer.writeheader()
        for result in results:
            writer.writerow(_to_photo_master_row(result))

    return path


def _to_qa_log_row(result: GeoCodedResult) -> list:
    return [
        result.image_id,
        result.image_name,
        result.coordinate_status,
        result.study_area_status,
        result.micro_watershed_id,  # mws_id, see note in _to_photo_master_row
        result.lulc_class,
        result.status,
        None,   # review_status -- human field, always blank
        None,   # remarks -- human field, always blank
    ]


def write_qa_log_xlsx(results: list[GeoCodedResult], path: str | Path | None = None) -> Path:
    path = Path(path) if path is not None else config.QA_LOG_XLSX
    path.parent.mkdir(parents=True, exist_ok=True)

    wb = openpyxl.Workbook()
    ws = wb.active
    ws.title = "QA_Log"
    ws.append(QA_LOG_FIELDNAMES)
    for result in results:
        ws.append(_to_qa_log_row(result))

    wb.save(path)
    return path


def _count(results: list[GeoCodedResult], predicate) -> int:
    return sum(1 for r in results if predicate(r))


def write_processing_log(
    results: list[GeoCodedResult],
    path: str | Path | None = None,
    *,
    operator: Optional[str] = None,
    mws_id_field: str = config.WATERSHED_ID_FIELD,
) -> Path:
    """
    Writes an aggregate, batch-level processing log. Every count here is
    computed directly from `results` -- nothing is estimated or assumed.
    """
    from datetime import datetime, timezone

    from . import spatial_analyzer as _spatial
    from .schema import (
        COORD_STATUS_MISSING,
        COORD_STATUS_SUSPICIOUS,
        STUDY_AREA_STATUS_BOUNDARY_REVIEW,
    )

    path = Path(path) if path is not None else config.PROCESSING_LOG_TXT
    path.parent.mkdir(parents=True, exist_ok=True)

    total = len(results)
    geotagged = _count(results, lambda r: r.latitude is not None and r.longitude is not None)
    missing_gps = _count(results, lambda r: r.coordinate_status == COORD_STATUS_MISSING)
    suspicious_gps = _count(results, lambda r: r.coordinate_status == COORD_STATUS_SUSPICIOUS)
    outside_study_area = _count(
        results, lambda r: r.status == _spatial.STATUS_OUTSIDE_STUDY_AREA
    )
    boundary_review = _count(
        results, lambda r: r.study_area_status == STUDY_AREA_STATUS_BOUNDARY_REVIEW
    )
    watershed_matched = _count(results, lambda r: r.micro_watershed_id is not None)
    lulc_matched = _count(results, lambda r: r.lulc_class is not None)
    errors = _count(results, lambda r: r.error_reason is not None)

    lines = [
        f"PROCESSING_TIMESTAMP: {datetime.now(timezone.utc).isoformat()}",
        f"OPERATOR: {operator or ''}",
        "",
        f"TOTAL_IMAGES: {total}",
        f"GEOTAGGED_IMAGES: {geotagged}",
        f"MISSING_GPS: {missing_gps}",
        f"INVALID_MALFORMED_GPS: {suspicious_gps}",
        f"OUTSIDE_STUDY_AREA: {outside_study_area}",
        f"BOUNDARY_REVIEW: {boundary_review}",
        f"WATERSHED_MATCHED: {watershed_matched}",
        f"LULC_MATCHED: {lulc_matched}",
        f"ERRORS: {errors}",
        "",
        f"CRS_USED: {config.WGS84} (EXIF/output) / {config.RASTER_CRS} (raster query)",
        f"MWS_FIELD_USED: {mws_id_field}",
        f"BOUNDARY_REVIEW_TOLERANCE_M: {config.BOUNDARY_REVIEW_TOLERANCE_M}",
    ]

    with open(path, "w") as f:
        f.write("\n".join(lines) + "\n")

    return path
