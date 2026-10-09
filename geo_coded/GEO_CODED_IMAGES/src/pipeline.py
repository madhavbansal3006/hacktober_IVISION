"""
pipeline.py — batch entry point. Iterates a directory of JPEG images,
runs image_analyzer.analyze_image on each, and returns the full list of
GeoCodedResult objects (one per image, regardless of success/failure).

image_analyzer.analyze_image already catches every anticipated and
unanticipated per-image failure internally (per Phase 3-6 requirements).
The try/except here is a deliberate final backstop, not the primary
error-handling layer -- if it ever fires, that's a bug in analyze_image's
own exception handling worth investigating, not expected behavior.
"""

from __future__ import annotations

from datetime import datetime, timezone
from pathlib import Path

from .geo_lulc_analyzer import GeoLULCAnalyzer
from .image_analyzer import _error_result, analyze_image
from .image_id_ledger import ImageIdLedger
from .schema import STATUS_ERROR, GeoCodedResult

_IMAGE_EXTENSIONS = (".jpg", ".jpeg", ".JPG", ".JPEG")


def find_images(image_dir: str | Path) -> list[Path]:
    image_dir = Path(image_dir)
    found: set[Path] = set()
    for ext in _IMAGE_EXTENSIONS:
        found.update(image_dir.glob(f"*{ext}"))
    return sorted(found)


def run_pipeline(
    image_dir: str | Path,
    analyzer: GeoLULCAnalyzer | None = None,
    id_ledger: ImageIdLedger | None = None,
) -> list[GeoCodedResult]:
    """
    Process every JPEG in `image_dir` and return one GeoCodedResult per
    image. The underlying spatial/LULC datasets (boundary, watersheds,
    raster) are loaded exactly once via `analyzer`, then reused across
    the whole batch -- not re-opened per image.

    id_ledger: optional, OPT-IN (default None -- no image_id is assigned,
    no ledger file is touched). Pass an ImageIdLedger to get persistent,
    stable image_id values across runs. See image_id_ledger.py.
    """
    analyzer = analyzer or GeoLULCAnalyzer()
    results: list[GeoCodedResult] = []

    for image_path in find_images(image_dir):
        try:
            result = analyze_image(image_path, analyzer, id_ledger=id_ledger)
        except Exception as exc:  # noqa: BLE001 - final backstop, see module docstring
            result = _error_result(
                image_path.name,
                datetime.now(timezone.utc).isoformat(),
                STATUS_ERROR,
                f"Unhandled pipeline-level error: {exc}",
            )
        results.append(result)

    return results
