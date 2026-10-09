import geopandas as gpd
import numpy as np
import pytest
import rasterio
from pyproj import Transformer
from affine import Affine


def _from_origin(west, north, xsize, ysize):
    """Equivalent to rasterio.transform.from_origin, built directly to
    avoid that helper's internal PendingDeprecationWarning (matmul vs mul)."""
    return Affine(xsize, 0.0, west, 0.0, -ysize, north)

from rasterio.transform import xy as transform_xy

from src.config import LULC_CLASS_MAP
from src.lulc_query import (
    STATUS_NODATA_PIXEL,
    STATUS_OK,
    STATUS_OUTSIDE_RASTER_EXTENT,
    LULCQuery,
)

_WGS84_FROM_UTM43N = Transformer.from_crs("EPSG:32643", "EPSG:4326", always_xy=True)
_UTM43N_FROM_WGS84 = Transformer.from_crs("EPSG:4326", "EPSG:32643", always_xy=True)


def _latlon_for_pixel(transform, row, col):
    x, y = transform_xy(transform, row, col)
    lon, lat = _WGS84_FROM_UTM43N.transform(x, y)
    return lat, lon


def _write_raster(path, array, transform, nodata=0):
    with rasterio.open(
        path,
        "w",
        driver="GTiff",
        height=array.shape[0],
        width=array.shape[1],
        count=1,
        dtype=array.dtype,
        crs="EPSG:32643",
        transform=transform,
        nodata=nodata,
    ) as dst:
        dst.write(array, 1)


# Arbitrary origin in a plausible UTM43N range (matches real raster's ballpark).
_ORIGIN_X, _ORIGIN_Y = 520000, 1660000


class TestSyntheticRaster:
    def test_known_class_value(self, tmp_path):
        array = np.array([[0, 0, 0], [0, 2, 0], [0, 0, 0]], dtype=np.uint8)
        transform = _from_origin(_ORIGIN_X, _ORIGIN_Y, 10, 10)
        path = tmp_path / "r.tif"
        _write_raster(path, array, transform)
        lat, lon = _latlon_for_pixel(transform, 1, 1)

        result = LULCQuery(path).query(lat, lon)
        assert result.status == STATUS_OK
        assert result.lulc_value == 2
        assert result.lulc_class == "Agriculture"
        assert result.raster_pixel_row == 1
        assert result.raster_pixel_col == 1

    def test_nodata_pixel(self, tmp_path):
        array = np.zeros((3, 3), dtype=np.uint8)
        transform = _from_origin(_ORIGIN_X, _ORIGIN_Y, 10, 10)
        path = tmp_path / "r.tif"
        _write_raster(path, array, transform)
        lat, lon = _latlon_for_pixel(transform, 1, 1)

        result = LULCQuery(path).query(lat, lon)
        assert result.status == STATUS_NODATA_PIXEL
        assert result.lulc_value == 0
        assert result.lulc_class == "NODATA"

    def test_unknown_class_value_not_in_map(self, tmp_path):
        array = np.array([[0, 0, 0], [0, 9, 0], [0, 0, 0]], dtype=np.uint8)
        transform = _from_origin(_ORIGIN_X, _ORIGIN_Y, 10, 10)
        path = tmp_path / "r.tif"
        _write_raster(path, array, transform)
        lat, lon = _latlon_for_pixel(transform, 1, 1)

        result = LULCQuery(path).query(lat, lon)
        assert result.lulc_value == 9
        assert result.lulc_class == "UNKNOWN_CLASS_9"
        assert result.status == STATUS_OK  # 9 != declared nodata (0)

    def test_outside_raster_extent(self, tmp_path):
        array = np.ones((3, 3), dtype=np.uint8)
        transform = _from_origin(_ORIGIN_X, _ORIGIN_Y, 10, 10)
        path = tmp_path / "r.tif"
        _write_raster(path, array, transform)

        result = LULCQuery(path).query(latitude=0.0, longitude=0.0)
        assert result.status == STATUS_OUTSIDE_RASTER_EXTENT
        assert result.lulc_value is None
        assert result.raster_pixel_row is None

    def test_neighborhood_purity_and_nodata_pct(self, tmp_path):
        array = np.array(
            [
                [1, 1, 1, 1, 1],
                [1, 2, 2, 2, 1],
                [1, 2, 1, 2, 1],
                [1, 2, 2, 2, 1],
                [1, 1, 1, 1, 1],
            ],
            dtype=np.uint8,
        )
        transform = _from_origin(_ORIGIN_X, _ORIGIN_Y, 10, 10)
        path = tmp_path / "r.tif"
        _write_raster(path, array, transform)
        lat, lon = _latlon_for_pixel(transform, 2, 2)  # center, value=1

        result = LULCQuery(path, neighborhood_window=3).query(lat, lon)
        assert result.lulc_value == 1
        assert result.neighborhood_window_size == 3
        # 3x3 window around (2,2): [[2,2,2],[2,1,2],[2,2,2]] -> 1/9 match center value
        assert result.neighborhood_class_purity_pct == pytest.approx(100 * 1 / 9)
        assert result.neighborhood_nodata_pct == pytest.approx(0.0)

    def test_neighborhood_stats_at_grid_edge_do_not_crash(self, tmp_path):
        """Sampling a corner pixel means the window is clipped by the array
        bounds -- must not index out of range or divide incorrectly."""
        array = np.array([[3, 1], [1, 1]], dtype=np.uint8)
        transform = _from_origin(_ORIGIN_X, _ORIGIN_Y, 10, 10)
        path = tmp_path / "r.tif"
        _write_raster(path, array, transform)
        lat, lon = _latlon_for_pixel(transform, 0, 0)  # top-left corner

        result = LULCQuery(path, neighborhood_window=3).query(lat, lon)
        assert result.lulc_value == 3
        # window clipped to the 2x2 available area: [[3,1],[1,1]] -> 1/4 match
        assert result.neighborhood_class_purity_pct == pytest.approx(100 * 1 / 4)

    def test_wrong_crs_raises(self, tmp_path):
        array = np.ones((3, 3), dtype=np.uint8)
        transform = _from_origin(75.0, 15.0, 0.001, 0.001)
        path = tmp_path / "r.tif"
        with rasterio.open(
            path, "w", driver="GTiff", height=3, width=3, count=1,
            dtype=array.dtype, crs="EPSG:4326", transform=transform, nodata=0,
        ) as dst:
            dst.write(array, 1)

        with pytest.raises(ValueError, match="CRS"):
            LULCQuery(path)

    def test_invalid_even_window_size_raises(self, tmp_path):
        array = np.ones((3, 3), dtype=np.uint8)
        transform = _from_origin(_ORIGIN_X, _ORIGIN_Y, 10, 10)
        path = tmp_path / "r.tif"
        _write_raster(path, array, transform)

        with pytest.raises(ValueError, match="odd"):
            LULCQuery(path, neighborhood_window=4)


class TestRealLULCRaster:
    """
    Integration tests against the actual audited lulc_prediction.tif.
    Expected values are computed independently via a direct rasterio read
    in the test itself, not hardcoded -- so this validates LULCQuery's
    reprojection + indexing logic against ground truth from the file,
    rather than testing against a guessed number.
    """

    def test_representative_point_matches_direct_raster_read(self):
        boundary_gdf = gpd.read_file("data/raw/study_area/shiggaon_boundary.gpkg")
        rep_point = boundary_gdf.geometry.iloc[0].representative_point()

        result = LULCQuery().query(latitude=rep_point.y, longitude=rep_point.x)

        with rasterio.open("data/raw/lulc/lulc_prediction.tif") as src:
            x, y = _UTM43N_FROM_WGS84.transform(rep_point.x, rep_point.y)
            expected_row, expected_col = src.index(x, y)
            expected_value = int(src.read(1)[expected_row, expected_col])

        assert result.raster_pixel_row == expected_row
        assert result.raster_pixel_col == expected_col
        assert result.lulc_value == expected_value
        assert result.lulc_class == LULC_CLASS_MAP.get(
            expected_value, f"UNKNOWN_CLASS_{expected_value}"
        )

    def test_all_five_confirmed_classes_are_mapped(self):
        """Every non-nodata value seen in the actual raster (per Phase 1
        audit: 1-5) must map to a real class name, not UNKNOWN_CLASS_n."""
        for value in (1, 2, 3, 4, 5):
            assert LULC_CLASS_MAP[value] != f"UNKNOWN_CLASS_{value}"
        assert LULC_CLASS_MAP[0] == "NODATA"
