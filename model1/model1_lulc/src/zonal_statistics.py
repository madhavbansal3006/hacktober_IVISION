"""
Compute per-micro-watershed LULC area statistics from lulc_prediction.tif.

This module is INTENTIONALLY independent of the core Random Forest
pipeline: the classifier produces a valid GeoTIFF regardless of
micro-watershed availability. As of this version, the REAL Shiggaon
micro-watershed layer (66 SLUSI-derived polygons, independently verified —
see config.yaml comments) is available locally, so this module uses it
directly rather than attempting any network download or proxy fallback.

No polygon boundaries are ever fabricated. If the prediction raster or the
micro-watershed file is missing, this module fails loudly rather than
producing a fake or empty CSV.
"""
from __future__ import annotations

import os
import sys

import geopandas as gpd
import numpy as np
import pandas as pd
import rasterio
from rasterio.mask import mask as rio_mask

from src.config import load_config, ensure_dirs


class PolygonLayerUnavailableError(RuntimeError):
    pass


def load_micro_watersheds(cfg: dict) -> gpd.GeoDataFrame:
    mw_cfg = cfg["micro_watersheds"]
    local_path = mw_cfg["local_path"]
    if not os.path.exists(local_path):
        raise PolygonLayerUnavailableError(
            f"Micro-watershed file not found at {local_path}. This dataset must be "
            f"provided by the user (real SLUSI-derived polygons) — it is not fetched "
            f"or fabricated automatically."
        )
    gdf = gpd.read_file(local_path)
    print(f"Loaded {len(gdf)} real micro-watershed polygons from {local_path}")
    return gdf


COVERAGE_THRESHOLDS = {
    "GOOD": 90.0,        # coverage >= 90%
    "ACCEPTABLE": 75.0,  # 75% <= coverage < 90%
    # below 75% -> LOW
}
INSUFFICIENT_DATA_MIN_VALID_PIXELS = 100  # defensible floor: below this, stats are not meaningful


def classify_coverage(pct_covered: float | None, valid_pixel_count: int) -> str:
    """Categorize a micro-watershed's data quality.
    INSUFFICIENT_DATA takes priority over the percentage-based bands: a
    watershed can have high percentage coverage of a tiny sliver and still
    have too few pixels to trust (e.g. a 5-pixel fragment).
    """
    if valid_pixel_count < INSUFFICIENT_DATA_MIN_VALID_PIXELS:
        return "INSUFFICIENT_DATA"
    if pct_covered is None:
        return "INSUFFICIENT_DATA"
    if pct_covered >= COVERAGE_THRESHOLDS["GOOD"]:
        return "GOOD"
    if pct_covered >= COVERAGE_THRESHOLDS["ACCEPTABLE"]:
        return "ACCEPTABLE"
    return "LOW"


def compute_zonal_stats(
    prediction_tif: str,
    polygon_gdf: gpd.GeoDataFrame,
    target_classes: dict,
    id_field: str,
) -> pd.DataFrame:
    """For each micro-watershed polygon, compute total area, per-class
    area/percent, and the dominant (majority) LULC class.

    Uses a windowed masked-read per polygon (rasterio.mask with crop=True)
    rather than loading the full raster into memory at once — fine for 66
    small polygons over a single taluk at 10m resolution.
    """
    rows = []
    class_ids_sorted = sorted(target_classes.keys())

    with rasterio.open(prediction_tif) as src:
        polygon_gdf = polygon_gdf.to_crs(src.crs)
        pixel_area_ha = abs(src.transform.a * src.transform.e) / 10000.0

        for idx, poly_row in polygon_gdf.iterrows():
            geom = [poly_row.geometry.__geo_interface__]
            try:
                out_image, _ = rio_mask(src, geom, crop=True, nodata=0)
            except ValueError:
                print(f"  WARNING: polygon {poly_row.get(id_field, idx)} does not overlap "
                      f"the prediction raster extent — skipped.")
                continue
            arr = out_image[0]

            total_valid_pixels = int((arr != 0).sum())
            row = {
                "micro_watershed_id": poly_row.get(id_field, idx),
                "internal_id": poly_row.get("id", idx),
                "source_area_km2": poly_row.get("area_km2", None),
                "total_area_ha": total_valid_pixels * pixel_area_ha,
            }
            if row["source_area_km2"]:
                row["pct_of_watershed_within_raster_extent"] = round(
                    100 * row["total_area_ha"] / (row["source_area_km2"] * 100), 2
                )
            else:
                row["pct_of_watershed_within_raster_extent"] = None

            if total_valid_pixels == 0:
                row["dominant_class"] = "NO_CLASSIFIED_PIXELS"
                for class_id in class_ids_sorted:
                    class_name = target_classes[class_id]
                    key = class_name.lower().replace("/", "_").replace(" ", "_").replace("-", "")
                    row[f"{key}_ha"] = 0.0
                    row[f"{key}_percent"] = 0.0
                rows.append(row)
                continue

            class_pct = {}
            for class_id in class_ids_sorted:
                class_name = target_classes[class_id]
                key = class_name.lower().replace("/", "_").replace(" ", "_").replace("-", "")
                class_pixels = int((arr == class_id).sum())
                pct = 100.0 * class_pixels / total_valid_pixels
                row[f"{key}_ha"] = class_pixels * pixel_area_ha
                row[f"{key}_percent"] = pct
                class_pct[class_name] = pct

            row["dominant_class"] = max(class_pct, key=class_pct.get)
            rows.append(row)

    return pd.DataFrame(rows)


if __name__ == "__main__":
    cfg = load_config()
    ensure_dirs(cfg)

    prediction_tif = cfg["paths"]["prediction_tif"]
    if not os.path.exists(prediction_tif):
        print(
            f"Prediction raster not found at {prediction_tif}. Zonal statistics unavailable "
            f"because the LULC raster does not exist yet — run the core pipeline "
            f"(predict.py) first. This is expected until Sentinel-2 imagery is available; "
            f"see the pipeline status report for the current blocker."
        )
        sys.exit(1)

    try:
        mw_gdf = load_micro_watersheds(cfg)
    except PolygonLayerUnavailableError as e:
        print(str(e))
        sys.exit(1)

    stats_df = compute_zonal_stats(
        prediction_tif, mw_gdf, cfg["target_classes"], cfg["micro_watersheds"]["id_field"]
    )

    out_path = cfg["paths"]["micro_watershed_stats_csv"]
    os.makedirs(os.path.dirname(out_path), exist_ok=True)
    stats_df.to_csv(out_path, index=False)
    print(f"Wrote zonal statistics for {len(stats_df)} micro-watersheds to {out_path}")
    print(stats_df[["micro_watershed_id", "total_area_ha", "dominant_class"]].to_string(index=False))
