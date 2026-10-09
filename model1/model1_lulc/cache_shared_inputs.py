"""
Run Stages 1-4 (boundary, WorldCover reference, Sentinel-2, feature/label
alignment) ONCE and cache the results to disk, so each experiment (A/B/C)
can be run as a separate short-lived process without redoing this
expensive setup — and without depending on any process surviving between
tool calls, since background jobs do not persist across tool invocations
in this environment.
"""
from __future__ import annotations

import pickle
import numpy as np

from src.config import load_config, ensure_dirs
from src.prepare_study_area import load_shiggaon_boundary
from src.prepare_reference import run as prepare_reference_run, reproject_labels_to_grid
from src.download_sentinel import run as download_sentinel_run
from src.preprocess import assemble_feature_stack, align_labels_to_features

CACHE_PATH = "data/processed/features/shared_inputs_cache.pkl"


def main():
    cfg = load_config()
    ensure_dirs(cfg)

    print("Stage 1: boundary...")
    boundary_gdf, is_real = load_shiggaon_boundary(cfg)

    print("Stage 2: WorldCover reference labels...")
    raw_wc, remapped_labels, wc_profile = prepare_reference_run(cfg, boundary_gdf)

    print("Stage 3: Sentinel-2 bands...")
    bands, good_mask, s2_transform, s2_crs = download_sentinel_run(cfg)

    print("Stage 4: feature stack + label alignment...")
    feature_array, valid_mask = assemble_feature_stack(bands, good_mask, cfg)
    labels_on_s2_grid = reproject_labels_to_grid(
        remapped_labels, wc_profile, s2_transform, s2_crs, feature_array.shape[:2]
    )
    aligned_labels = align_labels_to_features(labels_on_s2_grid, valid_mask, cfg["nodata_value"])

    print(f"Caching to {CACHE_PATH} ...")
    with open(CACHE_PATH, "wb") as f:
        pickle.dump({
            "feature_array": feature_array,
            "valid_mask": valid_mask,
            "aligned_labels": aligned_labels,
            "transform": s2_transform,
            "crs": s2_crs,
            "boundary_gdf": boundary_gdf,
        }, f, protocol=pickle.HIGHEST_PROTOCOL)
    print("Done. feature_array shape:", feature_array.shape)


if __name__ == "__main__":
    main()
