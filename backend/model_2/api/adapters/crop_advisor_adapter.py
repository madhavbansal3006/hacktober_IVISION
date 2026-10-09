import logging
from datetime import datetime, timezone
from typing import Optional, Dict, List, Any, Tuple
from pathlib import Path

from ..schemas import (
    CropRecommendation,
    CropCaution,
    WatershedWaterSummary,
    WatershedCropAdvisory,
)
from .gis_adapter import GISAdapter
from .model1_adapter import Model1Adapter
from .model2_adapter import Model2Adapter
from .water_quality_adapter import WaterQualityAdapter

logger = logging.getLogger("CropAdvisorAdapter")

# Authoritative Regional Crop Catalog for Shiggaon Taluk, Haveri District (Agro-Climatic Zone 8 / Northern Transition Zone)
REGIONAL_CROPS = [
    {
        "id": "byadgi_chilli",
        "crop_name": "Byadgi Chilli",
        "local_name": "ಬ್ಯಾಡಗಿ ಮೆಣಸಿನಕಾಯಿ (GI Tag)",
        "category": "High-Value Cash Crop / Spice",
        "season": "Kharif / Late Kharif",
        "base_water_min_mm": 500,
        "base_water_max_mm": 650,
        "water_tier": "MODERATE",
        "min_water_stress": 10,
        "max_water_stress": 68,
        "optimal_water_stress": (30, 52),
        "max_flood_risk": 55,
        "optimal_ph_range": (6.2, 7.8),
        "max_tds": 850,
        "max_slope": 8.0,
        "salinity_tolerance": "Moderate",
        "recommended_irrigation": "Drip irrigation with fertigation & plastic mulching",
        "key_advantages": [
            "GI-tagged signature commercial crop of Haveri district with high market price premium",
            "High oleoresin and low pungency suited for food extraction and export",
            "Responds excellently to micro-drip fertigation with 40% water savings"
        ],
        "risk_management": "Use raised beds to prevent damping-off in case of erratic runoff; avoid overhead sprinkler.",
        "stress_rationale_template": "Suited for current catchment moisture ({water_stress}/100 stress); drip irrigation optimizes yield without straining local water budget."
    },
    {
        "id": "sorghum_jowar",
        "crop_name": "Sorghum (Jowar / Maldandi)",
        "local_name": "ಜೋಳ (Maldandi M35-1)",
        "category": "Cereals & Millets",
        "season": "Kharif / Rabi",
        "base_water_min_mm": 350,
        "base_water_max_mm": 450,
        "water_tier": "LOW",
        "min_water_stress": 30,
        "max_water_stress": 90,
        "optimal_water_stress": (50, 75),
        "max_flood_risk": 60,
        "optimal_ph_range": (6.0, 8.5),
        "max_tds": 1250,
        "max_slope": 10.0,
        "salinity_tolerance": "High",
        "recommended_irrigation": "Protective / deficit furrow irrigation at panicle initiation & grain filling",
        "key_advantages": [
            "Extreme drought resilience with deep root system and waxy leaf cuticle",
            "Tolerates saline/high-TDS water where other crops fail",
            "Dual-purpose: essential nutritious food grain + vital drought-season livestock fodder"
        ],
        "risk_management": "Practice broad bed and furrow (BBF) planting to conserve in-situ rainwater; sow early post-monsoon.",
        "stress_rationale_template": "Ideal champion crop for high water stress ({water_stress}/100); thrives under water deficit and tolerates moderate salinity."
    },
    {
        "id": "pearl_millet_bajra",
        "crop_name": "Pearl Millet (Bajra / Sajje)",
        "local_name": "ಸಜ್ಜೆ (Bajra / Sajje)",
        "category": "Cereals & Millets",
        "season": "Kharif / Summer",
        "base_water_min_mm": 250,
        "base_water_max_mm": 350,
        "water_tier": "VERY_LOW",
        "min_water_stress": 45,
        "max_water_stress": 95,
        "optimal_water_stress": (60, 85),
        "max_flood_risk": 45,
        "optimal_ph_range": (6.5, 8.4),
        "max_tds": 1100,
        "max_slope": 12.0,
        "salinity_tolerance": "High",
        "recommended_irrigation": "Rainfed; 1-2 life-saving sprinkler or furrow irrigations during prolonged dry spells",
        "key_advantages": [
            "Lowest water footprint among major food cereals (<300 mm total requirement)",
            "Climate-smart C4 photosynthesis with high temperature tolerance up to 42°C",
            "Short duration (75-85 days), fits tight rain windows"
        ],
        "risk_management": "Avoid waterlogged lowlands; ensure free surface drainage to protect shallow seedbeds.",
        "stress_rationale_template": "Top recommendation under critical water deficit ({water_stress}/100); safeguards farm income with minimal irrigation demand."
    },
    {
        "id": "finger_millet_ragi",
        "crop_name": "Finger Millet (Ragi)",
        "local_name": "ರಾಗಿ (Ragi)",
        "category": "Cereals & Millets",
        "season": "Kharif",
        "base_water_min_mm": 350,
        "base_water_max_mm": 450,
        "water_tier": "LOW",
        "min_water_stress": 25,
        "max_water_stress": 80,
        "optimal_water_stress": (45, 68),
        "max_flood_risk": 65,
        "optimal_ph_range": (5.5, 8.0),
        "max_tds": 950,
        "max_slope": 10.0,
        "salinity_tolerance": "Moderate",
        "recommended_irrigation": "Rainfed with supplemental furrow irrigation at tillering and flowering",
        "key_advantages": [
            "Rich in calcium, fiber, and micronutrients; steady local market demand",
            "Hardy root system binds topsoil on gentle-to-moderate watershed slopes",
            "Stores for years without chemical treatment, enhancing household food security"
        ],
        "risk_management": "Use line sowing or Guli ragi transplanting method to maximize moisture utilization.",
        "stress_rationale_template": "Robust grain choice for moderate-to-high water stress ({water_stress}/100); low water footprint and highly climate-resilient."
    },
    {
        "id": "chickpea_bengalgram",
        "crop_name": "Chickpea / Bengal Gram (Chana)",
        "local_name": "ಕಡಲೆ (JG-11 / Annigeri-1)",
        "category": "Pulses & Legumes",
        "season": "Rabi (Post-Monsoon)",
        "base_water_min_mm": 250,
        "base_water_max_mm": 350,
        "water_tier": "LOW",
        "min_water_stress": 30,
        "max_water_stress": 82,
        "optimal_water_stress": (48, 70),
        "max_flood_risk": 40,
        "optimal_ph_range": (6.5, 8.2),
        "max_tds": 750,
        "max_slope": 7.0,
        "salinity_tolerance": "Moderate",
        "recommended_irrigation": "Residual soil moisture; one critical pod-initiation irrigation via micro-sprinkler",
        "key_advantages": [
            "Fixes 40-50 kg atmospheric nitrogen per hectare, naturally restoring soil fertility",
            "Consumes minimal irrigation water by tapping deep residual soil moisture",
            "High protein pulse with guaranteed minimum support price (MSP)"
        ],
        "risk_management": "Strictly avoid waterlogging; seed treatment with Trichoderma against Fusarium wilt.",
        "stress_rationale_template": "Optimal post-monsoon pulse for current water stress ({water_stress}/100); thrives on residual profile moisture."
    },
    {
        "id": "pigeonpea_tur",
        "crop_name": "Pigeonpea / Red Gram (Tur)",
        "local_name": "ತೊಗರಿ (TS-3R / GRG-811)",
        "category": "Pulses & Legumes",
        "season": "Kharif (Long Duration)",
        "base_water_min_mm": 400,
        "base_water_max_mm": 520,
        "water_tier": "LOW_MODERATE",
        "min_water_stress": 25,
        "max_water_stress": 78,
        "optimal_water_stress": (42, 65),
        "max_flood_risk": 50,
        "optimal_ph_range": (6.5, 8.2),
        "max_tds": 800,
        "max_slope": 8.0,
        "salinity_tolerance": "Moderate",
        "recommended_irrigation": "Protective irrigation at pod formation if terminal drought occurs",
        "key_advantages": [
            "Deep taproot (>2 meters) breaks plow pan and extracts subsoil water",
            "Superb intercropping partner with Jowar or Bajra (1:2 ratio)",
            "Heavy leaf fall provides green manure mulching to soil"
        ],
        "risk_management": "Nip apical buds at 45-50 days to stimulate secondary branching and flowering.",
        "stress_rationale_template": "Deep-rooting pulse perfectly matched for water stress score {water_stress}/100; stabilizes farm revenue during dry spells."
    },
    {
        "id": "cotton_bt",
        "crop_name": "Cotton (Bt / Medium-Long Staple)",
        "local_name": "ಹತ್ತಿ (Cotton)",
        "category": "Commercial Fiber Crop",
        "season": "Kharif",
        "base_water_min_mm": 600,
        "base_water_max_mm": 750,
        "water_tier": "MODERATE",
        "min_water_stress": 15,
        "max_water_stress": 62,
        "optimal_water_stress": (30, 52),
        "max_flood_risk": 55,
        "optimal_ph_range": (6.5, 8.5),
        "max_tds": 1200,
        "max_slope": 6.0,
        "salinity_tolerance": "High",
        "recommended_irrigation": "Alternate furrow irrigation or drip systems with mulching",
        "key_advantages": [
            "High commercial value with ready local ginning infrastructure in Haveri/Ranebennur",
            "Deep taproot tolerates moderate soil salinity and intermittent water deficits",
            "High yield when supported with targeted micro-irrigation at boll formation"
        ],
        "risk_management": "Ensure adequate soil drainage; monitor sucking pests using integrated pest management.",
        "stress_rationale_template": "Sustainable cash crop for watershed stress score {water_stress}/100; strong root architecture withstands moderate dry periods."
    },
    {
        "id": "maize_corn",
        "crop_name": "Maize (Corn / Hybrid)",
        "local_name": "ಮೆಕ್ಕೆಜೋಳ (Hybrid Maize)",
        "category": "Cereals & Feed",
        "season": "Kharif / Rabi",
        "base_water_min_mm": 500,
        "base_water_max_mm": 700,
        "water_tier": "MODERATE",
        "min_water_stress": 10,
        "max_water_stress": 55,
        "optimal_water_stress": (25, 45),
        "max_flood_risk": 58,
        "optimal_ph_range": (6.0, 7.8),
        "max_tds": 850,
        "max_slope": 6.0,
        "salinity_tolerance": "Moderate",
        "recommended_irrigation": "Furrow irrigation every 10-12 days; ensure moisture at critical tasseling/silking",
        "key_advantages": [
            "Rapid biomass generation with high grain yield per unit area",
            "Huge industrial demand from starch and poultry feed manufacturers",
            "Fits well in crop rotation before Rabi pulses"
        ],
        "risk_management": "Do not allow water stress during tasseling; ridge and furrow planting prevents both drought shock and root rot.",
        "stress_rationale_template": "Viable when water stress is controlled ({water_stress}/100); requires reliable irrigation scheduling during flowering."
    },
    {
        "id": "groundnut_peanut",
        "crop_name": "Groundnut (Peanut)",
        "local_name": "ಕಡಲೆಕಾಯಿ (TMV-2 / GPBD-4)",
        "category": "Oilseeds & Legumes",
        "season": "Kharif / Summer",
        "base_water_min_mm": 450,
        "base_water_max_mm": 580,
        "water_tier": "MODERATE",
        "min_water_stress": 15,
        "max_water_stress": 58,
        "optimal_water_stress": (28, 48),
        "max_flood_risk": 45,
        "optimal_ph_range": (6.0, 7.5),
        "max_tds": 650,
        "max_slope": 5.0,
        "salinity_tolerance": "Low-Moderate",
        "recommended_irrigation": "Sprinkler irrigation at pegging and pod-filling stages",
        "key_advantages": [
            "High-value edible oilseed + nutritious haulm fodder for livestock",
            "Enhances soil structure and fixes atmospheric nitrogen",
            "Rust-resistant varieties available from UAS Dharwad"
        ],
        "risk_management": "Apply gypsum (200 kg/ha) at flowering for pod filling; avoid saline or heavy crusting soils.",
        "stress_rationale_template": "Good fit for moderate moisture regimes ({water_stress}/100 stress); sprinkler irrigation maximizes pod recovery."
    },
    {
        "id": "soybean",
        "crop_name": "Soybean",
        "local_name": "ಸೋಯಾಬೀನ್ (JS-335 / DSb-21)",
        "category": "Oilseeds & Legumes",
        "season": "Kharif",
        "base_water_min_mm": 450,
        "base_water_max_mm": 600,
        "water_tier": "MODERATE",
        "min_water_stress": 15,
        "max_water_stress": 56,
        "optimal_water_stress": (25, 46),
        "max_flood_risk": 50,
        "optimal_ph_range": (6.2, 7.6),
        "max_tds": 750,
        "max_slope": 5.0,
        "salinity_tolerance": "Moderate",
        "recommended_irrigation": "Supplemental irrigation if dry spell exceeds 15 days during pod fill",
        "key_advantages": [
            "Dual revenue: high oil content (20%) + rich protein meal (40%)",
            "Early maturity (90-95 days) leaves time for a second Rabi crop",
            "Improves physical properties of black soils"
        ],
        "risk_management": "Use broad bed furrow (BBF) to prevent standing water while retaining rainwater.",
        "stress_rationale_template": "Balanced Kharif oilseed for moderate water stress ({water_stress}/100); best when rainfall anomaly is near baseline."
    },
    {
        "id": "pomegranate_horticulture",
        "crop_name": "Pomegranate (Bhagwa)",
        "local_name": "ದಾಳಿಂಬೆ (Bhagwa)",
        "category": "Dryland Horticulture",
        "season": "Perennial / Mrig Bahar",
        "base_water_min_mm": 350,
        "base_water_max_mm": 500,
        "water_tier": "LOW_MODERATE",
        "min_water_stress": 20,
        "max_water_stress": 75,
        "optimal_water_stress": (35, 62),
        "max_flood_risk": 40,
        "optimal_ph_range": (6.5, 8.5),
        "max_tds": 1200,
        "max_slope": 12.0,
        "salinity_tolerance": "High",
        "recommended_irrigation": "Precision drip irrigation (10-15 L/day/tree) with fertigation",
        "key_advantages": [
            "Thrives on sloping, gravelly soils and semi-arid micro-climates",
            "High drought and salinity tolerance; handles high-TDS irrigation water",
            "Exceptional economic return per cubic meter of water used"
        ],
        "risk_management": "Bacteriosis management with copper sprays; ensure strict root drainage.",
        "stress_rationale_template": "Premier horticultural choice for sloping terrain with water stress {water_stress}/100; highest economic return per drop of water."
    },
    {
        "id": "paddy_flood_lowland",
        "crop_name": "Paddy / Rice (Wetland / Flood Tolerant)",
        "local_name": "ಭತ್ತ (Swarna-Sub1 / Intan)",
        "category": "Cereals & Lowland Wetland",
        "season": "Kharif (Monsoon)",
        "base_water_min_mm": 1100,
        "base_water_max_mm": 1400,
        "water_tier": "VERY_HIGH",
        "min_water_stress": 0,
        "max_water_stress": 38,
        "optimal_water_stress": (10, 28),
        "max_flood_risk": 95,
        "optimal_ph_range": (5.5, 7.2),
        "max_tds": 600,
        "max_slope": 3.0,
        "salinity_tolerance": "Low-Moderate",
        "recommended_irrigation": "Alternate Wetting and Drying (AWD) or System of Rice Intensification (SRI)",
        "key_advantages": [
            "Utilizes excess streamflow and flood water in drainage valley bottoms",
            "Tolerates temporary submersion with Sub1 gene cultivars",
            "Staple cereal with established local mills"
        ],
        "risk_management": "Transition from continuous flooding to Alternate Wetting & Drying (AWD) to cut water use by 30%.",
        "stress_rationale_template": "Recommended strictly in low-lying valley bottoms with low water stress ({water_stress}/100) or high seasonal runoff."
    },
]

# High-water / High-risk crops requiring explicit caution flags under water stress
CAUTION_CROP_REGISTRY = [
    {
        "crop_name": "Sugarcane (ಕಬ್ಬು)",
        "critical_water_stress_threshold": 42.0,
        "water_needed_mm": "1,800 - 2,500 mm/year",
        "depletion_impact": "Severe groundwater depletion, aquifer drawdown, and water table collapse for downstream farmers.",
        "alternative_suggestion": "Replace with Sorghum (Jowar) or Byadgi Chilli with precision drip systems."
    },
    {
        "crop_name": "Paddy under Flood Irrigation (ಸಾಂಪ್ರದಾಯಿಕ ಭತ್ತ)",
        "critical_water_stress_threshold": 45.0,
        "water_needed_mm": "1,200 - 1,500 mm",
        "depletion_impact": "Massive percolation and evaporative water loss under high water stress; rapid reservoir drying.",
        "alternative_suggestion": "Switch to Pearl Millet (Bajra), Maize on raised beds, or pulses."
    },
    {
        "crop_name": "Banana / Cavendish (ಬಾಳೆ)",
        "critical_water_stress_threshold": 48.0,
        "water_needed_mm": "1,500 - 2,200 mm",
        "depletion_impact": "Continuous high transpiration demands deplete farm ponds and shallow borewells rapidly.",
        "alternative_suggestion": "Opt for Pomegranate, Guava, or Tur (Pigeonpea) with drip fertigation."
    }
]


class CropAdvisorAdapter:
    """
    Agro-Hydrological Crop Intelligence & Recommendation Adapter for Shiggaon Basin.
    Evaluates micro-watershed water stress, flood risk, rainfall anomaly, water quality (WQI, TDS, pH),
    slope, and land cover to deliver calibrated crop suggestions and water conservation advisories.
    """

    def __init__(
        self,
        gis_adapter: Optional[GISAdapter] = None,
        model1_adapter: Optional[Model1Adapter] = None,
        model2_adapter: Optional[Model2Adapter] = None,
        water_quality_adapter: Optional[WaterQualityAdapter] = None,
    ):
        self.gis_adapter = gis_adapter or GISAdapter()
        self.model1_adapter = model1_adapter or Model1Adapter()
        self.model2_adapter = model2_adapter or Model2Adapter()
        self.water_quality_adapter = water_quality_adapter or WaterQualityAdapter(gis_adapter=self.gis_adapter)
        logger.info("Initialized CropAdvisorAdapter with GIS, Model 1, Model 2, and Water Quality integration.")

    def _resolve_mws(self, identifier: str) -> Optional[Tuple[str, str]]:
        id_to_mws = self.gis_adapter.get_id_to_mws_map()
        mws_to_id = self.gis_adapter.get_mws_to_id_map()

        if identifier in id_to_mws:
            return identifier, id_to_mws[identifier]
        elif identifier in mws_to_id:
            return mws_to_id[identifier], identifier
        return None

    def get_crop_advisory(self, identifier: str) -> Optional[WatershedCropAdvisory]:
        """
        Generates calibrated crop recommendations and water management advisories
        for a specified micro-watershed.
        """
        resolved = self._resolve_mws(identifier)
        if not resolved:
            return None

        actual_id, actual_mws = resolved

        # 1. Fetch physical and environmental attributes
        risk = self.model2_adapter.get_risk(actual_id)
        features = self.model2_adapter.get_features(actual_id) or {}
        lulc = self.model1_adapter.get_by_id(actual_id)
        wq = self.water_quality_adapter.get_mws_reading(actual_id)

        # Baseline parameters
        water_stress = float(risk.water_stress_score if risk else 50.0)
        flood_risk = float(risk.flood_risk_score if risk else 40.0)
        final_risk = float(risk.final_risk_score if risk else 50.0)

        rainfall_mm = features.get("rainfall_mm")
        rainfall_anomaly = features.get("rainfall_anomaly")
        slope_mean = float(features.get("slope_mean") or 5.0)
        elevation_mean = float(features.get("elevation_mean") or 600.0)
        drainage_density = float(features.get("drainage_density") or 0.2)

        # Water quality parameters
        wqi = float(wq.wqi if wq else 70.0)
        wqi_category = wq.quality_category if wq else "Good"
        ph = float(wq.ph if wq else 7.0)
        tds = float(wq.tds if wq else 450.0)

        # Dominant LULC
        dominant_lulc = lulc.dominant_class if lulc else "Agriculture"

        # Water Stress Level
        if water_stress >= 70:
            stress_level = "CRITICAL"
        elif water_stress >= 55:
            stress_level = "HIGH"
        elif water_stress >= 40:
            stress_level = "MODERATE"
        else:
            stress_level = "LOW"

        # Flood Risk Level
        if flood_risk >= 70:
            flood_level = "CRITICAL"
        elif flood_risk >= 55:
            flood_level = "HIGH"
        elif flood_risk >= 40:
            flood_level = "MODERATE"
        else:
            flood_level = "LOW"

        # Irrigation advisory synthesis
        if stress_level in ("CRITICAL", "HIGH"):
            if tds > 900:
                irrig_adv = "Severe water deficit with elevated TDS salinity. Strictly enforce drip/micro-irrigation on salt-tolerant crops. Prohibit flood irrigation and high-water cash crops."
            else:
                irrig_adv = "Significant catchment moisture deficit. Prioritize low water-footprint millets and pulses. Deploy mulching and drip fertigation to conserve remaining ground storage."
        elif flood_level in ("CRITICAL", "HIGH"):
            irrig_adv = "High surface runoff and localized waterlogging risk. Ensure ridge-and-furrow planting, field drainage channels, and water-tolerant cultivars."
        else:
            irrig_adv = "Balanced watershed moisture regime. Favorable for diversified cropping including Byadgi chilli, cotton, maize, and pulses with standard scheduling."

        water_summary = WatershedWaterSummary(
            water_stress_score=water_stress,
            water_stress_level=stress_level,
            flood_risk_score=flood_risk,
            flood_risk_level=flood_level,
            rainfall_mm=rainfall_mm,
            rainfall_anomaly_sigma=rainfall_anomaly,
            wqi=wqi,
            wqi_category=wqi_category,
            tds_mg_l=tds,
            ph=ph,
            slope_mean_deg=slope_mean,
            dominant_lulc=dominant_lulc,
            irrigation_advisory=irrig_adv
        )

        # 2. Score each candidate crop
        scored_crops: List[CropRecommendation] = []

        for crop in REGIONAL_CROPS:
            # Component 1: Water Stress Alignment (Weight: 35%)
            opt_min, opt_max = crop["optimal_water_stress"]
            if opt_min <= water_stress <= opt_max:
                stress_fit = 100.0
            elif water_stress < opt_min:
                # Under-stressed: slightly penalized if crop specifically needs dry conditions
                diff = opt_min - water_stress
                stress_fit = max(40.0, 100.0 - (diff * 1.5))
            else:
                # Over-stressed: penalized based on distance from max tolerance
                diff = water_stress - opt_max
                max_tolerance = crop["max_water_stress"]
                if water_stress > max_tolerance:
                    stress_fit = max(10.0, 40.0 - (water_stress - max_tolerance) * 2.0)
                else:
                    stress_fit = max(30.0, 100.0 - (diff * 2.5))

            # Component 2: Rainfall Anomaly Alignment (Weight: 20%)
            rf_anom = rainfall_anomaly if rainfall_anomaly is not None else 0.0
            if crop["water_tier"] in ("VERY_LOW", "LOW"):
                # Low-water crops benefit when rainfall anomaly is negative (dry spell)
                rf_fit = 100.0 if rf_anom <= 0 else max(60.0, 100.0 - (rf_anom * 15.0))
            elif crop["water_tier"] == "MODERATE":
                # Moderate crops do best when rainfall is near baseline
                rf_fit = max(30.0, 100.0 - abs(rf_anom) * 18.0)
            else:
                # High-water crops suffer heavily when rainfall is negative
                rf_fit = 100.0 if rf_anom > 0 else max(10.0, 60.0 + (rf_anom * 25.0))

            # Component 3: Water Quality & Salinity (Weight: 20%)
            # Check TDS
            max_tds = crop["max_tds"]
            if tds <= max_tds * 0.7:
                tds_fit = 100.0
            elif tds <= max_tds:
                tds_fit = 80.0
            else:
                tds_fit = max(10.0, 80.0 - ((tds - max_tds) / 10.0))

            # Check pH
            ph_min, ph_max = crop["optimal_ph_range"]
            if ph_min <= ph <= ph_max:
                ph_fit = 100.0
            else:
                ph_dist = min(abs(ph - ph_min), abs(ph - ph_max))
                ph_fit = max(30.0, 100.0 - (ph_dist * 35.0))
            wq_fit = (tds_fit * 0.65) + (ph_fit * 0.35)

            # Component 4: Flood / Waterlogging Risk (Weight: 15%)
            crop_max_flood = crop["max_flood_risk"]
            if flood_risk <= crop_max_flood:
                flood_fit = 100.0
            else:
                flood_fit = max(10.0, 100.0 - (flood_risk - crop_max_flood) * 2.8)

            # Special case: wetland paddy thrives under high flood / runoff
            if crop["id"] == "paddy_flood_lowland":
                if flood_risk > 50 and water_stress < 40:
                    flood_fit = 100.0
                elif water_stress > 45:
                    flood_fit = 15.0

            # Component 5: Slope & Terrain (Weight: 10%)
            max_slope = crop["max_slope"]
            if slope_mean <= max_slope:
                slope_fit = 100.0
            else:
                slope_fit = max(20.0, 100.0 - (slope_mean - max_slope) * 12.0)

            # Aggregate Suitability Score
            composite_score = (
                0.35 * stress_fit
                + 0.20 * rf_fit
                + 0.20 * wq_fit
                + 0.15 * flood_fit
                + 0.10 * slope_fit
            )
            composite_score = round(min(100.0, max(0.0, composite_score)), 1)

            # Determine Tier
            if composite_score >= 82.0:
                tier = "OPTIMAL"
            elif composite_score >= 70.0:
                tier = "HIGHLY_SUITABLE"
            elif composite_score >= 55.0:
                tier = "MODERATELY_SUITABLE"
            elif composite_score >= 40.0:
                tier = "CONDITIONAL"
            else:
                tier = "NOT_RECOMMENDED"

            # Dynamic Rationale
            rationale = crop["stress_rationale_template"].format(
                water_stress=round(water_stress, 1),
                tds=round(tds, 1),
                ph=round(ph, 2),
                flood=round(flood_risk, 1)
            )

            scored_crops.append(
                CropRecommendation(
                    crop_name=crop["crop_name"],
                    local_name=crop["local_name"],
                    category=crop["category"],
                    season=crop["season"],
                    suitability_score=composite_score,
                    suitability_tier=tier,
                    water_requirement_mm=f"{crop['base_water_min_mm']} - {crop['base_water_max_mm']} mm",
                    water_tier=crop["water_tier"],
                    water_stress_rationale=rationale,
                    recommended_irrigation=crop["recommended_irrigation"],
                    salinity_tolerance=crop["salinity_tolerance"],
                    risk_management_tips=crop["risk_management"],
                    key_advantages=crop["key_advantages"]
                )
            )

        # Sort recommendations by suitability score descending
        scored_crops.sort(key=lambda c: c.suitability_score, reverse=True)

        # 3. Identify Caution / High-Risk Crops
        caution_crops: List[CropCaution] = []
        for caution in CAUTION_CROP_REGISTRY:
            thresh = caution["critical_water_stress_threshold"]
            if water_stress >= thresh:
                hazard_level = "CRITICAL_RISK" if water_stress >= 65 else "HIGH_RISK"
                hazard_msg = f"Water Stress score is {water_stress}/100, exceeding sustainable threshold ({thresh}/100). Requires {caution['water_needed_mm']}."
                caution_crops.append(
                    CropCaution(
                        crop_name=caution["crop_name"],
                        risk_level=hazard_level,
                        water_deficit_hazard=hazard_msg,
                        depletion_impact=caution["depletion_impact"],
                        alternative_suggestion=caution["alternative_suggestion"]
                    )
                )

        # 4. Conservation Practices tailored to conditions
        conservation_practices = [
            "In-situ soil moisture conservation using Broad Bed and Furrow (BBF) systems",
            "Plastic or organic straw mulching to suppress evaporative loss by up to 35%",
            "Farm pond water harvesting for life-saving supplemental micro-irrigation",
        ]
        if slope_mean > 6.0:
            conservation_practices.append(f"Contour bunding and vegetative barriers across catchment slopes ({slope_mean:.1f}° slope)")
        if tds > 800:
            conservation_practices.append(f"Gypsum application and periodic flushing to counter elevated TDS ({tds:.0f} mg/L)")
        if flood_risk > 50:
            conservation_practices.append("Excavation and desilting of drainage channels to prevent localized inundation")

        return WatershedCropAdvisory(
            id=actual_id,
            MWS=actual_mws,
            generated_at=datetime.now(timezone.utc).isoformat(),
            water_summary=water_summary,
            recommended_crops=scored_crops,
            caution_crops=caution_crops,
            conservation_practices=conservation_practices,
            status="available"
        )
