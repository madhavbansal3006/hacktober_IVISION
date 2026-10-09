"""
Evaluate the trained Random Forest against the held-out spatial test set.

IMPORTANT: all metrics here measure agreement with ESA WorldCover 2021 v200
reference labels, NOT verified real-world ground truth. WorldCover itself
has a documented overall accuracy of ~76.7% against independent validation
samples. Do not report these numbers as "real-world accuracy" anywhere
downstream — see README Limitations section.
"""
from __future__ import annotations

import json
import os

import joblib
import matplotlib
matplotlib.use("Agg")
import matplotlib.pyplot as plt
import numpy as np
from sklearn.metrics import (
    accuracy_score, precision_recall_fscore_support,
    classification_report, confusion_matrix, f1_score,
)

from src.config import load_config, ensure_dirs
from src.train import load_training_table


def evaluate_model(model, df, cfg: dict) -> dict:
    feature_cols = cfg["features"]["names"]
    target_classes = cfg["target_classes"]
    class_ids = sorted(target_classes.keys())
    class_names = [target_classes[c] for c in class_ids]

    test_df = df[df["split"] == "test"]
    X_test = test_df[feature_cols].values
    y_test = test_df["LULC_Label"].values
    y_pred = model.predict(X_test)

    accuracy = accuracy_score(y_test, y_pred)
    macro_p, macro_r, macro_f1, _ = precision_recall_fscore_support(
        y_test, y_pred, labels=class_ids, average="macro", zero_division=0
    )
    weighted_p, weighted_r, weighted_f1, _ = precision_recall_fscore_support(
        y_test, y_pred, labels=class_ids, average="weighted", zero_division=0
    )
    per_class_p, per_class_r, per_class_f1, per_class_support = precision_recall_fscore_support(
        y_test, y_pred, labels=class_ids, average=None, zero_division=0
    )

    report_txt = classification_report(
        y_test, y_pred, labels=class_ids, target_names=class_names, zero_division=0
    )
    cm = confusion_matrix(y_test, y_pred, labels=class_ids)

    metrics = {
        "IMPORTANT_NOTE": (
            "These metrics measure agreement between the Random Forest predictions and "
            "ESA WorldCover 2021 v200 reference labels on a spatially held-out test set. "
            "They do NOT represent verified real-world ground-truth accuracy. WorldCover "
            "2021 v200 itself has an independently validated overall accuracy of ~76.7%, "
            "which is an upper bound on how well this evaluation reflects reality."
        ),
        "n_test_samples": int(len(y_test)),
        "accuracy": float(accuracy),
        "macro_precision": float(macro_p),
        "macro_recall": float(macro_r),
        "macro_f1": float(macro_f1),
        "weighted_precision": float(weighted_p),
        "weighted_recall": float(weighted_r),
        "weighted_f1": float(weighted_f1),
        "per_class": {
            class_names[i]: {
                "class_id": int(class_ids[i]),
                "precision": float(per_class_p[i]),
                "recall": float(per_class_r[i]),
                "f1": float(per_class_f1[i]),
                "support": int(per_class_support[i]),
            }
            for i in range(len(class_ids))
        },
        "confusion_matrix": cm.tolist(),
        "confusion_matrix_class_order": class_names,
    }

    print(report_txt)
    print(f"Accuracy: {accuracy:.4f} | Macro F1: {macro_f1:.4f} | Weighted F1: {weighted_f1:.4f}")

    return metrics, report_txt, cm, class_names


def save_evaluation_artifacts(metrics, report_txt, cm, class_names, model, cfg):
    paths = cfg["paths"]
    os.makedirs(os.path.dirname(paths["classification_report_txt"]), exist_ok=True)

    with open(paths["classification_report_txt"], "w") as f:
        f.write(metrics["IMPORTANT_NOTE"] + "\n\n")
        f.write(report_txt)
    print(f"Saved {paths['classification_report_txt']}")

    with open(paths["metrics_json"], "w") as f:
        json.dump(metrics, f, indent=2)
    print(f"Saved {paths['metrics_json']}")

    # Confusion matrix plot
    fig, ax = plt.subplots(figsize=(6, 5))
    im = ax.imshow(cm, cmap="Blues")
    ax.set_xticks(range(len(class_names)))
    ax.set_yticks(range(len(class_names)))
    ax.set_xticklabels(class_names, rotation=45, ha="right")
    ax.set_yticklabels(class_names)
    ax.set_xlabel("Predicted (WorldCover-mapped label)")
    ax.set_ylabel("Actual (WorldCover-mapped label)")
    ax.set_title("Confusion Matrix (agreement with WorldCover reference)")
    for i in range(cm.shape[0]):
        for j in range(cm.shape[1]):
            ax.text(j, i, str(cm[i, j]), ha="center", va="center",
                    color="white" if cm[i, j] > cm.max() / 2 else "black")
    fig.colorbar(im, ax=ax)
    fig.tight_layout()
    fig.savefig(paths["confusion_matrix_png"], dpi=150)
    plt.close(fig)
    print(f"Saved {paths['confusion_matrix_png']}")

    # Feature importance plot — computed from the trained model, not assumed.
    importances = model.feature_importances_
    feature_names = cfg["features"]["names"]
    order = np.argsort(importances)[::-1]
    fig, ax = plt.subplots(figsize=(6, 4))
    ax.bar([feature_names[i] for i in order], importances[order])
    ax.set_ylabel("Importance")
    ax.set_title("Random Forest Feature Importance")
    fig.tight_layout()
    fig.savefig(paths["feature_importance_png"], dpi=150)
    plt.close(fig)
    print(f"Saved {paths['feature_importance_png']}")
    print("Feature importance ranking (highest to lowest):")
    for i in order:
        print(f"  {feature_names[i]}: {importances[i]:.4f}")


def plot_class_distribution(df, cfg):
    target_classes = cfg["target_classes"]
    counts = df["LULC_Label"].value_counts().sort_index()
    labels = [target_classes[i] for i in counts.index]

    fig, ax = plt.subplots(figsize=(6, 4))
    ax.bar(labels, counts.values)
    ax.set_ylabel("Sample count")
    ax.set_title("Training Sample Class Distribution")
    fig.tight_layout()
    fig.savefig(cfg["paths"]["class_distribution_png"], dpi=150)
    plt.close(fig)
    print(f"Saved {cfg['paths']['class_distribution_png']}")


if __name__ == "__main__":
    cfg = load_config()
    ensure_dirs(cfg)
    df = load_training_table(cfg)
    model = joblib.load(cfg["paths"]["model_path"])
    metrics, report_txt, cm, class_names = evaluate_model(model, df, cfg)
    save_evaluation_artifacts(metrics, report_txt, cm, class_names, model, cfg)
    plot_class_distribution(df, cfg)
