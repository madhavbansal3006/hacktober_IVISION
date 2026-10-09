"""
boundary_checker.py — checks whether a WGS84 point lies inside the
Shiggaon study-area boundary.

Responsibility boundary (per architecture, Phase 2):
  - Loads the boundary polygon once.
  - Answers point-in-boundary containment questions only.
  - Does NOT touch watershed or raster logic.
  - Never modifies data/raw/study_area/shiggaon_boundary.gpkg.
"""

from __future__ import annotations

from pathlib import Path

import geopandas as gpd
from pyproj import Transformer
from shapely.geometry import Point
from shapely.geometry.base import BaseGeometry

from . import config


class BoundaryChecker:
    """
    Loads the Shiggaon boundary polygon once and answers containment
    queries against it. Reused across a batch rather than re-reading the
    file per image.
    """

    def __init__(self, boundary_path: str | Path | None = None):
        path = boundary_path or config.BOUNDARY_PATH
        gdf = gpd.read_file(path)

        if gdf.crs is None or str(gdf.crs).upper() != config.WGS84:
            raise ValueError(
                f"Boundary layer at {path} has CRS {gdf.crs}, expected "
                f"{config.WGS84}. Reprojection for this layer is not "
                f"implemented -- verify the source file rather than "
                f"assuming this code will silently handle a CRS change."
            )

        if len(gdf) != 1:
            raise ValueError(
                f"Expected exactly 1 boundary feature, found {len(gdf)}. "
                f"Multi-feature boundaries are not handled by this checker."
            )

        self._boundary: BaseGeometry = gdf.geometry.iloc[0]

        # Precomputed once for distance_to_boundary_m() -- degree-based
        # distance is not proportional to real-world distance, so a
        # metric-CRS version (same CRS as the LULC raster) is needed for
        # any tolerance-based check.
        self._boundary_metric: BaseGeometry = (
            gpd.GeoSeries([self._boundary], crs=config.WGS84)
            .to_crs(config.RASTER_CRS)
            .iloc[0]
        )
        self._metric_transformer = Transformer.from_crs(
            config.WGS84, config.RASTER_CRS, always_xy=True
        )

    def distance_to_boundary_m(self, point: Point) -> float:
        """
        Real-world distance in meters from `point` (WGS84) to the
        boundary polygon's EDGE (not to its filled area) -- meaningful
        whether the point is inside or outside. This does not change
        is_inside()'s strict containment semantics; it's an additional,
        separate measurement a caller can use to flag "near the
        boundary" cases for manual review without altering the boundary
        geometry itself.
        """
        x, y = self._metric_transformer.transform(point.x, point.y)
        return self._boundary_metric.boundary.distance(Point(x, y))

    def is_inside(self, point: Point) -> bool:
        """
        True if `point` lies inside (or exactly on the edge of) the
        Shiggaon boundary polygon. Uses `intersects` rather than a strict
        interior-only test so that points on the boundary edge count as
        inside -- excluding them would silently drop legitimate edge-case
        field photos.
        """
        return self._boundary.intersects(point)
