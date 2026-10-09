import json
from pathlib import Path
from typing import Dict, Optional, List, Any
from collections import Counter
import pandas as pd
import logging
from ..schemas import WatershedLULC, LULCSummary, LULCConfidenceStats, LULCModelMetadata

logger = logging.getLogger(__name__)

class Model1Adapter:
    """
    Adapter for Model 1 LULC outputs.
    Reads micro_watershed_lulc_statistics.csv and metadata.json,
    maps the internal naming so that:
      id  <- internal_id (g_mws.*)
      MWS <- micro_watershed_id (4D4F*)
    """
    def __init__(self, stats_csv_path: Optional[Path] = None, metadata_path: Optional[Path] = None):
        base_dir = Path(__file__).resolve().parents[4]  # repo root
        if stats_csv_path is None:
            stats_csv_path = base_dir / "model1" / "model1_lulc" / "outputs" / "micro_watershed_lulc_statistics.csv"
        if metadata_path is None:
            metadata_path = base_dir / "model1" / "model1_lulc" / "outputs" / "metadata.json"
        
        self.stats_csv_path = Path(stats_csv_path)
        self.metadata_path = Path(metadata_path)
        self._data: Dict[str, WatershedLULC] = {}
        self._mws_to_id: Dict[str, str] = {}
        self._coverage_distribution: Dict[str, int] = {}
        self._summary: Optional[LULCSummary] = None
        self.load()

    def load(self) -> None:
        if not self.stats_csv_path.exists():
            logger.warning(f"Model 1 stats CSV not found at {self.stats_csv_path}")
            return

        try:
            df = pd.read_csv(self.stats_csv_path)
            for _, row in df.iterrows():
                mws_id = str(row["internal_id"]).strip()
                mws_code = str(row["micro_watershed_id"]).strip()

                lulc = WatershedLULC(
                    id=mws_id,
                    MWS=mws_code,
                    forest_pct=float(row.get("forest_percent", 0.0)),
                    agriculture_pct=float(row.get("agriculture_percent", 0.0)),
                    water_pct=float(row.get("water_percent", 0.0)),
                    builtup_pct=float(row.get("builtup_percent", 0.0)),
                    barren_pct=float(row.get("barren_percent", 0.0)),
                    coverage_category=str(row.get("coverage_category", "UNKNOWN")),
                    coverage_pct=float(row.get("pct_of_watershed_within_raster_extent", 0.0)) if pd.notna(row.get("pct_of_watershed_within_raster_extent")) else None,
                    valid_pixel_count=int(row.get("valid_pixel_count", 0)),
                    dominant_class=str(row.get("dominant_class", "Unknown")),
                    status="available"
                )
                self._data[mws_id] = lulc
                self._mws_to_id[mws_code] = mws_id

            cat_counts = Counter(item.coverage_category for item in self._data.values())
            self._coverage_distribution = dict(cat_counts)
            logger.info(f"Loaded LULC statistics for {len(self._data)} micro-watersheds from Model 1. Coverage: {self._coverage_distribution}")
        except Exception as e:
            logger.error(f"Failed loading Model 1 LULC stats: {e}")

        # Load metadata.json
        full_scene_dist: Dict[str, float] = {
            "Agriculture": 62.65,
            "Forest": 20.17,
            "Built-up": 14.76,
            "Barren": 1.70,
            "Water": 0.73
        }
        conf_stats = LULCConfidenceStats(
            mean_confidence=78.3,
            high_confidence_pct=59.8,
            medium_confidence_pct=33.1,
            low_confidence_pct=7.0
        )
        model_meta = LULCModelMetadata(
            classifier="RandomForestClassifier",
            resolution_m=10.0,
            crs="EPSG:32643",
            bands_used=["B02", "B03", "B04", "B08", "B11"],
            indices=["NDVI", "NDWI", "NDBI", "BSI"],
            accuracy=0.805,
            macro_f1=0.807,
            weighted_f1=0.807
        )

        if self.metadata_path.exists():
            try:
                with open(self.metadata_path, "r", encoding="utf-8") as f:
                    meta = json.load(f)
                
                if "full_scene_predicted_class_percent" in meta:
                    full_scene_dist = {k: float(v) for k, v in meta["full_scene_predicted_class_percent"].items()}
                
                if "confidence_stats" in meta:
                    c = meta["confidence_stats"]
                    conf_stats = LULCConfidenceStats(
                        mean_confidence=round(float(c.get("mean_confidence", 0.783)) * 100, 1) if float(c.get("mean_confidence", 0.783)) < 1.0 else round(float(c.get("mean_confidence", 78.3)), 1),
                        high_confidence_pct=round(float(c.get("high_confidence_pct", 59.8)), 1),
                        medium_confidence_pct=round(float(c.get("medium_confidence_pct", 33.1)), 1),
                        low_confidence_pct=round(float(c.get("low_confidence_pct", 7.0)), 1)
                    )

                if "evaluation_metrics" in meta:
                    em = meta["evaluation_metrics"]
                    model_meta = LULCModelMetadata(
                        classifier=str(meta.get("classifier", "RandomForestClassifier")),
                        resolution_m=float(meta.get("resolution_m", 10.0)),
                        crs=str(meta.get("crs", "EPSG:32643")),
                        bands_used=list(meta.get("bands_used", ["B02", "B03", "B04", "B08", "B11"])),
                        indices=list(meta.get("indices", ["NDVI", "NDWI", "NDBI", "BSI"])),
                        accuracy=round(float(em.get("accuracy", 0.805)), 3),
                        macro_f1=round(float(em.get("macro_f1", 0.807)), 3),
                        weighted_f1=round(float(em.get("weighted_f1", 0.807)), 3)
                    )
            except Exception as e:
                logger.error(f"Failed parsing Model 1 metadata.json: {e}")

        self._summary = LULCSummary(
            total_watersheds=len(self._data),
            coverage_distribution=self._coverage_distribution,
            full_scene_distribution=full_scene_dist,
            confidence_stats=conf_stats,
            model_metadata=model_meta,
            status="available" if len(self._data) > 0 else "no_data"
        )

    def get_by_id(self, mws_id: str) -> Optional[WatershedLULC]:
        if mws_id in self._data:
            return self._data[mws_id]
        if mws_id in self._mws_to_id:
            return self._data[self._mws_to_id[mws_id]]
        return None

    def get_all(self) -> Dict[str, WatershedLULC]:
        return self._data

    def get_lulc_summary(self) -> LULCSummary:
        if self._summary is None:
            return LULCSummary(
                total_watersheds=0,
                coverage_distribution={},
                full_scene_distribution={},
                confidence_stats=LULCConfidenceStats(
                    mean_confidence=0.0,
                    high_confidence_pct=0.0,
                    medium_confidence_pct=0.0,
                    low_confidence_pct=0.0
                ),
                model_metadata=LULCModelMetadata(
                    classifier="RandomForestClassifier",
                    resolution_m=10.0,
                    crs="EPSG:32643",
                    bands_used=[],
                    indices=[],
                    accuracy=0.0,
                    macro_f1=0.0,
                    weighted_f1=0.0
                ),
                status="no_data"
            )
        return self._summary

