"""
Generates synthetic JPEG fixtures with controlled EXIF GPS metadata for
tests. These are NOT real field photographs — plain in-memory images with
crafted EXIF blocks, per Phase 7 rule #14 (use controlled fixtures, don't
pretend they're real photos).

Run standalone (`python tests/make_fixtures.py`) or imported by conftest.py.
"""

from __future__ import annotations

from pathlib import Path

import piexif
from PIL import Image

FIXTURES_DIR = Path(__file__).parent / "fixtures"


def _deg_to_dms_rational(deg_decimal: float) -> tuple:
    """Convert a positive decimal degree value into piexif DMS rational tuples."""
    degrees = int(deg_decimal)
    minutes_full = (deg_decimal - degrees) * 60
    minutes = int(minutes_full)
    seconds = round((minutes_full - minutes) * 60 * 100)  # 2 decimal precision
    return ((degrees, 1), (minutes, 1), (seconds, 100))


def _blank_image(path: Path) -> None:
    img = Image.new("RGB", (32, 32), color=(120, 160, 90))
    img.save(path, format="JPEG")


def make_valid_gps_image(
    path: Path, lat: float, lon: float, lat_ref: str = None, lon_ref: str = None
) -> None:
    """A JPEG with well-formed GPS EXIF for the given decimal lat/lon."""
    if lat_ref is None:
        lat_ref = "N" if lat >= 0 else "S"
    if lon_ref is None:
        lon_ref = "E" if lon >= 0 else "W"

    _blank_image(path)

    gps_ifd = {
        piexif.GPSIFD.GPSLatitudeRef: lat_ref,
        piexif.GPSIFD.GPSLatitude: _deg_to_dms_rational(abs(lat)),
        piexif.GPSIFD.GPSLongitudeRef: lon_ref,
        piexif.GPSIFD.GPSLongitude: _deg_to_dms_rational(abs(lon)),
    }
    exif_dict = {"GPS": gps_ifd}
    exif_bytes = piexif.dump(exif_dict)
    piexif.insert(exif_bytes, str(path))


def make_no_gps_image(path: Path) -> None:
    """A plain JPEG with no EXIF GPS data at all."""
    _blank_image(path)
    # no EXIF inserted


def make_malformed_gps_image(path: Path, kind: str) -> None:
    """
    A JPEG with a GPS IFD present but broken in a specific way:
      - "missing_field": GPSLongitude tag absent entirely
      - "bad_ref": GPSLatitudeRef set to an invalid hemisphere letter
      - "wrong_shape": GPSLatitude has 2 components instead of 3
    """
    _blank_image(path)

    if kind == "missing_field":
        gps_ifd = {
            piexif.GPSIFD.GPSLatitudeRef: "N",
            piexif.GPSIFD.GPSLatitude: _deg_to_dms_rational(15.0),
            piexif.GPSIFD.GPSLongitudeRef: "E",
            # GPSLongitude intentionally omitted
        }
    elif kind == "bad_ref":
        gps_ifd = {
            piexif.GPSIFD.GPSLatitudeRef: "X",  # invalid hemisphere
            piexif.GPSIFD.GPSLatitude: _deg_to_dms_rational(15.0),
            piexif.GPSIFD.GPSLongitudeRef: "E",
            piexif.GPSIFD.GPSLongitude: _deg_to_dms_rational(75.0),
        }
    elif kind == "wrong_shape":
        gps_ifd = {
            piexif.GPSIFD.GPSLatitudeRef: "N",
            piexif.GPSIFD.GPSLatitude: ((15, 1), (30, 1)),  # only 2 components
            piexif.GPSIFD.GPSLongitudeRef: "E",
            piexif.GPSIFD.GPSLongitude: _deg_to_dms_rational(75.0),
        }
    else:
        raise ValueError(f"unknown malformed kind: {kind}")

    exif_dict = {"GPS": gps_ifd}
    exif_bytes = piexif.dump(exif_dict)
    piexif.insert(exif_bytes, str(path))


def make_out_of_range_image(path: Path) -> None:
    """
    A JPEG whose GPS DMS values, once converted, exceed the valid WGS84
    range (e.g. latitude > 90). Uses raw EXIF insertion since piexif's own
    DMS helper would clip; we build the IFD directly.
    """
    _blank_image(path)
    gps_ifd = {
        piexif.GPSIFD.GPSLatitudeRef: "N",
        piexif.GPSIFD.GPSLatitude: _deg_to_dms_rational(95.0),  # invalid: >90
        piexif.GPSIFD.GPSLongitudeRef: "E",
        piexif.GPSIFD.GPSLongitude: _deg_to_dms_rational(75.0),
    }
    exif_dict = {"GPS": gps_ifd}
    exif_bytes = piexif.dump(exif_dict)
    piexif.insert(exif_bytes, str(path))


def make_valid_gps_image_with_extras(
    path: Path,
    lat: float,
    lon: float,
    lat_ref: str = None,
    lon_ref: str = None,
    capture_datetime_original: str | None = None,
    gps_h_positioning_error_m: float | None = None,
) -> None:
    """
    Like make_valid_gps_image, but additionally sets EXIF DateTimeOriginal
    (Exif sub-IFD) and/or GPSHPositioningError (GPS IFD), for testing the
    teammate-README-compatibility EXIF extraction. Either extra can be
    omitted (None) to test the "field absent" case.
    """
    if lat_ref is None:
        lat_ref = "N" if lat >= 0 else "S"
    if lon_ref is None:
        lon_ref = "E" if lon >= 0 else "W"

    _blank_image(path)

    gps_ifd = {
        piexif.GPSIFD.GPSLatitudeRef: lat_ref,
        piexif.GPSIFD.GPSLatitude: _deg_to_dms_rational(abs(lat)),
        piexif.GPSIFD.GPSLongitudeRef: lon_ref,
        piexif.GPSIFD.GPSLongitude: _deg_to_dms_rational(abs(lon)),
    }
    if gps_h_positioning_error_m is not None:
        gps_ifd[piexif.GPSIFD.GPSHPositioningError] = (
            int(round(gps_h_positioning_error_m * 100)),
            100,
        )

    exif_ifd = {}
    if capture_datetime_original is not None:
        exif_ifd[piexif.ExifIFD.DateTimeOriginal] = capture_datetime_original

    exif_dict = {"GPS": gps_ifd, "Exif": exif_ifd}
    exif_bytes = piexif.dump(exif_dict)
    piexif.insert(exif_bytes, str(path))


def generate_all() -> None:
    FIXTURES_DIR.mkdir(parents=True, exist_ok=True)

    # A point known (from Phase 1 audit) to sit inside the Shiggaon bbox,
    # used generically here just as "a valid, plausible coordinate" —
    # boundary logic itself is out of scope for Phase 3.
    make_valid_gps_image(FIXTURES_DIR / "valid_ne.jpg", lat=15.01234, lon=75.21345)
    make_valid_gps_image(FIXTURES_DIR / "valid_sw.jpg", lat=15.01234, lon=75.21345,
                          lat_ref="S", lon_ref="W")

    make_no_gps_image(FIXTURES_DIR / "no_gps.jpg")

    make_malformed_gps_image(FIXTURES_DIR / "malformed_missing_field.jpg", "missing_field")
    make_malformed_gps_image(FIXTURES_DIR / "malformed_bad_ref.jpg", "bad_ref")
    make_malformed_gps_image(FIXTURES_DIR / "malformed_wrong_shape.jpg", "wrong_shape")

    make_out_of_range_image(FIXTURES_DIR / "out_of_range_lat.jpg")

    print(f"Generated fixtures in {FIXTURES_DIR}")


if __name__ == "__main__":
    generate_all()
