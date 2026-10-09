import pytest

from src.coordinate_validator import dms_to_decimal, validate
from src.exceptions import InvalidCoordinateError
from src.exif_reader import RawGPSData, extract_gps


class TestDmsToDecimal:
    def test_known_conversion_north_east(self):
        # 15 deg 0 min 44.424 sec = 15 + 0/60 + 44.424/3600 = 15.012340
        decimal = dms_to_decimal((15.0, 0.0, 44.424), "N")
        assert decimal == pytest.approx(15.012340, abs=1e-6)

    def test_south_ref_produces_negative(self):
        decimal = dms_to_decimal((15.0, 0.0, 44.424), "S")
        assert decimal == pytest.approx(-15.012340, abs=1e-6)

    def test_west_ref_produces_negative(self):
        decimal = dms_to_decimal((75.0, 12.0, 48.42), "W")
        assert decimal < 0

    def test_east_ref_produces_positive(self):
        decimal = dms_to_decimal((75.0, 12.0, 48.42), "E")
        assert decimal > 0

    def test_zero_minutes_seconds(self):
        assert dms_to_decimal((10.0, 0.0, 0.0), "N") == pytest.approx(10.0)


class TestValidateFromRawGPSData:
    def test_valid_ne_point(self):
        raw = RawGPSData(
            lat_dms=(15.0, 0.0, 44.42),
            lat_ref="N",
            lon_dms=(75.0, 12.0, 48.42),
            lon_ref="E",
            source_image="synthetic.jpg",
        )
        result = validate(raw)
        assert result.latitude == pytest.approx(15.01234, abs=1e-4)
        assert result.longitude == pytest.approx(75.21345, abs=1e-4)
        assert result.point.y == pytest.approx(result.latitude)
        assert result.point.x == pytest.approx(result.longitude)

    def test_valid_sw_point_is_negative(self):
        raw = RawGPSData(
            lat_dms=(15.0, 0.0, 44.42),
            lat_ref="S",
            lon_dms=(75.0, 12.0, 48.42),
            lon_ref="W",
            source_image="synthetic.jpg",
        )
        result = validate(raw)
        assert result.latitude < 0
        assert result.longitude < 0

    def test_latitude_over_90_raises(self):
        raw = RawGPSData(
            lat_dms=(95.0, 0.0, 0.0),
            lat_ref="N",
            lon_dms=(75.0, 0.0, 0.0),
            lon_ref="E",
            source_image="synthetic.jpg",
        )
        with pytest.raises(InvalidCoordinateError):
            validate(raw)

    def test_longitude_over_180_raises(self):
        raw = RawGPSData(
            lat_dms=(15.0, 0.0, 0.0),
            lat_ref="N",
            lon_dms=(185.0, 0.0, 0.0),
            lon_ref="E",
            source_image="synthetic.jpg",
        )
        with pytest.raises(InvalidCoordinateError):
            validate(raw)

    def test_minutes_ge_60_raises(self):
        # (15, 75, 0) -> minutes=75 is invalid, must be < 60
        raw = RawGPSData(
            lat_dms=(15.0, 75.0, 0.0),
            lat_ref="N",
            lon_dms=(75.0, 0.0, 0.0),
            lon_ref="E",
            source_image="synthetic.jpg",
        )
        with pytest.raises(InvalidCoordinateError):
            validate(raw)

    def test_seconds_ge_60_raises(self):
        # (15, 0, 75) -> seconds=75 is invalid, must be < 60
        raw = RawGPSData(
            lat_dms=(15.0, 0.0, 75.0),
            lat_ref="N",
            lon_dms=(75.0, 0.0, 0.0),
            lon_ref="E",
            source_image="synthetic.jpg",
        )
        with pytest.raises(InvalidCoordinateError):
            validate(raw)

    def test_minutes_exactly_60_raises(self):
        # boundary case: 60 is invalid, valid range is [0, 60)
        raw = RawGPSData(
            lat_dms=(15.0, 60.0, 0.0),
            lat_ref="N",
            lon_dms=(75.0, 0.0, 0.0),
            lon_ref="E",
            source_image="synthetic.jpg",
        )
        with pytest.raises(InvalidCoordinateError):
            validate(raw)

    def test_longitude_seconds_ge_60_raises(self):
        raw = RawGPSData(
            lat_dms=(15.0, 0.0, 0.0),
            lat_ref="N",
            lon_dms=(75.0, 0.0, 75.0),
            lon_ref="E",
            source_image="synthetic.jpg",
        )
        with pytest.raises(InvalidCoordinateError):
            validate(raw)

    def test_negative_dms_component_raises(self):
        # DMS magnitudes should never be negative in valid EXIF; sign comes
        # from the ref field only.
        raw = RawGPSData(
            lat_dms=(-15.0, 0.0, 0.0),
            lat_ref="N",
            lon_dms=(75.0, 0.0, 0.0),
            lon_ref="E",
            source_image="synthetic.jpg",
        )
        with pytest.raises(InvalidCoordinateError):
            validate(raw)


class TestEndToEndWithRealImageFixtures:
    def test_valid_image_end_to_end(self, fixtures_dir):
        raw = extract_gps(fixtures_dir / "valid_ne.jpg")
        result = validate(raw)
        assert result.latitude == pytest.approx(15.01234, abs=1e-3)
        assert result.longitude == pytest.approx(75.21345, abs=1e-3)

    def test_out_of_range_image_raises_invalid_coordinate(self, fixtures_dir):
        raw = extract_gps(fixtures_dir / "out_of_range_lat.jpg")
        with pytest.raises(InvalidCoordinateError):
            validate(raw)
