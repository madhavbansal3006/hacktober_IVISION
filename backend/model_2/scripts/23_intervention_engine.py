import pandas as pd
from pathlib import Path


# ============================================================
# PATHS
# ============================================================

BASE_DIR = Path(__file__).resolve().parent.parent

INPUT_FILE = BASE_DIR / "data/processed/risk_assessment_v4.csv"

OUTPUT_FILE = (
    BASE_DIR
    / "data/processed/intervention_recommendations_v1.csv"
)


# ============================================================
# INTERVENTION KNOWLEDGE BASE
# ============================================================

INTERVENTIONS = {

    "Water Stress": {
        "primary_intervention":
            "Spring recharge and groundwater recharge structures",

        "secondary_intervention":
            "Rainwater harvesting and catchment restoration",

        "long_term_intervention":
            "Protect recharge zones and improve watershed vegetation",

        "iot_sensors":
            "Water level sensor; Soil moisture sensor; Rain gauge",

        "monitoring_focus":
            "Groundwater availability and recharge conditions"
    },

    "Flood/Runoff": {
        "primary_intervention":
            "Runoff control structures and check dams",

        "secondary_intervention":
            "Improve drainage channels and slope stabilization",

        "long_term_intervention":
            "Catchment restoration and vegetation-based erosion control",

        "iot_sensors":
            "Rain gauge; Water level sensor; Flow sensor",

        "monitoring_focus":
            "Rainfall intensity and stream water levels"
    },

    "Ecosystem Pressure": {
        "primary_intervention":
            "Catchment ecosystem restoration and vegetation recovery",

        "secondary_intervention":
            "Control land degradation and protect forest cover",

        "long_term_intervention":
            "Sustainable land-use management and afforestation",

        "iot_sensors":
            "Soil moisture sensor; Temperature and humidity sensor",

        "monitoring_focus":
            "Vegetation condition and soil moisture"
    }
}


# ============================================================
# PRIORITY ENGINE
# ============================================================

def determine_priority(row):

    risk = row["risk_category"]

    warning_count = sum([
        bool(row["flood_warning_signal"]),
        bool(row["water_stress_warning_signal"]),
        bool(row["ecosystem_warning_signal"])
    ])

    if risk == "CRITICAL":
        return "IMMEDIATE"

    if risk == "HIGH" and warning_count >= 1:
        return "URGENT"

    if risk == "HIGH":
        return "HIGH"

    if risk == "MODERATE" and warning_count >= 1:
        return "ELEVATED"

    return "ROUTINE"


# ============================================================
# RESPONSE TIME
# ============================================================

def determine_response_time(priority):

    response_times = {
        "IMMEDIATE": "Immediate action required",
        "URGENT": "Within 24 hours",
        "HIGH": "Within 7 days",
        "ELEVATED": "Within 30 days",
        "ROUTINE": "Regular monitoring"
    }

    return response_times[priority]


# ============================================================
# ALERT STATUS
# ============================================================

def determine_alert(row):

    if row["risk_category"] == "CRITICAL":
        return "CRITICAL ALERT"

    if (
        row["risk_category"] == "HIGH"
        and (
            row["flood_warning_signal"]
            or row["water_stress_warning_signal"]
            or row["ecosystem_warning_signal"]
        )
    ):
        return "HIGH PRIORITY ALERT"

    if (
        row["flood_warning_signal"]
        or row["water_stress_warning_signal"]
        or row["ecosystem_warning_signal"]
    ):
        return "EARLY WARNING"

    return "NO ACTIVE ALERT"


# ============================================================
# MAIN
# ============================================================

print("=" * 70)
print("MODEL 2 — INTERVENTION INTELLIGENCE ENGINE")
print("=" * 70)


# ------------------------------------------------------------
# LOAD DATA
# ------------------------------------------------------------

print("\nLoading Risk Engine V4 output...")

df = pd.read_csv(INPUT_FILE)

print(f"Rows: {len(df)}")
print(f"Watersheds: {df['id'].nunique()}")
print(
    f"Years: {df['year'].min()}–{df['year'].max()}"
)


# ------------------------------------------------------------
# VALIDATE DRIVERS
# ------------------------------------------------------------

print("\nValidating primary risk drivers...")

available_drivers = df["primary_risk_driver"].unique()

print(
    "Drivers found:",
    list(available_drivers)
)


# ------------------------------------------------------------
# ADD INTERVENTION INFORMATION
# ------------------------------------------------------------

print("\nGenerating intervention recommendations...")

df["primary_intervention"] = (
    df["primary_risk_driver"]
    .map(lambda x: INTERVENTIONS[x]["primary_intervention"])
)

df["secondary_intervention"] = (
    df["primary_risk_driver"]
    .map(lambda x: INTERVENTIONS[x]["secondary_intervention"])
)

df["long_term_intervention"] = (
    df["primary_risk_driver"]
    .map(lambda x: INTERVENTIONS[x]["long_term_intervention"])
)

df["recommended_iot_sensors"] = (
    df["primary_risk_driver"]
    .map(lambda x: INTERVENTIONS[x]["iot_sensors"])
)

df["monitoring_focus"] = (
    df["primary_risk_driver"]
    .map(lambda x: INTERVENTIONS[x]["monitoring_focus"])
)


# ------------------------------------------------------------
# PRIORITY
# ------------------------------------------------------------

print("Calculating intervention priorities...")

df["intervention_priority"] = (
    df.apply(determine_priority, axis=1)
)

df["recommended_response_time"] = (
    df["intervention_priority"]
    .map(determine_response_time)
)


# ------------------------------------------------------------
# ALERTS
# ------------------------------------------------------------

print("Generating alert status...")

df["alert_status"] = (
    df.apply(determine_alert, axis=1)
)


# ------------------------------------------------------------
# DATA CONFIDENCE NOTE
# ------------------------------------------------------------

def confidence_note(row):

    if row["data_confidence"] == "VERY LOW":
        return (
            "Field verification recommended before major intervention"
        )

    if row["data_confidence"] == "LOW":
        return (
            "Use satellite risk assessment with additional field monitoring"
        )

    return (
        "Data confidence sufficient for decision support"
    )


df["decision_confidence_note"] = (
    df.apply(confidence_note, axis=1)
)


# ------------------------------------------------------------
# SUMMARY
# ------------------------------------------------------------

print("\n" + "=" * 70)
print("INTERVENTION SUMMARY")
print("=" * 70)

print("\nIntervention priorities:")

print(
    df["intervention_priority"]
    .value_counts()
    .to_string()
)


print("\nAlert status:")

print(
    df["alert_status"]
    .value_counts()
    .to_string()
)


print("\nPrimary interventions:")

print(
    df["primary_intervention"]
    .value_counts()
    .to_string()
)


print("\nIoT monitoring recommendations:")

print(
    df["recommended_iot_sensors"]
    .value_counts()
    .to_string()
)


# ------------------------------------------------------------
# SAVE
# ------------------------------------------------------------

OUTPUT_FILE.parent.mkdir(
    parents=True,
    exist_ok=True
)

df.to_csv(
    OUTPUT_FILE,
    index=False
)


# ============================================================
# COMPLETE
# ============================================================

print("\n" + "=" * 70)
print("INTERVENTION INTELLIGENCE ENGINE COMPLETE")
print("=" * 70)

print(f"\nOutput: {OUTPUT_FILE}")

print(f"Rows: {len(df)}")
print(f"Columns: {len(df.columns)}")

print("\nNew intelligence layers:")

new_columns = [
    "primary_intervention",
    "secondary_intervention",
    "long_term_intervention",
    "recommended_iot_sensors",
    "monitoring_focus",
    "intervention_priority",
    "recommended_response_time",
    "alert_status",
    "decision_confidence_note"
]

for column in new_columns:
    print(f"  ✓ {column}")


print("\n✓ Risk Engine V4 was NOT modified.")
print("✓ Intervention recommendations generated separately.")
print("✓ Output is ready for IoT and dashboard integration.")