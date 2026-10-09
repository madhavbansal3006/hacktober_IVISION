"""
Preprocesses the authoritative Copernicus GLO-30 DEM into a lightweight,
browser-compatible 3D elevation grid and per-MWS elevation & slope statistics lookup.

Source:
- backend/model_2/Data/raw/Shiggaon_Taluk_DEM_GLO30/Shiggaon_Taluk_DEM_GLO30.tif
- backend/model_2/Data/processed/dem_features.csv
- backend/model_2/data/raw/shiggaon_micro_watersheds_deliverables/shiggaon_micro_watersheds.gpkg

Output:
- frontend/public/data/shiggaon_dem_terrain.json
"""

import json
import math
from pathlib import Path
import geopandas as gpd
import numpy as np
import pandas as pd
import rasterio
from rasterio.enums import Resampling
from rasterio.mask import mask


def main():
    root = Path(__file__).resolve().parents[1]
    dem_path = (
        root
        / "backend"
        / "model_2"
        / "Data"
        / "raw"
        / "Shiggaon_Taluk_DEM_GLO30"
        / "Shiggaon_Taluk_DEM_GLO30.tif"
    )
    features_path = root / "backend" / "model_2" / "Data" / "processed" / "dem_features.csv"
    mws_gpkg_path = (
        root
        / "backend"
        / "model_2"
        / "data"
        / "raw"
        / "shiggaon_micro_watersheds_deliverables"
        / "shiggaon_micro_watersheds.gpkg"
    )
    out_path = root / "frontend" / "public" / "data" / "shiggaon_dem_terrain.json"

    out_path.parent.mkdir(parents=True, exist_ok=True)

    print(f"Reading source DEM: {dem_path}")
    with rasterio.open(dem_path) as src:
        bounds = [
            float(src.bounds.left),
            float(src.bounds.bottom),
            float(src.bounds.right),
            float(src.bounds.top),
        ]
        nodata = src.nodata
        orig_crs = str(src.crs)

        target_rows = 200
        target_cols = 200

        # Read downsampled with bilinear interpolation for the 3D surface mesh
        raw_grid = src.read(
            1,
            out_shape=(target_rows, target_cols),
            resampling=Resampling.bilinear,
        )

        valid_mask = (raw_grid != nodata) & (raw_grid > 0)
        min_elev = float(np.min(raw_grid[valid_mask]))
        max_elev = float(np.max(raw_grid[valid_mask]))
        mean_elev = float(np.mean(raw_grid[valid_mask]))

        # For nodata border areas outside the Taluk polygon boundary,
        # set elevation smoothly to min_elev - 5m to create a clean base pediment
        processed_grid = np.where(valid_mask, raw_grid, min_elev - 5.0)

        # Round to 1 decimal place to reduce JSON size
        elevations = np.round(processed_grid, 1).tolist()

        # Calculate pixel resolution in meters for slope gradient calculation
        res_x, res_y = src.res
        mean_lat = (bounds[1] + bounds[3]) / 2.0
        pixel_dx = res_x * 111320.0 * math.cos(math.radians(mean_lat))
        pixel_dy = res_y * 110600.0

        # Extract authentic per-MWS slope statistics from the 30m DEM
        print(f"Calculating DEM-derived slope statistics for all micro-watersheds...")
        gdf_mws = gpd.read_file(mws_gpkg_path).to_crs(src.crs)
        slope_by_mws = {}

        for _, row in gdf_mws.iterrows():
            mws_code = str(row["MWS"]).strip()
            mws_id = str(row["id"]).strip()
            geom = [row.geometry.__geo_interface__]
            try:
                out_img, _ = mask(src, geom, crop=True)
                crop_data = out_img[0].astype(float)
                crop_data[crop_data == nodata] = np.nan
                crop_data[crop_data <= 0] = np.nan
                gy, gx = np.gradient(crop_data, pixel_dy, pixel_dx)
                slopes = np.degrees(np.arctan(np.sqrt(gx**2 + gy**2)))
                valid_slopes = slopes[~np.isnan(slopes)]

                if len(valid_slopes) > 0:
                    s_min = round(float(np.min(valid_slopes)), 1)
                    s_max = round(float(np.max(valid_slopes)), 1)
                    s_mean = round(float(np.mean(valid_slopes)), 1)
                else:
                    s_min, s_max, s_mean = 0.0, 0.0, 0.0

                stats_entry = {
                    "slope_min": s_min,
                    "slope_max": s_max,
                    "slope_mean": s_mean,
                }
                slope_by_mws[mws_code] = stats_entry
                slope_by_mws[mws_id] = stats_entry
            except Exception as e:
                print(f"Warning: slope calculation error for {mws_code}: {e}")
                fallback = {"slope_min": 0.0, "slope_max": 0.0, "slope_mean": 0.0}
                slope_by_mws[mws_code] = fallback
                slope_by_mws[mws_id] = fallback

    print(f"DEM valid range: {min_elev:.1f} m to {max_elev:.1f} m (mean: {mean_elev:.1f} m)")
    print(f"Calculated authentic slope for {len(gdf_mws)} MWS units")

    # Load authoritative per-MWS elevation statistics from dem_features.csv
    print(f"Loading authoritative MWS statistics: {features_path}")
    df_feat = pd.read_csv(features_path)
    mws_stats = {}
    for _, row in df_feat.iterrows():
        mws_code = str(row["MWS"]).strip()
        mws_id = str(row["id"]).strip()
        s_stats = slope_by_mws.get(mws_code, {"slope_min": 0.0, "slope_max": 0.0, "slope_mean": 0.0})

        mws_stats[mws_code] = {
            "id": mws_id,
            "MWS": mws_code,
            "min": round(float(row.get("elevation_min", min_elev)), 1),
            "max": round(float(row.get("elevation_max", max_elev)), 1),
            "mean": round(float(row.get("elevation_mean", mean_elev)), 1),
            "range": round(float(row.get("elevation_range", 0.0)), 1),
            "slope_min": s_stats["slope_min"],
            "slope_max": s_stats["slope_max"],
            "slope_mean": s_stats["slope_mean"],
        }
        # Also index by canonical GIS ID
        mws_stats[mws_id] = mws_stats[mws_code]

    payload = {
        "source": "Copernicus GLO-30 DEM (ESA/AWS Open Data)",
        "crs": orig_crs,
        "bounds": bounds,  # [west, south, east, north]
        "grid_shape": [target_rows, target_cols],
        "min_elevation": round(min_elev, 1),
        "max_elevation": round(max_elev, 1),
        "mean_elevation": round(mean_elev, 1),
        "elevations": elevations,
        "mws_elevation_stats": mws_stats,
        "total_mws": len(df_feat),
    }

    with open(out_path, "w", encoding="utf-8") as f:
        json.dump(payload, f, separators=(",", ":"))

    size_kb = out_path.stat().st_size / 1024
    print(f"Successfully generated {out_path} ({size_kb:.1f} KB, {len(df_feat)} MWS units)")


if __name__ == "__main__":
    main()
