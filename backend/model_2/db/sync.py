"""
JalDrishti Database V1 Authoritative Data Sync.

Populates PostgreSQL + PostGIS with:
- 66 Canonical Micro-Watersheds and PostGIS boundary geometries (WGS84 EPSG:4326).
- Authoritative baseline risk metrics from Model 2.
- Recommended field interventions from Model 2.
- Operational alerts for high/critical catchments.

Strict rules:
- Does NOT modify the authoritative GPKG file.
- Does NOT duplicate the entire GPKG (only micro-watersheds and operational data).
- Converts geometries to WGS84 (EPSG:4326) MultiPolygon for PostGIS compliance.
"""

from pathlib import Path
import logging
from typing import Dict, Any, Optional

import geopandas as gpd
import pandas as pd
from shapely.geometry import Polygon, MultiPolygon
from geoalchemy2.elements import WKTElement
from sqlalchemy.orm import sessionmaker, Session

from .config import settings, BASE_DIR
from .session import engine
from .models import MicroWatershed, RiskHistory, Intervention, Alert

logger = logging.getLogger(__name__)

DEFAULT_GPKG = (
    BASE_DIR
    / "gis"
    / "SIH_2026_SHIGGAON_GIS_FINAL"
    / "03_MICRO_WATERSHEDS"
    / "Shiggaon_Model2_GIS_Integration_66_SPATIAL_FINAL.gpkg"
)

FALLBACK_GPKG = (
    BASE_DIR
    / "gis"
    / "SIH_2026_SHIGGAON_GIS_FINAL"
    / "03_MICRO_WATERSHEDS"
    / "Shiggaon_MWS_Master_66.gpkg"
)


def to_multipolygon_wkt(geometry) -> Optional[WKTElement]:
    """Ensures input geometry is converted to MultiPolygon WKTElement with SRID 4326."""
    if geometry is None or geometry.is_empty:
        return None
    if isinstance(geometry, Polygon):
        geometry = MultiPolygon([geometry])
    return WKTElement(geometry.wkt, srid=4326)


def sync_authoritative_data(
    target_engine=None,
    gpkg_path: Optional[Path] = None,
    force: bool = False
) -> Dict[str, Any]:
    """
    Reads authoritative GPKG and synchronizes the 66 micro-watershed records,
    baseline risk assessments, and intervention records into the database.
    Idempotent: updates existing records if already present.
    """
    active_engine = target_engine or engine
    SessionCls = sessionmaker(bind=active_engine)
    session: Session = SessionCls()

    source_path = Path(gpkg_path) if gpkg_path else DEFAULT_GPKG
    if not source_path.exists():
        if FALLBACK_GPKG.exists():
            source_path = FALLBACK_GPKG
            logger.warning(f"Default spatial final not found, using fallback: {source_path}")
        else:
            logger.error(f"Authoritative GPKG file not found at: {source_path}")
            return {
                "status": "error",
                "message": f"GPKG not found: {source_path}",
                "synced_micro_watersheds": 0,
            }

    try:
        # Read authoritative spatial layer (read-only, does not touch GPKG)
        gdf = gpd.read_file(source_path)
        gdf_4326 = gdf.to_crs("EPSG:4326")

        synced_mws = 0
        synced_risks = 0
        synced_interventions = 0
        synced_alerts = 0

        for _, row in gdf_4326.iterrows():
            mws_id = str(row["id"]).strip()
            display_code = str(row.get("MWS", "")).strip()

            # Topographic & hydrological features
            area_sqkm = float(row["area_km2"]) if "area_km2" in row and pd.notna(row["area_km2"]) else None
            stream_len = float(row["Stream_Len_km"]) if "Stream_Len_km" in row and pd.notna(row["Stream_Len_km"]) else 0.0
            drainage_density = float(row["Drain_Density"]) if "Drain_Density" in row and pd.notna(row["Drain_Density"]) else 0.0
            max_strahler = int(row["Max_Strahler"]) if "Max_Strahler" in row and pd.notna(row["Max_Strahler"]) else 0
            slope_mean = float(row["M2_slope_mean"]) if "M2_slope_mean" in row and pd.notna(row["M2_slope_mean"]) else 0.0
            elev_mean = float(row["M2_elevation_mean"]) if "M2_elevation_mean" in row and pd.notna(row["M2_elevation_mean"]) else 0.0

            # LULC
            forest_pct = float(row["Forest_pct"]) if "Forest_pct" in row and pd.notna(row["Forest_pct"]) else 0.0
            agri_pct = float(row["Agriculture_pct"]) if "Agriculture_pct" in row and pd.notna(row["Agriculture_pct"]) else 0.0
            water_pct = float(row["Water_pct"]) if "Water_pct" in row and pd.notna(row["Water_pct"]) else 0.0
            builtup_pct = float(row["Builtup_pct"]) if "Builtup_pct" in row and pd.notna(row["Builtup_pct"]) else 0.0
            barren_pct = float(row["Barren_pct"]) if "Barren_pct" in row and pd.notna(row["Barren_pct"]) else 0.0

            # Model 2 Risk
            risk_score = float(row["M2_latest_final_risk_score"]) if "M2_latest_final_risk_score" in row and pd.notna(row["M2_latest_final_risk_score"]) else None
            risk_cat = str(row.get("M2_latest_risk_category", "LOW")).strip()
            driver = str(row.get("M2_latest_primary_risk_driver", "None")).strip()
            health_index = round(100.0 - risk_score, 2) if risk_score is not None else None
            interv_priority = str(row.get("M2_latest_intervention_priority", "LOW")).strip()

            # Convert geometry
            geom_wkt = to_multipolygon_wkt(row.geometry)

            # Query existing record
            mws_obj = session.query(MicroWatershed).filter_by(mws_id=mws_id).first()
            if not mws_obj:
                mws_obj = MicroWatershed(mws_id=mws_id)
                session.add(mws_obj)

            mws_obj.display_code = display_code
            mws_obj.name = f"Micro-Watershed {display_code}"
            mws_obj.taluk = "Shiggaon"
            mws_obj.district = "Haveri"
            mws_obj.state = "Karnataka"
            mws_obj.area_sqkm = area_sqkm
            mws_obj.stream_length_km = stream_len
            mws_obj.drainage_density = drainage_density
            mws_obj.max_strahler_order = max_strahler
            mws_obj.slope_mean_deg = slope_mean
            mws_obj.elevation_mean_m = elev_mean
            mws_obj.forest_pct = forest_pct
            mws_obj.agriculture_pct = agri_pct
            mws_obj.water_pct = water_pct
            mws_obj.builtup_pct = builtup_pct
            mws_obj.barren_pct = barren_pct
            mws_obj.current_risk_score = risk_score
            mws_obj.current_risk_category = risk_cat
            mws_obj.current_primary_driver = driver
            mws_obj.current_health_index = health_index
            mws_obj.intervention_priority = interv_priority
            mws_obj.geometry = geom_wkt

            synced_mws += 1

            # Baseline Risk History entry
            if risk_score is not None:
                existing_risk = session.query(RiskHistory).filter_by(
                    mws_id=mws_id, source="gpkg_authoritative"
                ).first()
                if not existing_risk:
                    rh = RiskHistory(
                        mws_id=mws_id,
                        year=int(row.get("M2_latest_year", 2026)) if pd.notna(row.get("M2_latest_year")) else 2026,
                        month=int(row.get("M2_latest_month", 9)) if pd.notna(row.get("M2_latest_month")) else 9,
                        base_risk_score=float(row.get("M2_base_risk_score", 0.0)) if pd.notna(row.get("M2_base_risk_score")) else 0.0,
                        final_risk_score=risk_score,
                        risk_category=risk_cat,
                        primary_driver=driver,
                        water_stress_score=float(row.get("M2_water_stress_score", 0.0)) if pd.notna(row.get("M2_water_stress_score")) else 0.0,
                        flood_risk_score=float(row.get("M2_flood_risk_score", 0.0)) if pd.notna(row.get("M2_flood_risk_score")) else 0.0,
                        ecosystem_risk_score=float(row.get("M2_ecosystem_risk_score", 0.0)) if pd.notna(row.get("M2_ecosystem_risk_score")) else 0.0,
                        ml_anomaly_score=float(row.get("M2_ml_anomaly_score", 0.0)) if pd.notna(row.get("M2_ml_anomaly_score")) else 0.0,
                        source="gpkg_authoritative",
                    )
                    session.add(rh)
                    synced_risks += 1

            # Interventions
            interv_rec = str(row.get("M2_latest_recommended_interventions", "")).strip()
            if interv_rec and interv_rec != "nan":
                existing_int = session.query(Intervention).filter_by(
                    mws_id=mws_id, source="model2_recommendation"
                ).first()
                if not existing_int:
                    inv = Intervention(
                        mws_id=mws_id,
                        intervention_type=interv_rec,
                        priority=interv_priority,
                        status="RECOMMENDED",
                        monitoring_focus=f"Soil & water conservation priority for {display_code}",
                        source="model2_recommendation",
                    )
                    session.add(inv)
                    synced_interventions += 1

            # Alerts for CRITICAL or HIGH
            if risk_cat in ("CRITICAL", "HIGH"):
                existing_alert = session.query(Alert).filter_by(
                    mws_id=mws_id, is_active=True
                ).first()
                if not existing_alert:
                    alert = Alert(
                        mws_id=mws_id,
                        alert_level=risk_cat,
                        alert_type="BASELINE_ELEVATED_RISK",
                        headline=f"Elevated Risk Advisory: {display_code}",
                        message=f"Micro-watershed {display_code} ({mws_id}) has authoritative risk score {risk_score} ({risk_cat}) driven primarily by {driver}.",
                        is_active=True,
                    )
                    session.add(alert)
                    synced_alerts += 1

        session.commit()
        return {
            "status": "success",
            "synced_micro_watersheds": synced_mws,
            "synced_risk_history": synced_risks,
            "synced_interventions": synced_interventions,
            "synced_alerts": synced_alerts,
        }
    except Exception as e:
        session.rollback()
        logger.error(f"Sync failed: {e}")
        return {
            "status": "error",
            "error": str(e),
            "synced_micro_watersheds": 0,
        }
    finally:
        session.close()


if __name__ == "__main__":
    import sys
    logging.basicConfig(level=logging.INFO, format="%(asctime)s [%(levelname)s] %(message)s")
    stats = sync_authoritative_data()
    print("\nSync Results:")
    for k, v in stats.items():
        print(f"  {k}: {v}")
    if stats["status"] != "success":
        sys.exit(1)
