"""
exif_reader.py — extracts RAW GPS EXIF data from a JPEG.

Responsibility boundary (per architecture, Phase 2):
  - This module ONLY reads EXIF tags and returns them in their raw,
    unconverted form (degrees/minutes/seconds components + hemisphere refs).
  - It does NOT convert DMS to decimal degrees.
  - It does NOT validate coordinate ranges.
  - It NEVER writes to the input image. Files are opened read-only and
    never have `.save()` called on them.
"""

from __future__ import annotations

from dataclasses import dataclass
from pathlib import Path

from PIL import ExifTags, Image

from .exceptions import MalformedGPSError, NoGPSError

# GPS IFD tag ids (stable across Pillow versions via ExifTags.GPS enum)
_TAG_LAT_REF = ExifTags.GPS.GPSLatitudeRef
_TAG_LAT = ExifTags.GPS.GPSLatitude
_TAG_LON_REF = ExifTags.GPS.GPSLongitudeRef
_TAG_LON = ExifTags.GPS.GPSLongitude
_TAG_GPS_H_POSITIONING_ERROR = ExifTags.GPS.GPSHPositioningError

_VALID_LAT_REFS = {"N", "S"}
_VALID_LON_REFS = {"E", "W"}


@dataclass(frozen=True)
class RawGPSData:
    """Unconverted GPS EXIF data straight off the image."""

    lat_dms: tuple[float, float, float]   # (degrees, minutes, seconds)
    lat_ref: str                          # "N" or "S"
    lon_dms: tuple[float, float, float]   # (degrees, minutes, seconds)
    lon_ref: str                          # "E" or "W"
    source_image: str

    # Teammate README compatibility (additive, defaulted -- does not
    # affect any existing construction of this dataclass). Both are
    # "when available" per the README: never fabricated, always None if
    # the tag is absent or unparsable.
    capture_datetime_raw: str | None = None   # raw EXIF DateTimeOriginal string, e.g. "2026:03:14 09:21:07"
    gps_accuracy_m: float | None = None        # from GPSHPositioningError, if present


def _to_float_triplet(value, image_path: str, field_name: str) -> tuple[float, float, float]:
    """Coerce a GPS DMS tag value (tuple of IFDRational or similar) to 3 floats."""
    try:
        components = tuple(value)
    except TypeError as exc:
        raise MalformedGPSError(
            f"{field_name} is not an iterable DMS triplet: {value!r}", image_path
        ) from exc

    if len(components) != 3:
        raise MalformedGPSError(
            f"{field_name} does not have exactly 3 components (degrees, "
            f"minutes, seconds): got {len(components)}",
            image_path,
        )

    try:
        return tuple(float(c) for c in components)  # type: ignore[return-value]
    except (TypeError, ValueError) as exc:
        raise MalformedGPSError(
            f"{field_name} components are not numeric: {components!r}", image_path
        ) from exc


def extract_gps(image_path: str | Path) -> RawGPSData:
    """
    Extract raw GPS EXIF data from a JPEG.

    Raises:
        NoGPSError: the image has no GPS IFD at all (no GPS tags present).
        MalformedGPSError: a GPS IFD exists but is incomplete, has the wrong
            shape/type, or has a hemisphere ref outside {N,S}/{E,W}.
        FileNotFoundError: the image path does not exist.
        PIL.UnidentifiedImageError: the file is not a readable image.

    The input file is opened read-only; it is never modified.
    """
    image_path = str(image_path)
    if not Path(image_path).exists():
        raise FileNotFoundError(f"Image not found: {image_path}")

    with Image.open(image_path) as img:
        exif = img.getexif()
        gps_ifd = exif.get_ifd(ExifTags.IFD.GPSInfo)
        # Optional, best-effort extras -- read from the same already-open
        # file handle so we don't reopen the image. Never allowed to
        # affect the required-GPS validation below.
        capture_datetime_raw = _extract_capture_datetime_raw(exif, image_path)
        gps_accuracy_m = _extract_gps_accuracy_m(gps_ifd, image_path)

    if not gps_ifd:
        raise NoGPSError("No GPS IFD present in EXIF metadata", image_path)

    missing = [
        name
        for name, tag in (
            ("GPSLatitudeRef", _TAG_LAT_REF),
            ("GPSLatitude", _TAG_LAT),
            ("GPSLongitudeRef", _TAG_LON_REF),
            ("GPSLongitude", _TAG_LON),
        )
        if tag not in gps_ifd
    ]
    if missing:
        raise MalformedGPSError(
            f"GPS IFD present but missing required field(s): {missing}", image_path
        )

    lat_ref = str(gps_ifd[_TAG_LAT_REF]).strip().upper()
    lon_ref = str(gps_ifd[_TAG_LON_REF]).strip().upper()

    if lat_ref not in _VALID_LAT_REFS:
        raise MalformedGPSError(
            f"GPSLatitudeRef must be one of {_VALID_LAT_REFS}, got {lat_ref!r}",
            image_path,
        )
    if lon_ref not in _VALID_LON_REFS:
        raise MalformedGPSError(
            f"GPSLongitudeRef must be one of {_VALID_LON_REFS}, got {lon_ref!r}",
            image_path,
        )

    lat_dms = _to_float_triplet(gps_ifd[_TAG_LAT], image_path, "GPSLatitude")
    lon_dms = _to_float_triplet(gps_ifd[_TAG_LON], image_path, "GPSLongitude")

    return RawGPSData(
        lat_dms=lat_dms,
        lat_ref=lat_ref,
        lon_dms=lon_dms,
        lon_ref=lon_ref,
        source_image=image_path,
        capture_datetime_raw=capture_datetime_raw,
        gps_accuracy_m=gps_accuracy_m,
    )


def _extract_capture_datetime_raw(exif, image_path: str) -> str | None:
    """
    Best-effort read of EXIF DateTimeOriginal (tag 0x9003, in the Exif
    sub-IFD or base IFD, or GPS timestamps). Returns None -- never raises, never
    fabricates -- if the tag is absent or unreadable. This must never
    affect whether extract_gps() succeeds or fails; capture time is "preferred," not required.
    """
    try:
        exif_sub_ifd = exif.get_ifd(ExifTags.IFD.Exif)
        value = exif_sub_ifd.get(ExifTags.Base.DateTimeOriginal)
        if value is None:
            value = exif.get(ExifTags.Base.DateTimeOriginal) or exif.get(ExifTags.Base.DateTime)
        if value is None:
            gps_ifd = exif.get_ifd(ExifTags.IFD.GPSInfo)
            date_stamp = gps_ifd.get(ExifTags.GPS.GPSDateStamp)
            time_stamp = gps_ifd.get(ExifTags.GPS.GPSTimeStamp)
            if date_stamp and time_stamp and len(time_stamp) == 3:
                h, m, s = int(time_stamp[0]), int(time_stamp[1]), int(time_stamp[2])
                value = f"{date_stamp} {h:02d}:{m:02d}:{s:02d}"
    except Exception:
        return None
    if value is None:
        return None
    value = str(value).strip()
    return value or None


def _extract_gps_accuracy_m(gps_ifd, image_path: str) -> float | None:
    """
    Best-effort read of GPSHPositioningError (tag 31) from the GPS IFD.
    Most consumer cameras/phones never populate this -- returns None
    (never fabricated) whenever it's absent or not a valid number.
    """
    if not gps_ifd:
        return None
    try:
        value = gps_ifd.get(_TAG_GPS_H_POSITIONING_ERROR)
    except Exception:
        return None
    if value is None:
        return None
    try:
        return float(value)
    except (TypeError, ValueError):
        return None


def parse_capture_datetime(raw: str | None) -> str | None:
    """
    Convert an EXIF DateTimeOriginal string ("YYYY:MM:DD HH:MM:SS") to
    ISO-8601-shaped text ("YYYY-MM-DDTHH:MM:SS"). Returns None -- never
    raises -- for None input or a string that doesn't match the expected
    EXIF format.

    IMPORTANT: EXIF DateTimeOriginal carries no timezone information.
    This returns the camera's LOCAL time as recorded, unconverted --
    it is NOT UTC, unlike GeoCodedResult.processing_timestamp (which is
    wall-clock UTC at processing time, a completely different thing).
    Do not compare the two as if they were in the same timezone.
    """
    if not raw:
        return None
    from datetime import datetime as _datetime

    try:
        dt = _datetime.strptime(raw.strip(), "%Y:%m:%d %H:%M:%S")
    except ValueError:
        return None
    return dt.isoformat()
