"""
Demo/presentation-layer reporting for Model 1. Reads existing production
outputs and presents them safely — never recomputes predictions, never
retrains, never modifies any file under models/ or the core outputs/
raster/CSV artifacts.

Two responsibilities:
1. Confidence handling — load lulc_confidence.tif using the PREDICTION
   raster's nodata mask as the source of truth for pixel validity.

   HISTORICAL NOTE (fixed, kept for context): outputs/lulc_confidence.tif
   previously declared nodata=-1.0 in its GeoTIFF header while its actual
   invalid pixels were physically stored as 0.0, so 0 pixels in the file
   ever equaled the declared tag. This was identified and fixed directly
   in the file — the nodata tag now correctly reads 0.0, matching both
   the actual invalid-pixel values and lulc_prediction.tif's own nodata
   convention. Valid confidence pixels were not altered by the fix
   (verified bit-identical), and prediction/confidence valid-pixel masks
   now match exactly. The function below still derives validity from the
   prediction raster rather than trusting the confidence file's own
   nodata field — this is now redundant given the fix, but is kept as a
   defensive cross-check since the prediction raster's nodata encoding
   was independently verified and is the more heavily-tested of the two.

2. Watershed reliability guarding — wraps the existing coverage_category
   column so LOW/INSUFFICIENT_DATA watersheds cannot be silently read as
   if they were GOOD/ACCEPTABLE. Does not delete or alter any row.
"""
from __future__ import annotations

import numpy as np
import pandas as pd
import rasterio

# Confidence interpretation ranges, as already implemented in
# src/predict.py::summarize_confidence and stored in outputs/metadata.json.
# Restated here as named constants so demo/reporting code has one place to
# reference them rather than hardcoding thresholds again.
CONFIDENCE_THRESHOLDS = {"low": (0.0, 0.5), "medium": (0.5, 0.75), "high": (0.75, 1.0)}

RELIABLE_COVERAGE_CATEGORIES = {"GOOD", "ACCEPTABLE"}
UNRELIABLE_COVERAGE_CATEGORIES = {"LOW", "INSUFFICIENT_DATA"}


class UnreliableWatershedError(ValueError):
    """Raised when code tries to read watershed statistics for a
    LOW/INSUFFICIENT_DATA watershed without explicitly acknowledging it.
    """
    pass


def load_confidence_aligned(prediction_tif: str, confidence_tif: str) -> tuple[np.ndarray, np.ndarray]:
    """Load the confidence raster with validity derived from the
    PREDICTION raster's nodata (kept as the authoritative source, per the
    module docstring, even though confidence_tif's own nodata tag was
    fixed and is now consistent too). Returns (confidence_array,
    valid_mask). Raises if the two rasters aren't pixel-grid-aligned.
    """
    with rasterio.open(prediction_tif) as p, rasterio.open(confidence_tif) as c:
        if p.crs != c.crs or p.transform != c.transform or (p.width, p.height) != (c.width, c.height):
            raise ValueError(
                f"{prediction_tif} and {confidence_tif} are not grid-aligned "
                f"(CRS/transform/dimensions differ) — cannot safely combine them."
            )
        pred = p.read(1)
        conf = c.read(1)

    valid_mask = pred != (p.nodata if p.nodata is not None else 0)
    return conf, valid_mask


def confidence_tier(value: float) -> str:
    for tier, (lo, hi) in CONFIDENCE_THRESHOLDS.items():
        if tier == "high":
            if value >= lo:
                return "high"
        elif lo <= value < hi:
            return tier
    return "unknown"


def summarize_confidence_safe(prediction_tif: str, confidence_tif: str) -> dict:
    """Recompute confidence summary stats using the corrected (prediction-
    derived) validity mask, for cross-checking against the figures already
    stored in outputs/metadata.json (which were computed at generation
    time using the in-memory valid_mask, so should already be correct —
    this is a verification pass, not a new computation method).
    """
    conf, valid_mask = load_confidence_aligned(prediction_tif, confidence_tif)
    vals = conf[valid_mask]
    if vals.size == 0:
        return {"mean_confidence": None}
    return {
        "n_valid_pixels": int(vals.size),
        "mean_confidence": float(vals.mean()),
        "low_confidence_pct": float(100 * (vals < 0.5).sum() / vals.size),
        "medium_confidence_pct": float(100 * ((vals >= 0.5) & (vals < 0.75)).sum() / vals.size),
        "high_confidence_pct": float(100 * (vals >= 0.75).sum() / vals.size),
        "thresholds": {"low": "<0.5", "medium": "0.5-0.75", "high": ">=0.75"},
    }


def load_watershed_statistics(csv_path: str) -> pd.DataFrame:
    """Load the existing micro_watershed_lulc_statistics.csv unmodified,
    and verify every row has both coverage_percent and coverage_category
    populated, and that the category is one of the four allowed values.
    Raises if the file is malformed — does not silently patch it.
    """
    df = pd.read_csv(csv_path)
    required_cols = {"pct_of_watershed_within_raster_extent", "coverage_category"}
    missing = required_cols - set(df.columns)
    if missing:
        raise ValueError(f"{csv_path} is missing required columns: {missing}")

    allowed_categories = {"GOOD", "ACCEPTABLE", "LOW", "INSUFFICIENT_DATA"}
    bad_categories = set(df["coverage_category"].unique()) - allowed_categories
    if bad_categories:
        raise ValueError(f"Unexpected coverage_category values: {bad_categories}")

    if df["coverage_category"].isna().any() or df["pct_of_watershed_within_raster_extent"].isna().any():
        n_missing = df["coverage_category"].isna().sum()
        raise ValueError(
            f"{n_missing} watershed(s) missing coverage percentage or category — "
            f"every watershed must have both."
        )

    return df


def get_watershed_lulc_percentages(
    df: pd.DataFrame, watershed_id, allow_unreliable: bool = False
) -> dict:
    """Return a watershed's LULC percentage breakdown, GUARDED: raises
    UnreliableWatershedError for LOW/INSUFFICIENT_DATA watersheds unless
    the caller explicitly passes allow_unreliable=True. This is the
    mechanism that makes it impossible for downstream/demo code to
    accidentally treat a LOW/INSUFFICIENT_DATA watershed as equally
    reliable to a GOOD/ACCEPTABLE one — the caller has to opt in
    knowingly, in code, every time.
    """
    row = df[df["micro_watershed_id"] == watershed_id]
    if len(row) == 0:
        raise KeyError(f"No watershed with id {watershed_id!r} found.")
    row = row.iloc[0]
    category = row["coverage_category"]

    if category in UNRELIABLE_COVERAGE_CATEGORIES and not allow_unreliable:
        raise UnreliableWatershedError(
            f"Watershed {watershed_id!r} has coverage_category={category!r} "
            f"({row['pct_of_watershed_within_raster_extent']:.1f}% of its true area covered, "
            f"{row.get('valid_pixel_count', 'unknown')} valid pixels). Its statistics are not "
            f"reliable for interpretation. Pass allow_unreliable=True if you intend to use them "
            f"anyway (e.g. for a caveated display), and label the result accordingly."
        )

    pct_cols = [c for c in df.columns if c.endswith("_percent") and c != "pct_of_watershed_within_raster_extent"]
    return {
        "micro_watershed_id": watershed_id,
        "coverage_category": category,
        "coverage_percent": float(row["pct_of_watershed_within_raster_extent"]),
        "reliable": category in RELIABLE_COVERAGE_CATEGORIES,
        "lulc_percentages": {c: float(row[c]) for c in pct_cols},
        "dominant_class": row.get("dominant_class"),
    }


def watershed_reliability_summary(df: pd.DataFrame) -> dict:
    """Aggregate reliability breakdown — safe to show in a demo without
    touching any individual watershed's numbers."""
    counts = df["coverage_category"].value_counts().to_dict()
    reliable = df["coverage_category"].isin(RELIABLE_COVERAGE_CATEGORIES).sum()
    unreliable = df["coverage_category"].isin(UNRELIABLE_COVERAGE_CATEGORIES).sum()
    return {
        "total_watersheds": len(df),
        "category_counts": counts,
        "reliable_count": int(reliable),
        "unreliable_count": int(unreliable),
        "unreliable_watershed_ids": df[df["coverage_category"].isin(UNRELIABLE_COVERAGE_CATEGORIES)][
            "micro_watershed_id"
        ].tolist(),
    }
