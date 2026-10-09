"""
Spectral feature / index calculations.

All functions operate on numpy arrays (float) of matching shape and use
safe division so that division-by-zero produces 0.0 rather than inf/nan.
"""
from __future__ import annotations

import numpy as np


def safe_divide(numerator: np.ndarray, denominator: np.ndarray, eps: float = 1e-6) -> np.ndarray:
    """Element-wise division that returns 0.0 wherever the denominator is
    (near) zero instead of raising or producing inf/nan.
    """
    numerator = numerator.astype(np.float32)
    denominator = denominator.astype(np.float32)
    out = np.zeros_like(numerator, dtype=np.float32)
    mask = np.abs(denominator) > eps
    out[mask] = numerator[mask] / denominator[mask]
    return out


def compute_ndvi(nir: np.ndarray, red: np.ndarray, eps: float = 1e-6) -> np.ndarray:
    """NDVI = (NIR - Red) / (NIR + Red). Range approx [-1, 1]."""
    return safe_divide(nir - red, nir + red, eps)


def compute_ndwi(green: np.ndarray, nir: np.ndarray, eps: float = 1e-6) -> np.ndarray:
    """NDWI (McFeeters) = (Green - NIR) / (Green + NIR). Positive -> water."""
    return safe_divide(green - nir, green + nir, eps)


def compute_ndbi(swir: np.ndarray, nir: np.ndarray, eps: float = 1e-6) -> np.ndarray:
    """NDBI = (SWIR - NIR) / (SWIR + NIR). Positive -> built-up."""
    return safe_divide(swir - nir, swir + nir, eps)


def compute_bsi(swir, red, nir, blue, eps: float = 1e-6) -> np.ndarray:
    """BSI (Bare Soil Index) = ((SWIR+Red) - (NIR+Blue)) / ((SWIR+Red) + (NIR+Blue)).
    Positive -> bare soil / built-up-like; negative -> vegetation/water.
    """
    num = (swir + red) - (nir + blue)
    den = (swir + red) + (nir + blue)
    return safe_divide(num, den, eps)


def build_feature_stack(blue, green, red, nir, swir, eps: float = 1e-6) -> dict:
    """Compute all derived indices and return a dict of {feature_name: array}
    in the exact order defined by config.yaml's features.names.

    All inputs must be float arrays of identical shape (rows, cols).
    """
    shapes = {a.shape for a in [blue, green, red, nir, swir]}
    if len(shapes) != 1:
        raise ValueError(f"Band arrays must share identical shape, got shapes: {shapes}")

    ndvi = compute_ndvi(nir, red, eps)
    ndwi = compute_ndwi(green, nir, eps)
    ndbi = compute_ndbi(swir, nir, eps)
    bsi = compute_bsi(swir, red, nir, blue, eps)

    return {
        "B2": blue.astype(np.float32),
        "B3": green.astype(np.float32),
        "B4": red.astype(np.float32),
        "B8": nir.astype(np.float32),
        "B11": swir.astype(np.float32),
        "NDVI": ndvi,
        "NDWI": ndwi,
        "NDBI": ndbi,
        "BSI": bsi,
    }


FEATURE_ORDER = ["B2", "B3", "B4", "B8", "B11", "NDVI", "NDWI", "NDBI", "BSI"]


def stack_to_array(feature_dict: dict, order: list[str] = FEATURE_ORDER) -> np.ndarray:
    """Stack a {name: 2D array} dict into a (rows, cols, n_features) array
    in a guaranteed, explicit feature order.
    """
    return np.stack([feature_dict[name] for name in order], axis=-1)
