"""
Combine harmonized Sentinel-2 bands, the SCL quality mask, and the
remapped WorldCover reference labels into a single aligned feature stack
ready for sampling and model training/inference.

This module assumes download_sentinel.run() and prepare_reference's
mapping have already produced arrays on the SAME grid (same transform,
CRS, shape). It does not re-reproject — grid alignment is the
responsibility of download_sentinel.py (bands resampled to the 10m
reference grid) and prepare_reference.py (WorldCover clipped/reprojected
to that same grid before calling this module).
"""
from __future__ import annotations

import numpy as np

from src.features import build_feature_stack, stack_to_array, FEATURE_ORDER


def assemble_feature_stack(bands: dict, good_mask: np.ndarray, cfg: dict) -> tuple[np.ndarray, np.ndarray]:
    """Build the (rows, cols, n_features) feature array and a combined
    validity mask (good_mask AND all bands finite).

    bands: dict with keys 'blue','green','red','nir','swir' -> 2D arrays
    good_mask: boolean array, True = usable pixel (from SCL cloud mask)
    """
    feat_dict = build_feature_stack(
        blue=bands["blue"], green=bands["green"], red=bands["red"],
        nir=bands["nir"], swir=bands["swir"], eps=cfg["features"]["epsilon"],
    )
    feature_array = stack_to_array(feat_dict, order=cfg["features"]["names"])

    finite_mask = np.all(np.isfinite(feature_array), axis=-1)
    valid_mask = good_mask & finite_mask
    return feature_array, valid_mask


def align_labels_to_features(label_array: np.ndarray, valid_mask: np.ndarray, nodata_value: int = 0) -> np.ndarray:
    """Combine the remapped WorldCover label array with the feature
    validity mask: any pixel that is invalid in either is excluded (set to
    nodata_value) from the final training-eligible label array.
    """
    if label_array.shape != valid_mask.shape:
        raise ValueError(
            f"Label array shape {label_array.shape} does not match feature validity "
            f"mask shape {valid_mask.shape}. Bands and reference labels must be on "
            f"the identical grid before calling this function."
        )
    out = label_array.copy()
    out[~valid_mask] = nodata_value
    return out
