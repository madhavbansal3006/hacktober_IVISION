"""
coordinate_validator.py — converts RawGPSData (DMS + ref) into a validated
decimal-degree coordinate and a shapely Point in EPSG:4326.

Responsibility boundary (per architecture, Phase 2):
  - Converts DMS -> decimal degrees.
  - Applies hemisphere sign (S/W negative, N/E positive).
  - Validates the final coordinate is a physically valid WGS84 lat/lon.
  - Does NOT know about the Shiggaon boundary, watersheds, or the raster.
"""

from __future__ import annotations

from dataclasses import dataclass

from shapely.geometry import Point

from .exceptions import InvalidCoordinateError
from .exif_reader import RawGPSData

_LAT_MIN, _LAT_MAX = -90.0, 90.0
_LON_MIN, _LON_MAX = -180.0, 180.0


@dataclass(frozen=True)
class ValidatedCoordinate:
    """A decimal-degree WGS84 coordinate that has passed range validation."""

    latitude: float
    longitude: float
    point: Point  # shapely Point(x=longitude, y=latitude), CRS EPSG:4326 implied
    source_image: str


def dms_to_decimal(dms: tuple[float, float, float], ref: str) -> float:
    """
    Convert a (degrees, minutes, seconds) triplet + hemisphere ref into a
    signed decimal-degree value. Does not itself range-validate — that
    happens once both lat and lon are known, in `validate`.
    """
    degrees, minutes, seconds = dms
    decimal = degrees + (minutes / 60.0) + (seconds / 3600.0)
    if ref in ("S", "W"):
        decimal = -decimal
    return decimal


def validate(raw: RawGPSData) -> ValidatedCoordinate:
    """
    Convert raw EXIF GPS data to a validated decimal coordinate.

    Raises:
        InvalidCoordinateError: the resulting latitude/longitude falls
            outside the physically valid WGS84 range, or a DMS component
            is negative (which EXIF DMS values should never be — sign is
            carried by the ref, not the magnitude).
    """
    for label, dms in (("latitude", raw.lat_dms), ("longitude", raw.lon_dms)):
        if any(component < 0 for component in dms):
            raise InvalidCoordinateError(
                f"{label} DMS components must be non-negative; sign is "
                f"carried by the hemisphere ref, got {dms}",
                raw.source_image,
            )
        _, minutes, seconds = dms
        if minutes >= 60 or seconds >= 60:
            raise InvalidCoordinateError(
                f"{label} minutes and seconds must each be < 60, got {dms}",
                raw.source_image,
            )

    latitude = dms_to_decimal(raw.lat_dms, raw.lat_ref)
    longitude = dms_to_decimal(raw.lon_dms, raw.lon_ref)

    if not (_LAT_MIN <= latitude <= _LAT_MAX):
        raise InvalidCoordinateError(
            f"latitude {latitude} out of range [{_LAT_MIN}, {_LAT_MAX}]",
            raw.source_image,
        )
    if not (_LON_MIN <= longitude <= _LON_MAX):
        raise InvalidCoordinateError(
            f"longitude {longitude} out of range [{_LON_MIN}, {_LON_MAX}]",
            raw.source_image,
        )

    return ValidatedCoordinate(
        latitude=latitude,
        longitude=longitude,
        point=Point(longitude, latitude),
        source_image=raw.source_image,
    )
