"""
teammate_gis_writer.py — writes the spatial (GeoPackage) outputs required
by SIH_2026_Shiggaon_GeoCoded_Imagery_Teammate_README.docx:

  - GEO_CODED_PHOTO_POINTS.gpkg       (one point per successfully
                                        geocoded photo, EPSG:4326)
  - GEO_CODED_PHOTO_MWS_JOINED.gpkg   (same points, with mws_id/mws_code
                                        columns)

NOTE on "join": the teammate README describes a manual two-step QGIS
workflow (create points, THEN join against the 66-MWS layer via
Processing -> Join attributes by location). This pipeline's watershed
match is already computed inline during analysis (watershed_locator.py,
unchanged) -- there is no separate join step here. Both GeoPackages are
built from the same already-resolved results; GEO_CODED_PHOTO_MWS_JOINED
simply surfaces the mws_id/mws_code columns explicitly, for parity with
what the teammate's manual workflow produces. The existing watershed
matching algorithm is not touched by this module.

Only results with a valid (latitude, longitude) are included -- "one
point per successfully geocoded photo," per the user's explicit
instruction. This includes points outside the study area (still a valid
geocode) but excludes NO_GPS/MALFORMED_GPS/INVALID_COORDINATE/coordinate-
less ERROR results, which have no coordinate to plot.
"""

from __future__ import annotations

from pathlib import Path

import geopandas as gpd
from shapely.geometry import Point

from . import config
from .schema import GeoCodedResult

_POINT_LAYER_NAME = "GEO_CODED_PHOTO_POINTS"
_MWS_JOINED_LAYER_NAME = "GEO_CODED_PHOTO_POINTS_MWS"

# Columns shared by both GeoPackages.
_BASE_COLUMNS = [
    "image_id",
    "file_name",
    "latitude",
    "longitude",
    "capture_datetime",
    "gps_source",
    "gps_accuracy_m",
    "coordinate_status",
    "study_area_status",
    "status",
    "lulc_class",
    "lulc_value",
]

# Additional columns on the MWS-joined layer only.
_MWS_COLUMNS = ["mws_id", "mws_code"]


def _geocoded_results(results: list[GeoCodedResult]) -> list[GeoCodedResult]:
    return [r for r in results if r.latitude is not None and r.longitude is not None]


def _base_row(result: GeoCodedResult) -> dict:
    return {
        "image_id": result.image_id,
        "file_name": result.image_name,
        "latitude": result.latitude,
        "longitude": result.longitude,
        "capture_datetime": result.capture_datetime,
        "gps_source": result.gps_source,
        "gps_accuracy_m": result.gps_accuracy_m,
        "coordinate_status": result.coordinate_status,
        "study_area_status": result.study_area_status,
        "status": result.status,
        "lulc_class": result.lulc_class,
        "lulc_value": result.lulc_value,
    }


def _build_geodataframe(results: list[GeoCodedResult], include_mws: bool) -> gpd.GeoDataFrame:
    geocoded = _geocoded_results(results)
    rows = []
    geometries = []
    for result in geocoded:
        row = _base_row(result)
        if include_mws:
            # mws_id per the user's explicit integration-key decision:
            # this is `id` (result.micro_watershed_id), exposed under the
            # README's expected column name -- a rename at the export
            # layer only, not a change to the internal contract.
            row["mws_id"] = result.micro_watershed_id
            row["mws_code"] = result.mws_code
        rows.append(row)
        geometries.append(Point(result.longitude, result.latitude))

    columns = _BASE_COLUMNS + (_MWS_COLUMNS if include_mws else [])
    return gpd.GeoDataFrame(rows, geometry=geometries, crs=config.WGS84, columns=columns + ["geometry"])


def write_photo_points_gpkg(
    results: list[GeoCodedResult], path: str | Path | None = None
) -> Path:
    path = Path(path) if path is not None else config.GEO_CODED_PHOTO_POINTS_GPKG
    path.parent.mkdir(parents=True, exist_ok=True)

    gdf = _build_geodataframe(results, include_mws=False)
    gdf.to_file(path, layer=_POINT_LAYER_NAME, driver="GPKG")
    return path


def write_photo_mws_joined_gpkg(
    results: list[GeoCodedResult], path: str | Path | None = None
) -> Path:
    path = Path(path) if path is not None else config.GEO_CODED_PHOTO_MWS_JOINED_GPKG
    path.parent.mkdir(parents=True, exist_ok=True)

    gdf = _build_geodataframe(results, include_mws=True)
    gdf.to_file(path, layer=_MWS_JOINED_LAYER_NAME, driver="GPKG")
    return path
