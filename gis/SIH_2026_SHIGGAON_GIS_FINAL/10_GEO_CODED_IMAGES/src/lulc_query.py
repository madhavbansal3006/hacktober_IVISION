"""
lulc_query.py — samples the Model 1 LULC raster at a WGS84 GPS coordinate.

Responsibility boundary (per architecture, Phase 2):
  - Reprojects the incoming WGS84 point to the raster's CRS (EPSG:32643).
  - Samples the raster at that location using the raster's own transform
    (via rasterio -- never manual pixel math).
  - Maps the raw pixel value to a class name via config.LULC_CLASS_MAP.
  - Does NOT know about the Shiggaon boundary or micro-watersheds.
  - Opens data/raw/lulc/lulc_prediction.tif READ-ONLY. Never writes to it,
    never calls anything that would modify Model 1's production raster.
"""

from __future__ import annotations

from dataclasses import dataclass
from pathlib import Path
from typing import Optional

import numpy as np
import rasterio
from pyproj import Transformer
from rasterio.transform import rowcol

from . import config

# Status values specific to this module's query result.
STATUS_OK = "OK"
STATUS_NODATA_PIXEL = "NODATA_PIXEL"
STATUS_OUTSIDE_RASTER_EXTENT = "OUTSIDE_RASTER_EXTENT"


@dataclass(frozen=True)
class LULCResult:
    lulc_value: Optional[int]
    lulc_class: Optional[str]
    raster_pixel_row: Optional[int]
    raster_pixel_col: Optional[int]
    status: str  # OK | NODATA_PIXEL | OUTSIDE_RASTER_EXTENT
    # "relevant statistics" (Phase 5 requirement): homogeneity of the local
    # neighborhood around the sampled pixel -- what fraction of a small
    # window around this pixel share the same class. Useful as a rough
    # confidence signal (a photo at a class boundary will have low purity).
    # This is an addition beyond the Phase 2 schema, not something that
    # schema originally specified -- flagged here rather than silently
    # smuggled into the "core" fields.
    neighborhood_window_size: Optional[int]
    neighborhood_class_purity_pct: Optional[float]
    neighborhood_nodata_pct: Optional[float]


class LULCQuery:
    """
    Loads the LULC raster once (read-only) and answers point-sample
    queries against it. The full band is read into memory once at
    construction (~10MB, uint8) rather than re-opening the file or
    re-reading windows per query.
    """

    def __init__(self, raster_path: str | Path | None = None, neighborhood_window: int = 3):
        path = raster_path or config.LULC_RASTER_PATH
        if neighborhood_window < 1 or neighborhood_window % 2 == 0:
            raise ValueError("neighborhood_window must be a positive odd integer")
        self._window = neighborhood_window

        with rasterio.open(path) as src:
            if str(src.crs).upper() != config.RASTER_CRS:
                raise ValueError(
                    f"Raster at {path} has CRS {src.crs}, expected "
                    f"{config.RASTER_CRS}. Verify the source file rather "
                    f"than assuming this code will silently handle a "
                    f"CRS change."
                )
            self._transform = src.transform
            self._width = src.width
            self._height = src.height
            self._nodata = src.nodata
            self._array = src.read(1)  # read-only use; file is never written to

        self._transformer = Transformer.from_crs(
            config.WGS84, config.RASTER_CRS, always_xy=True
        )

    def query(self, latitude: float, longitude: float) -> LULCResult:
        """
        Reproject (latitude, longitude) from WGS84 into the raster's CRS,
        locate the containing pixel via the raster's actual affine
        transform (rasterio.transform.rowcol -- not manual arithmetic),
        and return the class at that pixel plus local neighborhood stats.
        """
        raster_x, raster_y = self._transformer.transform(longitude, latitude)
        row, col = rowcol(self._transform, raster_x, raster_y)
        row, col = int(row), int(col)  # rowcol returns numpy ints; normalize to
                                        # native Python ints so results are
                                        # JSON-serializable downstream (Phase 6).

        if not (0 <= row < self._height and 0 <= col < self._width):
            return LULCResult(
                lulc_value=None,
                lulc_class=None,
                raster_pixel_row=None,
                raster_pixel_col=None,
                status=STATUS_OUTSIDE_RASTER_EXTENT,
                neighborhood_window_size=None,
                neighborhood_class_purity_pct=None,
                neighborhood_nodata_pct=None,
            )

        raw_value = int(self._array[row, col])
        is_nodata = self._nodata is not None and raw_value == int(self._nodata)
        lulc_class = config.LULC_CLASS_MAP.get(raw_value, f"UNKNOWN_CLASS_{raw_value}")

        purity_pct, nodata_pct = self._neighborhood_stats(row, col, raw_value)

        return LULCResult(
            lulc_value=raw_value,
            lulc_class=lulc_class,
            raster_pixel_row=row,
            raster_pixel_col=col,
            status=STATUS_NODATA_PIXEL if is_nodata else STATUS_OK,
            neighborhood_window_size=self._window,
            neighborhood_class_purity_pct=purity_pct,
            neighborhood_nodata_pct=nodata_pct,
        )

    def _neighborhood_stats(
        self, row: int, col: int, center_value: int
    ) -> tuple[float, float]:
        half = self._window // 2
        row_start, row_end = max(0, row - half), min(self._height, row + half + 1)
        col_start, col_end = max(0, col - half), min(self._width, col + half + 1)

        window = self._array[row_start:row_end, col_start:col_end]
        total = window.size

        same_class = int(np.count_nonzero(window == center_value))
        purity_pct = 100.0 * same_class / total

        if self._nodata is not None:
            nodata_count = int(np.count_nonzero(window == int(self._nodata)))
        else:
            nodata_count = 0
        nodata_pct = 100.0 * nodata_count / total

        return purity_pct, nodata_pct
