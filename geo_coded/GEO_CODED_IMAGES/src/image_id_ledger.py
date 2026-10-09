"""
image_id_ledger.py — persistent, stable image_id (IMG_0001-style)
assignment, backed by a single local JSON file. NOT a database.

Identity is by file CONTENT hash (SHA-256), not filename -- a renamed or
copied photo still resolves to its existing image_id; two different
photos that happen to share a filename never collide.

Never reuses an old id: `next_id` is a monotonically increasing counter
stored in the ledger file itself, independent of which entries currently
exist in it, so manually removing an entry can never cause its number to
be issued again.

OPT-IN BY DESIGN: nothing in image_analyzer.py or pipeline.py constructs
or writes to a ledger unless the caller explicitly passes one in. This
keeps every existing test (and analyze_image()/run_pipeline() called
without an id_ledger argument) completely free of side effects on any
real ledger file on disk. See README "Persistent image_id" section for
how to wire this in for an actual run.
"""

from __future__ import annotations

import hashlib
import json
from pathlib import Path
from typing import Optional


class ImageIdLedger:
    def __init__(self, ledger_path: str | Path):
        self._path = Path(ledger_path)
        self._data = self._load()

    def _load(self) -> dict:
        if self._path.exists():
            with open(self._path) as f:
                data = json.load(f)
            data.setdefault("next_id", 1)
            data.setdefault("entries", {})
            return data
        return {"next_id": 1, "entries": {}}

    def _save(self) -> None:
        self._path.parent.mkdir(parents=True, exist_ok=True)
        # Write to a temp file then atomically replace, so a crash
        # mid-write can't corrupt the ledger.
        tmp_path = self._path.with_suffix(self._path.suffix + ".tmp")
        with open(tmp_path, "w") as f:
            json.dump(self._data, f, indent=2)
        tmp_path.replace(self._path)

    @staticmethod
    def _hash_file(path: Path) -> str:
        h = hashlib.sha256()
        with open(path, "rb") as f:
            for chunk in iter(lambda: f.read(65536), b""):
                h.update(chunk)
        return h.hexdigest()

    def get_or_create(self, image_path: str | Path) -> str:
        """
        Return the existing image_id for this file's content if one was
        already assigned; otherwise assign the next sequential id,
        persist it immediately, and return it.
        """
        image_path = Path(image_path)
        file_hash = self._hash_file(image_path)

        existing = self._data["entries"].get(file_hash)
        if existing is not None:
            return existing["image_id"]

        next_id = self._data["next_id"]
        image_id = f"IMG_{next_id:04d}"
        self._data["entries"][file_hash] = {
            "image_id": image_id,
            "file_name": image_path.name,
        }
        self._data["next_id"] = next_id + 1
        self._save()
        return image_id

    def lookup(self, image_path: str | Path) -> Optional[str]:
        """Return the existing image_id for this file's content without
        creating a new one, or None if it has never been assigned one."""
        file_hash = self._hash_file(Path(image_path))
        existing = self._data["entries"].get(file_hash)
        return existing["image_id"] if existing else None

    def __len__(self) -> int:
        return len(self._data["entries"])
