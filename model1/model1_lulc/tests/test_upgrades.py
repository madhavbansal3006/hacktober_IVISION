"""
Tests for the quality-upgrade modules: BSI index, prediction confidence,
watershed coverage categorization, and metadata validation.

SYNTHETIC DATA NOTICE: all arrays here are small hand-built numpy arrays
for testing formulas/logic in isolation — never satellite imagery, never
written to outputs/, never treated as real results.
"""
import json

import numpy as np
import pytest

from src.features import compute_bsi, build_feature_stack, FEATURE_ORDER
from src.predict import predict_full_raster, apply_conservative_cleanup
from src.zonal_statistics import classify_coverage, COVERAGE_THRESHOLDS, INSUFFICIENT_DATA_MIN_VALID_PIXELS
from src.validate_output import validate_metadata_json, ValidationError


def test_bsi_positive_for_bare_soil_like_pixel():
    # SYNTHETIC: bare soil -> high SWIR+Red, low NIR+Blue.
    swir = np.array([[0.4]]); red = np.array([[0.3]])
    nir = np.array([[0.15]]); blue = np.array([[0.1]])
    bsi = compute_bsi(swir, red, nir, blue)
    assert bsi[0, 0] > 0


def test_bsi_negative_for_vegetation_like_pixel():
    # SYNTHETIC: healthy vegetation -> high NIR, low SWIR/Red.
    swir = np.array([[0.1]]); red = np.array([[0.05]])
    nir = np.array([[0.5]]); blue = np.array([[0.05]])
    bsi = compute_bsi(swir, red, nir, blue)
    assert bsi[0, 0] < 0


def test_bsi_zero_denominator_safe():
    swir = np.array([[0.0]]); red = np.array([[0.0]])
    nir = np.array([[0.0]]); blue = np.array([[0.0]])
    bsi = compute_bsi(swir, red, nir, blue)
    assert np.isfinite(bsi[0, 0])
    assert bsi[0, 0] == 0.0


def test_feature_stack_includes_bsi():
    shape = (3, 3)
    bands = {name: np.random.default_rng(2).uniform(0, 1, shape) for name in
              ["blue", "green", "red", "nir", "swir"]}
    feats = build_feature_stack(**bands)
    assert "BSI" in feats
    assert "BSI" in FEATURE_ORDER
    assert feats["BSI"].shape == shape


class _FakeProbaModel:
    """SYNTHETIC stand-in classifier exposing predict_proba, used only to
    test confidence-array reconstruction — not a real trained model.
    """
    classes_ = np.array([1, 2], dtype=np.uint8)

    def predict(self, X):
        return np.ones(X.shape[0], dtype=np.uint8)

    def predict_proba(self, X):
        # Row 0: confident class 1 (0.9); Row 1: uncertain (0.5/0.5).
        out = np.tile([0.9, 0.1], (X.shape[0], 1))
        if X.shape[0] > 1:
            out[1] = [0.5, 0.5]
        return out


def test_predict_full_raster_confidence_range_and_shape():
    feature_array = np.random.default_rng(0).random((1, 2, 3))
    valid_mask = np.array([[True, True]])
    pred, conf = predict_full_raster(_FakeProbaModel(), feature_array, valid_mask,
                                      nodata_value=0, return_confidence=True)
    assert pred.shape == (1, 2)
    assert conf.shape == (1, 2)
    assert np.all((conf >= 0) & (conf <= 1))
    assert conf[0, 0] == pytest.approx(0.9)


def test_conservative_cleanup_only_touches_unanimous_isolated_pixels():
    # SYNTHETIC 3x3 grid: center pixel is class 2, all 8 neighbors are class 1.
    grid = np.array([
        [1, 1, 1],
        [1, 2, 1],
        [1, 1, 1],
    ], dtype=np.uint8)
    cleaned, stats = apply_conservative_cleanup(grid, nodata_value=0)
    assert cleaned[1, 1] == 1  # reclassified — truly isolated single pixel
    assert stats["n_pixels_changed"] == 1


def test_conservative_cleanup_preserves_small_legitimate_feature():
    # SYNTHETIC: a 2-pixel "pond" (class 3) inside class 1 — neither pond
    # pixel has ALL 8 neighbors disagreeing (each has at least one
    # same-class neighbor), so cleanup must NOT erase it.
    grid = np.array([
        [1, 1, 1, 1],
        [1, 3, 3, 1],
        [1, 1, 1, 1],
    ], dtype=np.uint8)
    cleaned, stats = apply_conservative_cleanup(grid, nodata_value=0)
    assert (cleaned == 3).sum() == 2  # pond pixels preserved


def test_conservative_cleanup_never_touches_nodata():
    grid = np.array([[0, 1], [1, 1]], dtype=np.uint8)
    cleaned, stats = apply_conservative_cleanup(grid, nodata_value=0)
    assert cleaned[0, 0] == 0


def test_coverage_classification_good_acceptable_low():
    assert classify_coverage(95.0, valid_pixel_count=5000) == "GOOD"
    assert classify_coverage(80.0, valid_pixel_count=5000) == "ACCEPTABLE"
    assert classify_coverage(50.0, valid_pixel_count=5000) == "LOW"


def test_coverage_classification_insufficient_data_overrides_percentage():
    # SYNTHETIC: 95% coverage but only 10 valid pixels -> still INSUFFICIENT_DATA.
    assert classify_coverage(95.0, valid_pixel_count=10) == "INSUFFICIENT_DATA"
    assert INSUFFICIENT_DATA_MIN_VALID_PIXELS > 10


def test_metadata_validation_rejects_missing_keys(tmp_path):
    incomplete = {"satellite": "UNKNOWN"}  # missing everything else required
    path = tmp_path / "bad_metadata.json"
    with open(path, "w") as f:
        json.dump(incomplete, f)
    with pytest.raises(ValidationError):
        validate_metadata_json(str(path))
