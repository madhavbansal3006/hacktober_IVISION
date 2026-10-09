import json
from pathlib import Path
from typing import List, Optional, Dict, Any
import pandas as pd
import logging
import sys

from ..schemas import EvidenceItem, ProcessedPhotoResult, BatchUploadResponse

logger = logging.getLogger(__name__)

class GeoCodedAdapter:
    """
    Adapter for Geo-Coded field photo observations.
    Reads validated photo master CSV or results CSV when available.
    Returns honest no_data state when field batches have not yet run.
    Provides direct execution of authoritative Geo-Coded pipeline for image analysis.
    """
    def __init__(self, geo_dir: Optional[Path] = None):
        if geo_dir is None:
            base_dir = Path(__file__).resolve().parents[4]  # repo root
            geo_dir = base_dir / "geo_coded" / "GEO_CODED_IMAGES"
        self.geo_dir = Path(geo_dir).resolve()
        self.base_dir = self.geo_dir.parents[1]  # repo root

        # Candidate paths for master validated outputs
        self.candidate_paths = [
            self.geo_dir / "outputs" / "geo_coded_results.json",
            self.geo_dir / "outputs" / "geo_coded_results.csv",
            self.geo_dir / "12_GEO_CODED_IMAGES" / "Metadata" / "Photo_Master_Validated.csv",
            self.geo_dir / "data" / "Photo_Master_Validated.csv",
            self.base_dir / "data" / "Photo_Master_Validated.csv",
        ]
        self._items: List[EvidenceItem] = []
        self._analyzer = None
        self.load()

    def load(self) -> None:
        target_path = None
        for p in self.candidate_paths:
            if p.exists():
                target_path = p
                break

        if not target_path:
            logger.info("No field photo master CSV found; field evidence will report honest empty state until photos are processed.")
            return

        try:
            if target_path.suffix == ".json":
                with open(target_path, "r", encoding="utf-8") as jf:
                    rows = json.load(jf)
                self._items.clear()
                for row in rows:
                    item = self._row_to_evidence_item(row)
                    if item:
                        self._items.append(item)
                logger.info(f"Loaded {len(self._items)} field evidence records from {target_path}.")
                return

            df = pd.read_csv(target_path)
            self._items.clear()
            for _, row in df.iterrows():
                item = self._row_to_evidence_item(row)
                if item:
                    self._items.append(item)
            logger.info(f"Loaded {len(self._items)} field evidence records from {target_path}.")
        except Exception as e:
            logger.error(f"Failed parsing field evidence from {target_path}: {e}")

    def _row_to_evidence_item(self, row: Any) -> Optional[EvidenceItem]:
        try:
            image_id = str(row.get("image_id", "")) if pd.notna(row.get("image_id")) else None
            filename = str(row.get("filename", row.get("file_name", row.get("image_name", "unknown"))))
            lat = float(row["latitude"]) if pd.notna(row.get("latitude")) else None
            lon = float(row["longitude"]) if pd.notna(row.get("longitude")) else None
            mws_id = str(row.get("id", row.get("mws_id", row.get("micro_watershed_id", "")))) if pd.notna(row.get("id", row.get("mws_id", row.get("micro_watershed_id")))) else None
            mws_code = str(row.get("MWS", row.get("mws_code", ""))) if pd.notna(row.get("MWS", row.get("mws_code"))) else None
            lulc_cls = str(row.get("lulc_class", "")) if pd.notna(row.get("lulc_class")) else None
            lulc_val = int(row["lulc_value"]) if pd.notna(row.get("lulc_value")) else None
            coord_st = str(row.get("coordinate_status", "")) if pd.notna(row.get("coordinate_status")) else None
            study_st = str(row.get("boundary_status", row.get("study_area_status", ""))) if pd.notna(row.get("boundary_status", row.get("study_area_status"))) else None
            obs_st = str(row.get("observation_status", row.get("status", ""))) if pd.notna(row.get("observation_status", row.get("status"))) else None
            proc_st = str(row.get("processing_status", "")) if pd.notna(row.get("processing_status")) else None
            timestamp = str(row.get("timestamp", row.get("capture_datetime", row.get("processing_timestamp", "")))) if pd.notna(row.get("timestamp", row.get("capture_datetime", row.get("processing_timestamp")))) else None
            gps_src = str(row.get("gps_source", "")) if pd.notna(row.get("gps_source")) else None
            gps_acc = float(row["gps_accuracy_m"]) if pd.notna(row.get("gps_accuracy_m")) else None

            return EvidenceItem(
                image_id=image_id,
                filename=filename,
                latitude=lat,
                longitude=lon,
                id=mws_id,
                MWS=mws_code,
                lulc_class=lulc_cls,
                lulc_value=lulc_val,
                boundary_status=study_st,
                coordinate_status=coord_st,
                observation_status=obs_st,
                processing_status=proc_st,
                timestamp=timestamp,
                gps_source=gps_src,
                gps_accuracy_m=gps_acc,
                source="geocoded_pipeline",
                status="available"
            )
        except Exception as e:
            logger.warning(f"Error parsing row to EvidenceItem: {e}")
            return None

    def get_all(self) -> List[EvidenceItem]:
        return list(self._items)

    def get_by_image_id(self, image_id: str) -> Optional[EvidenceItem]:
        for item in self._items:
            if item.image_id == image_id:
                return item
        return None

    def get_by_watershed(self, mws_id: str) -> List[EvidenceItem]:
        target = mws_id.strip()
        return [
            item for item in self._items
            if (item.id and item.id.strip() == target) or (item.MWS and item.MWS.strip() == target)
        ]

    def _ensure_pipeline_imported(self):
        geo_str = str(self.geo_dir)
        if geo_str not in sys.path:
            sys.path.insert(0, geo_str)

    def get_pipeline_analyzer(self):
        if self._analyzer is None:
            try:
                from geo_coded.GEO_CODED_IMAGES.src.geo_lulc_analyzer import GeoLULCAnalyzer
            except ImportError:
                self._ensure_pipeline_imported()
                from src.geo_lulc_analyzer import GeoLULCAnalyzer
            self._analyzer = GeoLULCAnalyzer()
        return self._analyzer

    def analyze_single_image(self, image_path: Path | str, id_ledger: Optional[Any] = None) -> EvidenceItem:
        """
        Runs a single image through the authoritative Geo-Coded pipeline without
        altering core algorithms. Adds the resulting EvidenceItem to memory.
        """
        try:
            from geo_coded.GEO_CODED_IMAGES.src.image_analyzer import analyze_image
        except ImportError:
            self._ensure_pipeline_imported()
            from src.image_analyzer import analyze_image

        analyzer = self.get_pipeline_analyzer()
        result = analyze_image(Path(image_path), analyzer, id_ledger=id_ledger)

        item = self._result_to_evidence_item(result)

        # Replace existing item with same image_id if present, otherwise append
        if item.image_id:
            for idx, existing in enumerate(self._items):
                if existing.image_id == item.image_id:
                    self._items[idx] = item
                    return item
        self._items.append(item)
        return item

    def _result_to_evidence_item(self, result: Any) -> EvidenceItem:
        lulc_cls = result.lulc_class
        lulc_val = result.lulc_value
        if not lulc_cls and result.micro_watershed_id:
            try:
                from .model1_adapter import Model1Adapter
                m1 = Model1Adapter()
                m1_rec = m1.get_by_id(result.micro_watershed_id)
                if m1_rec and m1_rec.dominant_class:
                    lulc_cls = m1_rec.dominant_class
                    class_vals = {"Forest": 1, "Agriculture": 2, "Water": 3, "Built-up": 4, "Barren": 5}
                    lulc_val = class_vals.get(lulc_cls, lulc_val)
            except Exception:
                pass

        return EvidenceItem(
            image_id=result.image_id,
            filename=result.image_name,
            latitude=result.latitude,
            longitude=result.longitude,
            id=result.micro_watershed_id,
            MWS=result.mws_code,
            lulc_class=lulc_cls,
            lulc_value=lulc_val,
            boundary_status=result.study_area_status,
            coordinate_status=result.coordinate_status,
            observation_status=result.status,
            timestamp=result.capture_datetime or result.processing_timestamp,
            gps_source=result.gps_source,
            gps_accuracy_m=result.gps_accuracy_m,
            source="geocoded_pipeline",
            status="available"
        )

    def upload_and_process_photos(self, files: List[tuple[str, bytes]]) -> BatchUploadResponse:
        """
        Accepts a batch of uploaded files (filename, file_bytes), validates format/size,
        runs each through the authoritative Geo-Coded pipeline, persists outputs to
        flat files, updates the in-memory ledger, and returns a comprehensive batch summary.
        """
        self._ensure_pipeline_imported()
        try:
            from geo_coded.GEO_CODED_IMAGES.src.image_analyzer import analyze_image
            from geo_coded.GEO_CODED_IMAGES.src.image_id_ledger import ImageIdLedger
            from geo_coded.GEO_CODED_IMAGES.src import config, io_writer, teammate_metadata_writer
            from geo_coded.GEO_CODED_IMAGES.src.schema import GeoCodedResult
        except ImportError:
            from src.image_analyzer import analyze_image
            from src.image_id_ledger import ImageIdLedger
            from src import config, io_writer, teammate_metadata_writer
            from src.schema import GeoCodedResult

        analyzer = self.get_pipeline_analyzer()
        ledger = ImageIdLedger(config.IMAGE_ID_LEDGER_PATH)

        upload_dir = self.geo_dir / "data" / "uploads"
        upload_dir.mkdir(parents=True, exist_ok=True)

        allowed_extensions = {".jpg", ".jpeg", ".png"}

        processed_results: List[ProcessedPhotoResult] = []
        new_geo_results: List[GeoCodedResult] = []

        valid_geotagged_count = 0
        inside_boundary_count = 0
        mws_resolved_count = 0
        rejected_missing_gps_count = 0
        outside_boundary_count = 0
        mws_unresolved_count = 0
        failed_or_invalid_count = 0

        for filename, file_bytes in files:
            safe_name = Path(filename).name
            ext = Path(filename).suffix.lower()

            if ext not in allowed_extensions:
                failed_or_invalid_count += 1
                processed_results.append(ProcessedPhotoResult(
                    filename=safe_name,
                    status="INVALID_FILE_TYPE",
                    state_category="rejected",
                    error_reason=f"Unsupported format '{ext}'. Only JPG, JPEG, and PNG are supported."
                ))
                continue

            if len(file_bytes) == 0:
                failed_or_invalid_count += 1
                processed_results.append(ProcessedPhotoResult(
                    filename=safe_name,
                    status="EMPTY_FILE",
                    state_category="rejected",
                    error_reason="File is empty (0 bytes)."
                ))
                continue

            if len(file_bytes) > 25 * 1024 * 1024:
                failed_or_invalid_count += 1
                processed_results.append(ProcessedPhotoResult(
                    filename=safe_name,
                    status="FILE_TOO_LARGE",
                    state_category="rejected",
                    error_reason="File exceeds maximum allowed size of 25MB."
                ))
                continue

            # Save to upload directory
            dest_path = upload_dir / safe_name
            dest_path.write_bytes(file_bytes)

            # Analyze using existing Geo-Coded pipeline
            geo_res = analyze_image(dest_path, analyzer, id_ledger=ledger)
            new_geo_results.append(geo_res)

            status = geo_res.status
            is_valid_geo = status not in ("NO_GPS", "MALFORMED_GPS", "INVALID_COORDINATE", "ERROR") and geo_res.latitude is not None and geo_res.longitude is not None
            is_inside = geo_res.inside_study_area is True or geo_res.study_area_status in ("INSIDE", "BOUNDARY_REVIEW")
            is_mws = bool(geo_res.micro_watershed_id or geo_res.mws_code)

            if is_valid_geo:
                valid_geotagged_count += 1
            if is_inside:
                inside_boundary_count += 1
            if is_mws:
                mws_resolved_count += 1

            if status in ("NO_GPS", "MALFORMED_GPS", "INVALID_COORDINATE"):
                state_cat = "missing_gps"
                rejected_missing_gps_count += 1
                error_msg = "No GPS EXIF metadata found." if status == "NO_GPS" else (geo_res.error_reason or "Invalid GPS EXIF metadata.")
            elif status == "OUTSIDE_STUDY_AREA":
                state_cat = "outside_boundary"
                outside_boundary_count += 1
                error_msg = "Photo is outside the Shiggaon Basin."
            elif status == "NO_WATERSHED_MATCH":
                state_cat = "mws_unresolved"
                mws_unresolved_count += 1
                error_msg = "GPS location could not be matched to a micro-watershed."
            elif status in ("OK", "NODATA_PIXEL", "OUTSIDE_RASTER_EXTENT") and is_inside and is_mws:
                state_cat = "processed"
                error_msg = None
            elif status == "ERROR":
                state_cat = "error"
                failed_or_invalid_count += 1
                error_msg = geo_res.error_reason or "Error during processing."
            else:
                state_cat = "rejected"
                failed_or_invalid_count += 1
                error_msg = geo_res.error_reason or "Photo rejected."

            # Check if Model 1 can enrich dominant LULC class
            lulc_cls = geo_res.lulc_class
            lulc_val = geo_res.lulc_value
            if not lulc_cls and geo_res.micro_watershed_id:
                try:
                    from .model1_adapter import Model1Adapter
                    m1 = Model1Adapter()
                    m1_rec = m1.get_by_id(geo_res.micro_watershed_id)
                    if m1_rec and m1_rec.dominant_class:
                        lulc_cls = m1_rec.dominant_class
                        class_vals = {"Forest": 1, "Agriculture": 2, "Water": 3, "Built-up": 4, "Barren": 5}
                        lulc_val = class_vals.get(lulc_cls, lulc_val)
                except Exception:
                    pass

            processed_results.append(ProcessedPhotoResult(
                filename=geo_res.image_name,
                status=geo_res.status,
                state_category=state_cat,
                error_reason=error_msg,
                image_id=geo_res.image_id,
                latitude=geo_res.latitude,
                longitude=geo_res.longitude,
                coordinate_status=geo_res.coordinate_status,
                study_area_status=geo_res.study_area_status,
                micro_watershed_id=geo_res.micro_watershed_id,
                mws_code=geo_res.mws_code,
                lulc_class=lulc_cls,
                lulc_value=lulc_val,
                timestamp=geo_res.capture_datetime or geo_res.processing_timestamp
            ))

            # Only add to active observation ledger if valid geotagged, inside basin, and resolved to an MWS!
            if state_cat == "processed" and is_valid_geo and is_inside and is_mws:
                item = self._result_to_evidence_item(geo_res)
                item.lulc_class = lulc_cls
                item.lulc_value = lulc_val
                # Update memory items (replace existing if same image_id or filename)
                replaced = False
                for idx, existing in enumerate(self._items):
                    if (item.image_id and existing.image_id == item.image_id) or existing.filename == item.filename:
                        self._items[idx] = item
                        replaced = True
                        break
                if not replaced:
                    self._items.append(item)

        # Flat-file persistence
        if new_geo_results:
            try:
                all_results_map: Dict[str, GeoCodedResult] = {}
                json_path = config.DEFAULT_JSON_PATH
                if json_path.exists():
                    with open(json_path, "r", encoding="utf-8") as jf:
                        saved_list = json.load(jf)
                    for item_d in saved_list:
                        try:
                            gr = GeoCodedResult(**item_d)
                            k = gr.image_id or gr.image_name
                            all_results_map[k] = gr
                        except Exception:
                            pass
                for gr in new_geo_results:
                    k = gr.image_id or gr.image_name
                    all_results_map[k] = gr

                merged = list(all_results_map.values())
                io_writer.write_outputs(merged, csv_path=config.DEFAULT_CSV_PATH, json_path=config.DEFAULT_JSON_PATH)
                teammate_metadata_writer.write_photo_master_validated_csv(merged, path=config.PHOTO_MASTER_VALIDATED_CSV)
            except Exception as e:
                logger.error(f"Error persisting geo-coded flat files: {e}")

        total_rec = len(files)
        total_proc = len(new_geo_results)
        summary_msg = f"{total_proc} photo{'s' if total_proc != 1 else ''} processed · {valid_geotagged_count} valid · {inside_boundary_count} inside boundary · {mws_resolved_count} MWS resolved"

        return BatchUploadResponse(
            total_received=total_rec,
            total_processed=total_proc,
            valid_geotagged=valid_geotagged_count,
            inside_boundary=inside_boundary_count,
            mws_resolved=mws_resolved_count,
            rejected_missing_gps=rejected_missing_gps_count,
            outside_boundary=outside_boundary_count,
            mws_unresolved=mws_unresolved_count,
            failed_or_invalid=failed_or_invalid_count,
            summary_message=summary_msg,
            results=processed_results,
            ledger=self.get_all(),
            status="available"
        )
