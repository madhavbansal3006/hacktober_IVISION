import hashlib

import pytest

from src.exceptions import MalformedGPSError, NoGPSError
from src.exif_reader import extract_gps


def _sha256(path) -> str:
    return hashlib.sha256(open(path, "rb").read()).hexdigest()


class TestValidExtraction:
    def test_extracts_lat_lon_ref_ne(self, fixtures_dir):
        raw = extract_gps(fixtures_dir / "valid_ne.jpg")
        assert raw.lat_ref == "N"
        assert raw.lon_ref == "E"
        assert len(raw.lat_dms) == 3
        assert len(raw.lon_dms) == 3
        # degrees component should match the whole-degree part of 15.01234
        assert raw.lat_dms[0] == pytest.approx(15.0)
        assert raw.lon_dms[0] == pytest.approx(75.0)

    def test_extracts_sw_hemisphere_refs(self, fixtures_dir):
        raw = extract_gps(fixtures_dir / "valid_sw.jpg")
        assert raw.lat_ref == "S"
        assert raw.lon_ref == "W"

    def test_does_not_modify_input_image(self, fixtures_dir):
        path = fixtures_dir / "valid_ne.jpg"
        before = _sha256(path)
        extract_gps(path)
        after = _sha256(path)
        assert before == after, "extract_gps must not modify the input file"


class TestMissingGPS:
    def test_no_gps_raises_no_gps_error(self, fixtures_dir):
        with pytest.raises(NoGPSError):
            extract_gps(fixtures_dir / "no_gps.jpg")

    def test_no_gps_error_carries_image_path(self, fixtures_dir):
        path = fixtures_dir / "no_gps.jpg"
        with pytest.raises(NoGPSError) as exc_info:
            extract_gps(path)
        assert exc_info.value.image_path == str(path)


class TestMalformedGPS:
    def test_missing_field_raises_malformed(self, fixtures_dir):
        with pytest.raises(MalformedGPSError):
            extract_gps(fixtures_dir / "malformed_missing_field.jpg")

    def test_bad_hemisphere_ref_raises_malformed(self, fixtures_dir):
        with pytest.raises(MalformedGPSError):
            extract_gps(fixtures_dir / "malformed_bad_ref.jpg")

    def test_wrong_shape_dms_raises_malformed(self, fixtures_dir):
        with pytest.raises(MalformedGPSError):
            extract_gps(fixtures_dir / "malformed_wrong_shape.jpg")


class TestFileHandling:
    def test_missing_file_raises_file_not_found(self, fixtures_dir):
        with pytest.raises(FileNotFoundError):
            extract_gps(fixtures_dir / "does_not_exist.jpg")


class TestCaptureDatetimeAndGpsAccuracyExtraction:
    """Teammate-README compatibility: DateTimeOriginal and
    GPSHPositioningError, both optional/best-effort, never fabricated."""

    def test_both_present(self, tmp_path):
        from tests.make_fixtures import make_valid_gps_image_with_extras

        path = tmp_path / "with_extras.jpg"
        make_valid_gps_image_with_extras(
            path, lat=15.01234, lon=75.21345,
            capture_datetime_original="2026:03:14 09:21:07",
            gps_h_positioning_error_m=4.5,
        )
        raw = extract_gps(path)
        assert raw.capture_datetime_raw == "2026:03:14 09:21:07"
        assert raw.gps_accuracy_m == pytest.approx(4.5)

    def test_both_absent_are_none_not_fabricated(self, tmp_path):
        from tests.make_fixtures import make_valid_gps_image_with_extras

        path = tmp_path / "no_extras.jpg"
        make_valid_gps_image_with_extras(path, lat=15.01234, lon=75.21345)
        raw = extract_gps(path)
        assert raw.capture_datetime_raw is None
        assert raw.gps_accuracy_m is None

    def test_datetime_present_accuracy_absent(self, tmp_path):
        from tests.make_fixtures import make_valid_gps_image_with_extras

        path = tmp_path / "datetime_only.jpg"
        make_valid_gps_image_with_extras(
            path, lat=15.0, lon=75.0,
            capture_datetime_original="2026:01:01 00:00:00",
        )
        raw = extract_gps(path)
        assert raw.capture_datetime_raw == "2026:01:01 00:00:00"
        assert raw.gps_accuracy_m is None

    def test_missing_extras_never_affects_required_gps_extraction(self, tmp_path):
        """Absence of these optional tags must never cause extract_gps to
        raise -- they're 'preferred'/'if available', not required."""
        from tests.make_fixtures import make_valid_gps_image_with_extras

        path = tmp_path / "gps_only.jpg"
        make_valid_gps_image_with_extras(path, lat=15.01234, lon=75.21345)
        raw = extract_gps(path)  # must not raise
        assert raw.lat_ref == "N"
        assert raw.lon_ref == "E"

    def test_extras_do_not_affect_existing_fixtures(self, fixtures_dir):
        """The original Phase 3 fixtures (built without these extras) must
        still extract cleanly with the new fields simply None."""
        raw = extract_gps(fixtures_dir / "valid_ne.jpg")
        assert raw.capture_datetime_raw is None
        assert raw.gps_accuracy_m is None


class TestParseCaptureDatetime:
    def test_valid_exif_datetime_string(self):
        from src.exif_reader import parse_capture_datetime

        result = parse_capture_datetime("2026:03:14 09:21:07")
        assert result == "2026-03-14T09:21:07"

    def test_none_input_returns_none(self):
        from src.exif_reader import parse_capture_datetime

        assert parse_capture_datetime(None) is None

    def test_empty_string_returns_none(self):
        from src.exif_reader import parse_capture_datetime

        assert parse_capture_datetime("") is None

    def test_malformed_string_returns_none_not_raise(self):
        from src.exif_reader import parse_capture_datetime

        assert parse_capture_datetime("not a datetime at all") is None

    def test_wrong_format_returns_none(self):
        from src.exif_reader import parse_capture_datetime

        # ISO format instead of EXIF's colon-separated date -- must not
        # be silently accepted as if it were validated EXIF format.
        assert parse_capture_datetime("2026-03-14 09:21:07") is None
