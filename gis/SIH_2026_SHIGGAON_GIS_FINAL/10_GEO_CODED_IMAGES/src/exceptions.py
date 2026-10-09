"""
Typed exceptions for the geo-coded image module.

All exceptions carry an `image_path` (when known) so callers building a
per-image result record (Phase 4+) can report which file failed and why,
without re-parsing exception message strings.
"""

from __future__ import annotations


class GeoCodedError(Exception):
    """Base class for all errors raised by the geo_coded pipeline."""

    def __init__(self, message: str, image_path: str | None = None):
        self.image_path = image_path
        super().__init__(message)


class NoGPSError(GeoCodedError):
    """Raised when a JPEG has no GPS IFD in its EXIF metadata at all."""


class MalformedGPSError(GeoCodedError):
    """
    Raised when a GPS IFD is present but is incomplete, has the wrong
    structure/type, or has a reference value outside {N, S, E, W}.
    """


class InvalidCoordinateError(GeoCodedError):
    """
    Raised when extracted GPS values convert to a decimal-degree coordinate
    outside the valid WGS84 range (lat not in [-90, 90], lon not in
    [-180, 180]), or the DMS components themselves are non-numeric/negative
    in a way that cannot represent a valid coordinate.
    """
