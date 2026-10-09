from pathlib import Path
from typing import Dict, Optional, Tuple, Any, List
import pandas as pd
import geopandas as gpd
import logging
from ..schemas import WatershedRisk, WatershedInterventions, BasinSummary, MonthlyHealthPoint

logger = logging.getLogger(__name__)

class Model2Adapter:
    """
    Adapter for Model 2 Risk Engine V4 outputs and Interventions.
    Prioritizes authoritative master spatial integration layer:
      Shiggaon_Model2_GIS_Integration_66_SPATIAL_FINAL.gpkg
    which contains verified risk categories and primary drivers for all 66 MWS.
    Also parses risk_assessment_v4.csv for 12-month historical monthly trends.
    """
    def __init__(self, data_dir: Optional[Path] = None):
        base_dir = Path(__file__).resolve().parents[4]  # repo root
        if data_dir is None:
            data_dir = base_dir / "backend" / "model_2" / "Data" / "processed"
        self.data_dir = Path(data_dir)
        self.gis_dir = base_dir / "gis" / "SIH_2026_SHIGGAON_GIS_FINAL"
        self._spatial_final_path = self.gis_dir / "03_MICRO_WATERSHEDS" / "Shiggaon_Model2_GIS_Integration_66_SPATIAL_FINAL.gpkg"
        
        self._latest_risk: Dict[str, WatershedRisk] = {}
        self._latest_interventions: Dict[str, WatershedInterventions] = {}
        self._features: Dict[str, Dict[str, float]] = {}
        self._basin_monthly_trend: List[MonthlyHealthPoint] = []
        self._mws_monthly_trends: Dict[str, List[MonthlyHealthPoint]] = {}
        self._risk_distribution: Dict[str, int] = {}
        self._primary_drivers: Dict[str, int] = {}
        self.load()

    def load(self) -> None:
        # 1. Load authoritative risk data from GPKG if available
        if self._spatial_final_path.exists():
            try:
                gdf = gpd.read_file(self._spatial_final_path)
                for _, row in gdf.iterrows():
                    mws_id = str(row["id"]).strip()
                    mws_code = str(row["MWS"]).strip()
                    
                    try:
                        risk_score = round(float(row["M2_latest_final_risk_score"]), 2)
                    except (ValueError, TypeError):
                        risk_score = 0.0

                    risk_cat = str(row.get("M2_latest_risk_category", "LOW")).strip()
                    driver = str(row.get("M2_latest_primary_risk_driver", "None")).strip()
                    w_stress = round(float(row.get("M2_water_stress_score", 0.0)), 2)
                    flood = round(float(row.get("M2_flood_risk_score", 0.0)), 2)
                    eco = round(float(row.get("M2_ecosystem_risk_score", 0.0)), 2)
                    base_r = round(float(row.get("M2_base_risk_score", 0.0)), 2)
                    ml_anom = round(float(row.get("M2_ml_anomaly_score", 0.0)), 2)

                    self._latest_risk[mws_id] = WatershedRisk(
                        id=mws_id,
                        MWS=mws_code,
                        water_stress_score=w_stress,
                        flood_risk_score=flood,
                        ecosystem_risk_score=eco,
                        base_risk_score=base_r,
                        ml_anomaly_score=ml_anom,
                        final_risk_score=risk_score,
                        risk_category=risk_cat,
                        primary_risk_driver=driver,
                        status="available"
                    )

                    # Also store intervention from GPKG if present
                    interv_str = str(row.get("M2_latest_recommended_interventions", "")).strip()
                    if interv_str and interv_str != "nan":
                        self._latest_interventions[mws_id] = WatershedInterventions(
                            id=mws_id,
                            MWS=mws_code,
                            risk_category=risk_cat,
                            primary_intervention=interv_str,
                            secondary_intervention=None,
                            monitoring_focus=str(row.get("M2_latest_intervention_priority", "Standard Monitoring")),
                            status="available"
                        )
                logger.info(f"Loaded authoritative risk outputs from GPKG for {len(self._latest_risk)} MWS.")
            except Exception as e:
                logger.error(f"Error loading GPKG risk data: {e}")

        # Fallback or supplementary risk CSV
        risk_csv = self.data_dir / "risk_assessment_v4.csv"
        interv_csv = self.data_dir / "intervention_recommendations_v1.csv"
        features_csv = self.data_dir / "model2_features_v6.csv"

        if len(self._latest_risk) == 0 and risk_csv.exists():
            try:
                df_risk = pd.read_csv(risk_csv)
                df_risk_sorted = df_risk.sort_values(by=["year", "month"])
                latest_risk_df = df_risk_sorted.groupby("id").last().reset_index()

                for _, row in latest_risk_df.iterrows():
                    mws_id = str(row["id"]).strip()
                    self._latest_risk[mws_id] = WatershedRisk(
                        id=mws_id,
                        MWS="",
                        water_stress_score=round(float(row.get("water_stress_score", 0.0)), 2),
                        flood_risk_score=round(float(row.get("flood_risk_score", 0.0)), 2),
                        ecosystem_risk_score=round(float(row.get("ecosystem_risk_score", 0.0)), 2),
                        base_risk_score=round(float(row.get("base_risk_score", 0.0)), 2),
                        ml_anomaly_score=round(float(row.get("ml_anomaly_score", 50.0)), 2),
                        final_risk_score=round(float(row.get("final_risk_score", 0.0)), 2),
                        risk_category=str(row.get("risk_category", "LOW")),
                        primary_risk_driver=str(row.get("primary_risk_driver", "None")),
                        status="available"
                    )
            except Exception as e:
                logger.error(f"Failed fallback risk CSV: {e}")

        # 2. Load Intervention Recommendations CSV for detailed interventions
        if interv_csv.exists():
            try:
                df_interv = pd.read_csv(interv_csv).sort_values(by=["year", "month"])
                latest_interv_df = df_interv.groupby("id").last().reset_index()
                for _, row in latest_interv_df.iterrows():
                    mws_id = str(row["id"]).strip()
                    # Preserve or enhance existing
                    prev = self._latest_interventions.get(mws_id)
                    primary = str(row.get("primary_intervention", "")) if pd.notna(row.get("primary_intervention")) else (prev.primary_intervention if prev else None)
                    secondary = str(row.get("secondary_intervention", "")) if pd.notna(row.get("secondary_intervention")) else (prev.secondary_intervention if prev else None)
                    focus = str(row.get("monitoring_focus", "")) if pd.notna(row.get("monitoring_focus")) else (prev.monitoring_focus if prev else None)

                    self._latest_interventions[mws_id] = WatershedInterventions(
                        id=mws_id,
                        MWS="",
                        risk_category=prev.risk_category if prev else str(row.get("risk_category", "LOW")),
                        primary_intervention=primary,
                        secondary_intervention=secondary,
                        long_term_intervention=str(row.get("long_term_intervention", "")) if pd.notna(row.get("long_term_intervention")) else None,
                        iot_sensors=str(row.get("recommended_iot_sensors", "")) if pd.notna(row.get("recommended_iot_sensors")) else None,
                        monitoring_focus=focus,
                        status="available"
                    )
            except Exception as e:
                logger.error(f"Failed loading intervention CSV: {e}")

        # 3. Load Features (Elevation, Slope, Hydrology, Climate, Vegetation)
        if features_csv.exists():
            try:
                df_feat = pd.read_csv(features_csv).sort_values(by=["year", "month"])
                latest_feat_df = df_feat.groupby("id").last().reset_index()
                for _, row in latest_feat_df.iterrows():
                    mws_id = str(row["id"]).strip()
                    self._features[mws_id] = {
                        "elevation_mean": round(float(row.get("elevation_mean", 0.0)), 1) if pd.notna(row.get("elevation_mean")) else None,
                        "slope_mean": round(float(row.get("slope_mean", 0.0)), 1) if pd.notna(row.get("slope_mean")) else None,
                        "stream_length_km": round(float(row.get("stream_length_km", 0.0)), 2) if pd.notna(row.get("stream_length_km")) else None,
                        "drainage_density": round(float(row.get("drainage_density", 0.0)), 3) if pd.notna(row.get("drainage_density")) else None,
                        "rainfall_mm": round(float(row.get("rainfall_mm", 0.0)), 1) if pd.notna(row.get("rainfall_mm")) else None,
                        "rainfall_anomaly": round(float(row.get("rainfall_anomaly", 0.0)), 2) if pd.notna(row.get("rainfall_anomaly")) else None,
                        "ndvi": round(float(row.get("ndvi", 0.0)), 3) if pd.notna(row.get("ndvi")) else None,
                        "ndvi_anomaly": round(float(row.get("ndvi_anomaly", 0.0)), 2) if pd.notna(row.get("ndvi_anomaly")) else None,
                    }

                self._basin_feature_averages = {
                    "avg_slope_mean": round(float(latest_feat_df["slope_mean"].mean()), 1) if "slope_mean" in latest_feat_df else 8.1,
                    "avg_elevation_mean": round(float(latest_feat_df["elevation_mean"].mean()), 1) if "elevation_mean" in latest_feat_df else 631.1,
                    "avg_drainage_density": round(float(latest_feat_df["drainage_density"].mean()), 3) if "drainage_density" in latest_feat_df else 0.207,
                    "avg_stream_length_km": round(float(latest_feat_df["stream_length_km"].mean()), 2) if "stream_length_km" in latest_feat_df else 3.03,
                    "avg_ndvi": round(float(latest_feat_df["ndvi"].mean()), 3) if "ndvi" in latest_feat_df else 0.443,
                    "avg_rainfall_mm": round(float(latest_feat_df["rainfall_mm"].mean()), 1) if "rainfall_mm" in latest_feat_df else 0.8,
                    "avg_rainfall_anomaly": round(float(latest_feat_df["rainfall_anomaly"].mean()), 2) if "rainfall_anomaly" in latest_feat_df else -2.17,
                }
            except Exception as e:
                logger.error(f"Failed loading features CSV: {e}")

        # 4. Load 12-month Historical Trends from risk_assessment_v4.csv
        month_names = ['Jan', 'Feb', 'Mar', 'Apr', 'May', 'Jun', 'Jul', 'Aug', 'Sep', 'Oct', 'Nov', 'Dec']
        if risk_csv.exists():
            try:
                df_risk = pd.read_csv(risk_csv)
                monthly_basin = df_risk.groupby(['year', 'month'])['final_risk_score'].mean().reset_index()
                for _, r in monthly_basin.tail(12).iterrows():
                    m_int = int(r.month)
                    y_int = int(r.year)
                    m_name = month_names[m_int - 1]
                    risk_val = round(float(r.final_risk_score), 1)
                    health_val = round(100.0 - risk_val, 1)
                    self._basin_monthly_trend.append(MonthlyHealthPoint(
                        month=m_name,
                        year=y_int,
                        health_index=health_val,
                        risk_score=risk_val
                    ))

                for mws_id, group in df_risk.groupby("id"):
                    mws_recent = group.sort_values(by=["year", "month"]).tail(12)
                    pts = []
                    for _, r in mws_recent.iterrows():
                        m_int = int(r.month)
                        y_int = int(r.year)
                        m_name = month_names[m_int - 1]
                        risk_val = round(float(r.final_risk_score), 1)
                        health_val = round(100.0 - risk_val, 1)
                        pts.append(MonthlyHealthPoint(
                            month=m_name,
                            year=y_int,
                            health_index=health_val,
                            risk_score=risk_val
                        ))
                    self._mws_monthly_trends[str(mws_id).strip()] = pts
            except Exception as e:
                logger.error(f"Failed loading monthly historical trends: {e}")

        # Compute risk distribution and driver counts
        cat_counts: Dict[str, int] = {}
        driver_counts: Dict[str, int] = {}
        for r in self._latest_risk.values():
            cat = r.risk_category
            if cat:
                cat_counts[cat] = cat_counts.get(cat, 0) + 1
            drv = r.primary_risk_driver
            if drv and drv != "None":
                driver_counts[drv] = driver_counts.get(drv, 0) + 1
        self._risk_distribution = cat_counts
        self._primary_drivers = driver_counts

        logger.info(
            f"Loaded Model 2 Risk records for {len(self._latest_risk)} MWS. "
            f"Categories: {self._risk_distribution}, Drivers: {self._primary_drivers}"
        )

    def get_risk(self, mws_id: str) -> Optional[WatershedRisk]:
        return self._latest_risk.get(mws_id)

    def get_all_risk(self) -> Dict[str, WatershedRisk]:
        return self._latest_risk

    def get_interventions(self, mws_id: str) -> Optional[WatershedInterventions]:
        return self._latest_interventions.get(mws_id)

    def get_features(self, mws_id: str) -> Dict[str, Any]:
        return self._features.get(mws_id, {})

    def get_monthly_trend(self, mws_id: str) -> Optional[List[MonthlyHealthPoint]]:
        return self._mws_monthly_trends.get(mws_id)

    def get_basin_summary(self) -> BasinSummary:
        total_mws = len(self._latest_risk)
        if total_mws == 0:
            return BasinSummary(
                watershed_count=0,
                total_area_km2=0.0,
                basin_health_index=0.0,
                average_risk_score=0.0,
                critical_count=0,
                high_count=0,
                moderate_count=0,
                low_count=0,
                risk_distribution={},
                primary_risk_drivers={},
                monthly_trend=[],
                status="no_data"
            )

        risks = [r.final_risk_score for r in self._latest_risk.values()]
        avg_risk = sum(risks) / total_mws
        health_index = round(100.0 - avg_risk, 1)

        critical = sum(1 for r in self._latest_risk.values() if r.risk_category == "CRITICAL")
        high = sum(1 for r in self._latest_risk.values() if r.risk_category == "HIGH")
        mod = sum(1 for r in self._latest_risk.values() if r.risk_category == "MODERATE")
        low = sum(1 for r in self._latest_risk.values() if r.risk_category == "LOW")

        risk_dist = {"CRITICAL": critical, "HIGH": high, "MODERATE": mod, "LOW": low}
        basin_feats = getattr(self, "_basin_feature_averages", {})

        return BasinSummary(
            watershed_count=total_mws,
            total_area_km2=966.2,  # SLUSI verified 66 MWS area
            basin_health_index=health_index,
            average_risk_score=round(avg_risk, 1),
            critical_count=critical,
            high_count=high,
            moderate_count=mod,
            low_count=low,
            risk_distribution=risk_dist,
            primary_risk_drivers=self._primary_drivers,
            monthly_trend=self._basin_monthly_trend,
            avg_slope_mean=basin_feats.get("avg_slope_mean", 8.1),
            avg_elevation_mean=basin_feats.get("avg_elevation_mean", 631.1),
            avg_drainage_density=basin_feats.get("avg_drainage_density", 0.207),
            avg_stream_length_km=basin_feats.get("avg_stream_length_km", 3.03),
            avg_ndvi=basin_feats.get("avg_ndvi", 0.443),
            avg_rainfall_mm=basin_feats.get("avg_rainfall_mm", 0.8),
            avg_rainfall_anomaly=basin_feats.get("avg_rainfall_anomaly", -2.17),
            status="available"
        )
