import pandas as pd
from pathlib import Path

BASE = Path(__file__).resolve().parents[1]

INPUT = BASE / "data/processed/risk_assessment_v2.csv"
OUTPUT = BASE / "data/processed/watershed_intelligence.csv"

print("Loading risk assessment...")
df = pd.read_csv(INPUT)

print("Rows:", len(df))
print("Watersheds:", df["id"].nunique())


# ============================================================
# INTERVENTION ENGINE
# ============================================================

def generate_interventions(row):

    recommendations = []
    drivers = []

    # --------------------------------------------------------
    # WATER STRESS
    # --------------------------------------------------------

    if row["water_stress_score"] >= 60:

        drivers.append("Water stress")

        if row["rainfall_mm"] < 30:
            recommendations.append(
                "Rainwater harvesting"
            )

        if row["ndvi"] < 0.35:
            recommendations.append(
                "Vegetation restoration"
            )

        if row["forest_pct"] < 15:
            recommendations.append(
                "Afforestation / forest restoration"
            )

        if row["water_pct"] < 1:
            recommendations.append(
                "Spring and groundwater recharge structures"
            )

        recommendations.append(
            "Soil-moisture monitoring"
        )


    # --------------------------------------------------------
    # FLOOD / RUNOFF
    # --------------------------------------------------------

    if row["flood_risk_score"] >= 60:

        drivers.append("Flood/runoff susceptibility")

        if row["max_daily_rainfall_mm"] > 30:
            recommendations.append(
                "Check dams"
            )

        if row["slope_mean"] > 10:
            recommendations.append(
                "Contour trenches / contour bunding"
            )

        if row["drainage_density"] > 0.3:
            recommendations.append(
                "Drainage-channel management"
            )

        if row["builtup_pct"] > 15:
            recommendations.append(
                "Urban runoff management"
            )


    # --------------------------------------------------------
    # ECOSYSTEM PRESSURE
    # --------------------------------------------------------

    if row["ecosystem_risk_score"] >= 60:

        drivers.append("Ecosystem degradation")

        if row["forest_pct"] < 20:
            recommendations.append(
                "Afforestation / native vegetation restoration"
            )

        if row["agriculture_pct"] > 70:
            recommendations.append(
                "Sustainable agricultural practices"
            )

        if row["builtup_pct"] > 15:
            recommendations.append(
                "Land-use management"
            )

        if row["soc_mean"] < 190:
            recommendations.append(
                "Soil organic matter improvement"
            )


    # --------------------------------------------------------
    # REMOVE DUPLICATES
    # --------------------------------------------------------

    recommendations = list(
        dict.fromkeys(recommendations)
    )

    drivers = list(
        dict.fromkeys(drivers)
    )


    # --------------------------------------------------------
    # FALLBACK
    # --------------------------------------------------------

    if not recommendations:

        recommendations.append(
            "Continue routine watershed monitoring"
        )


    if not drivers:

        drivers.append(
            "No dominant environmental pressure"
        )


    return (
        "; ".join(drivers),
        "; ".join(recommendations)
    )


# ============================================================
# APPLY ENGINE
# ============================================================

print("\nGenerating intervention recommendations...")

results = df.apply(
    generate_interventions,
    axis=1
)

df["risk_drivers"] = results.apply(
    lambda x: x[0]
)

df["recommended_interventions"] = results.apply(
    lambda x: x[1]
)


# ============================================================
# PRIORITY LEVEL
# ============================================================

def priority(score):

    if score >= 60:
        return "IMMEDIATE"

    elif score >= 50:
        return "HIGH"

    elif score >= 40:
        return "MODERATE"

    else:
        return "ROUTINE"


df["intervention_priority"] = (
    df["final_risk_score"]
    .apply(priority)
)


# ============================================================
# SAVE
# ============================================================

df.to_csv(
    OUTPUT,
    index=False
)


# ============================================================
# REPORT
# ============================================================

print("\n================================")
print("INTERVENTION ENGINE COMPLETE")
print("================================")

print("Output:", OUTPUT)

print("\nPriority distribution:")

print(
    df["intervention_priority"]
    .value_counts()
)

print("\nSample recommendations:")

print(
    df[
        [
            "id",
            "year",
            "month",
            "final_risk_score",
            "risk_category",
            "primary_risk_driver",
            "risk_drivers",
            "recommended_interventions",
            "intervention_priority"
        ]
    ]
    .head(10)
    .to_string(index=False)
)