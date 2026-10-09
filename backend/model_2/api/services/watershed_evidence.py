"""
Watershed Evidence Retrieval Service for Ask JalDrishti.

Retrieves real, verified evidence for a micro-watershed from existing adapters:
- GIS Adapter (spatial boundaries, area)
- Model 2 Risk Engine V4 (official risk score, risk components, interventions, terrain/climate features)
- Model 1 Sentinel-2 Classifier (LULC statistics, coverage)
- Water Quality Adapter (explicitly marked as simulation)
- Geo-Coded Pipeline (observed field photos)

Strict adherence to JalDrishti principles:
- Never invents missing values.
- Never silently replaces missing values with zero.
- Preserves exact source, unit, metric label, and provenance.
- Discloses missing data and low coverage.
- Strictly separates observed vs model-derived vs simulated telemetry.
"""

from typing import Dict, Any, Optional, List, Tuple
import logging
from ..schemas import EvidenceItemRecord

logger = logging.getLogger(__name__)

class WatershedEvidenceBundle:
    def __init__(
        self,
        mws_id: str,
        mws_code: str,
        items: List[EvidenceItemRecord],
        disclosed_gaps: List[str]
    ):
        self.mws_id = mws_id
        self.mws_code = mws_code
        self.items = items
        self.disclosed_gaps = disclosed_gaps
        self._item_map: Dict[str, EvidenceItemRecord] = {item.id: item for item in items}

    def get(self, item_id: str) -> Optional[EvidenceItemRecord]:
        return self._item_map.get(item_id)

    def contains(self, item_id: str) -> bool:
        return item_id in self._item_map

    def to_evidence_records(self) -> List[EvidenceItemRecord]:
        return list(self.items)

    def to_llm_context(self) -> str:
        """Formats the evidence bundle into a clean, structured context for Gemma 4."""
        lines = [
            f"MICRO-WATERSHED CONTRACT: ID={self.mws_id}, DISPLAY_CODE={self.mws_code}",
            "AVAILABLE RETRIEVED EVIDENCE (Use ONLY these items; cite their exact ID when referencing facts):"
        ]
        for it in self.items:
            unit_str = f" {it.unit}" if it.unit else ""
            lines.append(
                f"- [{it.id}] {it.metric}: {it.value}{unit_str} | Source Type: {it.source_type} | Source: {it.source} | Provenance: {it.provenance}"
            )
        
        if self.disclosed_gaps:
            lines.append("\nDISCLOSED DATA LIMITATIONS / GAPS:")
            for gap in self.disclosed_gaps:
                lines.append(f"- {gap}")

        return "\n".join(lines)


class WatershedEvidenceService:
    """
    Read-only evidence retrieval service integrating existing JalDrishti adapters.
    """
    def __init__(self, adapters: Dict[str, Any]):
        self.adapters = adapters

    def retrieve_evidence(self, mws_identifier: str) -> Optional[WatershedEvidenceBundle]:
        """
        Retrieves real evidence for a micro-watershed.
        Accepts either canonical GIS ID (e.g. 'g_mws.240575') or display code (e.g. '4D4F2m3').
        Returns None if watershed does not exist in official GIS catalog.
        """
        gis_adapter = self.adapters.get("gis")
        if not gis_adapter:
            logger.error("GIS adapter not found in adapters map.")
            return None

        id_to_mws = gis_adapter.get_id_to_mws_map()
        mws_to_id = gis_adapter.get_mws_to_id_map()

        clean_id = mws_identifier.strip()
        if clean_id in id_to_mws:
            canonical_id = clean_id
            display_mws = id_to_mws[clean_id]
        elif clean_id in mws_to_id:
            canonical_id = mws_to_id[clean_id]
            display_mws = clean_id
        else:
            logger.warning(f"Micro-watershed '{mws_identifier}' not found in official GIS catalog.")
            return None

        items: List[EvidenceItemRecord] = []
        disclosed_gaps: List[str] = []

        # 1. GIS Spatial Metadata
        gis_meta = gis_adapter.get_mws_meta(canonical_id) or {}
        area = gis_meta.get("area_km2")
        if area is not None:
            try:
                area_val = round(float(area), 2)
                items.append(
                    EvidenceItemRecord(
                        id="ev_area_km2",
                        metric="Micro-Watershed Area",
                        value=area_val,
                        unit="km²",
                        source_type="observed_spatial",
                        source="Shiggaon GIS Master Layer",
                        provenance="Shiggaon_Model2_GIS_Integration_66_SPATIAL_FINAL.gpkg",
                    )
                )
            except (ValueError, TypeError):
                pass

        # 2. Model 2 Risk Engine V4 Attributes
        m2_adapter = self.adapters.get("model2")
        if m2_adapter:
            risk = m2_adapter.get_risk(canonical_id)
            if risk:
                items.append(
                    EvidenceItemRecord(
                        id="ev_final_risk",
                        metric="Official Final Risk Score",
                        value=round(float(risk.final_risk_score), 2),
                        unit="/100",
                        source_type="official_risk_engine",
                        source="Model 2 Risk Engine V4",
                        provenance="Model 2 Risk Engine V4 (0.80 * Base Risk + 0.20 * ML Anomaly)",
                    )
                )
                items.append(
                    EvidenceItemRecord(
                        id="ev_risk_category",
                        metric="Official Risk Category",
                        value=str(risk.risk_category),
                        unit=None,
                        source_type="official_risk_engine",
                        source="Model 2 Risk Engine V4",
                        provenance="Official Risk Classification Thresholds (CRITICAL >= 70, HIGH >= 50, MODERATE >= 30, LOW < 30)",
                    )
                )
                items.append(
                    EvidenceItemRecord(
                        id="ev_health_index",
                        metric="Watershed Health Index",
                        value=round(100.0 - float(risk.final_risk_score), 2),
                        unit="/100",
                        source_type="official_risk_engine",
                        source="Model 2 Risk Engine V4",
                        provenance="Health Index Formulation: 100 - Final Risk",
                    )
                )
                items.append(
                    EvidenceItemRecord(
                        id="ev_primary_driver",
                        metric="Primary Risk Driver",
                        value=str(risk.primary_risk_driver),
                        unit=None,
                        source_type="official_risk_engine",
                        source="Model 2 Risk Engine V4",
                        provenance="Model 2 Factor Sensitivity Decomposition",
                    )
                )
                items.append(
                    EvidenceItemRecord(
                        id="ev_water_stress",
                        metric="Water Stress Component Score",
                        value=round(float(risk.water_stress_score), 2),
                        unit="/100",
                        source_type="official_risk_engine",
                        source="Model 2 Risk Engine V4",
                        provenance="Base Risk Sub-Component (Weight: 35% in Base Risk)",
                    )
                )
                items.append(
                    EvidenceItemRecord(
                        id="ev_flood_risk",
                        metric="Flood Risk Component Score",
                        value=round(float(risk.flood_risk_score), 2),
                        unit="/100",
                        source_type="official_risk_engine",
                        source="Model 2 Risk Engine V4",
                        provenance="Base Risk Sub-Component (Weight: 35% in Base Risk)",
                    )
                )
                items.append(
                    EvidenceItemRecord(
                        id="ev_ecosystem_risk",
                        metric="Ecosystem Risk Component Score",
                        value=round(float(risk.ecosystem_risk_score), 2),
                        unit="/100",
                        source_type="official_risk_engine",
                        source="Model 2 Risk Engine V4",
                        provenance="Base Risk Sub-Component (Weight: 30% in Base Risk)",
                    )
                )
                items.append(
                    EvidenceItemRecord(
                        id="ev_base_risk",
                        metric="Base Risk Score",
                        value=round(float(risk.base_risk_score), 2),
                        unit="/100",
                        source_type="official_risk_engine",
                        source="Model 2 Risk Engine V4",
                        provenance="0.35 * Water Stress + 0.35 * Flood Risk + 0.30 * Ecosystem Risk",
                    )
                )
                items.append(
                    EvidenceItemRecord(
                        id="ev_ml_anomaly",
                        metric="ML Anomaly Score",
                        value=round(float(risk.ml_anomaly_score), 2),
                        unit="/100",
                        source_type="official_risk_engine",
                        source="Model 2 Risk Engine V4",
                        provenance="Isolation Forest Multivariate Environmental Anomaly Engine",
                    )
                )
            else:
                disclosed_gaps.append("Official Model 2 risk assessment data is unavailable for this micro-watershed.")

            # Interventions
            interv = m2_adapter.get_interventions(canonical_id)
            if interv and interv.primary_intervention:
                items.append(
                    EvidenceItemRecord(
                        id="ev_primary_intervention",
                        metric="Primary Recommended Intervention",
                        value=str(interv.primary_intervention),
                        unit=None,
                        source_type="official_risk_engine",
                        source="Model 2 Intervention Engine",
                        provenance="intervention_recommendations_v1.csv",
                    )
                )
                if interv.secondary_intervention:
                    items.append(
                        EvidenceItemRecord(
                            id="ev_secondary_intervention",
                            metric="Secondary Recommended Intervention",
                            value=str(interv.secondary_intervention),
                            unit=None,
                            source_type="official_risk_engine",
                            source="Model 2 Intervention Engine",
                            provenance="intervention_recommendations_v1.csv",
                        )
                    )
                if interv.monitoring_focus:
                    items.append(
                        EvidenceItemRecord(
                            id="ev_monitoring_focus",
                            metric="Monitoring Focus",
                            value=str(interv.monitoring_focus),
                            unit=None,
                            source_type="official_risk_engine",
                            source="Model 2 Intervention Engine",
                            provenance="intervention_recommendations_v1.csv",
                        )
                    )

            # Features / Indicators (strictly preserving None when missing)
            features = m2_adapter.get_features(canonical_id) or {}
            
            if features.get("elevation_mean") is not None:
                items.append(
                    EvidenceItemRecord(
                        id="ev_elevation_m",
                        metric="Mean Elevation",
                        value=features["elevation_mean"],
                        unit="m",
                        source_type="model_derived",
                        source="DEM GLO30 Terrain Engine",
                        provenance="GLO30 Copernicus 30m Digital Elevation Model",
                    )
                )
            else:
                disclosed_gaps.append("Elevation data is not available for this micro-watershed.")

            if features.get("slope_mean") is not None:
                items.append(
                    EvidenceItemRecord(
                        id="ev_slope_deg",
                        metric="Mean Topographic Slope",
                        value=features["slope_mean"],
                        unit="degrees",
                        source_type="model_derived",
                        source="DEM GLO30 Terrain Engine",
                        provenance="GLO30 Slope Gradient Calculation",
                    )
                )
            else:
                disclosed_gaps.append("Slope data is not available for this micro-watershed.")

            stream_len = features.get("stream_length_km") if features.get("stream_length_km") is not None else gis_meta.get("stream_len_km")
            if stream_len is not None:
                items.append(
                    EvidenceItemRecord(
                        id="ev_stream_len_km",
                        metric="Stream Network Length",
                        value=round(float(stream_len), 2),
                        unit="km",
                        source_type="observed_spatial",
                        source="Hydrological Drainage Network",
                        provenance="GIS Hydrology Vectors EPSG:32643",
                    )
                )

            drainage_density = features.get("drainage_density") if features.get("drainage_density") is not None else gis_meta.get("drainage_density")
            if drainage_density is not None:
                items.append(
                    EvidenceItemRecord(
                        id="ev_drainage_density",
                        metric="Drainage Density",
                        value=round(float(drainage_density), 3),
                        unit="km/km²",
                        source_type="model_derived",
                        source="Hydrological Drainage Network",
                        provenance="Stream Length per Unit Catchment Area",
                    )
                )

            if features.get("rainfall_mm") is not None:
                items.append(
                    EvidenceItemRecord(
                        id="ev_rainfall_mm",
                        metric="Monthly Rainfall Indicator",
                        value=features["rainfall_mm"],
                        unit="mm",
                        source_type="model_derived",
                        source="CHIRPS / Climate Reanalysis",
                        provenance="Monthly Environmental Features V6",
                    )
                )
            else:
                disclosed_gaps.append("Monthly rainfall telemetry/reanalysis is unavailable for this catchment.")

            if features.get("rainfall_anomaly") is not None:
                items.append(
                    EvidenceItemRecord(
                        id="ev_rainfall_anomaly",
                        metric="Rainfall Anomaly",
                        value=features["rainfall_anomaly"],
                        unit="sigma",
                        source_type="model_derived",
                        source="CHIRPS / Climate Reanalysis",
                        provenance="Standard deviation deviation from 10-year monthly baseline",
                    )
                )

            if features.get("ndvi") is not None:
                items.append(
                    EvidenceItemRecord(
                        id="ev_ndvi",
                        metric="Mean NDVI (Vegetation Index)",
                        value=features["ndvi"],
                        unit=None,
                        source_type="model_derived",
                        source="Sentinel-2 Remote Sensing",
                        provenance="Monthly Sentinel-2 Surface Reflectance Composites",
                    )
                )

            if features.get("ndvi_anomaly") is not None:
                items.append(
                    EvidenceItemRecord(
                        id="ev_ndvi_anomaly",
                        metric="NDVI Anomaly",
                        value=features["ndvi_anomaly"],
                        unit="sigma",
                        source_type="model_derived",
                        source="Sentinel-2 Remote Sensing",
                        provenance="Normalized vegetation anomaly relative to historical seasonal mean",
                    )
                )

        # 3. Model 1 Sentinel-2 LULC Classification
        m1_adapter = self.adapters.get("model1")
        if m1_adapter:
            lulc = m1_adapter.get_by_id(canonical_id)
            if lulc:
                items.append(
                    EvidenceItemRecord(
                        id="ev_lulc_dominant",
                        metric="Dominant Land Cover Class",
                        value=str(lulc.dominant_class),
                        unit=None,
                        source_type="model_derived",
                        source="Sentinel-2 Random Forest V1",
                        provenance="micro_watershed_lulc_statistics.csv",
                    )
                )
                items.append(
                    EvidenceItemRecord(
                        id="ev_lulc_agri",
                        metric="Agricultural Land Coverage",
                        value=round(float(lulc.agriculture_pct), 2),
                        unit="%",
                        source_type="model_derived",
                        source="Sentinel-2 Random Forest V1",
                        provenance="micro_watershed_lulc_statistics.csv",
                    )
                )
                items.append(
                    EvidenceItemRecord(
                        id="ev_lulc_forest",
                        metric="Forest Land Coverage",
                        value=round(float(lulc.forest_pct), 2),
                        unit="%",
                        source_type="model_derived",
                        source="Sentinel-2 Random Forest V1",
                        provenance="micro_watershed_lulc_statistics.csv",
                    )
                )
                items.append(
                    EvidenceItemRecord(
                        id="ev_lulc_water",
                        metric="Surface Water Body Coverage",
                        value=round(float(lulc.water_pct), 2),
                        unit="%",
                        source_type="model_derived",
                        source="Sentinel-2 Random Forest V1",
                        provenance="micro_watershed_lulc_statistics.csv",
                    )
                )
                items.append(
                    EvidenceItemRecord(
                        id="ev_lulc_builtup",
                        metric="Built-up Land Coverage",
                        value=round(float(lulc.builtup_pct), 2),
                        unit="%",
                        source_type="model_derived",
                        source="Sentinel-2 Random Forest V1",
                        provenance="micro_watershed_lulc_statistics.csv",
                    )
                )
                items.append(
                    EvidenceItemRecord(
                        id="ev_lulc_barren",
                        metric="Barren Land Coverage",
                        value=round(float(lulc.barren_pct), 2),
                        unit="%",
                        source_type="model_derived",
                        source="Sentinel-2 Random Forest V1",
                        provenance="micro_watershed_lulc_statistics.csv",
                    )
                )
                items.append(
                    EvidenceItemRecord(
                        id="ev_lulc_coverage",
                        metric="LULC Raster Extent Category",
                        value=str(lulc.coverage_category),
                        unit=None,
                        source_type="model_derived",
                        source="Sentinel-2 Random Forest V1",
                        provenance="micro_watershed_lulc_statistics.csv",
                        coverage_or_notes=f"{lulc.coverage_pct}% raster overlap" if lulc.coverage_pct is not None else None,
                    )
                )

                if lulc.coverage_category in ("LOW", "PERIPHERAL", "PARTIAL") or (lulc.coverage_pct is not None and lulc.coverage_pct < 80.0):
                    cov_pct_str = f" ({lulc.coverage_pct}% raster overlap)" if lulc.coverage_pct is not None else ""
                    disclosed_gaps.append(
                        f"LULC raster coverage for this micro-watershed is categorized as {lulc.coverage_category}{cov_pct_str}. Statistics represent sampled sub-regions."
                    )
            else:
                disclosed_gaps.append("Sentinel-2 LULC classification data is unavailable for this micro-watershed.")

        # 4. Water Quality (strictly marked as simulation)
        wq_adapter = self.adapters.get("water_quality")
        if wq_adapter:
            wq_rec = wq_adapter.get_mws_reading(canonical_id)
            if wq_rec:
                items.append(
                    EvidenceItemRecord(
                        id="ev_wq_wqi",
                        metric="Water Quality Index (WQI)",
                        value=round(float(wq_rec.wqi), 2),
                        unit="WQI",
                        source_type="simulated_telemetry",
                        source="Water Quality Simulation Engine",
                        provenance="Synthetic water quality simulation run (sample_water_quality.csv)",
                    )
                )
                items.append(
                    EvidenceItemRecord(
                        id="ev_wq_category",
                        metric="Water Quality Rating Category",
                        value=str(wq_rec.quality_category),
                        unit=None,
                        source_type="simulated_telemetry",
                        source="Water Quality Simulation Engine",
                        provenance="Synthetic water quality simulation run",
                    )
                )
                disclosed_gaps.append(
                    "Water Quality (WQI) data is generated by synthetic simulation and does not reflect in-situ physical sensor telemetry."
                )
            else:
                disclosed_gaps.append("Water Quality data is currently unavailable for this catchment.")

        # 5. Field Observations (observed data from Geo-Coded pipeline)
        geo_adapter = self.adapters.get("geocoded")
        if geo_adapter:
            obs = geo_adapter.get_by_watershed(canonical_id)
            obs_count = len(obs) if obs else 0
            items.append(
                EvidenceItemRecord(
                    id="ev_field_obs_count",
                    metric="Geotagged Field Survey Photos Count",
                    value=obs_count,
                    unit="photos",
                    source_type="observed_field",
                    source="Geo-Coded Evidence Pipeline",
                    provenance="ImageIdLedger flat ledger",
                )
            )
            if obs_count == 0:
                disclosed_gaps.append(
                    "No geotagged field survey photos currently exist for this micro-watershed."
                )

        return WatershedEvidenceBundle(
            mws_id=canonical_id,
            mws_code=display_mws,
            items=items,
            disclosed_gaps=disclosed_gaps,
        )
