"""
Experiments A/B/C — investigating the class-imbalance / inference-prior
problem identified after the first full pipeline run (Built-up predicted
6.4x too often, Barren 7.6x too often, relative to reference-label
prevalence, under class_weight="balanced" + equal-count sampling).

Experiment A (baseline, preserved): equal-count sampling (3000/class),
    class_weight="balanced" — this is what produced the original
    lulc_prediction.tif in outputs/.
Experiment B: equal-count sampling (3000/class), class_weight=None.
Experiment C: natural-prior sampling (proportional to true class
    prevalence in the reference labels, capped at 20000 total, 50/class
    floor), class_weight=None.

For each experiment: train, evaluate on its own spatially-blocked test
set, and predict class proportions across the ENTIRE valid study-area
raster (not just the test set) — the full-scene proportion is the
number that actually matters for this problem, since the test set is
itself class-balanced and hides the effect being investigated.

This script does NOT silently pick a winner by accuracy. It prints a
comparison table and states the tradeoff; the final selection and
reasoning are written to outputs/experiment_comparison.json and
summarized in the README.
"""
from __future__ import annotations

import json
import os
import time

import numpy as np
import pandas as pd
from sklearn.metrics import (
    accuracy_score, precision_recall_fscore_support, confusion_matrix,
)

from src.config import load_config, ensure_dirs
from src.prepare_study_area import load_shiggaon_boundary
from src.prepare_reference import run as prepare_reference_run, reproject_labels_to_grid
from src.download_sentinel import run as download_sentinel_run
from src.preprocess import assemble_feature_stack, align_labels_to_features
from src.sampling import stratified_sample, finalize_columns, spatial_block_split
from src.train import train_model


def build_shared_inputs(cfg):
    """Stages 1-4, run once and shared across all three experiments so
    comparisons isolate the sampling/weighting choice, not data drift.
    """
    boundary_gdf, is_real = load_shiggaon_boundary(cfg)
    raw_wc, remapped_labels, wc_profile = prepare_reference_run(cfg, boundary_gdf)
    bands, good_mask, s2_transform, s2_crs = download_sentinel_run(cfg)
    feature_array, valid_mask = assemble_feature_stack(bands, good_mask, cfg)
    labels_on_s2_grid = reproject_labels_to_grid(
        remapped_labels, wc_profile, s2_transform, s2_crs, feature_array.shape[:2]
    )
    aligned_labels = align_labels_to_features(labels_on_s2_grid, valid_mask, cfg["nodata_value"])
    return feature_array, valid_mask, aligned_labels, s2_transform, s2_crs


def run_one_experiment(name, cfg, feature_array, aligned_labels, valid_mask, transform,
                        sampling_mode, class_weight, random_state=42):
    print(f"\n{'='*70}\nEXPERIMENT {name}: mode={sampling_mode}, class_weight={class_weight}\n{'='*70}")
    t0 = time.time()

    df = stratified_sample(
        feature_array, aligned_labels, transform,
        samples_per_class=cfg["sampling"]["samples_per_class"],
        target_classes=cfg["target_classes"],
        random_state=random_state,
        mode=sampling_mode,
        max_total_samples=20000,
    )
    df = finalize_columns(df, cfg["features"]["names"])
    df = spatial_block_split(df, cfg["sampling"]["spatial_block_size_m"],
                              cfg["sampling"]["test_block_fraction"], random_state)

    model, (X_train, y_train), (X_test, y_test) = train_model(
        cfg, df, class_weight=class_weight, random_state=random_state
    )

    y_pred = model.predict(X_test)
    class_ids = sorted(cfg["target_classes"].keys())
    class_names = [cfg["target_classes"][c] for c in class_ids]

    accuracy = accuracy_score(y_test, y_pred)
    macro_p, macro_r, macro_f1, _ = precision_recall_fscore_support(
        y_test, y_pred, labels=class_ids, average="macro", zero_division=0)
    weighted_p, weighted_r, weighted_f1, _ = precision_recall_fscore_support(
        y_test, y_pred, labels=class_ids, average="weighted", zero_division=0)
    per_class_p, per_class_r, per_class_f1, per_class_support = precision_recall_fscore_support(
        y_test, y_pred, labels=class_ids, average=None, zero_division=0)
    cm = confusion_matrix(y_test, y_pred, labels=class_ids)

    # Full-scene prediction proportions — the number that actually matters here.
    rows, cols, n_feat = feature_array.shape
    flat_features = feature_array.reshape(-1, n_feat)
    flat_valid = valid_mask.reshape(-1)
    full_pred = model.predict(flat_features[flat_valid])
    full_scene_counts = {int(c): int((full_pred == c).sum()) for c in class_ids}
    full_scene_total = sum(full_scene_counts.values())
    full_scene_pct = {cfg["target_classes"][c]: round(100 * full_scene_counts[c] / full_scene_total, 2)
                       for c in class_ids}

    elapsed = time.time() - t0
    result = {
        "experiment": name,
        "sampling_mode": sampling_mode,
        "class_weight": class_weight,
        "n_train_samples": int(len(X_train)),
        "n_test_samples": int(len(X_test)),
        "accuracy": float(accuracy),
        "macro_f1": float(macro_f1),
        "weighted_f1": float(weighted_f1),
        "per_class": {
            class_names[i]: {
                "precision": float(per_class_p[i]), "recall": float(per_class_r[i]),
                "f1": float(per_class_f1[i]), "support": int(per_class_support[i]),
            } for i in range(len(class_ids))
        },
        "confusion_matrix": cm.tolist(),
        "confusion_matrix_class_order": class_names,
        "full_scene_predicted_percent": full_scene_pct,
        "elapsed_seconds": round(elapsed, 1),
    }
    print(f"  accuracy={accuracy:.3f} macro_f1={macro_f1:.3f} weighted_f1={weighted_f1:.3f} "
          f"({elapsed:.1f}s)")
    print(f"  Full-scene predicted proportions: {full_scene_pct}")

    return result, model, df


def main():
    cfg = load_config()
    ensure_dirs(cfg)
    os.makedirs("outputs", exist_ok=True)

    print("Building shared inputs (Stages 1-4, run once)...")
    feature_array, valid_mask, aligned_labels, transform, crs = build_shared_inputs(cfg)

    # Reference-label prevalence (the "true" prior we're comparing against —
    # itself only a WorldCover-derived proxy, not field-verified truth).
    class_ids = sorted(cfg["target_classes"].keys())
    ref_counts = {c: int((aligned_labels == c).sum()) for c in class_ids}
    ref_total = sum(ref_counts.values())
    ref_pct = {cfg["target_classes"][c]: round(100 * ref_counts[c] / ref_total, 2) for c in class_ids}
    print(f"\nReference-label (WorldCover-derived) class prevalence within valid Sentinel-2 area: {ref_pct}")

    experiments = [
        ("A_baseline_balanced", "equal_count", "balanced"),
        ("B_equal_count_unweighted", "equal_count", None),
        ("C_natural_prior_unweighted", "natural_prior", None),
    ]

    results = []
    models = {}
    dfs = {}
    for name, mode, cw in experiments:
        result, model, df = run_one_experiment(
            name, cfg, feature_array, aligned_labels, valid_mask, transform, mode, cw
        )
        results.append(result)
        models[name] = model
        dfs[name] = df

    comparison = {
        "reference_label_prevalence_percent": ref_pct,
        "note": (
            "reference_label_prevalence is WorldCover-derived reference-label prevalence "
            "within the valid Sentinel-2 area, not field-verified ground truth — the closest "
            "available prior, not a target to force predictions toward."
        ),
        "experiments": results,
    }
    with open("outputs/experiment_comparison.json", "w") as f:
        json.dump(comparison, f, indent=2)

    print("\n" + "=" * 70)
    print("COMPARISON TABLE")
    print("=" * 70)
    header = f"{'Experiment':28s} {'Acc':>6s} {'MacroF1':>8s} {'WtF1':>6s}  Full-scene %"
    print(header)
    for r in results:
        pcts = ", ".join(f"{k}:{v}" for k, v in r["full_scene_predicted_percent"].items())
        print(f"{r['experiment']:28s} {r['accuracy']:.3f}  {r['macro_f1']:.3f}   {r['weighted_f1']:.3f}  {pcts}")
    print(f"\nReference-label prevalence: {ref_pct}")

    return comparison, models, dfs, feature_array, valid_mask, aligned_labels, transform, crs, cfg


if __name__ == "__main__":
    main()
