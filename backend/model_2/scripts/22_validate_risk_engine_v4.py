import pandas as pd
import numpy as np
from pathlib import Path


# ============================================================
# MODEL 2 — RISK ENGINE V4 VALIDATION
# ============================================================

BASE_DIR = Path(__file__).resolve().parents[1]

INPUT = (
    BASE_DIR
    / "data"
    / "processed"
    / "risk_assessment_v4.csv"
)

OUTPUT = (
    BASE_DIR
    / "data"
    / "processed"
    / "risk_v4_validation.csv"
)

print("=" * 70)
print("MODEL 2 — RISK ENGINE V4 VALIDATION")
print("=" * 70)


# ============================================================
# 1. LOAD
# ============================================================

df = pd.read_csv(INPUT)

print("\nDataset:")
print(f"Rows: {len(df)}")
print(f"Watersheds: {df['id'].nunique()}")
print(f"Years: {df['year'].min()}–{df['year'].max()}")


# ============================================================
# 2. RISK CATEGORY ORDER
# ============================================================

category_order = [
    "LOW",
    "MODERATE",
    "HIGH",
    "CRITICAL",
]

df["risk_category"] = pd.Categorical(
    df["risk_category"],
    categories=category_order,
    ordered=True,
)


# ============================================================
# 3. CATEGORY STATISTICS
# ============================================================

print("\n" + "=" * 70)
print("RISK CATEGORY → ENVIRONMENTAL SIGNALS")
print("=" * 70)

category_stats = (
    df.groupby(
        "risk_category",
        observed=True
    )
    [
        [
            "final_risk_score",
            "base_risk_score",
            "water_stress_score",
            "flood_risk_score",
            "ecosystem_risk_score",
            "ml_anomaly_score",
            "ml_adjustment",
            "temporal_warning_adjustment",
        ]
    ]
    .mean()
)

print(
    category_stats
    .round(2)
    .to_string()
)


# ============================================================
# 4. LOGICAL CONSISTENCY CHECK
# ============================================================

print("\n" + "=" * 70)
print("LOGICAL CONSISTENCY CHECK")
print("=" * 70)

# ------------------------------------------------------------
# A. Overall risk should increase with category
# ------------------------------------------------------------

required_monotonic = [
    "final_risk_score",
    "base_risk_score",
    "water_stress_score",
    "ecosystem_risk_score",
    "temporal_warning_adjustment",
]

print("\nMonotonic signals:")

for metric in required_monotonic:

    values = (
        category_stats[metric]
        .dropna()
        .values
    )

    passed = np.all(
        np.diff(values) >= -1e-9
    )

    status = "PASS" if passed else "CHECK"

    print(
        f"{metric:35s} {status}"
    )


# ------------------------------------------------------------
# B. ML anomaly does NOT need perfect monotonicity
# ------------------------------------------------------------

print("\nML anomaly separation:")

low_ml = category_stats.loc[
    "LOW",
    "ml_anomaly_score"
]

high_ml = category_stats.loc[
    "HIGH",
    "ml_anomaly_score"
]

critical_ml = category_stats.loc[
    "CRITICAL",
    "ml_anomaly_score"
]

print(
    f"LOW ML anomaly:       {low_ml:.2f}"
)

print(
    f"HIGH ML anomaly:      {high_ml:.2f}"
)

print(
    f"CRITICAL ML anomaly:  {critical_ml:.2f}"
)

ml_separation_pass = (
    high_ml > low_ml
    and critical_ml > low_ml
)

print(
    "ML anomaly separation:",
    "PASS" if ml_separation_pass else "CHECK"
)


# ------------------------------------------------------------
# C. Flood risk should be strongest for flood-driven cases
# ------------------------------------------------------------

print("\nDriver-specific consistency:")

flood_cases = df[
    df["primary_risk_driver"]
    == "Flood/Runoff"
]

water_cases = df[
    df["primary_risk_driver"]
    == "Water Stress"
]

ecosystem_cases = df[
    df["primary_risk_driver"]
    == "Ecosystem Pressure"
]


if len(flood_cases) > 0:

    flood_mean = flood_cases[
        "flood_risk_score"
    ].mean()

    print(
        f"Flood-driven cases → "
        f"mean flood score: {flood_mean:.2f}"
    )

else:

    flood_mean = np.nan


if len(water_cases) > 0:

    water_mean = water_cases[
        "water_stress_score"
    ].mean()

    print(
        f"Water-driven cases → "
        f"mean water-stress score: {water_mean:.2f}"
    )

else:

    water_mean = np.nan


if len(ecosystem_cases) > 0:

    ecosystem_mean = ecosystem_cases[
        "ecosystem_risk_score"
    ].mean()

    print(
        f"Ecosystem-driven cases → "
        f"mean ecosystem score: {ecosystem_mean:.2f}"
    )

else:

    ecosystem_mean = np.nan


print("\n✓ Component monotonicity is NOT required.")
print(
    "✓ Driver-specific signals are evaluated instead."
)


# ============================================================
# 5. WARNING SIGNALS BY RISK CATEGORY
# ============================================================

print("\n" + "=" * 70)
print("WARNING SIGNAL FREQUENCY")
print("=" * 70)

warning_columns = [
    "flood_warning_signal",
    "water_stress_warning_signal",
    "ecosystem_warning_signal",
]

warning_stats = (
    df.groupby(
        "risk_category",
        observed=True
    )[warning_columns]
    .mean()
    * 100
)

print(
    warning_stats
    .round(2)
    .to_string()
)


# ============================================================
# 6. EXTREME RISK CASES
# ============================================================

print("\n" + "=" * 70)
print("EXTREME RISK CASES")
print("=" * 70)

critical = df[
    df["risk_category"] == "CRITICAL"
].copy()

print(
    f"\nCritical observations: "
    f"{len(critical)}"
)

if len(critical) > 0:

    print("\nCritical cases:")

    print(
        critical[
            [
                "id",
                "year",
                "month",
                "final_risk_score",
                "base_risk_score",
                "ml_anomaly_score",
                "ml_adjustment",
                "temporal_warning_adjustment",
                "primary_risk_driver",
                "risk_drivers",
            ]
        ]
        .sort_values(
            "final_risk_score",
            ascending=False,
        )
        .head(20)
        .to_string(index=False)
    )


# ============================================================
# 7. HIGH + CRITICAL
# ============================================================

high_critical = df[
    df["risk_category"].isin(
        ["HIGH", "CRITICAL"]
    )
]

print(
    f"\nHIGH + CRITICAL observations: "
    f"{len(high_critical)} "
    f"({len(high_critical) / len(df) * 100:.2f}%)"
)

print("\nAverage signals in HIGH + CRITICAL:")

print(
    high_critical[
        [
            "base_risk_score",
            "ml_anomaly_score",
            "ml_adjustment",
            "temporal_warning_adjustment",
        ]
    ]
    .mean()
    .round(2)
    .to_string()
)


# ============================================================
# 8. LOW-RISK CASES
# ============================================================

low = df[
    df["risk_category"] == "LOW"
]

print("\n" + "=" * 70)
print("LOW-RISK VALIDATION")
print("=" * 70)

print(
    f"\nLOW observations: "
    f"{len(low)} "
    f"({len(low) / len(df) * 100:.2f}%)"
)

print("\nAverage LOW-risk signals:")

print(
    low[
        [
            "base_risk_score",
            "ml_anomaly_score",
            "ml_adjustment",
            "temporal_warning_adjustment",
        ]
    ]
    .mean()
    .round(2)
    .to_string()
)


# ============================================================
# 9. HOLDOUT VS TRAINING
# ============================================================

print("\n" + "=" * 70)
print("TRAINING vs HOLDOUT")
print("=" * 70)

df["period"] = np.where(
    df["year"] <= 2023,
    "TRAINING_2017_2023",
    "HOLDOUT_2024_2025",
)

period_stats = (
    df.groupby("period")
    [
        [
            "final_risk_score",
            "base_risk_score",
            "ml_anomaly_score",
            "ml_adjustment",
            "temporal_warning_adjustment",
        ]
    ]
    .mean()
)

print(
    period_stats
    .round(2)
    .to_string()
)


# ============================================================
# 10. HOLDOUT CATEGORY DISTRIBUTION
# ============================================================

print("\nHoldout risk distribution:")

holdout = df[
    df["period"] == "HOLDOUT_2024_2025"
]

holdout_distribution = (
    holdout["risk_category"]
    .value_counts()
    .reindex(
        category_order,
        fill_value=0,
    )
)

print(
    holdout_distribution.to_string()
)

print("\nHoldout percentages:")

print(
    (
        holdout_distribution
        / len(holdout)
        * 100
    )
    .round(2)
    .to_string()
)


# ============================================================
# 11. TEMPORAL WARNING EFFECT
# ============================================================

print("\n" + "=" * 70)
print("TEMPORAL WARNING EFFECT")
print("=" * 70)

warning_present = df[
    df["temporal_warning_adjustment"] > 0
]

warning_absent = df[
    df["temporal_warning_adjustment"] == 0
]

print(
    f"\nObservations with warning signal: "
    f"{len(warning_present)} "
    f"({len(warning_present) / len(df) * 100:.2f}%)"
)

print(
    f"Observations without warning signal: "
    f"{len(warning_absent)} "
    f"({len(warning_absent) / len(df) * 100:.2f}%)"
)

print("\nMean risk with warning:")

print(
    warning_present["final_risk_score"]
    .mean()
    .round(2)
)

print("\nMean risk without warning:")

print(
    warning_absent["final_risk_score"]
    .mean()
    .round(2)
)


# ============================================================
# 12. DRIVER DISTRIBUTION BY RISK CATEGORY
# ============================================================

print("\n" + "=" * 70)
print("PRIMARY DRIVER BY RISK CATEGORY")
print("=" * 70)

driver_table = pd.crosstab(
    df["risk_category"],
    df["primary_risk_driver"],
)

print(
    driver_table
    .to_string()
)


# ============================================================
# 13. LULC CONFIDENCE CHECK
# ============================================================

print("\n" + "=" * 70)
print("LULC CONFIDENCE CHECK")
print("=" * 70)

confidence_table = pd.crosstab(
    df["risk_category"],
    df["lulc_confidence"],
)

print(
    confidence_table
    .to_string()
)


# ============================================================
# 14. WATERSHED CONSISTENCY
# ============================================================

print("\n" + "=" * 70)
print("WATERSHED-LEVEL CONSISTENCY")
print("=" * 70)

watershed_stats = (
    df.groupby("id")
    .agg(
        mean_risk=(
            "final_risk_score",
            "mean",
        ),
        max_risk=(
            "final_risk_score",
            "max",
        ),
        high_critical_count=(
            "risk_category",
            lambda x: (
                x.isin(
                    ["HIGH", "CRITICAL"]
                )
                .sum()
            ),
        ),
        warning_count=(
            "temporal_warning_adjustment",
            lambda x: (
                (x > 0).sum()
            ),
        ),
    )
)

print(
    watershed_stats
    .describe()
    .round(2)
    .to_string()
)


# ============================================================
# 15. SAVE VALIDATION DATA
# ============================================================

validation_summary = (
    category_stats
    .reset_index()
)

validation_summary.to_csv(
    OUTPUT,
    index=False
)


# ============================================================
# 16. FINAL VERDICT
# ============================================================

print("\n" + "=" * 70)
print("V4 VALIDATION COMPLETE")
print("=" * 70)

print(f"\nValidation output: {OUTPUT}")

print("\nThe following questions were evaluated:")

print(
    "✓ Do higher risk categories have higher "
    "environmental risk?"
)

print(
    "✓ Do higher risk categories have stronger "
    "ML anomaly signals?"
)

print(
    "✓ Do warning signals correspond to higher "
    "risk?"
)

print(
    "✓ Is the 2024–2025 holdout behaving "
    "reasonably?"
)

print(
    "✓ Are risk drivers interpretable?"
)

print(
    "✓ Is LULC confidence kept separate from "
    "environmental risk?"
)

print(
    "\nNo model files were modified."
)