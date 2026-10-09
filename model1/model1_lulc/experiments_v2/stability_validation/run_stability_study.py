"""
Validation-Only Stability Study: Frozen Production Model 1 (V1) vs V2 Exp 4a.

STRICT CONSTRAINTS:
- Does NOT modify, overwrite, rename, or replace ANY production Model 1 artifact.
- Does NOT retrain either model.
- Evaluates the frozen V1 model (models/lulc_random_forest.joblib) and
  the saved V2 Exp 4a model (experiments_v2/models/Exp_4a_Leaf_Regularization_minleaf2.joblib).
- Uses the exact same feature definitions, labels, spatial validation methodology,
  and evaluation metrics as in existing V2 experiments.
- Evaluates stability across multiple independent validation seeds/splits.
- Records Accuracy, Macro-F1, Weighted-F1, per-class P/R/F1, confusion matrices,
  and explicit Built-up / Barren minority class consistency.
- Saves all outputs exclusively in experiments_v2/stability_validation/.
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
from scipy import stats
from sklearn.metrics import accuracy_score, precision_recall_fscore_support, confusion_matrix

PARENT_DIR = Path(__file__).resolve().parent.parent.parent
if str(PARENT_DIR) not in sys.path:
    sys.path.insert(0, str(PARENT_DIR))

from src.features import safe_divide

TARGET_CLASSES = {1: "Forest", 2: "Agriculture", 3: "Water", 4: "Built-up", 5: "Barren"}
CLASS_IDS = [1, 2, 3, 4, 5]
CLASS_NAMES = [TARGET_CLASSES[c] for c in CLASS_IDS]

OUT_DIR = Path(__file__).resolve().parent
OUT_DIR.mkdir(parents=True, exist_ok=True)

V1_MODEL_PATH = PARENT_DIR / "models" / "lulc_random_forest.joblib"
V2_MODEL_PATH = PARENT_DIR / "experiments_v2" / "models" / "Exp_4a_Leaf_Regularization_minleaf2.joblib"
TRAIN_DATA_PATH = PARENT_DIR / "outputs" / "training_data.csv"


def compute_spectral_indices_df(df: pd.DataFrame) -> pd.DataFrame:
    """Compute exact MNDWI and EVI indices identical to V2 experiments."""
    df = df.copy()
    b2 = df["B2"].values.astype(np.float32)
    b3 = df["B3"].values.astype(np.float32)
    b4 = df["B4"].values.astype(np.float32)
    b8 = df["B8"].values.astype(np.float32)
    b11 = df["B11"].values.astype(np.float32)

    df["MNDWI"] = safe_divide(b3 - b11, b3 + b11)
    df["EVI"] = safe_divide(2.5 * (b8 - b4), b8 + 6.0 * b4 - 7.5 * b2 + 10000.0)
    return df


def evaluate_predictions(y_true, y_pred):
    """Compute Accuracy, Macro-F1, Weighted-F1, per-class P/R/F1, and confusion matrix."""
    acc = accuracy_score(y_true, y_pred)
    macro_p, macro_r, macro_f1, _ = precision_recall_fscore_support(
        y_true, y_pred, labels=CLASS_IDS, average="macro", zero_division=0
    )
    weighted_p, weighted_r, weighted_f1, _ = precision_recall_fscore_support(
        y_true, y_pred, labels=CLASS_IDS, average="weighted", zero_division=0
    )
    p_c, r_c, f1_c, supp_c = precision_recall_fscore_support(
        y_true, y_pred, labels=CLASS_IDS, average=None, zero_division=0
    )
    cm = confusion_matrix(y_true, y_pred, labels=CLASS_IDS)

    per_class = {}
    for i, c in enumerate(CLASS_IDS):
        name = TARGET_CLASSES[c]
        per_class[name] = {
            "precision": float(p_c[i]),
            "recall": float(r_c[i]),
            "f1": float(f1_c[i]),
            "support": int(supp_c[i]),
        }

    return {
        "accuracy": float(acc),
        "macro_f1": float(macro_f1),
        "weighted_f1": float(weighted_f1),
        "per_class": per_class,
        "confusion_matrix": cm.tolist(),
    }


def compute_aggregate_stats(values: list[float]) -> dict:
    """Compute mean, std, min, max for a list of metric values."""
    arr = np.array(values, dtype=np.float64)
    return {
        "mean": float(np.mean(arr)),
        "std": float(np.std(arr, ddof=1)) if len(arr) > 1 else 0.0,
        "min": float(np.min(arr)),
        "max": float(np.max(arr)),
    }


def main():
    print("=" * 80)
    print("STARTING VALIDATION-ONLY STABILITY STUDY: V1 (PROD) VS V2 EXP 4a")
    print("=" * 80)

    # 1. Load models
    print(f"Loading frozen V1 model from {V1_MODEL_PATH}...")
    v1_model = joblib.load(V1_MODEL_PATH)

    print(f"Loading V2 Exp 4a model from {V2_MODEL_PATH}...")
    v2_bundle = joblib.load(V2_MODEL_PATH)
    v2_model = v2_bundle["model"]
    v2_features = v2_bundle["features"]

    v1_features = ["B2", "B3", "B4", "B8", "B11", "NDVI", "NDWI", "NDBI", "BSI"]
    assert v2_features == v1_features + ["MNDWI", "EVI"], f"Unexpected V2 features: {v2_features}"

    # 2. Load held-out test data
    print(f"Loading held-out test data from {TRAIN_DATA_PATH}...")
    df_raw = pd.read_csv(TRAIN_DATA_PATH)
    df = compute_spectral_indices_df(df_raw)

    test_df = df[df["split"] == "test"].copy().reset_index(drop=True)
    n_test = len(test_df)
    print(f"Held-out test set: {n_test} samples across spatial blocks.")

    # Assign 300m spatial block IDs identical to sampling.py
    block_size_m = 300.0
    bx = (test_df["x"] // block_size_m).astype(int)
    by = (test_df["y"] // block_size_m).astype(int)
    test_df["_block_id"] = list(zip(bx, by))
    unique_blocks = np.array(sorted(test_df["_block_id"].unique()))
    n_blocks = len(unique_blocks)
    print(f"Total unique 300m spatial blocks in test set: {n_blocks}")

    # Define 20 independent validation seeds
    validation_seeds = [
        42, 101, 202, 303, 404, 505, 606, 707, 808, 909,
        1001, 1111, 1234, 1357, 2026, 3141, 4096, 5555, 7777, 9999
    ]
    block_subsample_fraction = 0.80  # 80% of blocks per split (~814 blocks, ~3200 samples)

    split_results = []
    cm_v1_accum = np.zeros((5, 5), dtype=np.int64)
    cm_v2_accum = np.zeros((5, 5), dtype=np.int64)

    print(f"\nEvaluating across {len(validation_seeds)} independent spatial validation splits...")
    for split_idx, seed in enumerate(validation_seeds, start=1):
        rng = np.random.default_rng(seed)
        shuffled_blocks = unique_blocks.copy()
        rng.shuffle(shuffled_blocks)

        n_take_blocks = int(round(n_blocks * block_subsample_fraction))
        selected_blocks = set(map(tuple, shuffled_blocks[:n_take_blocks]))

        mask = test_df["_block_id"].isin(selected_blocks)
        sub_df = test_df[mask]

        y_true = sub_df["LULC_Label"].values
        X_v1 = sub_df[v1_features].values
        X_v2 = sub_df[v2_features].values

        # Predict
        y_pred_v1 = v1_model.predict(X_v1)
        y_pred_v2 = v2_model.predict(X_v2)

        metrics_v1 = evaluate_predictions(y_true, y_pred_v1)
        metrics_v2 = evaluate_predictions(y_true, y_pred_v2)

        cm_v1_accum += np.array(metrics_v1["confusion_matrix"])
        cm_v2_accum += np.array(metrics_v2["confusion_matrix"])

        macro_f1_delta = metrics_v2["macro_f1"] - metrics_v1["macro_f1"]
        acc_delta = metrics_v2["accuracy"] - metrics_v1["accuracy"]
        builtup_f1_delta = metrics_v2["per_class"]["Built-up"]["f1"] - metrics_v1["per_class"]["Built-up"]["f1"]
        barren_f1_delta = metrics_v2["per_class"]["Barren"]["f1"] - metrics_v1["per_class"]["Barren"]["f1"]

        entry = {
            "split_index": split_idx,
            "seed": seed,
            "n_blocks": n_take_blocks,
            "n_samples": int(len(sub_df)),
            "v1": metrics_v1,
            "v2": metrics_v2,
            "deltas": {
                "macro_f1": float(macro_f1_delta),
                "accuracy": float(acc_delta),
                "builtup_f1": float(builtup_f1_delta),
                "barren_f1": float(barren_f1_delta),
            },
        }
        split_results.append(entry)
        print(f"  Split {split_idx:2d} (seed {seed:4d}): N={len(sub_df):4d} | "
              f"V1 F1: {metrics_v1['macro_f1']:.4f}, V2 F1: {metrics_v2['macro_f1']:.4f} | "
              f"Delta: {macro_f1_delta:+.4f} | Builtup: {builtup_f1_delta:+.4f}, Barren: {barren_f1_delta:+.4f}")

    # Compute statistical summaries across the 20 splits
    metrics_to_summarize = ["accuracy", "macro_f1", "weighted_f1"]
    summary = {"v1": {}, "v2": {}, "delta": {}, "per_class": {}}

    for m in metrics_to_summarize:
        vals_v1 = [s["v1"][m] for s in split_results]
        vals_v2 = [s["v2"][m] for s in split_results]
        vals_delta = [s["v2"][m] - s["v1"][m] for s in split_results]

        summary["v1"][m] = compute_aggregate_stats(vals_v1)
        summary["v2"][m] = compute_aggregate_stats(vals_v2)
        summary["delta"][m] = compute_aggregate_stats(vals_delta)

    # Paired t-test on Macro-F1
    v1_f1_series = [s["v1"]["macro_f1"] for s in split_results]
    v2_f1_series = [s["v2"]["macro_f1"] for s in split_results]
    t_stat, p_val = stats.ttest_rel(v2_f1_series, v1_f1_series)

    # Per-class summary
    for cname in CLASS_NAMES:
        summary["per_class"][cname] = {}
        for sub_metric in ["precision", "recall", "f1"]:
            c_vals_v1 = [s["v1"]["per_class"][cname][sub_metric] for s in split_results]
            c_vals_v2 = [s["v2"]["per_class"][cname][sub_metric] for s in split_results]
            c_vals_delta = [c_vals_v2[i] - c_vals_v1[i] for i in range(len(split_results))]

            summary["per_class"][cname][f"v1_{sub_metric}"] = compute_aggregate_stats(c_vals_v1)
            summary["per_class"][cname][f"v2_{sub_metric}"] = compute_aggregate_stats(c_vals_v2)
            summary["per_class"][cname][f"delta_{sub_metric}"] = compute_aggregate_stats(c_vals_delta)

    # Minority class consistency check
    builtup_f1_deltas = [s["deltas"]["builtup_f1"] for s in split_results]
    barren_f1_deltas = [s["deltas"]["barren_f1"] for s in split_results]
    macro_f1_deltas = [s["deltas"]["macro_f1"] for s in split_results]

    builtup_improved_count = sum(d > 0 for d in builtup_f1_deltas)
    barren_improved_count = sum(d > 0 for d in barren_f1_deltas)
    macro_improved_count = sum(d > 0 for d in macro_f1_deltas)

    # Also evaluate the full 100% test set as the global anchor
    y_full_true = test_df["LULC_Label"].values
    y_full_v1 = v1_model.predict(test_df[v1_features].values)
    y_full_v2 = v2_model.predict(test_df[v2_features].values)
    full_eval_v1 = evaluate_predictions(y_full_true, y_full_v1)
    full_eval_v2 = evaluate_predictions(y_full_true, y_full_v2)

    # Final verdict determination
    mean_macro_delta = summary["delta"]["macro_f1"]["mean"]
    if mean_macro_delta > 0.005 and p_val < 0.01 and builtup_improved_count >= 15 and barren_improved_count >= 15:
        verdict = "V2 STABLE IMPROVEMENT — CANDIDATE FOR PROMOTION"
    elif mean_macro_delta > 0.0:
        verdict = "V2 INCREMENTAL / INCONCLUSIVE — KEEP V1 FROZEN"
    else:
        verdict = "V2 WORSE — KEEP V1 FROZEN"

    full_study_output = {
        "study_name": "Validation-Only Stability Study: V1 vs V2 Exp 4a",
        "timestamp_utc": time.strftime("%Y-%m-%dT%H:%M:%SZ", time.gmtime()),
        "verdict": verdict,
        "statistical_test": {
            "test_type": "Paired two-tailed Student t-test",
            "t_statistic": float(t_stat),
            "p_value": float(p_val),
            "degrees_of_freedom": len(validation_seeds) - 1,
        },
        "minority_class_consistency": {
            "total_splits": len(validation_seeds),
            "macro_f1_improved_splits": f"{macro_improved_count}/{len(validation_seeds)}",
            "builtup_f1_improved_splits": f"{builtup_improved_count}/{len(validation_seeds)}",
            "barren_f1_improved_splits": f"{barren_improved_count}/{len(validation_seeds)}",
        },
        "aggregate_metrics": summary,
        "full_anchor_evaluation": {
            "v1": full_eval_v1,
            "v2": full_eval_v2,
            "macro_f1_delta": float(full_eval_v2["macro_f1"] - full_eval_v1["macro_f1"]),
            "accuracy_delta": float(full_eval_v2["accuracy"] - full_eval_v1["accuracy"]),
        },
        "aggregate_confusion_matrices": {
            "class_order": CLASS_NAMES,
            "v1_aggregate_sum": cm_v1_accum.tolist(),
            "v2_aggregate_sum": cm_v2_accum.tolist(),
        },
        "split_evaluations": split_results,
    }

    # Save outputs
    json_path = OUT_DIR / "stability_results.json"
    with open(json_path, "w") as f:
        json.dump(full_study_output, f, indent=2)
    print(f"\nSaved full stability study results to {json_path}")

    # Build CSV summary table
    table_rows = []
    for s in split_results:
        table_rows.append({
            "Split": s["split_index"],
            "Seed": s["seed"],
            "Samples": s["n_samples"],
            "V1_Acc": round(s["v1"]["accuracy"] * 100, 2),
            "V2_Acc": round(s["v2"]["accuracy"] * 100, 2),
            "Acc_Delta": round(s["deltas"]["accuracy"] * 100, 2),
            "V1_MacroF1": round(s["v1"]["macro_f1"], 4),
            "V2_MacroF1": round(s["v2"]["macro_f1"], 4),
            "MacroF1_Delta": round(s["deltas"]["macro_f1"], 4),
            "V1_BuiltupF1": round(s["v1"]["per_class"]["Built-up"]["f1"], 4),
            "V2_BuiltupF1": round(s["v2"]["per_class"]["Built-up"]["f1"], 4),
            "BuiltupF1_Delta": round(s["deltas"]["builtup_f1"], 4),
            "V1_BarrenF1": round(s["v1"]["per_class"]["Barren"]["f1"], 4),
            "V2_BarrenF1": round(s["v2"]["per_class"]["Barren"]["f1"], 4),
            "BarrenF1_Delta": round(s["deltas"]["barren_f1"], 4),
        })
    csv_df = pd.DataFrame(table_rows)
    csv_path = OUT_DIR / "stability_summary_table.csv"
    csv_df.to_csv(csv_path, index=False)
    print(f"Saved summary CSV table to {csv_path}")

    print("\n" + "=" * 80)
    print(f"STABILITY STUDY COMPLETE. VERDICT: {verdict}")
    print("=" * 80)
    print(f"V1 Macro-F1: {summary['v1']['macro_f1']['mean']:.4f} ± {summary['v1']['macro_f1']['std']:.4f} (Min: {summary['v1']['macro_f1']['min']:.4f}, Max: {summary['v1']['macro_f1']['max']:.4f})")
    print(f"V2 Macro-F1: {summary['v2']['macro_f1']['mean']:.4f} ± {summary['v2']['macro_f1']['std']:.4f} (Min: {summary['v2']['macro_f1']['min']:.4f}, Max: {summary['v2']['macro_f1']['max']:.4f})")
    print(f"Mean Macro-F1 Improvement: {summary['delta']['macro_f1']['mean']:+.4f} (t={t_stat:.3f}, p={p_val:.4e})")
    print(f"Minority class improvements: Built-up {builtup_improved_count}/{len(validation_seeds)} splits, Barren {barren_improved_count}/{len(validation_seeds)} splits.")


if __name__ == "__main__":
    main()
