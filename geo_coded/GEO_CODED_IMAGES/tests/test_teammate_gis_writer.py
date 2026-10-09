import geopandas as gpd
import pytest

from src.schema import SCHEMA_VERSION, GeoCodedResult
from src.teammate_gis_writer import write_photo_mws_joined_gpkg, write_photo_points_gpkg


def _make_result(**overrides) -> GeoCodedResult:
    defaults = dict(
        schema_version=SCHEMA_VERSION,
        image_name="photo_001.jpg",
        processing_timestamp="2026-08-31T10:15:00+00:00",
        latitude=15.01234,
        longitude=75.21345,
        status="OK",
        error_reason=None,
        inside_study_area=True,
        micro_watershed_id="g_mws.240575",
        mws_code="4D4F2m3",
        lulc_value=2,
        lulc_class="Agriculture",
        raster_pixel_row=1842,
        raster_pixel_col=2210,
        lulc_neighborhood_window_size=3,
        lulc_neighborhood_class_purity_pct=88.89,
        lulc_neighborhood_nodata_pct=0.0,
        image_id="IMG_0001",
        file_path="/data/photos/photo_001.jpg",
        capture_datetime="2026-03-14T09:21:07",
        gps_source="EXIF",
        gps_accuracy_m=4.5,
        coordinate_status="VALID",
        study_area_status="INSIDE",
    )
    defaults.update(overrides)
    return GeoCodedResult(**defaults)


def _make_no_coordinate_result(**overrides) -> GeoCodedResult:
    defaults = dict(
        schema_version=SCHEMA_VERSION,
        image_name="no_gps.jpg",
        processing_timestamp="2026-08-31T10:16:00+00:00",
        latitude=None,
        longitude=None,
        status="NO_GPS",
        error_reason="No GPS IFD present in EXIF metadata",
        inside_study_area=None,
        micro_watershed_id=None,
        mws_code=None,
        lulc_value=None,
        lulc_class=None,
        raster_pixel_row=None,
        raster_pixel_col=None,
        lulc_neighborhood_window_size=None,
        lulc_neighborhood_class_purity_pct=None,
        lulc_neighborhood_nodata_pct=None,
        image_id="IMG_0002",
        file_path="/data/photos/no_gps.jpg",
        capture_datetime=None,
        gps_source=None,
        gps_accuracy_m=None,
        coordinate_status="MISSING",
        study_area_status=None,
    )
    defaults.update(overrides)
    return GeoCodedResult(**defaults)


class TestPhotoPointsGpkg:
    def test_writes_valid_gpkg_with_point_geometry(self, tmp_path):
        path = write_photo_points_gpkg([_make_result()], tmp_path / "points.gpkg")
        gdf = gpd.read_file(path)
        assert len(gdf) == 1
        assert gdf.crs.to_string() == "EPSG:4326"
        assert gdf.geometry.iloc[0].geom_type == "Point"

    def test_geometry_matches_lat_lon(self, tmp_path):
        result = _make_result(latitude=15.01234, longitude=75.21345)
        path = write_photo_points_gpkg([result], tmp_path / "points.gpkg")
        gdf = gpd.read_file(path)
        pt = gdf.geometry.iloc[0]
        assert pt.x == pytest.approx(75.21345)
        assert pt.y == pytest.approx(15.01234)

    def test_excludes_results_without_coordinates(self, tmp_path):
        """'One point per successfully geocoded photo' -- a NO_GPS result
        has no coordinate and must not appear in the point layer at all."""
        results = [_make_result(), _make_no_coordinate_result()]
        path = write_photo_points_gpkg(results, tmp_path / "points.gpkg")
        gdf = gpd.read_file(path)
        assert len(gdf) == 1
        assert gdf.iloc[0]["image_id"] == "IMG_0001"

    def test_includes_outside_study_area_points(self, tmp_path):
        """A photo outside the study area still HAS a valid coordinate --
        it must still appear as a point (per user's explicit instruction:
        'successfully geocoded' means has coordinates, not 'inside the
        study area')."""
        result = _make_result(
            image_id="IMG_0003", status="OUTSIDE_STUDY_AREA",
            coordinate_status="OUTSIDE_STUDY_AREA", study_area_status="OUTSIDE",
            inside_study_area=False, micro_watershed_id=None, mws_code=None,
            lulc_value=None, lulc_class=None, latitude=15.0, longitude=65.0,
        )
        path = write_photo_points_gpkg([result], tmp_path / "points.gpkg")
        gdf = gpd.read_file(path)
        assert len(gdf) == 1
        assert gdf.iloc[0]["status"] == "OUTSIDE_STUDY_AREA"

    def test_does_not_include_mws_columns(self, tmp_path):
        """The base points layer intentionally excludes mws_id/mws_code --
        that's the joined layer's job."""
        path = write_photo_points_gpkg([_make_result()], tmp_path / "points.gpkg")
        gdf = gpd.read_file(path)
        assert "mws_id" not in gdf.columns
        assert "mws_code" not in gdf.columns

    def test_attribute_values_correct(self, tmp_path):
        path = write_photo_points_gpkg([_make_result()], tmp_path / "points.gpkg")
        gdf = gpd.read_file(path)
        row = gdf.iloc[0]
        assert row["image_id"] == "IMG_0001"
        assert row["file_name"] == "photo_001.jpg"
        assert row["lulc_class"] == "Agriculture"
        assert row["coordinate_status"] == "VALID"

    def test_empty_results_writes_empty_but_valid_gpkg(self, tmp_path):
        path = write_photo_points_gpkg([], tmp_path / "points.gpkg")
        gdf = gpd.read_file(path)
        assert len(gdf) == 0

    def test_creates_parent_directories(self, tmp_path):
        nested = tmp_path / "gis" / "sub" / "points.gpkg"
        write_photo_points_gpkg([_make_result()], nested)
        assert nested.exists()


class TestPhotoMwsJoinedGpkg:
    def test_includes_mws_id_and_mws_code_columns(self, tmp_path):
        path = write_photo_mws_joined_gpkg([_make_result()], tmp_path / "joined.gpkg")
        gdf = gpd.read_file(path)
        assert "mws_id" in gdf.columns
        assert "mws_code" in gdf.columns

    def test_mws_id_equals_micro_watershed_id_not_mws_code(self, tmp_path):
        """Explicit integration-key check on the GIS output too."""
        result = _make_result(micro_watershed_id="g_mws.555555", mws_code="AAA111")
        path = write_photo_mws_joined_gpkg([result], tmp_path / "joined.gpkg")
        gdf = gpd.read_file(path)
        row = gdf.iloc[0]
        assert row["mws_id"] == "g_mws.555555"
        assert row["mws_code"] == "AAA111"
        assert row["mws_id"] != row["mws_code"]

    def test_unmatched_watershed_has_null_mws_fields(self, tmp_path):
        """A point inside the boundary but with NO_WATERSHED_MATCH must
        still appear (it has a coordinate) with blank mws_id/mws_code --
        per the README's 'preserve unmatched records for QA' intent."""
        result = _make_result(
            image_id="IMG_0006", status="NO_WATERSHED_MATCH",
            micro_watershed_id=None, mws_code=None,
        )
        path = write_photo_mws_joined_gpkg([result], tmp_path / "joined.gpkg")
        gdf = gpd.read_file(path)
        assert len(gdf) == 1
        assert gdf.iloc[0]["mws_id"] is None or str(gdf.iloc[0]["mws_id"]) in ("None", "")

    def test_same_point_count_as_base_layer(self, tmp_path):
        results = [_make_result(), _make_no_coordinate_result()]
        points_path = write_photo_points_gpkg(results, tmp_path / "points.gpkg")
        joined_path = write_photo_mws_joined_gpkg(results, tmp_path / "joined.gpkg")
        assert len(gpd.read_file(points_path)) == len(gpd.read_file(joined_path)) == 1

    def test_crs_is_wgs84(self, tmp_path):
        path = write_photo_mws_joined_gpkg([_make_result()], tmp_path / "joined.gpkg")
        gdf = gpd.read_file(path)
        assert gdf.crs.to_string() == "EPSG:4326"

    def test_creates_parent_directories(self, tmp_path):
        nested = tmp_path / "gis" / "sub" / "joined.gpkg"
        write_photo_mws_joined_gpkg([_make_result()], nested)
        assert nested.exists()
