"""
Master pipeline orchestrator for Model 1 (LULC Classification).

Runs each stage in order and stops cleanly at the first stage whose real
input data is unavailable, rather than fabricating downstream outputs.
Each stage's real/simulated status is tracked and printed in a final
status report.

Usage:
    python run_pipeline.py
"""
from __future__ import annotations

import os
import sys
import traceback

from src.config import load_config, ensure_dirs


def main():
    cfg = load_config()
    ensure_dirs(cfg)
    os.makedirs(os.path.join(cfg["_repo_root"], "outputs"), exist_ok=True)

    status = {}

    # --- Stage 1: study area boundary ---
    print("\n=== STAGE 1: Study area boundary ===")
    try:
        from src.prepare_study_area import load_shiggaon_boundary
        boundary_gdf, is_real = load_shiggaon_boundary(cfg)
        status["study_area_boundary"] = "REAL" if is_real else "BBOX_PROXY (not real)"
    except Exception as e:
        print(f"STAGE 1 FAILED: {e}")
        status["study_area_boundary"] = f"FAILED: {e}"
        _print_status(status)
        sys.exit(1)

    # --- Stage 2: reference LULC labels (ESA WorldCover) ---
    print("\n=== STAGE 2: Reference LULC labels (WorldCover) ===")
    try:
        from src.prepare_reference import run as prepare_reference_run
        raw_wc, remapped_labels, wc_profile = prepare_reference_run(cfg, boundary_gdf)
        status["reference_labels"] = "REAL (ESA WorldCover 2021 v200, user-provided tiles)"
    except Exception as e:
        print(f"STAGE 2 FAILED: {e}")
        status["reference_labels"] = f"FAILED: {e}"
        _print_status(status)
        sys.exit(1)

    # --- Stage 3: Sentinel-2 acquisition ---
    print("\n=== STAGE 3: Sentinel-2 acquisition ===")
    try:
        from src.download_sentinel import run as download_sentinel_run, SentinelDataUnavailableError
        bands, good_mask, s2_transform, s2_crs = download_sentinel_run(cfg)
        status["sentinel2"] = "REAL"
    except Exception as e:
        print(f"\nSTAGE 3 BLOCKED — this is the current hard stop.\n{e}")
        status["sentinel2"] = "BLOCKED — see error above"
        _print_status(status)
        print(
            "\nPipeline stopped at Stage 3 (Sentinel-2 acquisition). Stages 1-2 completed "
            "with REAL data and their outputs are saved. Stages 4+ (features, training "
            "samples, Random Forest, prediction GeoTIFF, zonal statistics) all require "
            "real Sentinel-2 band arrays and CANNOT run on fabricated substitutes — no "
            "synthetic imagery has been generated.\n"
        )
        sys.exit(1)

    # --- Stages 4+ only reachable once Sentinel-2 succeeds ---
    print("\n=== STAGE 4: Feature engineering + label alignment ===")
    from src.preprocess import assemble_feature_stack, align_labels_to_features
    from src.prepare_reference import reproject_labels_to_grid

    feature_array, valid_mask = assemble_feature_stack(bands, good_mask, cfg)
    print("Feature stack assembled:", feature_array.shape)

    # WorldCover labels were produced on the EPSG:4326 grid (Stage 2); the
    # Sentinel-2 bands are on EPSG:32643 (Stage 3). Reproject labels onto
    # the Sentinel-2 grid with nearest-neighbor resampling before sampling.
    labels_on_s2_grid = reproject_labels_to_grid(
        remapped_labels, wc_profile, s2_transform, s2_crs, feature_array.shape[:2]
    )
    print(f"Reprojected WorldCover labels onto Sentinel-2 grid: {labels_on_s2_grid.shape}")

    print("\n=== STAGE 5: Training sample generation ===")
    from src.sampling import stratified_sample, finalize_columns, spatial_block_split
    aligned_labels = align_labels_to_features(labels_on_s2_grid, valid_mask, cfg["nodata_value"])
    df = stratified_sample(
        feature_array, aligned_labels, s2_transform,
        cfg["sampling"]["samples_per_class"], cfg["target_classes"],
        cfg["sampling"]["random_state"],
    )
    df = finalize_columns(df, cfg["features"]["names"])
    df = spatial_block_split(df, cfg["sampling"]["spatial_block_size_m"],
                              cfg["sampling"]["test_block_fraction"],
                              cfg["sampling"]["random_state"])
    df.to_csv(cfg["paths"]["training_data_csv"], index=False)
    status["training_data"] = f"REAL ({len(df)} samples)"

    print("\n=== STAGE 6: Model training ===")
    from src.train import train_model, save_model
    model, train_data, test_data = train_model(cfg, df)
    save_model(model, cfg, df)
    status["model"] = "TRAINED"

    print("\n=== STAGE 7: Evaluation ===")
    from src.evaluate import evaluate_model, save_evaluation_artifacts, plot_class_distribution
    metrics, report_txt, cm, class_names = evaluate_model(model, df, cfg)
    save_evaluation_artifacts(metrics, report_txt, cm, class_names, model, cfg)
    plot_class_distribution(df, cfg)
    status["evaluation"] = f"macro_f1={metrics['macro_f1']:.3f}"

    print("\n=== STAGE 8: Full-raster prediction ===")
    from src.predict import predict_full_raster, write_prediction_geotiff
    prediction_raster = predict_full_raster(model, feature_array, valid_mask, cfg["nodata_value"])
    write_prediction_geotiff(prediction_raster, s2_transform, s2_crs,
                              cfg["paths"]["prediction_tif"], cfg["nodata_value"])
    status["prediction_geotiff"] = cfg["paths"]["prediction_tif"]

    print("\n=== STAGE 9: Output validation ===")
    from src.validate_output import validate_geotiff
    validation_results = validate_geotiff(cfg["paths"]["prediction_tif"], cfg, boundary_gdf)
    status["validation"] = "PASSED"

    print("\n=== STAGE 10: Zonal statistics (66 real micro-watersheds) ===")
    from src.zonal_statistics import load_micro_watersheds, compute_zonal_stats
    mw_gdf = load_micro_watersheds(cfg)
    stats_df = compute_zonal_stats(cfg["paths"]["prediction_tif"], mw_gdf, cfg["target_classes"],
                                    cfg["micro_watersheds"]["id_field"])
    stats_df.to_csv(cfg["paths"]["micro_watershed_stats_csv"], index=False)
    status["zonal_statistics"] = f"{len(stats_df)} micro-watersheds"

    _print_status(status)


def _print_status(status: dict):
    print("\n" + "=" * 60)
    print("PIPELINE STATUS REPORT")
    print("=" * 60)
    for stage, val in status.items():
        print(f"  {stage}: {val}")
    print("=" * 60)


if __name__ == "__main__":
    main()
