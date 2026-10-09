"""
Model 1 V2 Improvement Experiment Runner.

CRITICAL CONSTRAINTS:
- Does NOT modify, rename, delete, or overwrite any production Model 1 artifacts.
- Runs strictly in experiments_v2/.
- Evaluates Macro-F1, Accuracy, per-class Precision/Recall/F1, Confusion Matrix,
  and Full-Raster Class Proportions for every experiment.
- Follows the required experimental sequence.
"""
from __future__ import annotations

import json
import os
import sys
import time
from pathlib import Path

import joblib
import numpy as np
import pandas as pd
from sklearn.ensemble import RandomForestClassifier
from sklearn.metrics import accuracy_score, precision_recall_fscore_support, confusion_matrix

# Add parent directory to sys.path to access src modules if needed
PARENT_DIR = Path(__file__).resolve().parent.parent
if str(PARENT_DIR) not in sys.path:
    sys.path.insert(0, str(PARENT_DIR))

from src.config import load_config
from src.download_sentinel import load_local_bands
from src.features import build_feature_stack, stack_to_array, safe_divide
from src.sampling import stratified_sample, finalize_columns, spatial_block_split

TARGET_CLASSES = {1: "Forest", 2: "Agriculture", 3: "Water", 4: "Built-up", 5: "Barren"}
CLASS_IDS = [1, 2, 3, 4, 5]
CLASS_NAMES = [TARGET_CLASSES[c] for c in CLASS_IDS]

RESULTS_DIR = Path(__file__).resolve().parent / "results"
MODELS_DIR = Path(__file__).resolve().parent / "models"
RESULTS_DIR.mkdir(parents=True, exist_ok=True)
MODELS_DIR.mkdir(parents=True, exist_ok=True)


def compute_spectral_indices_df(df: pd.DataFrame) -> pd.DataFrame:
    """Compute additional spectral indices on the sample DataFrame."""
    df = df.copy()
    b2 = df["B2"].values.astype(np.float32)
    b3 = df["B3"].values.astype(np.float32)
    b4 = df["B4"].values.astype(np.float32)
    b8 = df["B8"].values.astype(np.float32)
    b11 = df["B11"].values.astype(np.float32)

    # MNDWI = (Green - SWIR) / (Green + SWIR) = (B3 - B11) / (B3 + B11)
    df["MNDWI"] = safe_divide(b3 - b11, b3 + b11)

    # EVI = 2.5 * (NIR - Red) / (NIR + 6*Red - 7.5*Blue + 10000)
    # Scaling reflectances with DN / 10000
    evi_num = 2.5 * (b8 - b4)
    evi_den = b8 + 6.0 * b4 - 7.5 * b2 + 10000.0
    df["EVI"] = safe_divide(evi_num, evi_den)

    # SAVI = 1.5 * (NIR - Red) / (NIR + Red + 5000) with L = 0.5
    savi_num = 1.5 * (b8 - b4)
    savi_den = b8 + b4 + 5000.0
    df["SAVI"] = safe_divide(savi_num, savi_den)

    return df


def prepare_full_scene_features(cfg):
    """Load Sentinel-2 bands and construct full-scene valid pixel feature matrices."""
    print("Loading Sentinel-2 bands for full-scene evaluation...")
    t0 = time.time()
    bands, good_mask, transform, crs, _ = load_local_bands(cfg)

    b2 = bands["blue"].astype(np.float32)
    b3 = bands["green"].astype(np.float32)
    b4 = bands["red"].astype(np.float32)
    b8 = bands["nir"].astype(np.float32)
    b11 = bands["swir"].astype(np.float32)

    feat_dict = build_feature_stack(b2, b3, b4, b8, b11, eps=1e-6)
    feat_array = stack_to_array(feat_dict, cfg["features"]["names"])

    # Compute additional indices
    mndwi = safe_divide(b3 - b11, b3 + b11)
    evi = safe_divide(2.5 * (b8 - b4), b8 + 6.0 * b4 - 7.5 * b2 + 10000.0)
    savi = safe_divide(1.5 * (b8 - b4), b8 + b4 + 5000.0)

    # Combined validity mask
    all_indices = [feat_array, mndwi[..., None], evi[..., None], savi[..., None]]
    finite_mask = good_mask.copy()
    for arr in all_indices:
        finite_mask &= np.all(np.isfinite(arr), axis=-1)

    valid_mask = finite_mask
    n_valid = int(valid_mask.sum())
    print(f"Full-scene loaded: {n_valid} valid pixels ({100*n_valid/valid_mask.size:.2f}% of study area) in {time.time()-t0:.1f}s")

    # Construct flat valid feature dictionary
    full_scene_data = {
        "B2": b2[valid_mask],
        "B3": b3[valid_mask],
        "B4": b4[valid_mask],
        "B8": b8[valid_mask],
        "B11": b11[valid_mask],
        "NDVI": feat_dict["NDVI"][valid_mask],
        "NDWI": feat_dict["NDWI"][valid_mask],
        "NDBI": feat_dict["NDBI"][valid_mask],
        "BSI": feat_dict["BSI"][valid_mask],
        "MNDWI": mndwi[valid_mask],
        "EVI": evi[valid_mask],
        "SAVI": savi[valid_mask],
    }
    return full_scene_data, n_valid, transform, crs, bands, valid_mask


def predict_full_scene_proportions(model, feature_names: list[str], full_scene_data: dict, n_valid: int, chunk_size: int = 1_000_000) -> dict:
    """Predict across all valid pixels in chunks and compute class percentages."""
    X_full = np.column_stack([full_scene_data[col] for col in feature_names])
    counts = {c: 0 for c in CLASS_IDS}

    for start in range(0, n_valid, chunk_size):
        end = min(start + chunk_size, n_valid)
        chunk_preds = model.predict(X_full[start:end])
        u, c = np.unique(chunk_preds, return_counts=True)
        for cls_id, count in zip(u, c):
            if int(cls_id) in counts:
                counts[int(cls_id)] += int(count)

    total = sum(counts.values())
    pcts = {TARGET_CLASSES[c]: round(100.0 * counts[c] / total, 2) for c in CLASS_IDS}
    return pcts


def evaluate_model(y_test, y_pred, model, feature_names, full_scene_data, n_valid, baseline_per_class=None):
    """Compute all evaluation metrics, confusion matrix, and full-scene proportions."""
    acc = accuracy_score(y_test, y_pred)
    macro_p, macro_r, macro_f1, _ = precision_recall_fscore_support(
        y_test, y_pred, labels=CLASS_IDS, average="macro", zero_division=0
    )
    weighted_p, weighted_r, weighted_f1, _ = precision_recall_fscore_support(
        y_test, y_pred, labels=CLASS_IDS, average="weighted", zero_division=0
    )
    p_c, r_c, f1_c, supp_c = precision_recall_fscore_support(
        y_test, y_pred, labels=CLASS_IDS, average=None, zero_division=0
    )
    cm = confusion_matrix(y_test, y_pred, labels=CLASS_IDS)

    per_class = {}
    for i, c in enumerate(CLASS_IDS):
        name = TARGET_CLASSES[c]
        per_class[name] = {
            "precision": float(p_c[i]),
            "recall": float(r_c[i]),
            "f1": float(f1_c[i]),
            "support": int(supp_c[i]),
        }

    # Full scene prediction proportions
    t_pred0 = time.time()
    full_scene_pct = predict_full_scene_proportions(model, feature_names, full_scene_data, n_valid)
    t_pred = time.time() - t_pred0

    # Delta for Built-up and Barren
    builtup_f1_delta = None
    barren_f1_delta = None
    if baseline_per_class:
        builtup_f1_delta = per_class["Built-up"]["f1"] - baseline_per_class["Built-up"]["f1"]
        barren_f1_delta = per_class["Barren"]["f1"] - baseline_per_class["Barren"]["f1"]

    return {
        "accuracy": float(acc),
        "macro_f1": float(macro_f1),
        "weighted_f1": float(weighted_f1),
        "per_class": per_class,
        "confusion_matrix": cm.tolist(),
        "confusion_matrix_class_order": CLASS_NAMES,
        "full_scene_predicted_percent": full_scene_pct,
        "builtup_f1_delta": builtup_f1_delta,
        "barren_f1_delta": barren_f1_delta,
        "full_scene_pred_time_sec": round(t_pred, 1),
    }


def main():
    print("=" * 80)
    print("STARTING MODEL 1 V2 IMPROVEMENT EXPERIMENTS")
    print("=" * 80)

    cfg = load_config(str(PARENT_DIR / "config.yaml"))

    # Load full-scene features once
    full_scene_data, n_valid, transform, crs, bands, valid_mask = prepare_full_scene_features(cfg)

    # Load existing production training table (15,000 samples, 10988 train, 4012 test)
    train_data_path = PARENT_DIR / "outputs" / "training_data.csv"
    print(f"Loading exact production training data from {train_data_path}...")
    df_raw = pd.read_csv(train_data_path)
    df = compute_spectral_indices_df(df_raw)

    train_mask = df["split"] == "train"
    test_mask = df["split"] == "test"
    y_train = df.loc[train_mask, "LULC_Label"].values
    y_test = df.loc[test_mask, "LULC_Label"].values
    print(f"Train samples: {len(y_train)}, Test samples: {len(y_test)}")

    baseline_features = ["B2", "B3", "B4", "B8", "B11", "NDVI", "NDWI", "NDBI", "BSI"]

    experiments_plan = [
        {
            "id": "Exp_0_Baseline_V1",
            "name": "Production V1 Baseline (9 Features, RF default)",
            "features": baseline_features,
            "rf_params": {"n_estimators": 200, "class_weight": None, "random_state": 42, "n_jobs": -1},
            "category": "Baseline",
        },
        {
            "id": "Exp_1_Plus_MNDWI",
            "name": "V2 Exp 1 (+MNDWI: 10 Features)",
            "features": baseline_features + ["MNDWI"],
            "rf_params": {"n_estimators": 200, "class_weight": None, "random_state": 42, "n_jobs": -1},
            "category": "Spectral Features",
        },
        {
            "id": "Exp_2_Plus_MNDWI_EVI",
            "name": "V2 Exp 2 (+MNDWI + EVI: 11 Features)",
            "features": baseline_features + ["MNDWI", "EVI"],
            "rf_params": {"n_estimators": 200, "class_weight": None, "random_state": 42, "n_jobs": -1},
            "category": "Spectral Features",
        },
        {
            "id": "Exp_3_Plus_MNDWI_EVI_SAVI",
            "name": "V2 Exp 3 (+MNDWI + EVI + SAVI: 12 Features)",
            "features": baseline_features + ["MNDWI", "EVI", "SAVI"],
            "rf_params": {"n_estimators": 200, "class_weight": None, "random_state": 42, "n_jobs": -1},
            "category": "Spectral Features",
        },
        {
            "id": "Exp_4a_Leaf_Regularization_minleaf2",
            "name": "V2 Exp 4a (HP: min_samples_leaf=2 on +MNDWI+EVI)",
            "features": baseline_features + ["MNDWI", "EVI"],
            "rf_params": {"n_estimators": 200, "min_samples_leaf": 2, "class_weight": None, "random_state": 42, "n_jobs": -1},
            "category": "Hyperparameter Tuning",
        },
        {
            "id": "Exp_4b_Leaf_Regularization_minleaf4",
            "name": "V2 Exp 4b (HP: min_samples_leaf=4 on +MNDWI+EVI)",
            "features": baseline_features + ["MNDWI", "EVI"],
            "rf_params": {"n_estimators": 200, "min_samples_leaf": 4, "class_weight": None, "random_state": 42, "n_jobs": -1},
            "category": "Hyperparameter Tuning",
        },
        {
            "id": "Exp_5a_Max_Features_log2",
            "name": "V2 Exp 5a (HP: max_features='log2' on +MNDWI+EVI)",
            "features": baseline_features + ["MNDWI", "EVI"],
            "rf_params": {"n_estimators": 200, "max_features": "log2", "class_weight": None, "random_state": 42, "n_jobs": -1},
            "category": "Hyperparameter Tuning",
        },
        {
            "id": "Exp_5b_Trees_300",
            "name": "V2 Exp 5b (HP: n_estimators=300 on +MNDWI+EVI)",
            "features": baseline_features + ["MNDWI", "EVI"],
            "rf_params": {"n_estimators": 300, "class_weight": None, "random_state": 42, "n_jobs": -1},
            "category": "Hyperparameter Tuning",
        },
        {
            "id": "Exp_6_Balanced_Weights",
            "name": "V2 Exp 6 (HP: class_weight='balanced' on +MNDWI+EVI)",
            "features": baseline_features + ["MNDWI", "EVI"],
            "rf_params": {"n_estimators": 200, "class_weight": "balanced", "random_state": 42, "n_jobs": -1},
            "category": "Cost-Sensitive Weighting",
        },
    ]

    all_results = []
    baseline_metrics = None
    best_candidate_model = None
    best_candidate_id = None
    best_candidate_f1 = -1.0

    for exp in experiments_plan:
        exp_id = exp["id"]
        exp_name = exp["name"]
        feat_cols = exp["features"]
        rf_params = exp["rf_params"]

        print(f"\n---> Running {exp_id}: {exp_name}")
        t_start = time.time()

        X_train = df.loc[train_mask, feat_cols].values
        X_test = df.loc[test_mask, feat_cols].values

        rf = RandomForestClassifier(**rf_params)
        rf.fit(X_train, y_train)
        t_train = time.time() - t_start

        y_pred = rf.predict(X_test)

        baseline_pc = baseline_metrics["per_class"] if baseline_metrics else None
        metrics = evaluate_model(y_test, y_pred, rf, feat_cols, full_scene_data, n_valid, baseline_pc)

        if exp_id == "Exp_0_Baseline_V1":
            baseline_metrics = metrics

        result_entry = {
            "experiment_id": exp_id,
            "experiment_name": exp_name,
            "category": exp["category"],
            "features": feat_cols,
            "hyperparameters": {k: (v if not isinstance(v, np.generic) else v.item()) for k, v in rf_params.items()},
            "sampling": "equal_count (3000/class, spatial 300m block split)",
            "train_time_sec": round(t_train, 1),
            **metrics,
        }
        all_results.append(result_entry)

        # Track best candidate (excluding baseline)
        if exp_id != "Exp_0_Baseline_V1" and metrics["macro_f1"] > best_candidate_f1:
            best_candidate_f1 = metrics["macro_f1"]
            best_candidate_id = exp_id
            best_candidate_model = (rf, feat_cols, exp_name)

        print(f"     Accuracy: {metrics['accuracy']*100:.2f}%, Macro-F1: {metrics['macro_f1']:.4f}")
        print(f"     Per-Class F1 -> Forest: {metrics['per_class']['Forest']['f1']:.4f}, "
              f"Agri: {metrics['per_class']['Agriculture']['f1']:.4f}, "
              f"Water: {metrics['per_class']['Water']['f1']:.4f}, "
              f"Built-up: {metrics['per_class']['Built-up']['f1']:.4f}, "
              f"Barren: {metrics['per_class']['Barren']['f1']:.4f}")
        print(f"     Full-scene proportions: {metrics['full_scene_predicted_percent']}")

    # -------------------------------------------------------------------------
    # Experiment 7: Separate Sampling Strategy Experiment
    # -------------------------------------------------------------------------
    print("\n" + "=" * 80)
    print("---> Running Exp 7: Natural Prior Sampling vs Equal Count")
    print("=" * 80)
    # Load remapped WorldCover labels to perform natural prior sampling
    from src.prepare_study_area import load_shiggaon_boundary
    from src.prepare_reference import run as prepare_reference_run, reproject_labels_to_grid
    from src.preprocess import align_labels_to_features

    boundary_gdf, _ = load_shiggaon_boundary(cfg)
    raw_wc, remapped_labels, wc_profile = prepare_reference_run(cfg, boundary_gdf)
    labels_on_s2_grid = reproject_labels_to_grid(
        remapped_labels, wc_profile, transform, crs, (valid_mask.shape[0], valid_mask.shape[1])
    )
    aligned_labels = align_labels_to_features(labels_on_s2_grid, valid_mask, cfg["nodata_value"])

    # Reconstruct 2D feature stack for sampling
    b2_arr = bands["blue"].astype(np.float32)
    b3_arr = bands["green"].astype(np.float32)
    b4_arr = bands["red"].astype(np.float32)
    b8_arr = bands["nir"].astype(np.float32)
    b11_arr = bands["swir"].astype(np.float32)

    feat_dict_sample = build_feature_stack(b2_arr, b3_arr, b4_arr, b8_arr, b11_arr, eps=1e-6)
    mndwi_arr = safe_divide(b3_arr - b11_arr, b3_arr + b11_arr)
    evi_arr = safe_divide(2.5 * (b8_arr - b4_arr), b8_arr + 6.0 * b4_arr - 7.5 * b2_arr + 10000.0)

    extended_features_order = baseline_features + ["MNDWI", "EVI"]
    extended_dict = {**feat_dict_sample, "MNDWI": mndwi_arr, "EVI": evi_arr}
    extended_feat_array = stack_to_array(extended_dict, order=extended_features_order)

    # Sample using natural_prior
    t_samp0 = time.time()
    df_nat = stratified_sample(
        extended_feat_array, aligned_labels, transform,
        samples_per_class=cfg["sampling"]["samples_per_class"],
        target_classes=cfg["target_classes"],
        random_state=42,
        mode="natural_prior",
        max_total_samples=20000,
    )
    df_nat = finalize_columns(df_nat, extended_features_order)
    df_nat = spatial_block_split(df_nat, cfg["sampling"]["spatial_block_size_m"],
                                 cfg["sampling"]["test_block_fraction"], random_state=42)

    train_nat = df_nat["split"] == "train"
    test_nat = df_nat["split"] == "test"
    X_train_nat = df_nat.loc[train_nat, extended_features_order].values
    y_train_nat = df_nat.loc[train_nat, "LULC_Label"].values
    X_test_nat = df_nat.loc[test_nat, extended_features_order].values
    y_test_nat = df_nat.loc[test_nat, "LULC_Label"].values

    rf_nat = RandomForestClassifier(n_estimators=200, class_weight=None, random_state=42, n_jobs=-1)
    rf_nat.fit(X_train_nat, y_train_nat)
    y_pred_nat = rf_nat.predict(X_test_nat)

    metrics_nat = evaluate_model(y_test_nat, y_pred_nat, rf_nat, extended_features_order, full_scene_data, n_valid, baseline_metrics["per_class"])

    exp_7_entry = {
        "experiment_id": "Exp_7_Natural_Prior_Sampling",
        "experiment_name": "V2 Exp 7 (Sampling: Natural-Prior Prevalence Proportional)",
        "category": "Sampling Strategy",
        "features": extended_features_order,
        "hyperparameters": {"n_estimators": 200, "class_weight": None, "random_state": 42, "n_jobs": -1},
        "sampling": "natural_prior (prevalence proportional, capped at 20000, 50/class floor)",
        "train_time_sec": round(time.time() - t_samp0, 1),
        **metrics_nat,
    }
    all_results.append(exp_7_entry)
    print(f"     Accuracy: {metrics_nat['accuracy']*100:.2f}%, Macro-F1: {metrics_nat['macro_f1']:.4f}")
    print(f"     Per-Class F1 -> Forest: {metrics_nat['per_class']['Forest']['f1']:.4f}, "
          f"Agri: {metrics_nat['per_class']['Agriculture']['f1']:.4f}, "
          f"Water: {metrics_nat['per_class']['Water']['f1']:.4f}, "
          f"Built-up: {metrics_nat['per_class']['Built-up']['f1']:.4f}, "
          f"Barren: {metrics_nat['per_class']['Barren']['f1']:.4f}")
    print(f"     Full-scene proportions: {metrics_nat['full_scene_predicted_percent']}")

    # Save best model to experiments_v2/models/
    if best_candidate_model is not None:
        best_rf, best_feats, best_name = best_candidate_model
        save_path = MODELS_DIR / f"{best_candidate_id}.joblib"
        joblib.dump({"model": best_rf, "features": best_feats, "name": best_name}, save_path)
        print(f"\nSaved best experimental candidate model to {save_path}")

    # Write results JSON
    out_json = RESULTS_DIR / "v2_experiment_results.json"
    with open(out_json, "w") as f:
        json.dump(all_results, f, indent=2)
    print(f"Saved complete experiment results to {out_json}")


if __name__ == "__main__":
    main()
