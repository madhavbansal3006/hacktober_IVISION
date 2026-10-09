"""
geo_lulc_analyzer.py — combines spatial_analyzer (Phase 4) + lulc_query
(Phase 5) into a single result matching the geospatial subset of the
Phase 2 architecture's JSON schema.

Not the full `image_analyzer` from the Phase 2 doc yet -- EXIF extraction
(Phase 3, already built in exif_reader.py/coordinate_validator.py) is not
wired in here. This module answers "given a validated coordinate, what
does the full geospatial + LULC picture look like," which is exactly what
Phase 5 asked for. Wiring EXIF -> this -> CSV/JSON output is Phase 6/7.

---------------------------------------------------------------------------
STATUS PRIORITY -- IMPLEMENTATION DECISION, NOT DICTATED BY ANY SPEC.

A point can trigger more than one "unusual" condition at once (e.g. inside
the boundary, but the watershed layer has a gap here AND the raster pixel
happens to be NoData). Only one status can be reported per result, so
STATUS_PRIORITY below decides which condition wins, most severe first.

This is intentionally a flat, ordered list rather than baked into if/elif
branching, so changing the priority later is a one-line reorder of this
list -- nothing else in this module, or in spatial_analyzer.py/
lulc_query.py, needs to change. The underlying analysis (whether the point
is in the boundary, which watershed it's in, what the raster says) is
computed independently of this ordering; STATUS_PRIORITY only affects
which single label gets reported when multiple conditions are true.

Current order, most to least severe:
  1. OUTSIDE_STUDY_AREA      -- point isn't in Shiggaon at all; LULC is
                                 never even queried for this point.
  2. OUTSIDE_RASTER_EXTENT   -- inside boundary but off the raster's pixel
                                 grid (Phase 1's audit showed near-total
                                 raster/boundary coverage, so this should
                                 be rare, but is not assumed impossible).
  3. NO_WATERSHED_MATCH      -- inside boundary, LULC likely resolvable,
                                 but the watershed layer has a gap here.
  4. NODATA_PIXEL            -- watershed matched, but the LULC raster
                                 itself has no classification at this
                                 exact pixel.
  5. OK                      -- everything resolved.
---------------------------------------------------------------------------
"""

from __future__ import annotations

from dataclasses import dataclass
from typing import Optional

from . import lulc_query as lulc_module
from . import spatial_analyzer as spatial_module
from .lulc_query import LULCQuery
from .spatial_analyzer import SpatialAnalyzer

STATUS_OK = "OK"

STATUS_PRIORITY: list[str] = [
    spatial_module.STATUS_OUTSIDE_STUDY_AREA,
    lulc_module.STATUS_OUTSIDE_RASTER_EXTENT,
    spatial_module.STATUS_NO_WATERSHED_MATCH,
    lulc_module.STATUS_NODATA_PIXEL,
    STATUS_OK,
]


def _resolve_status(spatial_status: str, lulc_status: str) -> str:
    """
    Given the (already-computed, independent) spatial status and LULC
    status for a point known to be inside the study boundary, pick the
    single status to report, per STATUS_PRIORITY above.
    """
    active = set()
    if spatial_status == spatial_module.STATUS_NO_WATERSHED_MATCH:
        active.add(spatial_module.STATUS_NO_WATERSHED_MATCH)
    if lulc_status == lulc_module.STATUS_OUTSIDE_RASTER_EXTENT:
        active.add(lulc_module.STATUS_OUTSIDE_RASTER_EXTENT)
    if lulc_status == lulc_module.STATUS_NODATA_PIXEL:
        active.add(lulc_module.STATUS_NODATA_PIXEL)
    if not active:
        return STATUS_OK

    for candidate in STATUS_PRIORITY:
        if candidate in active:
            return candidate
    return STATUS_OK  # unreachable given STATUS_PRIORITY always ends in STATUS_OK


@dataclass(frozen=True)
class GeoCodedCoreResult:
    """
    Geospatial + LULC subset of the final per-image schema. Field names
    match the Phase 2 architecture doc's JSON schema exactly, for the
    fields that phase already covers.
    """

    latitude: float
    longitude: float
    status: str

    inside_study_area: bool
    micro_watershed_id: Optional[str]
    mws_code: Optional[str]

    lulc_value: Optional[int]
    lulc_class: Optional[str]
    raster_pixel_row: Optional[int]
    raster_pixel_col: Optional[int]

    # Phase 5 addition beyond the original Phase 2 schema -- see
    # lulc_query.py docstring.
    lulc_neighborhood_window_size: Optional[int]
    lulc_neighborhood_class_purity_pct: Optional[float]
    lulc_neighborhood_nodata_pct: Optional[float]


class GeoLULCAnalyzer:
    def __init__(
        self,
        spatial_analyzer: SpatialAnalyzer | None = None,
        lulc_query: LULCQuery | None = None,
    ):
        self._spatial = spatial_analyzer or SpatialAnalyzer()
        self._lulc = lulc_query or LULCQuery()

    @property
    def boundary_checker(self):
        """Exposed for the same reason as SpatialAnalyzer.boundary_checker."""
        return self._spatial.boundary_checker

    def analyze(self, latitude: float, longitude: float) -> GeoCodedCoreResult:
        spatial = self._spatial.analyze(latitude=latitude, longitude=longitude)

        if spatial.status == spatial_module.STATUS_OUTSIDE_STUDY_AREA:
            return GeoCodedCoreResult(
                latitude=latitude,
                longitude=longitude,
                status=spatial.status,
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

        lulc = self._lulc.query(latitude=latitude, longitude=longitude)
        final_status = _resolve_status(spatial.status, lulc.status)

        return GeoCodedCoreResult(
            latitude=latitude,
            longitude=longitude,
            status=final_status,
            inside_study_area=True,
            micro_watershed_id=spatial.micro_watershed_id,
            mws_code=spatial.mws_code,
            lulc_value=lulc.lulc_value,
            lulc_class=lulc.lulc_class,
            raster_pixel_row=lulc.raster_pixel_row,
            raster_pixel_col=lulc.raster_pixel_col,
            lulc_neighborhood_window_size=lulc.neighborhood_window_size,
            lulc_neighborhood_class_purity_pct=lulc.neighborhood_class_purity_pct,
            lulc_neighborhood_nodata_pct=lulc.neighborhood_nodata_pct,
        )
