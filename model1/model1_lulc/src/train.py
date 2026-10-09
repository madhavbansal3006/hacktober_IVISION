"""
Train the Random Forest LULC classifier on training_data.csv, using the
pre-computed spatial train/test split column so evaluation reflects
held-out spatial regions rather than randomly interleaved neighboring
pixels.
"""
from __future__ import annotations

import json
import os
import sys
from datetime import datetime, timezone

import joblib
import pandas as pd
from sklearn.ensemble import RandomForestClassifier

from src.config import load_config, ensure_dirs


class TrainingDataUnavailableError(RuntimeError):
    pass


def load_training_table(cfg: dict) -> pd.DataFrame:
    path = cfg["paths"]["training_data_csv"]
    if not os.path.exists(path):
        raise TrainingDataUnavailableError(
            f"Training data not found at {path}.\n"
            "Run the earlier pipeline stages first:\n"
            "  python -m src.prepare_study_area\n"
            "  python -m src.download_sentinel\n"
            "  python -m src.prepare_reference\n"
            "  python -m src.sampling\n"
        )
    df = pd.read_csv(path)

    required_cols = set(cfg["features"]["names"]) | {"LULC_Label", "split"}
    missing = required_cols - set(df.columns)
    if missing:
        raise TrainingDataUnavailableError(
            f"training_data.csv is missing required columns: {missing}. "
            f"Found columns: {list(df.columns)}"
        )

    if df[cfg["features"]["names"]].isna().any().any():
        raise TrainingDataUnavailableError(
            "training_data.csv contains missing feature values. Fix upstream sampling/"
            "feature generation before training — do not silently drop or impute here."
        )
    if not (df["LULC_Label"].isin(list(cfg["target_classes"].keys()))).all():
        bad = sorted(set(df["LULC_Label"].unique()) - set(cfg["target_classes"].keys()))
        raise TrainingDataUnavailableError(
            f"training_data.csv contains label values outside the expected classes "
            f"{list(cfg['target_classes'].keys())}: found unexpected values {bad}"
        )

    return df


def train_model(cfg: dict, df: pd.DataFrame, class_weight="balanced", n_estimators=None, random_state=None):
    """Train a RandomForestClassifier. class_weight and other overrides let
    callers run multiple experiments (A/B/C) against the same base config
    without mutating config.yaml.
    """
    feature_cols = cfg["features"]["names"]
    train_df = df[df["split"] == "train"]
    test_df = df[df["split"] == "test"]

    if len(train_df) == 0 or len(test_df) == 0:
        raise TrainingDataUnavailableError(
            f"Spatial split produced an empty train or test set (train={len(train_df)}, "
            f"test={len(test_df)}). Adjust sampling.spatial_block_size_m or "
            f"sampling.test_block_fraction in config.yaml."
        )

    X_train = train_df[feature_cols].values
    y_train = train_df["LULC_Label"].values
    X_test = test_df[feature_cols].values
    y_test = test_df["LULC_Label"].values

    rf_cfg = cfg["random_forest"]
    model = RandomForestClassifier(
        n_estimators=n_estimators or rf_cfg["n_estimators"],
        random_state=random_state if random_state is not None else rf_cfg["random_state"],
        class_weight=class_weight,
        n_jobs=rf_cfg["n_jobs"],
        max_depth=rf_cfg.get("max_depth"),
    )
    print(f"Training RandomForestClassifier (class_weight={class_weight}) on {len(X_train)} samples "
          f"({len(feature_cols)} features, {len(set(y_train))} classes)...")
    model.fit(X_train, y_train)
    print("Training complete.")

    return model, (X_train, y_train), (X_test, y_test)


def save_model(model, cfg: dict, df: pd.DataFrame):
    model_path = cfg["paths"]["model_path"]
    os.makedirs(os.path.dirname(model_path), exist_ok=True)
    joblib.dump(model, model_path)
    print(f"Saved model to {model_path}")

    class_counts = df["LULC_Label"].value_counts().to_dict()
    metadata = {
        "feature_names": cfg["features"]["names"],
        "class_mapping": cfg["target_classes"],
        "training_date_utc": datetime.now(timezone.utc).isoformat(),
        "n_training_samples": int((df["split"] == "train").sum()),
        "n_test_samples": int((df["split"] == "test").sum()),
        "class_counts_all_samples": {int(k): int(v) for k, v in class_counts.items()},
        "model_parameters": cfg["random_forest"],
        "random_seed": cfg["random_forest"]["random_state"],
        "reference_label_source": cfg["reference_lulc"]["name"],
        "reference_label_vintage_year": cfg["reference_lulc"]["vintage_year"],
        "sentinel2_date_range_requested": cfg["sentinel2"]["date_range"],
    }
    meta_path = cfg["paths"]["model_metadata_path"]
    with open(meta_path, "w") as f:
        json.dump(metadata, f, indent=2)
    print(f"Saved model metadata to {meta_path}")
    return metadata


if __name__ == "__main__":
    cfg = load_config()
    ensure_dirs(cfg)
    try:
        df = load_training_table(cfg)
        model, train_data, test_data = train_model(cfg, df)
        save_model(model, cfg, df)
    except TrainingDataUnavailableError as e:
        print(str(e))
        sys.exit(1)
