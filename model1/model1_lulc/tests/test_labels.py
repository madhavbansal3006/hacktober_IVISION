"""
Unit tests for WorldCover class-mapping logic (src/prepare_reference.py)
and label/nodata alignment (src/preprocess.py).

SYNTHETIC DATA NOTICE: every array here is a small hand-built numpy array
used only to test mapping/masking logic in isolation. None of it is
satellite imagery or real WorldCover pixels, and it is never written to
any output file or treated as a real classification result anywhere in
this test module or elsewhere in the codebase.
"""
import numpy as np
import pytest

from src.prepare_reference import map_worldcover_to_target
from src.preprocess import align_labels_to_features


class _FakeCfg(dict):
    """Minimal config stand-in exposing only what map_worldcover_to_target needs."""
    pass


def make_cfg(strategy="exclude"):
    return {
        "reference_lulc": {
            "class_mapping": {10: 1, 40: 2, 80: 3, 50: 4, 60: 5},
            "ambiguous_classes": [20, 30],
            "ambiguous_class_strategy": strategy,
            "ambiguous_mapping": {20: 5, 30: 5},
        }
    }


def test_clean_classes_map_correctly():
    # SYNTHETIC: a tiny 1x6 "raster" covering one pixel of each clean WorldCover class.
    wc = np.array([[10, 40, 80, 50, 60, 70]], dtype=np.uint8)  # 70 = Snow/Ice, not in mapping
    cfg = make_cfg(strategy="exclude")
    out = map_worldcover_to_target(wc, cfg)
    expected = np.array([[1, 2, 3, 4, 5, 0]], dtype=np.uint8)  # 70 -> 0 (unmapped, excluded)
    np.testing.assert_array_equal(out, expected)


def test_ambiguous_classes_excluded_by_default():
    # SYNTHETIC pixels of Grassland (30) and Shrubland (20).
    wc = np.array([[20, 30]], dtype=np.uint8)
    cfg = make_cfg(strategy="exclude")
    out = map_worldcover_to_target(wc, cfg)
    np.testing.assert_array_equal(out, np.array([[0, 0]], dtype=np.uint8))


def test_ambiguous_classes_mapped_when_strategy_is_map():
    wc = np.array([[20, 30]], dtype=np.uint8)
    cfg = make_cfg(strategy="map")
    out = map_worldcover_to_target(wc, cfg)
    np.testing.assert_array_equal(out, np.array([[5, 5]], dtype=np.uint8))  # both -> Barren per config


def test_unmapped_class_never_guessed():
    # SYNTHETIC: Mangroves (95) has no entry anywhere in class_mapping or
    # ambiguous_mapping — must become NoData (0), never silently assigned
    # to a random target class.
    wc = np.array([[95]], dtype=np.uint8)
    cfg = make_cfg(strategy="map")
    out = map_worldcover_to_target(wc, cfg)
    assert out[0, 0] == 0


def test_align_labels_drops_invalid_pixels():
    # SYNTHETIC label raster + a feature-validity mask with one bad pixel.
    labels = np.array([[1, 2], [3, 4]], dtype=np.uint8)
    valid_mask = np.array([[True, False], [True, True]])
    out = align_labels_to_features(labels, valid_mask, nodata_value=0)
    expected = np.array([[1, 0], [3, 4]], dtype=np.uint8)
    np.testing.assert_array_equal(out, expected)


def test_align_labels_shape_mismatch_raises():
    labels = np.zeros((2, 2), dtype=np.uint8)
    valid_mask = np.zeros((3, 3), dtype=bool)
    with pytest.raises(ValueError):
        align_labels_to_features(labels, valid_mask, nodata_value=0)
