"""
config.py — single source of truth for dataset paths and CRS constants.

Values here were established/verified in the Phase 1 dataset audit
(docs/GEO_CODED_DATA_AUDIT.md) and confirmed by the user. Do not
re-derive or assume these elsewhere in the codebase — import from here.
"""

from __future__ import annotations

from pathlib import Path

_MODULE_ROOT = Path(__file__).resolve().parent.parent  # geo_coded/

DATA_DIR = _MODULE_ROOT / "data" / "raw"
BOUNDARY_PATH = DATA_DIR / "study_area" / "shiggaon_boundary.gpkg"
MICRO_WATERSHEDS_PATH = DATA_DIR / "micro_watersheds" / "shiggaon_micro_watersheds.gpkg"
LULC_RASTER_PATH = DATA_DIR / "lulc" / "lulc_prediction.tif"  # used from Phase 5 onward

# CRS confirmed in Phase 1 audit: both vector layers are WGS84, GPS EXIF is
# also WGS84 -- no reprojection is needed for boundary/watershed checks.
# The raster is EPSG:32643 (UTM 43N) and DOES require point reprojection;
# that happens in lulc_query.py.
WGS84 = "EPSG:4326"
RASTER_CRS = "EPSG:32643"

# LULC class encoding for lulc_prediction.tif.
#
# SOURCE OF TRUTH: this mapping was explicitly confirmed by the user in the
# Phase 1 audit resolution as "the official Model 1 class encoding...fixed
# throughout Model 1...must NOT be reordered." No Model 1 training/export
# code or legend file was ever uploaded to this session -- this mapping is
# NOT independently verified against source code. If Model 1's training
# script or a legend file becomes available, cross-check this dict against
# it before relying on it for anything beyond this hackathon demo.
LULC_CLASS_MAP = {
    0: "NODATA",
    1: "Forest",
    2: "Agriculture",
    3: "Water",
    4: "Built-up",
    5: "Barren",
}

# Watershed attribute field names, per user's Phase 1 confirmation:
#   `id`  -> canonical micro_watershed_id (cross-module integration key)
#   `MWS` -> mws_code (hydrological/GIS identifier, retained separately)
WATERSHED_ID_FIELD = "id"
WATERSHED_MWS_FIELD = "MWS"

# Phase 6 output locations.
OUTPUTS_DIR = _MODULE_ROOT / "outputs"
DEFAULT_CSV_PATH = OUTPUTS_DIR / "geo_coded_results.csv"
DEFAULT_JSON_PATH = OUTPUTS_DIR / "geo_coded_results.json"

# ---------------------------------------------------------------------------
# Teammate handover compatibility (per
# SIH_2026_Shiggaon_GeoCoded_Imagery_Teammate_README.docx). These are
# ADDITIVE outputs on top of the existing outputs/ CSV/JSON above -- they
# don't replace them.
# ---------------------------------------------------------------------------

# Boundary-proximity tolerance for flagging a coordinate as needing manual
# review (the teammate README's BOUNDARY_REVIEW status), in meters.
# Configurable here; changing it does NOT modify the study boundary
# geometry itself -- see boundary_checker.py: distance_to_boundary_m().
BOUNDARY_REVIEW_TOLERANCE_M = 15.0

TEAMMATE_HANDOVER_ROOT = _MODULE_ROOT / "12_GEO_CODED_IMAGES"
TEAMMATE_METADATA_DIR = TEAMMATE_HANDOVER_ROOT / "Metadata"
TEAMMATE_GIS_DIR = TEAMMATE_HANDOVER_ROOT / "GIS"
TEAMMATE_QA_DIR = TEAMMATE_HANDOVER_ROOT / "QA"

IMAGE_ID_LEDGER_PATH = TEAMMATE_METADATA_DIR / "image_id_ledger.json"
PHOTO_MASTER_VALIDATED_CSV = TEAMMATE_METADATA_DIR / "Photo_Master_Validated.csv"
PROCESSING_LOG_TXT = TEAMMATE_METADATA_DIR / "GeoCoded_Processing_Log.txt"
GEO_CODED_PHOTO_POINTS_GPKG = TEAMMATE_GIS_DIR / "GEO_CODED_PHOTO_POINTS.gpkg"
GEO_CODED_PHOTO_MWS_JOINED_GPKG = TEAMMATE_GIS_DIR / "GEO_CODED_PHOTO_MWS_JOINED.gpkg"
QA_LOG_XLSX = TEAMMATE_QA_DIR / "QA_Log.xlsx"
