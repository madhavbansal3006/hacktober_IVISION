"""
spatial_analyzer.py — combines BoundaryChecker + WatershedLocator into the
single structured result Phase 4 asks for.

This is intentionally NOT the full `image_analyzer` from the Phase 2
architecture doc -- that also incorporates EXIF extraction (Phase 3) and
LULC querying (Phase 5, not yet built). This module only covers "given a
validated coordinate, where does it sit spatially."
"""

from __future__ import annotations

from dataclasses import dataclass
from typing import Optional

from shapely.geometry import Point

from .boundary_checker import BoundaryChecker
from .watershed_locator import WatershedLocator

# Status values for this phase only. "OK" is deliberately NOT used here --
# per the Phase 2 schema, "OK" means the FULL pipeline (through LULC)
# succeeded. Using it here would be misleading once Phase 5 exists.
STATUS_WATERSHED_MATCHED = "WATERSHED_MATCHED"
STATUS_OUTSIDE_STUDY_AREA = "OUTSIDE_STUDY_AREA"
STATUS_NO_WATERSHED_MATCH = "NO_WATERSHED_MATCH"


@dataclass(frozen=True)
class SpatialResult:
    latitude: float
    longitude: float
    inside_study_area: bool
    micro_watershed_id: Optional[str]
    mws_code: Optional[str]
    status: str


class SpatialAnalyzer:
    """
    Wraps a BoundaryChecker and WatershedLocator so both underlying
    datasets are loaded exactly once, then reused across many points/images.
    """

    def __init__(
        self,
        boundary_checker: BoundaryChecker | None = None,
        watershed_locator: WatershedLocator | None = None,
    ):
        self._boundary_checker = boundary_checker or BoundaryChecker()
        self._watershed_locator = watershed_locator or WatershedLocator()

    @property
    def boundary_checker(self) -> BoundaryChecker:
        """Exposed so callers (e.g. image_analyzer.py) can call
        distance_to_boundary_m() without reaching into a private attribute."""
        return self._boundary_checker

    def analyze(self, latitude: float, longitude: float) -> SpatialResult:
        """
        Given a validated WGS84 (latitude, longitude), determine:
          1. whether it's inside the Shiggaon study-area boundary
          2. if so, which micro-watershed (if any) it falls inside

        Boundary is always checked first; watershed lookup only happens
        for points inside the boundary, per the required data flow.
        """
        point = Point(longitude, latitude)

        if not self._boundary_checker.is_inside(point):
            return SpatialResult(
                latitude=latitude,
                longitude=longitude,
                inside_study_area=False,
                micro_watershed_id=None,
                mws_code=None,
                status=STATUS_OUTSIDE_STUDY_AREA,
            )

        match = self._watershed_locator.locate(point)
        if match is None:
            return SpatialResult(
                latitude=latitude,
                longitude=longitude,
                inside_study_area=True,
                micro_watershed_id=None,
                mws_code=None,
                status=STATUS_NO_WATERSHED_MATCH,
            )

        return SpatialResult(
            latitude=latitude,
            longitude=longitude,
            inside_study_area=True,
            micro_watershed_id=match.micro_watershed_id,
            mws_code=match.mws_code,
            status=STATUS_WATERSHED_MATCHED,
        )
