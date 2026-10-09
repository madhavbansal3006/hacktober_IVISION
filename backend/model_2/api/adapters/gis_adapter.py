from pathlib import Path
from typing import Dict, Optional, Any, List
import json
import logging
import geopandas as gpd
import pandas as pd

logger = logging.getLogger(__name__)

class GISAdapter:
    """
    Adapter for the canonical Shiggaon GIS Package.
    Reads the authoritative master spatial integration dataset:
      Shiggaon_Model2_GIS_Integration_66_SPATIAL_FINAL.gpkg
    which contains the official 66 project MWS polygons and integrated
    Model 1 LULC / Model 2 Risk attributes in EPSG:32643.
    Provides web-compatible WGS84 GeoJSON for frontend interactive mapping.
    """
    def __init__(self, gis_dir: Optional[Path] = None):
        if gis_dir is None:
            base_dir = Path(__file__).resolve().parents[4]  # repo root
            gis_dir = base_dir / "gis" / "SIH_2026_SHIGGAON_GIS_FINAL"
        self.gis_dir = Path(gis_dir)
        self._spatial_final_path = self.gis_dir / "03_MICRO_WATERSHEDS" / "Shiggaon_Model2_GIS_Integration_66_SPATIAL_FINAL.gpkg"
        self._mws_master_path = self.gis_dir / "03_MICRO_WATERSHEDS" / "Shiggaon_MWS_Master_66.gpkg"
        self._taluk_boundary_path = self.gis_dir / "01_STUDY_AREA" / "Shiggaon_Taluk_Boundary.gpkg"
        
        self._mws_df: Optional[gpd.GeoDataFrame] = None
        self._mws_geojson: Optional[Dict[str, Any]] = None
        self._boundary_geojson: Optional[Dict[str, Any]] = None
        self._mws_meta: Dict[str, Dict[str, Any]] = {}
        self._id_to_mws: Dict[str, str] = {}
        self._mws_to_id: Dict[str, str] = {}
        self._risk_distribution: Dict[str, int] = {}
        self._primary_drivers: Dict[str, int] = {}
        self.load()

    def load(self) -> None:
        source_path = None
        if self._spatial_final_path.exists():
            source_path = self._spatial_final_path
            logger.info(f"Using authoritative spatial integration layer: {self._spatial_final_path.name}")
        elif self._mws_master_path.exists():
            source_path = self._mws_master_path
            logger.warning(f"Spatial final not found; falling back to master: {self._mws_master_path.name}")
        else:
            logger.error(f"Neither spatial final nor master MWS layer found in {self.gis_dir}")
            return

        try:
            gdf = gpd.read_file(source_path)
            self._mws_df = gdf
            
            # Reproject to WGS84 for web map delivery
            gdf_4326 = gdf.to_crs("EPSG:4326")
            
            features = []
            risk_counts: Dict[str, int] = {}
            driver_counts: Dict[str, int] = {}

            for _, row in gdf_4326.iterrows():
                mws_id = str(row["id"]).strip()
                mws_code = str(row["MWS"]).strip()
                self._id_to_mws[mws_id] = mws_code
                self._mws_to_id[mws_code] = mws_id

                # Extract risk fields if present
                risk_score = None
                if "M2_latest_final_risk_score" in row and pd.notna(row["M2_latest_final_risk_score"]):
                    try:
                        risk_score = round(float(row["M2_latest_final_risk_score"]), 2)
                    except (ValueError, TypeError):
                        risk_score = None

                risk_cat = str(row.get("M2_latest_risk_category", "UNKNOWN")).strip()
                if risk_cat in ("CRITICAL", "HIGH", "MODERATE", "LOW"):
                    risk_counts[risk_cat] = risk_counts.get(risk_cat, 0) + 1

                driver = str(row.get("M2_latest_primary_risk_driver", "None")).strip()
                if driver and driver != "None":
                    driver_counts[driver] = driver_counts.get(driver, 0) + 1

                interv_priority = str(row.get("M2_latest_intervention_priority", "LOW")).strip()
                health_index = round(100.0 - risk_score, 2) if risk_score is not None else None

                area_km2 = round(float(row["area_km2"]), 2) if "area_km2" in row and pd.notna(row["area_km2"]) else None
                stream_len = round(float(row["Stream_Len_km"]), 2) if "Stream_Len_km" in row and pd.notna(row["Stream_Len_km"]) else 0.0
                drainage = round(float(row["Drain_Density"]), 3) if "Drain_Density" in row and pd.notna(row["Drain_Density"]) else 0.0
                max_strahler = int(row["Max_Strahler"]) if "Max_Strahler" in row and pd.notna(row["Max_Strahler"]) else 0

                props = {
                    "id": mws_id,
                    "MWS": mws_code,
                    "area_km2": area_km2,
                    "risk_score": risk_score,
                    "risk_category": risk_cat,
                    "health_index": health_index,
                    "primary_driver": driver,
                    "intervention_priority": interv_priority,
                    "forest_pct": round(float(row["Forest_pct"]), 2) if "Forest_pct" in row and pd.notna(row["Forest_pct"]) else 0.0,
                    "agriculture_pct": round(float(row["Agriculture_pct"]), 2) if "Agriculture_pct" in row and pd.notna(row["Agriculture_pct"]) else 0.0,
                    "water_pct": round(float(row["Water_pct"]), 2) if "Water_pct" in row and pd.notna(row["Water_pct"]) else 0.0,
                    "builtup_pct": round(float(row["Builtup_pct"]), 2) if "Builtup_pct" in row and pd.notna(row["Builtup_pct"]) else 0.0,
                    "barren_pct": round(float(row["Barren_pct"]), 2) if "Barren_pct" in row and pd.notna(row["Barren_pct"]) else 0.0,
                    "stream_len_km": stream_len,
                    "drainage_density": drainage,
                    "max_strahler": max_strahler,
                }

                self._mws_meta[mws_id] = props

                geom_json = row.geometry.__geo_interface__ if row.geometry is not None else None
                features.append({
                    "type": "Feature",
                    "geometry": geom_json,
                    "properties": props
                })

            self._risk_distribution = risk_counts
            self._primary_drivers = driver_counts

            self._mws_geojson = {
                "type": "FeatureCollection",
                "total_features": len(features),
                "risk_distribution": self._risk_distribution,
                "primary_drivers": self._primary_drivers,
                "features": features
            }

            # 2. Load Taluk Boundary GeoJSON
            if self._taluk_boundary_path.exists():
                boundary_gdf = gpd.read_file(self._taluk_boundary_path).to_crs("EPSG:4326")
                self._boundary_geojson = json.loads(boundary_gdf.to_json())

            logger.info(
                f"Loaded canonical GIS layer for {len(self._id_to_mws)} MWS. "
                f"Risk: {self._risk_distribution}, Drivers: {self._primary_drivers}"
            )
        except Exception as e:
            logger.error(f"Failed loading canonical GIS layers: {e}")

    def get_id_to_mws_map(self) -> Dict[str, str]:
        return self._id_to_mws

    def get_mws_to_id_map(self) -> Dict[str, str]:
        return self._mws_to_id

    def get_mws_meta(self, mws_id: str) -> Optional[Dict[str, Any]]:
        if mws_id in self._mws_meta:
            return self._mws_meta[mws_id]
        if mws_id in self._mws_to_id:
            return self._mws_meta[self._mws_to_id[mws_id]]
        return None

    def get_all_mws_meta(self) -> Dict[str, Dict[str, Any]]:
        return self._mws_meta

    def get_mws_geojson(self) -> Dict[str, Any]:
        return self._mws_geojson or {"type": "FeatureCollection", "features": [], "total_features": 0}

    def get_boundary_geojson(self) -> Dict[str, Any]:
        return self._boundary_geojson or {"type": "FeatureCollection", "features": []}

    def get_risk_distribution(self) -> Dict[str, int]:
        return self._risk_distribution

    def get_primary_drivers(self) -> Dict[str, int]:
        return self._primary_drivers
