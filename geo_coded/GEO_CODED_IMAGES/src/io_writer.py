"""
io_writer.py — serializes a list of GeoCodedResult to CSV and JSON.

No spatial computation happens here -- purely I/O. Every value in
GeoCodedResult is a native Python type (str, float, int, bool, None), per
the Phase 5 fix that cast numpy ints to native ints in lulc_query.py, so
json.dumps works directly with no custom encoder needed.
"""

from __future__ import annotations

import csv
import dataclasses
import json
from pathlib import Path

from . import config
from .schema import GeoCodedResult


def _as_dicts(results: list[GeoCodedResult]) -> list[dict]:
    return [dataclasses.asdict(r) for r in results]


def write_json(results: list[GeoCodedResult], path: str | Path | None = None) -> Path:
    path = Path(path) if path is not None else config.DEFAULT_JSON_PATH
    path.parent.mkdir(parents=True, exist_ok=True)

    rows = _as_dicts(results)
    # json.dumps directly, not through a lossy round-trip -- if any field
    # were ever a non-native type, this raises immediately rather than
    # silently stringifying it.
    with open(path, "w") as f:
        json.dump(rows, f, indent=2)

    return path


def write_csv(results: list[GeoCodedResult], path: str | Path | None = None) -> Path:
    path = Path(path) if path is not None else config.DEFAULT_CSV_PATH
    path.parent.mkdir(parents=True, exist_ok=True)

    fieldnames = [f.name for f in dataclasses.fields(GeoCodedResult)]

    with open(path, "w", newline="") as f:
        writer = csv.DictWriter(f, fieldnames=fieldnames)
        writer.writeheader()
        for result in results:
            writer.writerow(dataclasses.asdict(result))

    return path


def write_outputs(
    results: list[GeoCodedResult],
    csv_path: str | Path | None = None,
    json_path: str | Path | None = None,
) -> tuple[Path, Path]:
    """Convenience wrapper: write both CSV and JSON in one call."""
    written_csv = write_csv(results, csv_path)
    written_json = write_json(results, json_path)
    return written_csv, written_json
