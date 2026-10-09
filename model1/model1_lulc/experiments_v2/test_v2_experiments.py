"""
Tests for Model 1 V2 improvement experiments.
Ensures production artifact protection and verifies experiment results structure.
"""
import hashlib
import json
from pathlib import Path
import pytest
import joblib

MODEL1_DIR = Path(__file__).resolve().parent.parent
EXP2_DIR = MODEL1_DIR / "experiments_v2"


def test_production_artifacts_untouched():
    """Verify that every production artifact listed in the manifest matches its original MD5."""
    manifest_path = MODEL1_DIR / "PROTECTION_MANIFEST_pre_t2_audit.txt"
    assert manifest_path.exists(), "Protection manifest missing"

    with open(manifest_path, "r") as f:
        lines = [line.strip() for line in f if line.strip()]

    for line in lines:
        expected_md5, rel_path = line.split()
        full_path = MODEL1_DIR / rel_path
        assert full_path.exists(), f"Production file missing: {rel_path}"
        actual_md5 = hashlib.md5(full_path.read_bytes()).hexdigest()
        assert actual_md5 == expected_md5, f"Production file was modified: {rel_path} (expected {expected_md5}, got {actual_md5})"


def test_v2_results_complete():
    """Verify that all 10 V2 experiments were recorded with valid metrics."""
    results_path = EXP2_DIR / "results" / "v2_experiment_results.json"
    assert results_path.exists(), "V2 results JSON missing"

    with open(results_path, "r") as f:
        results = json.load(f)

    assert len(results) == 10, f"Expected 10 experiments, got {len(results)}"

    required_keys = [
        "experiment_id", "experiment_name", "category", "features", "hyperparameters",
        "sampling", "accuracy", "macro_f1", "weighted_f1", "per_class",
        "confusion_matrix", "full_scene_predicted_percent"
    ]

    for exp in results:
        for k in required_keys:
            assert k in exp, f"Missing key {k} in experiment {exp.get('experiment_id')}"
        
        # Verify 5 target classes in per_class
        for cname in ["Forest", "Agriculture", "Water", "Built-up", "Barren"]:
            assert cname in exp["per_class"], f"Missing class {cname} in {exp['experiment_id']}"
            assert 0.0 <= exp["per_class"][cname]["f1"] <= 1.0

        # Verify full-scene percentages sum to ~100%
        scene_sum = sum(exp["full_scene_predicted_percent"].values())
        assert abs(scene_sum - 100.0) < 1.0, f"Scene percentages sum to {scene_sum}, expected ~100"


def test_v2_best_candidate_model():
    """Verify that the best candidate model was saved and can be loaded."""
    model_path = EXP2_DIR / "models" / "Exp_4a_Leaf_Regularization_minleaf2.joblib"
    assert model_path.exists(), f"Best candidate model missing at {model_path}"

    saved = joblib.load(model_path)
    assert "model" in saved
    assert "features" in saved
    assert len(saved["features"]) == 11
    assert "MNDWI" in saved["features"]
    assert "EVI" in saved["features"]


def test_stability_validation_outputs():
    """Verify that stability validation study outputs exist and have valid structure."""
    stab_dir = EXP2_DIR / "stability_validation"
    assert (stab_dir / "run_stability_study.py").exists()
    assert (stab_dir / "stability_results.json").exists()
    assert (stab_dir / "stability_summary_table.csv").exists()
    assert (stab_dir / "STABILITY_VALIDATION_REPORT.md").exists()

    with open(stab_dir / "stability_results.json", "r") as f:
        data = json.load(f)

    assert "aggregate_metrics" in data
    assert "statistical_test" in data
    assert "verdict" in data
    assert data["verdict"] in [
        "V2 STABLE IMPROVEMENT — CANDIDATE FOR PROMOTION",
        "V2 INCREMENTAL / INCONCLUSIVE — KEEP V1 FROZEN",
        "V2 WORSE — KEEP V1 FROZEN"
    ]
    assert len(data["split_evaluations"]) == 20

