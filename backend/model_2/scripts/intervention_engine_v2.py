import pandas as pd
from pathlib import Path

BASE = Path(__file__).resolve().parents[1]

INPUT = BASE / "data/processed/risk_assessment_v2.csv"
OUTPUT = BASE / "data/processed/watershed_intelligence_v2.csv"

print("================================")
print("INTERVENTION ENGINE V2")
print("================================")

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

    if row["water_stress_score"] >= 55:

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

    if row["flood_risk_score"] >= 55:

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

    if row["ecosystem_risk_score"] >= 55:

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
    # IF PRIMARY DRIVER EXISTS BUT DID NOT CROSS TRIGGER
    # --------------------------------------------------------

    primary_driver = row["primary_risk_driver"]

    if not drivers:

        # Give a lower-priority monitoring recommendation
        if primary_driver == "Water Stress":
            recommendations.append(
                "Monitor rainfall, NDVI and soil moisture"
            )
            drivers.append(
                "Emerging water-stress signal"
            )

        elif primary_driver == "Flood/Runoff":
            recommendations.append(
                "Monitor rainfall and drainage conditions"
            )
            drivers.append(
                "Emerging flood/runoff signal"
            )

        elif primary_driver == "Ecosystem Pressure":
            recommendations.append(
                "Monitor vegetation and land-use changes"
            )
            drivers.append(
                "Emerging ecosystem-pressure signal"
            )


    # --------------------------------------------------------
    # FINAL FALLBACK
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
# APPLY
# ============================================================

print("\nGenerating recommendations...")

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
# PRIORITY
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
print("INTERVENTION ENGINE V2 COMPLETE")
print("================================")

print("Output:", OUTPUT)

print("\nPriority distribution:")
print(
    df["intervention_priority"]
    .value_counts()
)

print("\nDriver distribution:")
print(
    df["risk_drivers"]
    .value_counts()
    .head(10)
)

print("\nSample:")
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