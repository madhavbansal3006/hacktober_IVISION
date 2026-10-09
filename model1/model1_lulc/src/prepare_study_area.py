"""
Load, validate, and reproject the Shiggaon Taluk boundary polygon.

Primary source: LGD-derived subdistrict layer (bharatlas/india-geodata
mirror of India's Local Government Directory) — a third-party
redistribution of a government-derived dataset, NOT itself an official
government portal download.

Fallback 1: GADM level-3 taluk polygon, explicitly documented as
non-authoritative.

Fallback 2 (LAST RESORT): a rectangular bounding-box PROXY built from
config.yaml study_area.bbox, used ONLY when neither real source is
network-reachable. This is clearly flagged everywhere it is used — it is
NOT the Shiggaon Taluk polygon and must be replaced before any output is
treated as final.

load_shiggaon_boundary() returns (GeoDataFrame, is_real_boundary: bool) so
callers can propagate this distinction rather than silently treating a
bbox rectangle as the real taluk shape.
"""
from __future__ import annotations

import os
import sys

import geopandas as gpd
from shapely.geometry import box

from src.config import load_config, ensure_dirs

PROXY_SUFFIX = "_BBOX_PROXY_NOT_REAL_BOUNDARY.gpkg"

try:
    import requests
except ImportError:
    requests = None


class StudyAreaUnavailableError(RuntimeError):
    pass


def _try_download(url: str, out_path: str, timeout: int = 20) -> bool:
    if requests is None:
        return False
    try:
        r = requests.get(url, stream=True, timeout=timeout)
        if r.status_code != 200:
            print(f"  [download] {url} -> HTTP {r.status_code}")
            return False
        with open(out_path, "wb") as f:
            for chunk in r.iter_content(chunk_size=1 << 20):
                f.write(chunk)
        return True
    except Exception as e:
        print(f"  [download] FAILED for {url}: {type(e).__name__}: {e}")
        return False


def load_shiggaon_boundary(cfg: dict) -> tuple[gpd.GeoDataFrame, bool]:
    """Return (boundary_gdf, is_real_boundary).

    is_real_boundary is False only when the bbox proxy fallback was used —
    every downstream caller should check this and propagate the caveat
    into logs/README/metadata rather than presenting proxy-derived output
    as final.
    """
    sa_cfg = cfg["study_area"]
    local_path = sa_cfg["local_path"]
    proxy_path = local_path.replace(".gpkg", PROXY_SUFFIX)

    if os.path.exists(local_path):
        gdf = gpd.read_file(local_path)
        print(f"Loaded cached REAL study-area boundary from {local_path}")
        return _validate_and_reproject(gdf, cfg), True

    if os.path.exists(proxy_path):
        gdf = gpd.read_file(proxy_path)
        print(f"Loaded cached BBOX PROXY (NOT the real boundary) from {proxy_path}")
        return _validate_and_reproject(gdf, cfg), False

    os.makedirs(os.path.dirname(local_path), exist_ok=True)

    # --- Attempt 1: primary LGD source ---
    primary = sa_cfg["boundary_source_primary"]
    tmp_path = local_path + ".primary_download.parquet"
    print(f"Attempting primary boundary source: {primary['description']}")
    if _try_download(primary["url"], tmp_path):
        try:
            full_gdf = gpd.read_parquet(tmp_path)
            field = primary["filter_field"]
            value = primary["filter_value"]
            subset = (full_gdf[full_gdf[field].astype(str).str.contains(value, case=False, na=False)]
                       if field in full_gdf.columns else gpd.GeoDataFrame())
            if len(subset) > 0:
                subset.to_file(local_path, driver="GPKG")
                print(f"  Found {len(subset)} matching feature(s) for '{value}'. Saved to {local_path}")
                return _validate_and_reproject(subset, cfg), True
        except Exception as e:
            print(f"  Failed to parse primary source: {type(e).__name__}: {e}")
        finally:
            if os.path.exists(tmp_path):
                os.remove(tmp_path)

    # --- Attempt 2: GADM fallback (explicitly non-authoritative but still REAL) ---
    fallback = sa_cfg["boundary_source_fallback"]
    print(f"Primary source unavailable. Attempting FALLBACK (non-authoritative): {fallback['description']}")
    tmp_gadm = local_path + ".gadm_download.gpkg"
    if _try_download(fallback["url"], tmp_gadm):
        try:
            gadm = gpd.read_file(tmp_gadm, layer="ADM_ADM_3")
            subset = gadm[gadm["NAME_3"].astype(str).str.contains("Shiggaon", case=False, na=False)]
            if len(subset) > 0:
                subset = subset.copy()
                subset["_source"] = "GADM (NOT authoritative)"
                subset.to_file(local_path, driver="GPKG")
                print("  Using GADM fallback boundary. NOT an authoritative government source.")
                return _validate_and_reproject(subset, cfg), True
        except Exception as e:
            print(f"  Failed to parse GADM fallback: {type(e).__name__}: {e}")
        finally:
            if os.path.exists(tmp_gadm):
                os.remove(tmp_gadm)

    # --- Attempt 3 (LAST RESORT): rectangular bbox proxy ---
    print(
        "\nWARNING: Both real boundary sources are unreachable from this environment "
        "(network access to bharatlas.com and geodata.ucdavis.edu is required and "
        "denied here). Falling back to a RECTANGULAR BOUNDING-BOX PROXY built from "
        "config.yaml study_area.bbox. This is NOT the real Shiggaon Taluk polygon: "
        "it includes area outside the taluk and excludes parts of the taluk near its "
        "border. It exists only so the rest of the pipeline can be built and tested. "
        "Replace it with a real polygon (see instructions below) before treating any "
        "downstream output as final.\n"
        f"  A) LGD subdistrict layer: {primary['url']} (filter to 'Shiggaon') -> {local_path}\n"
        f"  B) GADM: https://gadm.org/download_country.html (India, level 3) -> {local_path}\n"
    )
    bbox = sa_cfg["bbox"]
    proxy_gdf = gpd.GeoDataFrame(
        {"name": ["Shiggaon_bbox_proxy"], "is_real_boundary": [False]},
        geometry=[box(*bbox)], crs="EPSG:4326",
    )
    proxy_gdf.to_file(proxy_path, driver="GPKG")
    print(f"Saved bbox proxy to {proxy_path}")
    return _validate_and_reproject(proxy_gdf, cfg), False


def _validate_and_reproject(gdf: gpd.GeoDataFrame, cfg: dict) -> gpd.GeoDataFrame:
    if len(gdf) == 0:
        raise StudyAreaUnavailableError("Boundary GeoDataFrame is empty after filtering.")

    if gdf.crs is None:
        print("  WARNING: input has no CRS defined, assuming EPSG:4326")
        gdf = gdf.set_crs("EPSG:4326")

    invalid = ~gdf.geometry.is_valid
    if invalid.any():
        print(f"  Fixing {invalid.sum()} invalid geometries with buffer(0)")
        gdf.loc[invalid, "geometry"] = gdf.loc[invalid, "geometry"].buffer(0)

    target_crs = cfg["study_area"]["target_crs"]
    gdf_reprojected = gdf.to_crs(target_crs)

    area_km2 = gdf_reprojected.geometry.area.sum() / 1e6
    print(f"  Validated boundary: {len(gdf)} feature(s), CRS={target_crs}, "
          f"total area={area_km2:.1f} km^2")
    print("  Reference figures for Shiggaon Taluk: ~584-588 km^2 (Wikipedia / villageinfo.in). "
          "Compare this to the loaded area as a sanity check.")

    return gdf_reprojected


if __name__ == "__main__":
    cfg = load_config()
    ensure_dirs(cfg)
    gdf, is_real = load_shiggaon_boundary(cfg)
    print(f"is_real_boundary = {is_real}")
    print(gdf[["geometry"]].head())
