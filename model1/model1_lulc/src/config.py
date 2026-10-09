"""
Central configuration loader for Model 1 (LULC Classification).

All other modules import `load_config()` from here rather than reading
config.yaml themselves, so there is exactly one place that resolves paths
and defaults.
"""
from __future__ import annotations

import os
import yaml
from pathlib import Path

# Repository root = parent of the src/ directory this file lives in.
REPO_ROOT = Path(__file__).resolve().parent.parent
DEFAULT_CONFIG_PATH = REPO_ROOT / "config.yaml"


def load_config(config_path: str | Path = DEFAULT_CONFIG_PATH) -> dict:
    """Load config.yaml and resolve all relative paths to absolute paths
    rooted at the repository root, so scripts work regardless of the
    directory they're invoked from.
    """
    config_path = Path(config_path)
    if not config_path.exists():
        raise FileNotFoundError(
            f"Config file not found at {config_path}. "
            f"Expected config.yaml at the repository root."
        )

    with open(config_path, "r") as f:
        cfg = yaml.safe_load(f)

    # Resolve every path-like value under 'paths' and known local_path keys
    def _resolve(d, keys):
        for k in keys:
            if k in d and isinstance(d[k], str):
                d[k] = str((REPO_ROOT / d[k]).resolve())

    if "paths" in cfg:
        _resolve(cfg["paths"], list(cfg["paths"].keys()))

    for section in ["study_area", "sentinel2", "reference_lulc"]:
        if section in cfg and "local_path" in cfg[section]:
            cfg[section]["local_path"] = str((REPO_ROOT / cfg[section]["local_path"]).resolve())

    if "micro_watersheds" in cfg:
        for k in ["local_path", "local_path_fallback"]:
            if k in cfg["micro_watersheds"]:
                cfg["micro_watersheds"][k] = str(
                    (REPO_ROOT / cfg["micro_watersheds"][k]).resolve()
                )

    cfg["_repo_root"] = str(REPO_ROOT)
    return cfg


def ensure_dirs(cfg: dict) -> None:
    """Create all output directories referenced in config.yaml if missing."""
    dirs_to_make = set()
    for p in cfg.get("paths", {}).values():
        if isinstance(p, str):
            dirs_to_make.add(str(Path(p).parent))
    for section in ["study_area", "sentinel2", "reference_lulc"]:
        lp = cfg.get(section, {}).get("local_path")
        if lp:
            dirs_to_make.add(lp if Path(lp).suffix == "" else str(Path(lp).parent))
    mw = cfg.get("micro_watersheds", {})
    for k in ["local_path", "local_path_fallback"]:
        if mw.get(k):
            dirs_to_make.add(str(Path(mw[k]).parent))

    for d in dirs_to_make:
        os.makedirs(d, exist_ok=True)


if __name__ == "__main__":
    cfg = load_config()
    ensure_dirs(cfg)
    print("Config loaded OK. Repo root:", cfg["_repo_root"])
    print("Study area bbox:", cfg["study_area"]["bbox"])
    print("Target classes:", cfg["target_classes"])
