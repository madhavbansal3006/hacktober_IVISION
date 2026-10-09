import pandas as pd
import numpy as np
from pathlib import Path


# ============================================================
# MODEL 2 — V2 vs V3 RISK ENGINE COMPARISON
# ============================================================

BASE_DIR = Path(__file__).resolve().parents[1]

V2_PATH = BASE_DIR / "data" / "processed" / "risk_assessment_v2.csv"
V3_PATH = BASE_DIR / "data" / "processed" / "risk_assessment_v3.csv"

OUTPUT = BASE_DIR / "data" / "processed" / "risk_engine_comparison.csv"


print("=" * 70)
print("MODEL 2 — V2 vs V3 COMPARISON")
print("=" * 70)


# ============================================================
# 1. LOAD
# ============================================================

print("\nLoading V2...")

v2 = pd.read_csv(V2_PATH)

print(f"V2 rows: {len(v2)}")

print("\nLoading V3...")

v3 = pd.read_csv(V3_PATH)

print(f"V3 rows: {len(v3)}")


# ============================================================
# 2. BASIC VALIDATION
# ============================================================

print("\nValidating datasets...")

assert len(v2) == len(v3), \
    "V2 and V3 have different row counts."

assert set(v2["id"]) == set(v3["id"]), \
    "Watershed IDs do not match."

assert (
    v2[["id", "year", "month"]]
    .drop_duplicates()
    .shape
    ==
    v3[["id", "year", "month"]]
    .drop_duplicates()
    .shape
), "Temporal observations do not match."

print("✓ Same observations")
print("✓ Same watersheds")
print("✓ Same temporal coverage")


# ============================================================
# 3. RISK SCORE COMPARISON
# ============================================================

print("\n" + "=" * 70)
print("RISK SCORE COMPARISON")
print("=" * 70)

comparison = pd.DataFrame({
    "v2_risk": v2["final_risk_score"],
    "v3_risk": v3["final_risk_score"],
})

comparison["risk_change"] = (
    comparison["v3_risk"]
    - comparison["v2_risk"]
)

print(
    comparison.describe()
    .round(2)
    .to_string()
)


# ============================================================
# 4. CATEGORY DISTRIBUTION
# ============================================================

print("\n" + "=" * 70)
print("RISK CATEGORY DISTRIBUTION")
print("=" * 70)

categories = [
    "LOW",
    "MODERATE",
    "HIGH",
    "CRITICAL",
]

category_table = pd.DataFrame(index=categories)

category_table["V2"] = (
    v2["risk_category"]
    .value_counts()
    .reindex(categories, fill_value=0)
)

category_table["V3"] = (
    v3["risk_category"]
    .value_counts()
    .reindex(categories, fill_value=0)
)

category_table["V2_%"] = (
    category_table["V2"]
    / len(v2)
    * 100
)

category_table["V3_%"] = (
    category_table["V3"]
    / len(v3)
    * 100
)

print(
    category_table
    .round(2)
    .to_string()
)


# ============================================================
# 5. TEMPORAL HOLDOUT COMPARISON
# ============================================================

print("\n" + "=" * 70)
print("HOLDOUT COMPARISON — 2024–2025")
print("=" * 70)

v2_holdout = v2[
    v2["year"] >= 2024
].copy()

v3_holdout = v3[
    v3["year"] >= 2024
].copy()

holdout_table = pd.DataFrame({
    "V2 risk": v2_holdout["final_risk_score"].describe(),
    "V3 risk": v3_holdout["final_risk_score"].describe(),
})

print(
    holdout_table
    .round(2)
    .to_string()
)


# ============================================================
# 6. HOLDOUT CATEGORY DISTRIBUTION
# ============================================================

print("\nHoldout risk categories:")

holdout_categories = pd.DataFrame(index=categories)

holdout_categories["V2"] = (
    v2_holdout["risk_category"]
    .value_counts()
    .reindex(categories, fill_value=0)
)

holdout_categories["V3"] = (
    v3_holdout["risk_category"]
    .value_counts()
    .reindex(categories, fill_value=0)
)

holdout_categories["V2_%"] = (
    holdout_categories["V2"]
    / len(v2_holdout)
    * 100
)

holdout_categories["V3_%"] = (
    holdout_categories["V3"]
    / len(v3_holdout)
    * 100
)

print(
    holdout_categories
    .round(2)
    .to_string()
)


# ============================================================
# 7. PRIMARY DRIVER COMPARISON
# ============================================================

print("\n" + "=" * 70)
print("PRIMARY DRIVER COMPARISON")
print("=" * 70)

driver_table = pd.DataFrame({
    "V2": v2["primary_risk_driver"]
    .value_counts(),

    "V3": v3["primary_risk_driver"]
    .value_counts(),
}).fillna(0)

print(
    driver_table
    .astype(int)
    .to_string()
)


# ============================================================
# 8. RISK SCORE CORRELATION
# ============================================================

correlation = (
    comparison["v2_risk"]
    .corr(comparison["v3_risk"])
)

print(
    f"\nV2 ↔ V3 risk correlation: "
    f"{correlation:.3f}"
)


# ============================================================
# 9. LARGE CHANGES
# ============================================================

comparison["absolute_change"] = (
    comparison["risk_change"].abs()
)

large_changes = comparison[
    comparison["absolute_change"] >= 10
]

print(
    f"\nObservations with ≥10 point risk change: "
    f"{len(large_changes)} "
    f"({len(large_changes) / len(comparison) * 100:.2f}%)"
)


# ============================================================
# 10. HOLDOUT RISK CHANGE
# ============================================================

v2_holdout_indexed = v2_holdout.set_index(
    ["id", "year", "month"]
)

v3_holdout_indexed = v3_holdout.set_index(
    ["id", "year", "month"]
)

holdout_change = (
    v3_holdout_indexed["final_risk_score"]
    -
    v2_holdout_indexed["final_risk_score"]
)

print("\nHoldout risk change:")

print(
    holdout_change.describe()
    .round(2)
    .to_string()
)


# ============================================================
# 11. WATERSHED-LEVEL COMPARISON
# ============================================================

watershed_comparison = pd.DataFrame({
    "V2_mean_risk": v2.groupby("id")[
        "final_risk_score"
    ].mean(),

    "V3_mean_risk": v3.groupby("id")[
        "final_risk_score"
    ].mean(),
})

watershed_comparison["change"] = (
    watershed_comparison["V3_mean_risk"]
    -
    watershed_comparison["V2_mean_risk"]
)

print("\nWatershed-level risk change:")

print(
    watershed_comparison["change"]
    .describe()
    .round(2)
    .to_string()
)


# ============================================================
# 12. SAVE ROW-LEVEL COMPARISON
# ============================================================

result = pd.DataFrame({
    "id": v2["id"],
    "year": v2["year"],
    "month": v2["month"],

    "v2_risk": v2["final_risk_score"],
    "v3_risk": v3["final_risk_score"],

    "v2_category": v2["risk_category"],
    "v3_category": v3["risk_category"],

    "v2_driver": v2["primary_risk_driver"],
    "v3_driver": v3["primary_risk_driver"],
})

result["risk_change"] = (
    result["v3_risk"]
    -
    result["v2_risk"]
)

result["category_changed"] = (
    result["v2_category"]
    !=
    result["v3_category"]
)

result.to_csv(
    OUTPUT,
    index=False
)


# ============================================================
# 13. FINAL SUMMARY
# ============================================================

print("\n" + "=" * 70)
print("COMPARISON COMPLETE")
print("=" * 70)

print(f"Output: {OUTPUT}")

print(
    f"\nCategory changes: "
    f"{result['category_changed'].sum()} "
    f"({result['category_changed'].mean() * 100:.2f}%)"
)

print(
    f"Mean risk change: "
    f"{result['risk_change'].mean():.2f}"
)

print(
    f"Median risk change: "
    f"{result['risk_change'].median():.2f}"
)

print(
    f"Mean absolute change: "
    f"{result['risk_change'].abs().mean():.2f}"
)

print("\n✓ V2 was NOT modified.")
print("✓ V3 was NOT modified.")
print("✓ Comparison output saved.")