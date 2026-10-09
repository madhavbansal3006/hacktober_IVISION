"""
watershed_locator.py — identifies which micro-watershed a WGS84 point
falls inside.

Responsibility boundary (per architecture, Phase 2):
  - Loads the 66 micro-watershed polygons once, builds a spatial index.
  - Answers point-in-watershed containment queries only.
  - Does NOT know about the Shiggaon boundary (callers check boundary
    first, per the pipeline data flow -- this module doesn't enforce
    that order itself).
  - Never modifies data/raw/micro_watersheds/shiggaon_micro_watersheds.gpkg.

Per the Phase 1 audit, watershed polygons are NOT clipped to the Shiggaon
boundary -- 48 of the 66 extend beyond it. That's expected (watersheds
don't respect administrative boundaries) and is handled correctly here by
simply doing point-in-polygon against each watershed independently, with
no reference to the boundary at all.
"""

from __future__ import annotations

from dataclasses import dataclass
from pathlib import Path
from typing import Optional

import geopandas as gpd
from shapely.geometry import Point
from shapely.strtree import STRtree

from . import config


@dataclass(frozen=True)
class WatershedMatch:
    """Result of a successful watershed lookup."""

    micro_watershed_id: str  # from `id` field -- cross-module integration key
    mws_code: str             # from `MWS` field -- hydrological/GIS identifier
    match_type: str           # "unique" or "multiple_candidates_smallest_area_selected"
    candidate_count: int      # number of watersheds the point intersected


class WatershedLocator:
    """
    Loads all micro-watershed polygons once and answers point-location
    queries against them using a spatial index (STRtree) rather than a
    linear scan over 66 polygons per image.
    """

    def __init__(self, watershed_path: str | Path | None = None):
        path = watershed_path or config.MICRO_WATERSHEDS_PATH
        gdf = gpd.read_file(path)

        if gdf.crs is None or str(gdf.crs).upper() != config.WGS84:
            raise ValueError(
                f"Micro-watershed layer at {path} has CRS {gdf.crs}, "
                f"expected {config.WGS84}. Reprojection for this layer is "
                f"not implemented -- verify the source file."
            )

        id_field = config.WATERSHED_ID_FIELD
        mws_field = config.WATERSHED_MWS_FIELD
        for field in (id_field, mws_field):
            if field not in gdf.columns:
                raise ValueError(
                    f"Expected field '{field}' not present in micro-watershed "
                    f"layer columns: {list(gdf.columns)}"
                )

        if gdf[id_field].duplicated().any():
            dupes = gdf.loc[gdf[id_field].duplicated(), id_field].tolist()
            raise ValueError(
                f"'{id_field}' field is not unique -- integration-key "
                f"invariant violated. Duplicate values: {dupes}"
            )

        self._gdf = gdf.reset_index(drop=True)
        self._tree = STRtree(self._gdf.geometry.values)

    def locate(self, point: Point) -> Optional[WatershedMatch]:
        """
        Return the WatershedMatch for the micro-watershed containing
        `point`, or None if the point falls inside no watershed at all
        (a real possibility even for points inside the Shiggaon boundary,
        since the boundary and watershed layers are independently
        sourced -- see architecture doc).

        If the point intersects more than one watershed (possible at a
        shared edge/vertex between adjacent polygons), the smallest-area
        candidate is selected deterministically and `match_type` /
        `candidate_count` record that this happened, rather than silently
        picking an arbitrary one.
        """
        candidate_idx = self._tree.query(point, predicate="intersects")
        if len(candidate_idx) == 0:
            return None

        candidates = self._gdf.iloc[candidate_idx]

        if len(candidates) > 1:
            # Area in degrees (geographic CRS) is not proportional to true
            # area, so reproject to a metric CRS (UTM 43N, same as the LULC
            # raster) just for this comparison -- the tiebreak must reflect
            # real-world size, not degree^2.
            areas_m2 = candidates.geometry.to_crs("EPSG:32643").area
            candidates = candidates.assign(_area=areas_m2)
            candidates = candidates.sort_values("_area")
            match_type = "multiple_candidates_smallest_area_selected"
        else:
            match_type = "unique"

        chosen = candidates.iloc[0]
        return WatershedMatch(
            micro_watershed_id=str(chosen[config.WATERSHED_ID_FIELD]),
            mws_code=str(chosen[config.WATERSHED_MWS_FIELD]),
            match_type=match_type,
            candidate_count=len(candidates),
        )
