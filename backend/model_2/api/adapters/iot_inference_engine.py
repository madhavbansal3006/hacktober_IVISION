from pathlib import Path
from typing import Dict, Optional, Any, List
import json
from datetime import datetime
import logging
import joblib
import numpy as np
import pandas as pd
from ..schemas import IoTReading, LiveRiskResult

logger = logging.getLogger(__name__)

class LiveIoTInferenceEngine:
    """
    Live Model 2 IoT Risk Inference Engine.
    Encapsulates the exact calibrated pipeline from scripts/24_iot_risk_engine.py:
    1. Historical Seasonal Baseline
    2. Real-time z-score & Sensor Disturbance scoring
    3. Isolation Forest ML Anomaly Inference
    4. Calibrated ML Adjustment & IoT Adjustment
    5. Compound Event Intelligence & Alert Level Classification
    """
    def __init__(self, backend_dir: Optional[Path] = None):
        if backend_dir is None:
            base_dir = Path(__file__).resolve().parents[4]  # repo root
            backend_dir = base_dir / "backend" / "model_2"
        self.backend_dir = Path(backend_dir)

        self.model_path = self.backend_dir / "models" / "model2_live_iot_isolation_forest.joblib"
        self.risk_input = self.backend_dir / "Data" / "processed" / "intervention_recommendations_v1.csv"
        self.feature_input = self.backend_dir / "Data" / "processed" / "model2_features_v6.csv"
        self.live_json_path = self.backend_dir / "Data" / "live" / "iot_live_data.json"
        self.output_csv_path = self.backend_dir / "Data" / "processed" / "iot_live_risk_output.csv"

        self.iso_forest = None
        self.scaler = None
        self.ml_features = []
        self.train_medians = None
        self.train_median = 0.0
        self.train_mad = 1.0

        self.risk_df = None
        self.features_df = None

        self.latest_reading: Optional[IoTReading] = None
        self.latest_result: Optional[LiveRiskResult] = None
        self.last_received_at: Optional[datetime] = None
        self.latest_by_watershed: Dict[str, LiveRiskResult] = {}
        self.latest_by_device: Dict[str, LiveRiskResult] = {}
        self.last_received_by_watershed: Dict[str, datetime] = {}
        self.stale_timeout_seconds: float = 35.0
        self.load()

    def load(self) -> None:
        # 1. Load ML Model Package
        if self.model_path.exists():
            try:
                pkg = joblib.load(self.model_path)
                self.iso_forest = pkg["model"]
                self.scaler = pkg["scaler"]
                self.ml_features = pkg["feature_names"]
                self.train_medians = pkg["train_medians"]
                self.train_median = pkg["train_median"]
                self.train_mad = pkg["train_mad"]
                if self.train_mad <= 0:
                    self.train_mad = 1.0
                logger.info(f"Loaded Isolation Forest live model ({len(self.ml_features)} features).")
            except Exception as e:
                logger.error(f"Failed loading Isolation Forest model: {e}")
        else:
            logger.warning(f"Model file not found at {self.model_path}")

        # 2. Load Historical Tables
        if self.risk_input.exists():
            try:
                self.risk_df = pd.read_csv(self.risk_input)
            except Exception as e:
                logger.error(f"Failed reading risk baseline: {e}")

        if self.feature_input.exists():
            try:
                self.features_df = pd.read_csv(self.feature_input)
            except Exception as e:
                logger.error(f"Failed reading feature baseline: {e}")

        # 3. Load latest saved telemetry if present
        if self.live_json_path.exists():
            try:
                with open(self.live_json_path, "r") as f:
                    saved_data = json.load(f)
                self.latest_reading = IoTReading(**saved_data)
                # Run inference on cached telemetry to populate latest_result
                if self.iso_forest is not None and self.risk_df is not None:
                    self.latest_result = self.infer(self.latest_reading, persist=False)
                    self.latest_result.source = "live"
                    # Initial state is marked stale until fresh live telemetry packet arrives
                    self.latest_result.is_stale = True
                    self.latest_result.connection_status = "OFFLINE / NO DATA"
                    self.latest_by_watershed[self.latest_result.id] = self.latest_result
                    if self.latest_result.device_id:
                        self.latest_by_device[self.latest_result.device_id] = self.latest_result
            except Exception as e:
                logger.warning(f"Could not load initial live telemetry: {e}")

    def infer(self, reading: IoTReading, persist: bool = True, mws_code: Optional[str] = None) -> LiveRiskResult:
        rainfall_val = float(reading.rainfall_mm_hr if reading.rainfall_mm_hr is not None else (reading.rainfall_mm if reading.rainfall_mm is not None else 0.0))
        rainfall_hr_val = float(reading.rainfall_mm_hr if reading.rainfall_mm_hr is not None else rainfall_val)
        device_id_val = reading.device_id or "ESP32_SHIGGAON_NODE_01"

        if self.iso_forest is None or self.risk_df is None or self.features_df is None:
            return LiveRiskResult(
                id=reading.id or "g_mws.240575",
                MWS=mws_code,
                device_id=device_id_val,
                year=reading.year or datetime.now().year,
                month=reading.month or datetime.now().month,
                timestamp=reading.timestamp or datetime.now().isoformat(),
                rainfall=rainfall_val,
                rainfall_mm=rainfall_val,
                rainfall_mm_hr=rainfall_hr_val,
                soil_moisture=float(reading.soil_moisture_pct),
                soil_moisture_pct=float(reading.soil_moisture_pct),
                water_level=float(reading.water_level_cm),
                water_level_cm=float(reading.water_level_cm),
                turbidity=float(reading.turbidity_ntu),
                turbidity_ntu=float(reading.turbidity_ntu),
                base_risk_score=0.0,
                rainfall_z_score=0.0,
                live_ml_anomaly_score=50.0,
                ml_anomaly_score=50.0,
                iot_disturbance_score=0.0,
                live_risk_score=0.0,
                live_risk_category="LOW",
                risk_category="LOW",
                live_risk_drivers="Model components unavailable",
                compound_event_detected=False,
                compound_event_type="No compound environmental event",
                event_classification="No compound environmental event",
                compound_alert_level="NORMAL",
                compound_alert="NORMAL",
                is_stale=False,
                connection_status="CONNECTED" if persist else "SIMULATION",
                source="live" if persist else "simulation",
                status="unavailable"
            )

        watershed_id = reading.id
        now = datetime.now()
        live_year = reading.year or now.year
        live_month = reading.month or now.month

        # Seasonal Risk Baseline
        watershed_risk = self.risk_df[self.risk_df["id"] == watershed_id]
        if watershed_risk.empty:
            logger.warning(f"Watershed {watershed_id} not in historical risk data.")
            base_risk = 50.0
        else:
            seasonal_risk = watershed_risk[watershed_risk["month"] == live_month]
            hist_seasonal_risk = seasonal_risk[seasonal_risk["year"] < live_year]
            if len(hist_seasonal_risk) < 3:
                hist_seasonal_risk = watershed_risk[watershed_risk["year"] < live_year]
            if not hist_seasonal_risk.empty:
                base_risk = float(hist_seasonal_risk["final_risk_score"].median())
            else:
                base_risk = float(watershed_risk["final_risk_score"].median())

        # Seasonal Feature Baseline
        watershed_features = self.features_df[self.features_df["id"] == watershed_id]
        if watershed_features.empty:
            historical_rainfall_mean = 100.0
            historical_rainfall_std = 50.0
            feature_baseline = pd.Series(dtype=float)
        else:
            seasonal_features = watershed_features[watershed_features["month"] == live_month]
            hist_seasonal = seasonal_features[seasonal_features["year"] < live_year]
            if len(hist_seasonal) < 3:
                hist_seasonal = seasonal_features if not seasonal_features.empty else watershed_features
            
            historical_rainfall_mean = float(hist_seasonal["rainfall_mm"].mean())
            historical_rainfall_std = float(hist_seasonal["rainfall_mm"].std())
            if pd.isna(historical_rainfall_std) or historical_rainfall_std <= 0:
                historical_rainfall_std = 1.0
            feature_baseline = hist_seasonal.median(numeric_only=True)

        # Rainfall Anomaly
        live_rainfall = float(reading.rainfall_mm)
        rainfall_z_score = (live_rainfall - historical_rainfall_mean) / historical_rainfall_std
        rainfall_anomaly_intensity = float(np.clip(max(rainfall_z_score, 0) / 3.0, 0, 1))

        # Sensor Intensities
        soil_saturation_intensity = float(np.clip((reading.soil_moisture_pct - 60) / 30, 0, 1))
        water_level_intensity = float(np.clip((reading.water_level_cm - 20) / 40, 0, 1))
        turbidity_intensity = float(np.clip((reading.turbidity_ntu - 100) / 900, 0, 1))

        # Live ML Feature Vector
        live_ml_dict = {}
        for feat in self.ml_features:
            if feat in feature_baseline.index:
                val = feature_baseline[feat]
            elif self.train_medians is not None and feat in self.train_medians.index:
                val = self.train_medians[feat]
            else:
                val = 0.0
            live_ml_dict[feat] = val

        if "rainfall_mm" in self.ml_features:
            live_ml_dict["rainfall_mm"] = live_rainfall
        if "rainfall_anomaly" in self.ml_features:
            live_ml_dict["rainfall_anomaly"] = rainfall_z_score

        live_ml_df = pd.DataFrame([[live_ml_dict[f] for f in self.ml_features]], columns=self.ml_features)
        for col in self.ml_features:
            live_ml_df[col] = pd.to_numeric(live_ml_df[col], errors="coerce")
        live_ml_df = live_ml_df.replace([np.inf, -np.inf], np.nan)
        if self.train_medians is not None:
            live_ml_df = live_ml_df.fillna(self.train_medians)
        live_ml_df = live_ml_df.fillna(0.0)

        # Scale & Predict Isolation Forest
        live_ml_scaled = self.scaler.transform(live_ml_df)
        live_ml_raw = float(-self.iso_forest.decision_function(live_ml_scaled)[0])
        live_ml_anomaly_score = float(np.clip(50.0 + 20.0 * ((live_ml_raw - self.train_median) / self.train_mad), 0.0, 100.0))

        # ML Adjustment (+/- 7 points max)
        ml_adjustment = ((live_ml_anomaly_score - 50.0) / 50.0) * 7.0

        # IoT Disturbance Score & Adjustment
        iot_disturbance_score = (
            0.35 * rainfall_anomaly_intensity
            + 0.30 * soil_saturation_intensity
            + 0.20 * water_level_intensity
            + 0.15 * turbidity_intensity
        )
        MAX_IOT_ADJUSTMENT = 15.0
        iot_adjustment = iot_disturbance_score * MAX_IOT_ADJUSTMENT

        # Final Live Risk
        live_risk_score = float(np.clip(base_risk + ml_adjustment + iot_adjustment, 0.0, 100.0))

        def classify_risk(score: float) -> str:
            if score < 40:
                return "LOW"
            elif score < 55:
                return "MODERATE"
            elif score < 70:
                return "HIGH"
            return "CRITICAL"

        live_risk_category = classify_risk(live_risk_score)

        # Drivers
        drivers = []
        if live_ml_anomaly_score >= 70:
            drivers.append("ML-detected environmental anomaly")
        if rainfall_anomaly_intensity >= 0.50:
            drivers.append("Extreme rainfall anomaly")
        if soil_saturation_intensity >= 0.50:
            drivers.append("High soil saturation")
        if water_level_intensity >= 0.50:
            drivers.append("Elevated water level")
        if turbidity_intensity >= 0.50:
            drivers.append("High sediment/turbidity")
        if not drivers:
            drivers.append("No significant live anomaly")
        live_risk_drivers = "; ".join(drivers)

        # Compound Event Intelligence
        extreme_signals = []
        if rainfall_anomaly_intensity >= 0.70:
            extreme_signals.append("Extreme rainfall")
        if soil_saturation_intensity >= 0.80:
            extreme_signals.append("Severe soil saturation")
        if water_level_intensity >= 0.80:
            extreme_signals.append("Dangerous water level")
        if turbidity_intensity >= 0.80:
            extreme_signals.append("Severe turbidity")

        extreme_count = len(extreme_signals)
        sig_count = sum([
            rainfall_anomaly_intensity >= 0.50,
            soil_saturation_intensity >= 0.50,
            water_level_intensity >= 0.50,
            turbidity_intensity >= 0.50
        ])

        compound_event_detected = False
        compound_event_type = "No compound environmental event"
        compound_alert_level = "NORMAL"
        recommended_action = "Continue routine monitoring"

        if sig_count >= 2:
            compound_event_detected = True
            compound_event_type = "Emerging compound hydrological disturbance"
            compound_alert_level = "WARNING"
            recommended_action = "Increase monitoring frequency and inspect the watershed for developing runoff conditions"

        if extreme_count >= 2:
            compound_event_detected = True
            compound_event_type = "Compound runoff and flood event"
            compound_alert_level = "HIGH ALERT"
            recommended_action = "Conduct field inspection and monitor downstream areas for possible flooding or erosion"

        if extreme_count >= 3:
            compound_event_detected = True
            compound_event_type = "Extreme compound runoff and flood event"
            compound_alert_level = "EMERGENCY"
            recommended_action = "Initiate immediate field verification, issue downstream warnings and activate emergency response protocols"

        timestamp_val = reading.timestamp or now.isoformat()
        source_val = "live" if persist else "simulation"

        device_id_val = reading.device_id or "ESP32_SHIGGAON_NODE_01"
        rainfall_val = float(reading.rainfall_mm_hr if reading.rainfall_mm_hr is not None else (reading.rainfall_mm if reading.rainfall_mm is not None else 0.0))
        rainfall_hr_val = float(reading.rainfall_mm_hr if reading.rainfall_mm_hr is not None else rainfall_val)

        result = LiveRiskResult(
            id=watershed_id,
            MWS=mws_code,
            device_id=device_id_val,
            year=live_year,
            month=live_month,
            timestamp=timestamp_val,
            rainfall=rainfall_val,
            rainfall_mm=rainfall_val,
            rainfall_mm_hr=rainfall_hr_val,
            soil_moisture=float(reading.soil_moisture_pct),
            soil_moisture_pct=float(reading.soil_moisture_pct),
            water_level=float(reading.water_level_cm),
            water_level_cm=float(reading.water_level_cm),
            turbidity=float(reading.turbidity_ntu),
            turbidity_ntu=float(reading.turbidity_ntu),
            ph=float(reading.ph) if reading.ph is not None else None,
            air_temperature_c=float(reading.air_temperature_c) if reading.air_temperature_c is not None else None,
            water_temperature_c=float(reading.water_temperature_c) if reading.water_temperature_c is not None else None,
            humidity_pct=float(reading.humidity_pct) if reading.humidity_pct is not None else None,
            base_risk_score=round(base_risk, 2),
            rainfall_z_score=round(rainfall_z_score, 2),
            live_ml_anomaly_score=round(live_ml_anomaly_score, 2),
            ml_anomaly_score=round(live_ml_anomaly_score, 2),
            iot_disturbance_score=round(iot_disturbance_score, 3),
            live_risk_score=round(live_risk_score, 2),
            live_risk_category=live_risk_category,
            risk_category=live_risk_category,
            live_risk_drivers=live_risk_drivers,
            compound_event_detected=compound_event_detected,
            compound_event_type=compound_event_type,
            event_classification=compound_event_type,
            compound_alert_level=compound_alert_level,
            compound_alert=compound_alert_level,
            recommended_action=recommended_action,
            is_stale=False,
            connection_status="CONNECTED" if persist else "SIMULATION",
            source=source_val,
            status="available"
        )

        if persist:
            self.latest_reading = reading
            self.latest_result = result
            self.last_received_at = datetime.now()
            self.latest_by_watershed[result.id] = result
            if mws_code:
                self.latest_by_watershed[mws_code] = result
            if result.device_id:
                self.latest_by_device[result.device_id] = result
            self.last_received_by_watershed[result.id] = self.last_received_at
            self._persist_data(reading, result)

        return result

    def _persist_data(self, reading: IoTReading, result: LiveRiskResult) -> None:
        try:
            self.live_json_path.parent.mkdir(parents=True, exist_ok=True)
            dump_data = reading.model_dump()
            dump_data["year"] = result.year
            dump_data["month"] = result.month
            dump_data["timestamp"] = result.timestamp
            with open(self.live_json_path, "w") as f:
                json.dump(dump_data, f, indent=4)

            # Also update/append to iot_live_risk_output.csv
            row_dict = {
                "id": result.id,
                "device_id": result.device_id,
                "year": result.year,
                "month": result.month,
                "timestamp": result.timestamp,
                "source": result.source,
                "base_risk_score": result.base_risk_score,
                "live_rainfall_mm": result.rainfall_mm,
                "rainfall_z_score": result.rainfall_z_score,
                "live_ml_anomaly_score": result.live_ml_anomaly_score,
                "iot_disturbance_score": result.iot_disturbance_score,
                "live_risk_score": result.live_risk_score,
                "live_risk_category": result.live_risk_category,
                "live_risk_drivers": result.live_risk_drivers,
                "compound_event_detected": result.compound_event_detected,
                "compound_event_type": result.compound_event_type,
                "compound_alert_level": result.compound_alert_level,
                "recommended_action": result.recommended_action,
            }
            pd.DataFrame([row_dict]).to_csv(self.output_csv_path, index=False)
        except Exception as e:
            logger.error(f"Failed persisting live IoT outputs: {e}")

    def get_latest(self, watershed_id: Optional[str] = None, device_id: Optional[str] = None) -> Optional[LiveRiskResult]:
        candidate: Optional[LiveRiskResult] = None
        if watershed_id:
            candidate = self.latest_by_watershed.get(watershed_id)
            if not candidate and self.latest_result and (self.latest_result.id == watershed_id or self.latest_result.MWS == watershed_id):
                candidate = self.latest_result
        elif device_id:
            candidate = self.latest_by_device.get(device_id)
            if not candidate and self.latest_result and self.latest_result.device_id == device_id:
                candidate = self.latest_result
        else:
            candidate = self.latest_result

        if candidate is None:
            return None

        # Check staleness based on elapsed time since last live telemetry ingestion
        if self.last_received_at is None:
            candidate.is_stale = True
            candidate.connection_status = "OFFLINE / NO DATA"
        else:
            elapsed = (datetime.now() - self.last_received_at).total_seconds()
            if elapsed > self.stale_timeout_seconds:
                candidate.is_stale = True
                candidate.connection_status = "OFFLINE / NO DATA"
            else:
                candidate.is_stale = False
                candidate.connection_status = "CONNECTED"

        return candidate

    def get_latest_reading(self) -> Optional[IoTReading]:
        return self.latest_reading
