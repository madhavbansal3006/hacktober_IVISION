"""
Prepare the reference LULC label raster (ESA WorldCover 2021 v200) for the
Shiggaon study area.

WorldCover is a REFERENCE product, not ground truth. This module:
  1. Locates local WorldCover GeoTIFF tile(s) (auto-download attempted
     first via AWS Open Data; manual placement supported as fallback).
  2. Mosaics multiple tiles if the study area straddles a tile boundary
     (Shiggaon's bbox spans the N12E075 / N15E075 seam at lat=15).
  3. Clips the mosaic to the Shiggaon study-area geometry.
  4. Remaps WorldCover source classes to our 5 target classes using the
     mapping in config.yaml, honoring the configured strategy for
     ambiguous classes (Grassland=30, Shrubland=20): "exclude" (default)
     drops those pixels from training rather than guessing their label.

This module NEVER fabricates label values. If no real WorldCover raster is
found, it raises an explicit error naming the exact file(s) to provide.
"""
from __future__ import annotations

import glob
import os
import sys

import numpy as np
import rasterio
from rasterio.merge import merge as rio_merge
from rasterio.mask import mask as rio_mask
from rasterio.warp import transform_geom
from rasterio.windows import from_bounds as window_from_bounds

from src.config import load_config, ensure_dirs

try:
    import requests
except ImportError:
    requests = None


class ReferenceDataUnavailableError(RuntimeError):
    pass


def find_local_worldcover_tiles(cfg: dict) -> list[str]:
    """Return ALL matching local WorldCover Map.tif files (there can be
    more than one if the study area straddles a 3x3-degree tile boundary).
    """
    local_dir = cfg["reference_lulc"]["local_path"]
    pattern = os.path.join(local_dir, cfg["reference_lulc"]["expected_filename_glob"])
    return sorted(glob.glob(pattern))


def attempt_download_worldcover(cfg: dict) -> list[str]:
    """Best-effort automated download of all candidate tiles covering the
    bbox from the AWS Open Data mirror. Returns list of local paths
    successfully downloaded (possibly empty) — never raises.
    """
    if requests is None:
        return []

    bbox = cfg["study_area"]["bbox"]
    min_lon, min_lat, max_lon, max_lat = bbox

    def tile_name(lat, lon):
        lat_tile = int(np.floor(lat / 3.0) * 3)
        lon_tile = int(np.floor(lon / 3.0) * 3)
        ns = f"N{lat_tile:02d}" if lat_tile >= 0 else f"S{abs(lat_tile):02d}"
        ew = f"E{lon_tile:03d}" if lon_tile >= 0 else f"W{abs(lon_tile):03d}"
        return f"{ns}{ew}"

    candidate_tiles = {
        tile_name(min_lat, min_lon), tile_name(min_lat, max_lon),
        tile_name(max_lat, min_lon), tile_name(max_lat, max_lon),
    }

    out_dir = cfg["reference_lulc"]["local_path"]
    os.makedirs(out_dir, exist_ok=True)
    downloaded = []
    for tile in candidate_tiles:
        url = cfg["reference_lulc"]["s3_url_template"].format(tile=tile)
        out_path = os.path.join(out_dir, f"ESA_WorldCover_10m_2021_v200_{tile}_Map.tif")
        try:
            r = requests.get(url, stream=True, timeout=15)
            if r.status_code != 200:
                print(f"  [worldcover download] {url} -> HTTP {r.status_code}, skipping")
                continue
            with open(out_path, "wb") as f:
                for chunk in r.iter_content(chunk_size=1 << 20):
                    f.write(chunk)
            downloaded.append(out_path)
            print(f"  [worldcover download] saved {out_path}")
        except Exception as e:
            print(f"  [worldcover download] FAILED for tile {tile}: {type(e).__name__}: {e}")
    return downloaded


def mosaic_and_clip_worldcover(tile_paths: list[str], boundary_gdf, pad_deg: float = 0.02) -> tuple[np.ndarray, dict]:
    """Mosaic one or more WorldCover tiles and clip to the study-area
    geometry, using WINDOWED reads so we never load a full 36000x36000
    (3x3 degree, ~1.3GB) tile into memory just to throw most of it away.
    Only the small window around the study-area bounds (plus a small pad)
    is read from each source tile before merging.

    Returns (2D uint8 array, rasterio profile).
    """
    wc_crs = "EPSG:4326"
    boundary_wc_crs = boundary_gdf.to_crs(wc_crs)
    minx, miny, maxx, maxy = boundary_wc_crs.total_bounds
    minx, miny, maxx, maxy = minx - pad_deg, miny - pad_deg, maxx + pad_deg, maxy + pad_deg

    windowed_srcs = []
    memfiles = []
    for p in tile_paths:
        src = rasterio.open(p)
        # Intersect requested bounds with this tile's own bounds so we
        # never request a window outside the raster.
        tminx, tminy, tmaxx, tmaxy = src.bounds
        wminx, wminy = max(minx, tminx), max(miny, tminy)
        wmaxx, wmaxy = min(maxx, tmaxx), min(maxy, tmaxy)
        if wminx >= wmaxx or wminy >= wmaxy:
            src.close()
            continue  # this tile doesn't actually intersect our area

        window = window_from_bounds(wminx, wminy, wmaxx, wmaxy, transform=src.transform)
        window = window.round_offsets().round_lengths()
        sub_arr = src.read(1, window=window)
        sub_transform = src.window_transform(window)

        profile = src.profile.copy()
        profile.update(height=sub_arr.shape[0], width=sub_arr.shape[1], transform=sub_transform)
        src.close()

        memfile = rasterio.io.MemoryFile()
        memfiles.append(memfile)
        with memfile.open(**profile) as tmp:
            tmp.write(sub_arr, 1)
        windowed_srcs.append(memfile.open())

    if not windowed_srcs:
        raise ReferenceDataUnavailableError(
            "None of the provided WorldCover tiles intersect the study-area bounds."
        )

    try:
        mosaic_arr, mosaic_transform = rio_merge(windowed_srcs)
        profile = windowed_srcs[0].profile.copy()
        profile.update(height=mosaic_arr.shape[1], width=mosaic_arr.shape[2], transform=mosaic_transform)
    finally:
        for s in windowed_srcs:
            s.close()
        for m in memfiles:
            m.close()

    geoms = [geom.__geo_interface__ for geom in boundary_wc_crs.geometry]
    with rasterio.io.MemoryFile() as memfile:
        with memfile.open(**profile) as tmp:
            tmp.write(mosaic_arr)
        with memfile.open() as tmp:
            clipped_arr, clipped_transform = rio_mask(tmp, geoms, crop=True, nodata=0)

    profile.update(height=clipped_arr.shape[1], width=clipped_arr.shape[2],
                    transform=clipped_transform, nodata=0)
    return clipped_arr[0], profile


def map_worldcover_to_target(wc_array: np.ndarray, cfg: dict) -> np.ndarray:
    """Remap WorldCover source class codes to our 5 target classes.
    Ambiguous classes (Grassland=30, Shrubland=20) are excluded (set to
    0/NoData) by default per config.yaml's ambiguous_class_strategy — we
    do not guess.
    """
    ref_cfg = cfg["reference_lulc"]
    class_mapping = {int(k): int(v) for k, v in ref_cfg["class_mapping"].items()}
    strategy = ref_cfg["ambiguous_class_strategy"]

    out = np.zeros_like(wc_array, dtype=np.uint8)
    for src_class, target_class in class_mapping.items():
        out[wc_array == src_class] = target_class

    if strategy == "map":
        ambiguous_mapping = {int(k): int(v) for k, v in ref_cfg["ambiguous_mapping"].items()}
        for src_class, target_class in ambiguous_mapping.items():
            out[wc_array == src_class] = target_class

    return out


def run(cfg: dict, boundary_gdf) -> tuple[np.ndarray, np.ndarray, dict]:
    """Full reference-label preparation. Returns
    (raw_worldcover_clipped, remapped_target_classes, rasterio_profile).
    """
    tiles = find_local_worldcover_tiles(cfg)
    if not tiles:
        print("No local WorldCover tiles found. Attempting automated download...")
        tiles = attempt_download_worldcover(cfg)

    if not tiles:
        expected_dir = cfg["reference_lulc"]["local_path"]
        raise ReferenceDataUnavailableError(
            "\nESA WorldCover 2021 v200 raster(s) not available and could not be "
            "downloaded automatically.\n\nACTION REQUIRED:\n"
            f"  Place WorldCover Map.tif tile(s) covering bbox {cfg['study_area']['bbox']} in:\n"
            f"    {expected_dir}\n"
            f"  matching pattern: {cfg['reference_lulc']['expected_filename_glob']}\n"
        )

    print(f"Using {len(tiles)} WorldCover tile(s):")
    for t in tiles:
        print(f"  {t}")

    raw_clipped, profile = mosaic_and_clip_worldcover(tiles, boundary_gdf)
    print(f"Mosaicked + clipped WorldCover raster shape: {raw_clipped.shape}, CRS: {profile['crs']}")

    unique, counts = np.unique(raw_clipped, return_counts=True)
    source_classes = cfg["reference_lulc"]["source_classes"]
    print("Raw WorldCover class pixel counts within study area:")
    for u, c in zip(unique, counts):
        name = source_classes.get(int(u), f"unknown({u})" if u != 0 else "NoData")
        print(f"  {u} ({name}): {c} pixels ({100*c/raw_clipped.size:.2f}%)")

    remapped = map_worldcover_to_target(raw_clipped, cfg)
    target_classes = cfg["target_classes"]
    print("Remapped target-class pixel counts:")
    for class_id in sorted(target_classes.keys()):
        c = int((remapped == class_id).sum())
        print(f"  {class_id} ({target_classes[class_id]}): {c} pixels ({100*c/remapped.size:.2f}%)")
    excluded = int((remapped == 0).sum())
    print(f"  Excluded/NoData (incl. ambiguous Grassland/Shrubland + outside study area): "
          f"{excluded} pixels ({100*excluded/remapped.size:.2f}%)")

    return raw_clipped, remapped, profile


def reproject_labels_to_grid(label_array: np.ndarray, src_profile: dict,
                              dst_transform, dst_crs, dst_shape) -> np.ndarray:
    """Reproject/resample the remapped (categorical, uint8) label raster
    onto an arbitrary target grid — used to align WorldCover labels
    (native EPSG:4326) onto the Sentinel-2 processing grid (EPSG:32643).
    Nearest-neighbor resampling only, since class codes are categorical
    and any other method would invent fractional/blended class values.
    """
    from rasterio.warp import reproject as rio_reproject
    from rasterio.enums import Resampling

    dst_array = np.zeros(dst_shape, dtype=np.uint8)
    rio_reproject(
        source=label_array,
        destination=dst_array,
        src_transform=src_profile["transform"],
        src_crs=src_profile["crs"],
        dst_transform=dst_transform,
        dst_crs=dst_crs,
        resampling=Resampling.nearest,
    )
    return dst_array


if __name__ == "__main__":
    cfg = load_config()
    ensure_dirs(cfg)
    from src.prepare_study_area import load_shiggaon_boundary

    boundary_gdf, is_real = load_shiggaon_boundary(cfg)
    if not is_real:
        print("NOTE: clipping against the BBOX PROXY, not the real Shiggaon Taluk polygon.\n")

    try:
        raw, remapped, profile = run(cfg, boundary_gdf)
    except ReferenceDataUnavailableError as e:
        print(str(e))
        sys.exit(1)

    out_path = os.path.join(os.path.dirname(cfg["paths"]["training_data_csv"]), "features",
                             "worldcover_remapped.tif")
    os.makedirs(os.path.dirname(out_path), exist_ok=True)
    write_profile = profile.copy()
    write_profile.update(dtype="uint8", count=1, nodata=0)
    with rasterio.open(out_path, "w", **write_profile) as dst:
        dst.write(remapped, 1)
    print(f"Saved remapped label raster to {out_path}")
