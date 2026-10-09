"""
Search and acquire Sentinel-2 L2A imagery via Microsoft Planetary Computer's
STAC API for the Shiggaon study area, and produce harmonized 10 m band
arrays (B02, B03, B04, B08, B11) with an SCL-based cloud/quality mask.

This module requires network access to planetarycomputer.microsoft.com.
If that host is unreachable, it fails loudly with the exact command to run
in an environment that does have access, rather than fabricating imagery.
"""
from __future__ import annotations

import os
import sys
import json

import numpy as np
import rasterio
from rasterio.enums import Resampling
from rasterio.warp import calculate_default_transform, reproject

from src.config import load_config, ensure_dirs

try:
    import pystac_client
    import planetary_computer as pc
except ImportError:
    pystac_client = None
    pc = None


class SentinelDataUnavailableError(RuntimeError):
    pass


def search_scenes(cfg: dict):
    """Query Planetary Computer STAC for candidate Sentinel-2 L2A scenes.
    Returns a list of pystac Items sorted by ascending cloud cover.
    """
    if pystac_client is None:
        raise SentinelDataUnavailableError(
            "pystac-client is not installed. Run: pip install pystac-client planetary-computer"
        )

    s2_cfg = cfg["sentinel2"]
    try:
        catalog = pystac_client.Client.open(s2_cfg["stac_url"], modifier=pc.sign_inplace)
    except Exception as e:
        raise SentinelDataUnavailableError(
            "\n"
            f"Could not reach the Planetary Computer STAC API at {s2_cfg['stac_url']}.\n"
            f"Underlying error: {type(e).__name__}: {e}\n\n"
            "ACTION REQUIRED: run this module in an environment with network access\n"
            "to planetarycomputer.microsoft.com. Reproducible command:\n\n"
            "  python -m src.download_sentinel\n\n"
            "If you're behind a restricted proxy/sandbox, add planetarycomputer.microsoft.com\n"
            "to its egress allowlist, or run this step on your own machine and place the\n"
            f"resulting band GeoTIFFs in {s2_cfg['local_path']}\n"
        )

    search = catalog.search(
        collections=[s2_cfg["collection"]],
        bbox=cfg["study_area"]["bbox"],
        datetime=s2_cfg["date_range"],
        query={"eo:cloud_cover": {"lt": s2_cfg["max_cloud_cover"]}},
    )
    items = list(search.get_items())
    items_sorted = sorted(items, key=lambda i: i.properties.get("eo:cloud_cover", 100))
    return items_sorted


def select_best_scene(items, cfg: dict):
    if not items:
        raise SentinelDataUnavailableError(
            f"No Sentinel-2 scenes found for bbox {cfg['study_area']['bbox']} in date range "
            f"{cfg['sentinel2']['date_range']} with cloud cover < {cfg['sentinel2']['max_cloud_cover']}%.\n"
            "Try widening the date range in config.yaml (sentinel2.date_range) or raising "
            "sentinel2.max_cloud_cover."
        )
    best = items[0]
    print(f"Selected scene: {best.id}")
    print(f"  Date: {best.datetime}")
    print(f"  Cloud cover: {best.properties.get('eo:cloud_cover')}%")
    return best


def load_band_arrays(item, cfg: dict) -> dict:
    """Read each required band into a numpy array at native resolution,
    resample B11 (20m) to the 10m grid, and return a dict of
    {band_name: (array, transform, crs)}.
    """
    s2_cfg = cfg["sentinel2"]
    bands = s2_cfg["bands"]  # {'blue': 'B02', ...}
    target_res = s2_cfg["output_resolution_m"]
    resample_method = getattr(Resampling, s2_cfg["resample_method"])

    # First pass: read the 10m reference band to get the target grid.
    ref_band_key = "B04"
    ref_asset = item.assets[ref_band_key]
    with rasterio.open(ref_asset.href) as ref_src:
        ref_transform = ref_src.transform
        ref_crs = ref_src.crs
        ref_shape = (ref_src.height, ref_src.width)

    out = {}
    for logical_name, band_code in bands.items():
        asset = item.assets[band_code]
        native_res = s2_cfg["native_resolution_m"].get(band_code, 10)
        with rasterio.open(asset.href) as src:
            if native_res == target_res:
                arr = src.read(1).astype(np.float32)
            else:
                # Resample onto the reference (10m) grid.
                arr = np.empty(ref_shape, dtype=np.float32)
                reproject(
                    source=rasterio.band(src, 1),
                    destination=arr,
                    src_transform=src.transform,
                    src_crs=src.crs,
                    dst_transform=ref_transform,
                    dst_crs=ref_crs,
                    resampling=resample_method,
                )
                print(f"  Resampled {band_code} ({native_res}m -> {target_res}m) using "
                      f"{s2_cfg['resample_method']}")
        out[logical_name] = arr

    return out, ref_transform, ref_crs


def load_scl_mask(item, cfg: dict, ref_transform, ref_crs, ref_shape) -> np.ndarray:
    """Load the Scene Classification Layer (SCL) and return a boolean array
    (True = good pixel) at the 10m reference grid.
    """
    s2_cfg = cfg["sentinel2"]
    if not s2_cfg.get("scl_mask_enabled", True):
        return np.ones(ref_shape, dtype=bool)

    if "SCL" not in item.assets:
        print("  WARNING: SCL asset not found on this item; skipping pixel-level cloud mask "
              "(scene-level cloud_cover filter still applies).")
        return np.ones(ref_shape, dtype=bool)

    exclude_values = set(s2_cfg["scl_exclude_values"])
    with rasterio.open(item.assets["SCL"].href) as src:
        scl_arr = np.empty(ref_shape, dtype=np.uint8)
        reproject(
            source=rasterio.band(src, 1),
            destination=scl_arr,
            src_transform=src.transform,
            src_crs=src.crs,
            dst_transform=ref_transform,
            dst_crs=ref_crs,
            resampling=Resampling.nearest,  # categorical data: nearest only
        )
    good_mask = ~np.isin(scl_arr, list(exclude_values))
    pct_good = 100 * good_mask.sum() / good_mask.size
    print(f"  SCL mask: {pct_good:.1f}% of pixels retained after excluding "
          f"cloud/shadow/snow/nodata classes {sorted(exclude_values)}")
    return good_mask


def load_local_bands(cfg: dict):
    """If all required band GeoTIFFs already exist locally (e.g. user-
    provided, pre-clipped/resampled outside this sandbox), load them
    directly and skip the STAC search entirely.

    Returns (bands, good_mask, transform, crs, scene_metadata) or None if
    not all required bands are present locally.

    IMPORTANT: no scene ID, acquisition date, or cloud-cover percentage is
    known for these files — no STAC item was queried to produce them. This
    is recorded explicitly in scene_metadata rather than invented.
    Similarly, no Scene Classification (SCL) layer was provided, so only
    nodata-based masking is applied here — no pixel-level cloud/shadow
    masking. Both gaps are surfaced in the returned metadata and should be
    stated in any report using this data.
    """
    s2_cfg = cfg["sentinel2"]
    local_dir = s2_cfg["local_path"]
    band_files = {name: os.path.join(local_dir, f"{code}.tif") for name, code in s2_cfg["bands"].items()}

    if not all(os.path.exists(p) for p in band_files.values()):
        return None

    print("Found all required band files locally — loading directly, skipping STAC search.")
    bands = {}
    ref_transform, ref_crs, ref_shape = None, None, None
    nodata_mask = None

    for logical_name, path in band_files.items():
        with rasterio.open(path) as src:
            arr = src.read(1).astype(np.float32)
            nodata = src.nodata
            if nodata is not None:
                band_nodata_mask = (arr == nodata)
            else:
                band_nodata_mask = np.zeros(arr.shape, dtype=bool)
            arr[band_nodata_mask] = np.nan

            if ref_transform is None:
                ref_transform, ref_crs, ref_shape = src.transform, src.crs, arr.shape
                nodata_mask = band_nodata_mask.copy()
            else:
                if arr.shape != ref_shape:
                    raise SentinelDataUnavailableError(
                        f"Band {logical_name} ({path}) shape {arr.shape} does not match "
                        f"reference shape {ref_shape} from the first band loaded. All local "
                        f"band files must already share an identical grid."
                    )
                if src.transform != ref_transform or src.crs != ref_crs:
                    raise SentinelDataUnavailableError(
                        f"Band {logical_name} ({path}) has a different transform/CRS than "
                        f"the reference band. All local band files must already share an "
                        f"identical grid — reproject them to match before placing here."
                    )
                nodata_mask |= band_nodata_mask

        bands[logical_name] = arr

    good_mask = ~nodata_mask
    pct_good = 100 * good_mask.sum() / good_mask.size
    print(f"  Loaded {len(bands)} bands locally. Shape: {ref_shape}, CRS: {ref_crs}")
    print(f"  Valid (non-nodata) pixels: {pct_good:.2f}%")
    print("  NOTE: no scene ID/date/cloud-cover metadata available (bands were provided "
          "pre-processed, not queried via STAC). No SCL cloud mask applied — only nodata "
          "masking. Document both gaps in any report using this raster.")

    scene_metadata = {
        "source": "user-provided pre-processed local GeoTIFFs (no STAC query performed)",
        "scene_id": "UNKNOWN",
        "datetime": "UNKNOWN",
        "cloud_cover_scene_pct": "UNKNOWN",
        "scl_cloud_mask_applied": False,
        "pct_good_pixels_nodata_mask_only": float(pct_good),
    }

    return bands, good_mask, ref_transform, ref_crs, scene_metadata


def run(cfg: dict):
    local_result = load_local_bands(cfg)
    if local_result is not None:
        bands, good_mask, transform, crs, scene_metadata = local_result
        out_dir = cfg["sentinel2"]["local_path"]
        with open(os.path.join(out_dir, "scene_metadata.json"), "w") as f:
            json.dump(scene_metadata, f, indent=2)
        return bands, good_mask, transform, crs

    print("Searching Sentinel-2 L2A scenes via Planetary Computer STAC...")
    items = search_scenes(cfg)
    print(f"Found {len(items)} candidate scene(s).")
    item = select_best_scene(items, cfg)

    print("Loading and harmonizing band arrays...")
    bands, transform, crs = load_band_arrays(item, cfg)
    ref_shape = bands["red"].shape

    print("Loading cloud/quality mask (SCL)...")
    good_mask = load_scl_mask(item, cfg, transform, crs, ref_shape)

    out_dir = cfg["sentinel2"]["local_path"]
    os.makedirs(out_dir, exist_ok=True)
    profile = {
        "driver": "GTiff", "dtype": "float32", "count": 1,
        "height": ref_shape[0], "width": ref_shape[1],
        "crs": crs, "transform": transform, "nodata": np.nan,
    }
    for name, arr in bands.items():
        masked = np.where(good_mask, arr, np.nan)
        path = os.path.join(out_dir, f"{name}.tif")
        with rasterio.open(path, "w", **profile) as dst:
            dst.write(masked, 1)
        print(f"  Wrote {path}")

    meta = {
        "scene_id": item.id,
        "datetime": str(item.datetime),
        "cloud_cover_scene_pct": item.properties.get("eo:cloud_cover"),
        "pct_good_pixels_after_scl_mask": float(100 * good_mask.sum() / good_mask.size),
    }
    with open(os.path.join(out_dir, "scene_metadata.json"), "w") as f:
        json.dump(meta, f, indent=2)
    print("Scene metadata:", json.dumps(meta, indent=2))

    return bands, good_mask, transform, crs


if __name__ == "__main__":
    cfg = load_config()
    ensure_dirs(cfg)
    try:
        run(cfg)
    except SentinelDataUnavailableError as e:
        print(str(e))
        sys.exit(1)
