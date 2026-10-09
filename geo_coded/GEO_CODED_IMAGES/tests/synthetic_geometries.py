"""
Synthetic boundary/watershed geometries for Phase 4 tests, in a simple
0-10 degree coordinate space (not real Shiggaon coordinates) so test
geometry and expected results are easy to reason about by hand.

Layout (lon=x, lat=y):

    (0,10)---------------(10,10)
      |    GAP (no        |
      |    watershed)     |
      |------(5,5)---------------(15,10)
      |   W1  |         W2          |
    (0,0)----(5,0)---------------(15,0)

  - Boundary square: (0,0) to (10,10)
  - W1: (0,0) to (5,5)  -- fully inside boundary
  - W2: (5,0) to (15,10) -- EXTENDS BEYOND the boundary (x up to 15)
  - Gap region: (0,5) to (5,10) -- inside boundary, no watershed covers it
"""

from __future__ import annotations

from pathlib import Path

import geopandas as gpd
from shapely.geometry import Point, box

CRS = "EPSG:4326"


def make_boundary_gpkg(path: Path) -> None:
    boundary = box(0, 0, 10, 10)
    gdf = gpd.GeoDataFrame({"name": ["synthetic_boundary"]}, geometry=[boundary], crs=CRS)
    gdf.to_file(path, driver="GPKG")


def make_watersheds_gpkg(path: Path) -> None:
    w1 = box(0, 0, 5, 5)
    w2 = box(5, 0, 15, 10)  # deliberately extends past the boundary's x=10 edge
    gdf = gpd.GeoDataFrame(
        {
            "id": ["W1", "W2"],
            "MWS": ["MWS-A", "MWS-B"],
        },
        geometry=[w1, w2],
        crs=CRS,
    )
    gdf.to_file(path, driver="GPKG")


def make_duplicate_id_watersheds_gpkg(path: Path) -> None:
    w1 = box(0, 0, 5, 5)
    w2 = box(5, 0, 10, 5)
    gdf = gpd.GeoDataFrame(
        {"id": ["DUPLICATE", "DUPLICATE"], "MWS": ["MWS-A", "MWS-B"]},
        geometry=[w1, w2],
        crs=CRS,
    )
    gdf.to_file(path, driver="GPKG")


def make_wrong_crs_gpkg(path: Path, geometry) -> None:
    gdf = gpd.GeoDataFrame({"id": ["X"], "MWS": ["MWS-X"]}, geometry=[geometry], crs="EPSG:3857")
    gdf.to_file(path, driver="GPKG")


# Named test points, per the layout diagram above
POINT_INSIDE_W1 = Point(2, 2)          # inside boundary, inside W1
POINT_INSIDE_W2 = Point(8, 2)          # inside boundary, inside W2 (W2 also extends beyond boundary)
POINT_OUTSIDE_BOUNDARY_IN_W2 = Point(12, 2)  # OUTSIDE boundary but inside W2's extended area
POINT_IN_GAP = Point(2, 8)             # inside boundary, no watershed covers this
POINT_FAR_OUTSIDE = Point(-50, -50)    # outside everything
