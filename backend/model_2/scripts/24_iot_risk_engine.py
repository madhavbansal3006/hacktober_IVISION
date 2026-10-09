import pandas as pd
import numpy as np
from pathlib import Path
import json
import joblib


# ============================================================
# MODEL 2 — LIVE IoT + ML RISK ENGINE
# ============================================================
#
# ARCHITECTURE
#
# Historical Watershed Data
#           ↓
# Seasonal Model 2 Baseline
#           ↓
# Live IoT Sensor Data
#           ↓
# Historical Feature Reconstruction
#           ↓
# Isolation Forest ML Inference
#           ↓
# ML Anomaly Adjustment
#           ↓
# Live IoT Adjustment
#           ↓
# Final Live Risk
#           ↓
# Compound Event Intelligence
#           ↓
# Operational Alert
#
# ============================================================


# ============================================================
# PATH CONFIGURATION
# ============================================================

BASE_DIR = Path(__file__).resolve().parents[1]


RISK_INPUT = (
    BASE_DIR
    / "data"
    / "processed"
    / "intervention_recommendations_v1.csv"
)


FEATURE_INPUT = (
    BASE_DIR
    / "data"
    / "processed"
    / "model2_features_v6.csv"
)


IOT_INPUT = (
    BASE_DIR
    / "data"
    / "live"
    / "iot_live_data.json"
)


ML_MODEL_PATH = (
    BASE_DIR
    / "models"
    / "model2_live_iot_isolation_forest.joblib"
)


OUTPUT = (
    BASE_DIR
    / "data"
    / "processed"
    / "iot_live_risk_output.csv"
)


# ============================================================
# START
# ============================================================

print("=" * 70)
print("MODEL 2 — LIVE IoT + ML RISK ENGINE")
print("=" * 70)


# ============================================================
# 1. LOAD TRAINED ML MODEL
# ============================================================

print("\nLoading trained Isolation Forest model...")


if not ML_MODEL_PATH.exists():

    raise FileNotFoundError(
        f"Live ML model not found: {ML_MODEL_PATH}"
    )


ml_package = joblib.load(
    ML_MODEL_PATH
)


# IMPORTANT:
# These keys match your exported model package.

iso_forest = ml_package[
    "model"
]


scaler = ml_package[
    "scaler"
]


ML_FEATURES = ml_package[
    "feature_names"
]


train_medians = ml_package[
    "train_medians"
]


train_median = ml_package[
    "train_median"
]


train_mad = ml_package[
    "train_mad"
]


print("✓ Isolation Forest loaded successfully.")
print(f"✓ ML features: {len(ML_FEATURES)}")


# ============================================================
# 2. LOAD HISTORICAL MODEL DATA
# ============================================================

print("\nLoading Model 2 historical data...")


risk_df = pd.read_csv(
    RISK_INPUT
)


features_df = pd.read_csv(
    FEATURE_INPUT
)


print(
    f"Risk records: {len(risk_df)}"
)


print(
    f"Feature records: {len(features_df)}"
)


print(
    f"Watersheds: "
    f"{risk_df['id'].nunique()}"
)


# ============================================================
# 3. LOAD LIVE IoT DATA
# ============================================================

print("\nLoading live IoT data...")


if not IOT_INPUT.exists():

    raise FileNotFoundError(
        f"IoT data file not found: {IOT_INPUT}"
    )


with open(
    IOT_INPUT,
    "r"
) as file:

    iot_data = json.load(
        file
    )


print("✓ Live IoT data loaded successfully.")


# ============================================================
# REQUIRED IoT FIELDS
# ============================================================

REQUIRED_FIELDS = [

    "id",
    "year",
    "month",
    "rainfall_mm",
    "soil_moisture_pct",
    "water_level_cm",
    "turbidity_ntu",
    "air_temperature_c",
    "humidity_pct",
    "water_temperature_c",
    "ph"

]


missing_fields = [

    field

    for field in REQUIRED_FIELDS

    if field not in iot_data

]


if missing_fields:

    raise ValueError(

        "Missing required IoT fields: "

        + ", ".join(
            missing_fields
        )

    )


print("\nLive IoT node:")


for key, value in iot_data.items():

    print(
        f"{key}: {value}"
    )


# ============================================================
# 4. GET LIVE LOCATION AND TIME
# ============================================================

watershed_id = iot_data["id"]


live_year = int(
    iot_data["year"]
)


live_month = int(
    iot_data["month"]
)


# ============================================================
# 5. GET SEASONAL MODEL 2 BASELINE
# ============================================================

watershed_risk = risk_df[

    risk_df["id"]
    == watershed_id

].copy()


if watershed_risk.empty:

    raise ValueError(

        f"Watershed {watershed_id} "
        f"not found in risk data."
    )


seasonal_risk = watershed_risk[

    watershed_risk["month"]
    == live_month

].copy()


historical_seasonal_risk = seasonal_risk[

    seasonal_risk["year"]
    < live_year

].copy()


# Fallback

if len(
    historical_seasonal_risk
) < 3:

    print(
        "\nWARNING: Insufficient same-month "
        "historical records."
    )


    print(
        "Falling back to watershed-wide "
        "historical baseline."
    )


    historical_seasonal_risk = watershed_risk[

        watershed_risk["year"]
        < live_year

    ].copy()


if historical_seasonal_risk.empty:

    raise ValueError(

        f"No historical risk records found "
        f"for watershed {watershed_id}."
    )


# ============================================================
# CALCULATE BASELINE
# ============================================================

base_risk = float(

    historical_seasonal_risk[
        "final_risk_score"
    ].median()

)


baseline_mean = float(

    historical_seasonal_risk[
        "final_risk_score"
    ].mean()

)


baseline_std = float(

    historical_seasonal_risk[
        "final_risk_score"
    ].std()

)


if pd.isna(
    baseline_std
):

    baseline_std = 0.0


baseline_records = len(
    historical_seasonal_risk
)


# ============================================================
# REPORT BASELINE
# ============================================================

print("\n" + "=" * 70)
print("SEASONAL MODEL 2 BASELINE")
print("=" * 70)


print(
    f"Watershed: {watershed_id}"
)


print(
    f"Live period: "
    f"{live_year}-{live_month:02d}"
)


print(
    f"Historical records used: "
    f"{baseline_records}"
)


print(
    f"Seasonal Mean Risk: "
    f"{baseline_mean:.2f}"
)


print(
    f"Seasonal Median Risk: "
    f"{base_risk:.2f}"
)


# ============================================================
# 6. GET HISTORICAL WATERSHED FEATURES
# ============================================================

watershed_features = features_df[

    features_df["id"]
    == watershed_id

].copy()


if watershed_features.empty:

    raise ValueError(

        f"No historical feature data found "
        f"for watershed {watershed_id}."
    )


# ============================================================
# 7. GET SEASONAL FEATURE BASELINE
# ============================================================

seasonal_features = watershed_features[

    watershed_features["month"]
    == live_month

].copy()


historical_seasonal = seasonal_features[

    seasonal_features["year"]
    < live_year

].copy()


# Fallback hierarchy

if len(
    historical_seasonal
) < 3:

    historical_seasonal = seasonal_features.copy()


if historical_seasonal.empty:

    historical_seasonal = watershed_features.copy()


# ============================================================
# HISTORICAL RAINFALL STATISTICS
# ============================================================

historical_rainfall_mean = float(

    historical_seasonal[
        "rainfall_mm"
    ].mean()

)


historical_rainfall_std = float(

    historical_seasonal[
        "rainfall_mm"
    ].std()

)


if (

    pd.isna(
        historical_rainfall_std
    )

    or

    historical_rainfall_std <= 0

):

    historical_rainfall_std = 1.0


# ============================================================
# 8. LIVE RAINFALL ANALYSIS
# ============================================================

live_rainfall = float(

    iot_data["rainfall_mm"]
)


rainfall_z_score = (

    live_rainfall
    -
    historical_rainfall_mean

) / historical_rainfall_std


rainfall_anomaly_intensity = np.clip(

    max(
        rainfall_z_score,
        0
    ) / 3.0,

    0,
    1

)


# ============================================================
# 9. LIVE SENSOR INTENSITIES
# ============================================================

soil_moisture = float(

    iot_data[
        "soil_moisture_pct"
    ]

)


soil_saturation_intensity = np.clip(

    (
        soil_moisture
        - 60
    ) / 30,

    0,
    1

)


water_level = float(

    iot_data[
        "water_level_cm"
    ]

)


water_level_intensity = np.clip(

    (
        water_level
        - 20
    ) / 40,

    0,
    1

)


turbidity = float(

    iot_data[
        "turbidity_ntu"
    ]

)


turbidity_intensity = np.clip(

    (
        turbidity
        - 100
    ) / 900,

    0,
    1

)


# ============================================================
# 10. BUILD LIVE ML FEATURE VECTOR
# ============================================================

print("\nBuilding live ML feature vector...")


# Seasonal median provides the historical context
# for static and unavailable real-time features.

feature_baseline = (

    historical_seasonal
    .median(
        numeric_only=True
    )

)


live_ml_features = {}


for feature in ML_FEATURES:

    # Prefer watershed seasonal historical values

    if feature in feature_baseline.index:

        value = feature_baseline[
            feature
        ]

    # Otherwise use the training median

    elif feature in train_medians.index:

        value = train_medians[
            feature
        ]

    else:

        value = 0


    live_ml_features[
        feature
    ] = value


# ============================================================
# OVERRIDE FEATURES WITH LIVE DATA
# ============================================================


# Live rainfall

if "rainfall_mm" in ML_FEATURES:

    live_ml_features[
        "rainfall_mm"
    ] = live_rainfall


# Live rainfall anomaly

if "rainfall_anomaly" in ML_FEATURES:

    live_ml_features[
        "rainfall_anomaly"
    ] = rainfall_z_score


# ============================================================
# CREATE ML DATAFRAME
# ============================================================

live_ml_df = pd.DataFrame(

    [[

        live_ml_features[
            feature
        ]

        for feature in ML_FEATURES

    ]],

    columns=ML_FEATURES

)


# ============================================================
# CLEAN ML INPUT
# ============================================================

for column in ML_FEATURES:

    live_ml_df[
        column
    ] = pd.to_numeric(

        live_ml_df[
            column
        ],

        errors="coerce"

    )


live_ml_df = live_ml_df.replace(

    [np.inf, -np.inf],

    np.nan

)


# Make sure medians align properly
# with the ML feature columns.

median_values = {

    feature:

    train_medians[
        feature
    ]

    if feature in train_medians.index

    else 0

    for feature in ML_FEATURES

}


live_ml_df = live_ml_df.fillna(

    pd.Series(
        median_values
    )

)


live_ml_df = live_ml_df.fillna(
    0
)


# ============================================================
# 11. SCALE LIVE ML FEATURES
# ============================================================

live_ml_scaled = scaler.transform(

    live_ml_df

)


# ============================================================
# 12. ISOLATION FOREST INFERENCE
# ============================================================

print(
    "Running Isolation Forest inference..."
)


live_ml_raw = float(

    -iso_forest.decision_function(

        live_ml_scaled

    )[0]

)


# ============================================================
# NORMALIZE ML ANOMALY SCORE
# ============================================================

if train_mad <= 0:

    train_mad = 1.0


live_ml_anomaly_score = (

    50

    +

    20

    *

    (

        (
            live_ml_raw
            -
            train_median
        )

        /

        train_mad

    )

)


live_ml_anomaly_score = float(

    np.clip(

        live_ml_anomaly_score,

        0,

        100

    )

)


# ============================================================
# ML ADJUSTMENT
# ============================================================
#
# Same calibrated logic as Risk Engine V4.
#
# ML Score = 50 → neutral
# ML Score > 50 → positive risk adjustment
# ML Score < 50 → negative risk adjustment
#
# Maximum = ±7 points
#
# ============================================================

ml_adjustment = (

    (
        live_ml_anomaly_score
        - 50
    )

    / 50

    * 7

)


print(
    f"Live ML anomaly score: "
    f"{live_ml_anomaly_score:.2f}"
)


print(
    f"ML risk adjustment: "
    f"{ml_adjustment:+.2f}"
)


# ============================================================
# 13. IoT DISTURBANCE SCORE
# ============================================================

iot_disturbance_score = (

    0.35
    *
    rainfall_anomaly_intensity

    +

    0.30
    *
    soil_saturation_intensity

    +

    0.20
    *
    water_level_intensity

    +

    0.15
    *
    turbidity_intensity

)


# ============================================================
# 14. BOUNDED IoT ADJUSTMENT
# ============================================================

MAX_IOT_ADJUSTMENT = 15


iot_adjustment = (

    iot_disturbance_score
    *
    MAX_IOT_ADJUSTMENT

)


# ============================================================
# 15. FINAL LIVE RISK SCORE
# ============================================================
#
# Seasonal Model 2 Baseline
#            +
# Isolation Forest Adjustment
#            +
# Live IoT Adjustment
#
# ============================================================

live_risk_score = np.clip(

    base_risk

    +

    ml_adjustment

    +

    iot_adjustment,

    0,

    100

)


# ============================================================
# 16. RISK CATEGORY
# ============================================================

def classify_risk(score):

    if score < 40:

        return "LOW"

    elif score < 55:

        return "MODERATE"

    elif score < 70:

        return "HIGH"

    return "CRITICAL"


live_risk_category = classify_risk(

    live_risk_score

)


# ============================================================
# 17. IDENTIFY LIVE RISK DRIVERS
# ============================================================

live_drivers = []


if live_ml_anomaly_score >= 70:

    live_drivers.append(

        "ML-detected environmental anomaly"

    )


if rainfall_anomaly_intensity >= 0.50:

    live_drivers.append(

        "Extreme rainfall anomaly"

    )


if soil_saturation_intensity >= 0.50:

    live_drivers.append(

        "High soil saturation"

    )


if water_level_intensity >= 0.50:

    live_drivers.append(

        "Elevated water level"

    )


if turbidity_intensity >= 0.50:

    live_drivers.append(

        "High sediment/turbidity"

    )


if not live_drivers:

    live_drivers.append(

        "No significant live anomaly"

    )


# ============================================================
# 18. COMPOUND EVENT INTELLIGENCE
# ============================================================

extreme_signals = []


if rainfall_anomaly_intensity >= 0.70:

    extreme_signals.append(

        "Extreme rainfall"

    )


if soil_saturation_intensity >= 0.80:

    extreme_signals.append(

        "Severe soil saturation"

    )


if water_level_intensity >= 0.80:

    extreme_signals.append(

        "Dangerous water level"

    )


if turbidity_intensity >= 0.80:

    extreme_signals.append(

        "Severe turbidity"

    )


extreme_signal_count = len(
    extreme_signals
)


significant_signal_count = sum([

    rainfall_anomaly_intensity >= 0.50,

    soil_saturation_intensity >= 0.50,

    water_level_intensity >= 0.50,

    turbidity_intensity >= 0.50

])


compound_event_detected = False


compound_event_type = (

    "No compound environmental event"

)


compound_alert_level = (

    "NORMAL"

)


recommended_action = (

    "Continue routine monitoring"

)


# ============================================================
# LEVEL 1 — WARNING
# ============================================================

if significant_signal_count >= 2:

    compound_event_detected = True

    compound_event_type = (

        "Emerging compound hydrological disturbance"

    )

    compound_alert_level = (

        "WARNING"

    )

    recommended_action = (

        "Increase monitoring frequency and inspect "
        "the watershed for developing runoff conditions"

    )


# ============================================================
# LEVEL 2 — HIGH ALERT
# ============================================================

if extreme_signal_count >= 2:

    compound_event_detected = True

    compound_event_type = (

        "Compound runoff and flood event"

    )

    compound_alert_level = (

        "HIGH ALERT"

    )

    recommended_action = (

        "Conduct field inspection and monitor downstream "
        "areas for possible flooding or erosion"

    )


# ============================================================
# LEVEL 3 — EMERGENCY
# ============================================================

if extreme_signal_count >= 3:

    compound_event_detected = True

    compound_event_type = (

        "Extreme compound runoff and flood event"

    )

    compound_alert_level = (

        "EMERGENCY"

    )

    recommended_action = (

        "Initiate immediate field verification, issue "
        "downstream warnings and activate emergency "
        "response protocols"

    )


# ============================================================
# 19. CREATE OUTPUT
# ============================================================

output_data = {


    # LOCATION

    "id":

        watershed_id,


    "year":

        live_year,


    "month":

        live_month,


    # MODEL 2 BASELINE

    "base_risk_score":

        base_risk,


    "seasonal_mean_risk":

        baseline_mean,


    "seasonal_risk_std":

        baseline_std,


    "historical_baseline_records":

        baseline_records,


    # RAINFALL

    "historical_rainfall_mean":

        historical_rainfall_mean,


    "historical_rainfall_std":

        historical_rainfall_std,


    "live_rainfall_mm":

        live_rainfall,


    "rainfall_z_score":

        rainfall_z_score,


    # ML

    "live_ml_raw_score":

        live_ml_raw,


    "live_ml_anomaly_score":

        live_ml_anomaly_score,


    "ml_adjustment":

        ml_adjustment,


    # IoT SENSOR INTENSITIES

    "rainfall_anomaly_intensity":

        rainfall_anomaly_intensity,


    "soil_saturation_intensity":

        soil_saturation_intensity,


    "water_level_intensity":

        water_level_intensity,


    "turbidity_intensity":

        turbidity_intensity,


    # IoT

    "iot_disturbance_score":

        iot_disturbance_score,


    "iot_adjustment":

        iot_adjustment,


    # FINAL RISK

    "live_risk_score":

        live_risk_score,


    "live_risk_category":

        live_risk_category,


    "live_risk_drivers":

        "; ".join(
            live_drivers
        ),


    # COMPOUND EVENTS

    "compound_event_detected":

        compound_event_detected,


    "compound_event_type":

        compound_event_type,


    "compound_alert_level":

        compound_alert_level,


    "recommended_action":

        recommended_action,


    "extreme_signal_count":

        extreme_signal_count,


    "significant_signal_count":

        significant_signal_count

}


# ============================================================
# 20. SAVE OUTPUT
# ============================================================

output_df = pd.DataFrame(

    [output_data]

)


OUTPUT.parent.mkdir(

    parents=True,

    exist_ok=True

)


output_df.to_csv(

    OUTPUT,

    index=False

)


# ============================================================
# 21. FINAL REPORT
# ============================================================

print("\n" + "=" * 70)
print("LIVE MACHINE LEARNING INFERENCE")
print("=" * 70)


print(
    f"\nML anomaly score: "
    f"{live_ml_anomaly_score:.2f}"
)


print(
    f"ML adjustment: "
    f"{ml_adjustment:+.2f}"
)


print("\n" + "=" * 70)
print("LIVE IoT + ML RISK ANALYSIS")
print("=" * 70)


print(
    f"\nSeasonal Model 2 Baseline: "
    f"{base_risk:.2f}"
)


print(
    f"ML Adjustment: "
    f"{ml_adjustment:+.2f}"
)


print(
    f"IoT Adjustment: "
    f"{iot_adjustment:+.2f}"
)


print(
    f"\nFINAL LIVE RISK SCORE: "
    f"{live_risk_score:.2f}"
)


print(
    f"RISK CATEGORY: "
    f"{live_risk_category}"
)


print("\nLIVE DRIVERS:")


for driver in live_drivers:

    print(
        f"• {driver}"
    )


print("\n" + "=" * 70)
print("COMPOUND EVENT INTELLIGENCE")
print("=" * 70)


print(
    f"\nCompound Event Detected: "
    f"{compound_event_detected}"
)


print(
    f"Event Type: "
    f"{compound_event_type}"
)


print(
    f"Alert Level: "
    f"{compound_alert_level}"
)


print(
    f"Recommended Action: "
    f"{recommended_action}"
)


print("\n" + "=" * 70)
print("LIVE IoT + ML RISK ENGINE COMPLETE")
print("=" * 70)


print(
    f"\nOutput saved to:\n{OUTPUT}"
)