import csv
import dataclasses
import json

import pytest

from src.io_writer import write_csv, write_json, write_outputs
from src.schema import SCHEMA_VERSION, STATUS_ERROR, STATUS_NO_GPS, GeoCodedResult
from src.spatial_analyzer import STATUS_OUTSIDE_STUDY_AREA


def _sample_results() -> list[GeoCodedResult]:
    ok_result = GeoCodedResult(
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
    )
    outside_result = GeoCodedResult(
        schema_version=SCHEMA_VERSION,
        image_name="photo_002.jpg",
        processing_timestamp="2026-08-31T10:16:00+00:00",
        latitude=15.0,
        longitude=65.0,
        status=STATUS_OUTSIDE_STUDY_AREA,
        error_reason=None,
        inside_study_area=False,
        micro_watershed_id=None,
        mws_code=None,
        lulc_value=None,
        lulc_class=None,
        raster_pixel_row=None,
        raster_pixel_col=None,
        lulc_neighborhood_window_size=None,
        lulc_neighborhood_class_purity_pct=None,
        lulc_neighborhood_nodata_pct=None,
    )
    error_result = GeoCodedResult(
        schema_version=SCHEMA_VERSION,
        image_name="photo_003.jpg",
        processing_timestamp="2026-08-31T10:17:00+00:00",
        latitude=None,
        longitude=None,
        status=STATUS_NO_GPS,
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
    )
    return [ok_result, outside_result, error_result]


class TestWriteJson:
    def test_writes_valid_json_matching_input(self, tmp_path):
        results = _sample_results()
        path = write_json(results, tmp_path / "out.json")

        assert path.exists()
        with open(path) as f:
            parsed = json.load(f)

        assert len(parsed) == 3
        assert parsed[0]["image_name"] == "photo_001.jpg"
        assert parsed[0]["lulc_class"] == "Agriculture"
        assert parsed[0]["micro_watershed_id"] == "g_mws.240575"
        assert parsed[1]["status"] == STATUS_OUTSIDE_STUDY_AREA
        assert parsed[1]["lulc_value"] is None
        assert parsed[2]["error_reason"] == "No GPS IFD present in EXIF metadata"

    def test_creates_parent_directories(self, tmp_path):
        nested = tmp_path / "a" / "b" / "c" / "out.json"
        write_json(_sample_results(), nested)
        assert nested.exists()

    def test_default_path_used_when_none_given(self, tmp_path, monkeypatch):
        import src.config as config_module
        import src.io_writer as io_writer_module

        monkeypatch.setattr(config_module, "DEFAULT_JSON_PATH", tmp_path / "default.json")
        monkeypatch.setattr(io_writer_module.config, "DEFAULT_JSON_PATH", tmp_path / "default.json")
        path = write_json(_sample_results())
        assert path == tmp_path / "default.json"
        assert path.exists()


class TestWriteCsv:
    def test_writes_csv_with_correct_row_count(self, tmp_path):
        results = _sample_results()
        path = write_csv(results, tmp_path / "out.csv")

        assert path.exists()
        with open(path, newline="") as f:
            rows = list(csv.DictReader(f))
        assert len(rows) == 3

    def test_header_matches_schema_field_names_exactly(self, tmp_path):
        path = write_csv(_sample_results(), tmp_path / "out.csv")
        with open(path, newline="") as f:
            header = next(csv.reader(f))
        expected = [f.name for f in dataclasses.fields(GeoCodedResult)]
        assert header == expected

    def test_none_values_become_empty_string(self, tmp_path):
        path = write_csv(_sample_results(), tmp_path / "out.csv")
        with open(path, newline="") as f:
            rows = list(csv.DictReader(f))
        # photo_002.jpg row: micro_watershed_id is None -> empty CSV field
        outside_row = next(r for r in rows if r["image_name"] == "photo_002.jpg")
        assert outside_row["micro_watershed_id"] == ""
        assert outside_row["lulc_value"] == ""

    def test_values_preserved_correctly(self, tmp_path):
        path = write_csv(_sample_results(), tmp_path / "out.csv")
        with open(path, newline="") as f:
            rows = list(csv.DictReader(f))
        ok_row = next(r for r in rows if r["image_name"] == "photo_001.jpg")
        assert ok_row["lulc_class"] == "Agriculture"
        assert ok_row["mws_code"] == "4D4F2m3"
        assert float(ok_row["latitude"]) == pytest.approx(15.01234)


class TestWriteOutputs:
    def test_writes_both_files(self, tmp_path):
        csv_path, json_path = write_outputs(
            _sample_results(), csv_path=tmp_path / "r.csv", json_path=tmp_path / "r.json"
        )
        assert csv_path.exists()
        assert json_path.exists()

    def test_empty_results_list_still_writes_valid_empty_outputs(self, tmp_path):
        csv_path, json_path = write_outputs(
            [], csv_path=tmp_path / "empty.csv", json_path=tmp_path / "empty.json"
        )
        with open(json_path) as f:
            assert json.load(f) == []
        with open(csv_path, newline="") as f:
            header = next(csv.reader(f))
        # header row still written even with zero data rows
        assert header == [f.name for f in dataclasses.fields(GeoCodedResult)]
