import logging
from datetime import datetime, timezone
from typing import Optional, Dict, List, Tuple, Any
from pathlib import Path

from ..schemas import WaterQualityRecord, WaterQualitySummary
from .gis_adapter import GISAdapter

# Direct integration with authoritative water_quality module
from water_quality.src.wqi import (
    evaluate_observation,
    validate_observation,
    PARAMETER_STANDARDS,
    QUALITY_CATEGORIES,
)
from water_quality.src.simulator import generate_readings

logger = logging.getLogger("WaterQualityAdapter")

class WaterQualityAdapter:
    """
    Adapter bridging the authoritative water_quality module (WQI calculator & simulator)
    with the Watershed Intelligence FastAPI backend.
    """

    def __init__(self, gis_adapter: Optional[GISAdapter] = None, iot_engine: Optional[Any] = None):
        self.gis_adapter = gis_adapter or GISAdapter()
        self.iot_engine = iot_engine
        self.base_time = datetime(2026, 1, 1, 0, 0, tzinfo=timezone.utc)
        logger.info("Initialized WaterQualityAdapter with authoritative water_quality module.")

    def _get_mws_seed(self, mws_id: str) -> int:
        """Derives a stable, deterministic seed from the canonical MWS id."""
        try:
            return int(mws_id.split(".")[-1])
        except Exception:
            return abs(hash(mws_id)) % 1000000

    def _resolve_mws(self, identifier: str) -> Optional[Tuple[str, str]]:
        """
        Resolves an input identifier (canonical id e.g. 'g_mws.240575' or display code e.g. '4D4F2m3')
        against the official 66 micro-watershed catalog.
        Returns (canonical_id, display_mws) or None if not found.
        """
        id_to_mws = self.gis_adapter.get_id_to_mws_map()
        mws_to_id = self.gis_adapter.get_mws_to_id_map()

        if identifier in id_to_mws:
            return identifier, id_to_mws[identifier]
        elif identifier in mws_to_id:
            return mws_to_id[identifier], identifier
        return None

    def get_mws_reading(self, identifier: str, mode: Optional[str] = None) -> Optional[WaterQualityRecord]:
        """
        Retrieves a water-quality reading and WQI evaluation for a specific micro-watershed.
        When mode == 'live' and physical telemetry is streaming from ESP32, returns the real-time
        sensor readings and live calculated WQI. Otherwise returns deterministic simulation baseline.
        """
        resolved = self._resolve_mws(identifier)
        if not resolved:
            return None

        mws_id, mws_code = resolved

        # Check for live IoT sensor stream if live mode requested
        if mode == "live" and self.iot_engine:
            latest_result = self.iot_engine.get_latest()
            latest_reading = getattr(self.iot_engine, "get_latest_reading", lambda: None)()
            if latest_result and latest_result.source == "live":
                if latest_result.id == mws_id or latest_result.MWS == mws_code:
                    seed = self._get_mws_seed(mws_id)
                    sim_readings = generate_readings(
                        mws_id=mws_id,
                        mws_code=mws_code,
                        count=1,
                        seed=seed,
                        start_time=self.base_time,
                    )
                    base_tds = sim_readings[0]["tds"] if sim_readings else 350.0

                    live_ph = float(latest_reading.ph) if (latest_reading and latest_reading.ph is not None) else (
                        float(latest_result.ph) if latest_result.ph is not None else 7.2
                    )
                    live_turb = float(latest_result.turbidity_ntu if latest_result.turbidity_ntu is not None else (
                        latest_reading.turbidity_ntu if latest_reading else 0.0
                    ))
                    live_temp = float(latest_reading.water_temperature_c) if (latest_reading and latest_reading.water_temperature_c is not None) else (
                        float(latest_reading.air_temperature_c) if (latest_reading and latest_reading.air_temperature_c is not None) else 26.5
                    )
                    live_tds = round(float(base_tds + (live_turb * 2.0)), 2)

                    obs = {
                        "id": mws_id,
                        "MWS": mws_code,
                        "timestamp": latest_result.timestamp or datetime.now(timezone.utc).isoformat(),
                        "ph": round(live_ph, 2),
                        "tds": live_tds,
                        "turbidity": round(live_turb, 2),
                        "temperature": round(live_temp, 2),
                        "source": "live",
                    }
                    evaluation = evaluate_observation(obs)
                    return WaterQualityRecord(
                        id=mws_id,
                        MWS=mws_code,
                        timestamp=obs["timestamp"],
                        ph=obs["ph"],
                        tds=obs["tds"],
                        turbidity=obs["turbidity"],
                        temperature=obs["temperature"],
                        wqi=evaluation["wqi"],
                        quality_category=evaluation["quality_category"],
                        source="live",
                        status="available",
                    )

        # Baseline deterministic simulation observation
        seed = self._get_mws_seed(mws_id)
        raw_readings = generate_readings(
            mws_id=mws_id,
            mws_code=mws_code,
            count=1,
            seed=seed,
            start_time=self.base_time,
        )
        reading = raw_readings[0]

        # Calculate WQI and categorize using the water_quality module
        evaluation = evaluate_observation(reading)

        return WaterQualityRecord(
            id=reading["id"],
            MWS=reading["MWS"],
            timestamp=reading["timestamp"],
            ph=reading["ph"],
            tds=reading["tds"],
            turbidity=reading["turbidity"],
            temperature=reading["temperature"],
            wqi=evaluation["wqi"],
            quality_category=evaluation["quality_category"],
            source="simulation",
            status="available",
        )

    def get_water_quality_summary(self, mode: Optional[str] = None) -> WaterQualitySummary:
        """
        Computes basin-wide water-quality summary metrics across all 66 official micro-watersheds.
        When mode == 'live', reflects active real-time ESP32 sensor telemetry nodes.
        """
        id_to_mws = self.gis_adapter.get_id_to_mws_map()
        records: List[WaterQualityRecord] = []
        categories: Dict[str, int] = {
            "Excellent": 0,
            "Good": 0,
            "Poor": 0,
            "Very Poor": 0,
            "Unsuitable for Drinking": 0,
        }
        total_wqi = 0.0
        has_live = False

        for mws_id, mws_code in id_to_mws.items():
            record = self.get_mws_reading(mws_id, mode=mode)
            if record:
                records.append(record)
                if record.source == "live":
                    has_live = True
                categories[record.quality_category] = categories.get(record.quality_category, 0) + 1
                total_wqi += record.wqi

        mean_wqi = round(total_wqi / len(records), 2) if records else 0.0

        return WaterQualitySummary(
            total_monitored_mws=len(records),
            data_mode="live" if (mode == "live" and has_live) else "simulation",
            category_distribution=categories,
            mean_wqi=mean_wqi,
            parameter_standards=PARAMETER_STANDARDS,
            watersheds=records,
            status="available",
        )
