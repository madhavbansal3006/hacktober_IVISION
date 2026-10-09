"""
Unit tests for spectral index math (src/features.py).

These use small SYNTHETIC numpy arrays purely to test formula correctness
— they are not satellite data and are never treated as such anywhere else
in the pipeline.
"""
import numpy as np
import pytest

from src.features import (
    safe_divide, compute_ndvi, compute_ndwi, compute_ndbi,
    build_feature_stack, stack_to_array, FEATURE_ORDER,
)


def test_safe_divide_normal():
    num = np.array([4.0, 9.0])
    den = np.array([2.0, 3.0])
    out = safe_divide(num, den)
    np.testing.assert_allclose(out, [2.0, 3.0])


def test_safe_divide_zero_denominator_does_not_raise_or_produce_inf():
    num = np.array([1.0, 5.0])
    den = np.array([0.0, 0.0])
    out = safe_divide(num, den)
    assert np.all(np.isfinite(out))
    np.testing.assert_allclose(out, [0.0, 0.0])


def test_ndvi_positive_when_nir_greater_than_red():
    nir = np.array([[0.5]])
    red = np.array([[0.1]])
    ndvi = compute_ndvi(nir, red)
    assert ndvi[0, 0] > 0


def test_ndvi_negative_when_nir_less_than_red():
    nir = np.array([[0.1]])
    red = np.array([[0.5]])
    ndvi = compute_ndvi(nir, red)
    assert ndvi[0, 0] < 0


def test_ndvi_range_bounded():
    rng = np.random.default_rng(0)
    nir = rng.uniform(0, 1, size=(20, 20))
    red = rng.uniform(0, 1, size=(20, 20))
    ndvi = compute_ndvi(nir, red)
    assert ndvi.min() >= -1.0001
    assert ndvi.max() <= 1.0001


def test_ndwi_positive_for_water_like_pixel():
    # Water: green reflectance > NIR reflectance (NIR strongly absorbed by water)
    green = np.array([[0.3]])
    nir = np.array([[0.05]])
    ndwi = compute_ndwi(green, nir)
    assert ndwi[0, 0] > 0


def test_ndbi_positive_for_builtup_like_pixel():
    # Built-up: SWIR reflectance > NIR reflectance
    swir = np.array([[0.4]])
    nir = np.array([[0.2]])
    ndbi = compute_ndbi(swir, nir)
    assert ndbi[0, 0] > 0


def test_build_feature_stack_shape_and_keys():
    shape = (5, 5)
    bands = {name: np.random.default_rng(1).uniform(0, 1, shape) for name in
              ["blue", "green", "red", "nir", "swir"]}
    feats = build_feature_stack(**bands)
    assert set(feats.keys()) == set(FEATURE_ORDER)
    for arr in feats.values():
        assert arr.shape == shape


def test_build_feature_stack_rejects_mismatched_shapes():
    good = np.zeros((3, 3))
    bad = np.zeros((4, 4))
    with pytest.raises(ValueError):
        build_feature_stack(blue=good, green=good, red=good, nir=bad, swir=good)


def test_stack_to_array_preserves_feature_order():
    shape = (2, 2)
    feats = {name: np.full(shape, i) for i, name in enumerate(FEATURE_ORDER)}
    arr = stack_to_array(feats, order=FEATURE_ORDER)
    assert arr.shape == (2, 2, len(FEATURE_ORDER))
    for i, name in enumerate(FEATURE_ORDER):
        assert np.all(arr[:, :, i] == i)
