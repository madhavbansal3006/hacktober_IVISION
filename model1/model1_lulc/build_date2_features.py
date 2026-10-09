"""
Build the full-raster feature stack for the new 2021-05-01 Sentinel-2
scene, apply SCL-based cloud/shadow masking (same policy as
config.yaml:sentinel2.scl_exclude_values, for consistency with the
existing pipeline), and cache to disk for the multi-temporal experiments.

Does not touch any production file. Output: data/processed/features/
date2_20210501_cache.pkl
"""
from __future__ import annotations

import pickle

import numpy as np
import rasterio

from src.config import load_config
from src.features import build_feature_stack, FEATURE_ORDER

DATE2_DIR = "data/raw/sentinel2_20210501"
OUT_PATH = "data/processed/features/date2_20210501_cache.pkl"


def main():
    cfg = load_config()
    scl_exclude = set(cfg["sentinel2"]["scl_exclude_values"])

    bands = {}
    for logical, code in cfg["sentinel2"]["bands"].items():
        with rasterio.open(f"{DATE2_DIR}/{code}.tif") as src:
            arr = src.read(1).astype(np.float32)
            nodata = src.nodata
            nodata_mask = (arr == nodata) if nodata is not None else np.zeros(arr.shape, dtype=bool)
            arr[nodata_mask] = np.nan
            if logical == "blue":
                ref_transform, ref_crs, ref_shape = src.transform, src.crs, arr.shape
                combined_nodata_mask = nodata_mask.copy()
            else:
                combined_nodata_mask |= nodata_mask
        bands[logical] = arr

    with rasterio.open(f"{DATE2_DIR}/SCL.tif") as src:
        scl = src.read(1)
        assert src.transform == ref_transform and src.crs == ref_crs and src.shape == ref_shape, \
            "SCL grid does not match band grid — cannot proceed without alignment."

    scl_bad = np.isin(scl, list(scl_exclude))
    valid_mask_date2 = (~combined_nodata_mask) & (~scl_bad)
    pct_valid = 100 * valid_mask_date2.sum() / valid_mask_date2.size
    print(f"Date2 (2021-05-01) valid pixels after nodata+SCL masking "
          f"(exclude={sorted(scl_exclude)}): {pct_valid:.2f}%")

    feat_dict = build_feature_stack(
        blue=bands["blue"], green=bands["green"], red=bands["red"],
        nir=bands["nir"], swir=bands["swir"], eps=cfg["features"]["epsilon"],
    )
    # Rename to date2-suffixed keys, keep FEATURE_ORDER's base ordering
    date2_features = {f"{name}_date2": feat_dict[name] for name in FEATURE_ORDER}

    with open(OUT_PATH, "wb") as f:
        pickle.dump({
            "features": date2_features,  # dict of {name: 2D array}
            "valid_mask": valid_mask_date2,
            "transform": ref_transform,
            "crs": ref_crs,
            "feature_order_base": FEATURE_ORDER,
        }, f, protocol=pickle.HIGHEST_PROTOCOL)
    print(f"Cached date2 feature stack to {OUT_PATH}")


if __name__ == "__main__":
    main()
