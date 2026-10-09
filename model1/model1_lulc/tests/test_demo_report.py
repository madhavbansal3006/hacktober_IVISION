"""
Tests for src/demo_report.py — the presentation/reliability layer.
Uses small synthetic in-memory rasters/dataframes to test guard logic in
isolation; never touches real production outputs.
"""
import numpy as np
import pandas as pd
import pytest
import rasterio
from rasterio.transform import from_origin

from src.demo_report import (
    load_confidence_aligned, confidence_tier, load_watershed_statistics,
    get_watershed_lulc_percentages, watershed_reliability_summary,
    UnreliableWatershedError, RELIABLE_COVERAGE_CATEGORIES,
)


def _write_raster(path, arr, dtype, nodata, crs="EPSG:32643"):
    transform = from_origin(500000, 1700000, 10, 10)
    profile = {"driver": "GTiff", "dtype": dtype, "count": 1, "height": arr.shape[0],
               "width": arr.shape[1], "crs": crs, "transform": transform, "nodata": nodata}
    with rasterio.open(path, "w", **profile) as dst:
        dst.write(arr, 1)


def test_load_confidence_aligned_uses_prediction_nodata_not_confidence_tag(tmp_path):
    # SYNTHETIC: replicate the real bug — confidence raster declares
    # nodata=-1.0 but invalid pixels are actually stored as 0.0.
    pred = np.array([[1, 0], [2, 0]], dtype=np.uint8)  # 0 = nodata
    conf = np.array([[0.9, 0.0], [0.8, 0.0]], dtype=np.float32)  # invalid pixels stored as 0.0, not -1.0

    pred_path = tmp_path / "pred.tif"
    conf_path = tmp_path / "conf.tif"
    _write_raster(str(pred_path), pred, "uint8", 0)
    _write_raster(str(conf_path), conf, "float32", -1.0)  # mismatched nodata tag, like the real file

    conf_arr, valid_mask = load_confidence_aligned(str(pred_path), str(conf_path))
    # Validity must come from the prediction raster (2 valid pixels), not from
    # matching conf_arr against its own (unused) -1.0 nodata tag.
    assert valid_mask.sum() == 2
    assert valid_mask[0, 0] and valid_mask[1, 0]
    assert not valid_mask[0, 1] and not valid_mask[1, 1]


def test_load_confidence_aligned_rejects_misaligned_rasters(tmp_path):
    pred = np.zeros((2, 2), dtype=np.uint8)
    conf = np.zeros((3, 3), dtype=np.float32)  # different shape
    pred_path, conf_path = tmp_path / "pred.tif", tmp_path / "conf.tif"
    _write_raster(str(pred_path), pred, "uint8", 0)
    _write_raster(str(conf_path), conf, "float32", -1.0)
    with pytest.raises(ValueError):
        load_confidence_aligned(str(pred_path), str(conf_path))


def test_confidence_tier_boundaries():
    assert confidence_tier(0.3) == "low"
    assert confidence_tier(0.5) == "medium"
    assert confidence_tier(0.74) == "medium"
    assert confidence_tier(0.75) == "high"
    assert confidence_tier(1.0) == "high"


def _synthetic_watershed_df():
    return pd.DataFrame({
        "micro_watershed_id": ["A", "B", "C", "D"],
        "pct_of_watershed_within_raster_extent": [95.0, 80.0, 40.0, 95.0],
        "valid_pixel_count": [5000, 3000, 500, 10],
        "coverage_category": ["GOOD", "ACCEPTABLE", "LOW", "INSUFFICIENT_DATA"],
        "forest_percent": [50.0, 40.0, 20.0, 60.0],
        "agriculture_percent": [50.0, 60.0, 80.0, 40.0],
        "dominant_class": ["Forest", "Agriculture", "Agriculture", "Forest"],
    })


def test_get_watershed_lulc_percentages_good_watershed_succeeds():
    df = _synthetic_watershed_df()
    result = get_watershed_lulc_percentages(df, "A")
    assert result["reliable"] is True
    assert result["coverage_category"] == "GOOD"
    assert result["lulc_percentages"]["forest_percent"] == 50.0


def test_get_watershed_lulc_percentages_low_watershed_raises_by_default():
    df = _synthetic_watershed_df()
    with pytest.raises(UnreliableWatershedError):
        get_watershed_lulc_percentages(df, "C")


def test_get_watershed_lulc_percentages_insufficient_data_raises_by_default():
    df = _synthetic_watershed_df()
    with pytest.raises(UnreliableWatershedError):
        get_watershed_lulc_percentages(df, "D")


def test_get_watershed_lulc_percentages_low_watershed_allowed_with_explicit_opt_in():
    df = _synthetic_watershed_df()
    result = get_watershed_lulc_percentages(df, "C", allow_unreliable=True)
    assert result["reliable"] is False
    assert result["coverage_category"] == "LOW"


def test_get_watershed_lulc_percentages_unknown_id_raises_keyerror():
    df = _synthetic_watershed_df()
    with pytest.raises(KeyError):
        get_watershed_lulc_percentages(df, "ZZZ")


def test_watershed_reliability_summary_counts():
    df = _synthetic_watershed_df()
    summary = watershed_reliability_summary(df)
    assert summary["total_watersheds"] == 4
    assert summary["reliable_count"] == 2
    assert summary["unreliable_count"] == 2
    assert set(summary["unreliable_watershed_ids"]) == {"C", "D"}


def test_load_watershed_statistics_rejects_missing_columns(tmp_path):
    bad_csv = tmp_path / "bad.csv"
    pd.DataFrame({"micro_watershed_id": ["A"]}).to_csv(bad_csv, index=False)
    with pytest.raises(ValueError):
        load_watershed_statistics(str(bad_csv))


def test_load_watershed_statistics_rejects_invalid_category(tmp_path):
    bad_csv = tmp_path / "bad.csv"
    pd.DataFrame({
        "micro_watershed_id": ["A"],
        "pct_of_watershed_within_raster_extent": [90.0],
        "coverage_category": ["SUPER_GOOD"],  # not an allowed category
    }).to_csv(bad_csv, index=False)
    with pytest.raises(ValueError):
        load_watershed_statistics(str(bad_csv))
