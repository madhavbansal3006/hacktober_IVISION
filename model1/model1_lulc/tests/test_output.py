"""
Unit tests for prediction reconstruction (src/predict.py) and GeoTIFF
validation (src/validate_output.py).

SYNTHETIC DATA NOTICE: this module builds a tiny in-memory GeoTIFF from a
hand-crafted class array purely to test the validation/reconstruction
logic. It is written to a temporary file that pytest cleans up, is never
copied into outputs/, and must never be confused with the real
lulc_prediction.tif produced from actual Sentinel-2 imagery.
"""
import numpy as np
import pytest
import rasterio
from rasterio.transform import from_origin

from src.predict import predict_full_raster, write_prediction_geotiff
from src.validate_output import validate_prediction_geotiff, ValidationError


class _FakeModel:
    """Stand-in classifier: predicts class 1 for every input row.
    Used only to test that spatial reconstruction (flat -> rows x cols)
    is correct — no real Random Forest involved.
    """
    def predict(self, X):
        return np.ones(X.shape[0], dtype=np.uint8)


def test_predict_full_raster_preserves_shape_and_nodata():
    rows, cols, n_features = 4, 5, 3
    feature_array = np.random.default_rng(0).random((rows, cols, n_features))
    valid_mask = np.ones((rows, cols), dtype=bool)
    valid_mask[0, 0] = False  # one deliberately invalid pixel

    pred = predict_full_raster(_FakeModel(), feature_array, valid_mask, nodata_value=0)

    assert pred.shape == (rows, cols)
    assert pred[0, 0] == 0          # invalid pixel -> nodata
    assert pred[1, 1] == 1          # valid pixel -> predicted class from fake model


def test_predict_full_raster_rejects_all_invalid():
    feature_array = np.zeros((2, 2, 3))
    valid_mask = np.zeros((2, 2), dtype=bool)
    with pytest.raises(ValueError):
        predict_full_raster(_FakeModel(), feature_array, valid_mask, nodata_value=0)


def test_validate_geotiff_accepts_valid_synthetic_raster(tmp_path):
    # SYNTHETIC 3x3 raster with only expected class values {1,2,3,4,5} + nodata 0.
    arr = np.array([[1, 2, 0], [3, 4, 5], [1, 1, 2]], dtype=np.uint8)
    transform = from_origin(500000, 1700000, 10, 10)
    out_path = tmp_path / "synthetic_test_raster.tif"
    write_prediction_geotiff(arr, transform, "EPSG:32643", str(out_path), nodata_value=0)

    cfg = {"target_classes": {1: "Forest", 2: "Agriculture", 3: "Water", 4: "Built-up", 5: "Barren"}}
    results = validate_prediction_geotiff(str(out_path), cfg, boundary_gdf=None)
    assert results["opens_successfully"] is True
    assert set(results["unique_class_values"]) <= {1, 2, 3, 4, 5}


def test_validate_geotiff_rejects_unexpected_class_values(tmp_path):
    # SYNTHETIC raster deliberately containing an invalid class value (9).
    arr = np.array([[1, 9], [2, 3]], dtype=np.uint8)
    transform = from_origin(500000, 1700000, 10, 10)
    out_path = tmp_path / "synthetic_bad_raster.tif"
    write_prediction_geotiff(arr, transform, "EPSG:32643", str(out_path), nodata_value=0)

    cfg = {"target_classes": {1: "Forest", 2: "Agriculture", 3: "Water", 4: "Built-up", 5: "Barren"}}
    with pytest.raises(ValidationError):
        validate_prediction_geotiff(str(out_path), cfg, boundary_gdf=None)
