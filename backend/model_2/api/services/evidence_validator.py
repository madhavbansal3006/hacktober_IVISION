"""
Deterministic Evidence Validator for Ask JalDrishti.

Verifies AI-generated answers against retrieved watershed evidence:
1. Schema conformity (required fields and structures).
2. Every cited evidence ID exists in the retrieved evidence bundle.
3. Numerical claims match referenced evidence values within a defined rounding tolerance (±0.15 or 2%).
4. Risk categories agree with official thresholds and official risk category.
5. Missing or low-coverage data is disclosed.
6. Unsupported numerical claims are rejected.

If validation fails, the unverified answer is NOT displayed; instead, a safe,
authoritative deterministic explanation is constructed from trusted project data.
"""

from typing import Dict, Any, List, Optional, Tuple, Union
import re
import logging
from ..schemas import (
    ClaimItem,
    ValidationDetails,
    EvidenceItemRecord,
)
from .watershed_evidence import WatershedEvidenceBundle

logger = logging.getLogger(__name__)

ROUNDING_TOLERANCE_ABSOLUTE = 0.20  # Allows e.g. 55.3 vs 55.27
ROUNDING_TOLERANCE_RELATIVE = 0.02  # 2% relative tolerance

OFFICIAL_RISK_THRESHOLDS = {
    "CRITICAL": (70.0, 100.0),
    "HIGH": (50.0, 69.999),
    "MODERATE": (30.0, 49.999),
    "LOW": (0.0, 29.999),
}

def parse_float(val: Any) -> Optional[float]:
    if val is None:
        return None
    if isinstance(val, (int, float)):
        return float(val)
    if isinstance(val, str):
        # Extract first floating point number if present
        clean = val.replace("%", "").replace("/100", "").replace("km²", "").replace("mm", "").strip()
        match = re.search(r"[-+]?\d*\.?\d+", clean)
        if match:
            try:
                return float(match.group(0))
            except ValueError:
                return None
    return None

class EvidenceValidator:
    """
    Lightweight, deterministic evidence validator.
    """

    @classmethod
    def build_deterministic_fallback(
        cls,
        bundle: WatershedEvidenceBundle,
        reason: str = "Deterministic verification safeguard active."
    ) -> str:
        """
        Constructs an authoritative, 100% verified deterministic explanation
        directly from trusted project evidence.
        """
        ev = {item.id: item for item in bundle.items}

        area = ev.get("ev_area_km2")
        risk = ev.get("ev_final_risk")
        cat = ev.get("ev_risk_category")
        health = ev.get("ev_health_index")
        driver = ev.get("ev_primary_driver")
        w_stress = ev.get("ev_water_stress")
        flood = ev.get("ev_flood_risk")
        eco = ev.get("ev_ecosystem_risk")
        ml_anom = ev.get("ev_ml_anomaly")
        lulc_dom = ev.get("ev_lulc_dominant")
        lulc_cov = ev.get("ev_lulc_coverage")
        agri = ev.get("ev_lulc_agri")
        forest = ev.get("ev_lulc_forest")
        interv = ev.get("ev_primary_intervention")
        elev = ev.get("ev_elevation_m")
        slope = ev.get("ev_slope_deg")
        stream = ev.get("ev_stream_len_km")

        lines = [
            f"### Authoritative Profile: Micro-Watershed {bundle.mws_code} ({bundle.mws_id})",
            "",
            "**Official Risk & Health Status:**",
        ]

        if risk and cat:
            lines.append(
                f"- **Final Risk Score:** {risk.value}/100 ({cat.value} risk category, Health Index: {health.value if health else 'N/A'}/100)."
            )
        if driver:
            lines.append(f"- **Primary Risk Driver:** {driver.value}.")

        sub_parts = []
        if w_stress:
            sub_parts.append(f"Water Stress: {w_stress.value}/100")
        if flood:
            sub_parts.append(f"Flood Risk: {flood.value}/100")
        if eco:
            sub_parts.append(f"Ecosystem Risk: {eco.value}/100")
        if ml_anom:
            sub_parts.append(f"ML Anomaly: {ml_anom.value}/100")
        if sub_parts:
            lines.append(f"- **Component Breakdown:** {', '.join(sub_parts)}.")

        lines.append("")
        lines.append("**Land Cover & Physical Topography:**")
        if lulc_dom and agri:
            forest_str = f", Forest: {forest.value}%" if forest else ""
            cov_str = f" ({lulc_cov.value} raster coverage)" if lulc_cov else ""
            lines.append(f"- **Dominant Land Cover:** {lulc_dom.value} (Agriculture: {agri.value}%{forest_str}){cov_str}.")
        
        topo_parts = []
        if area:
            topo_parts.append(f"Area: {area.value} km²")
        if elev:
            topo_parts.append(f"Mean Elevation: {elev.value} m")
        if slope:
            topo_parts.append(f"Mean Slope: {slope.value}°")
        if stream:
            topo_parts.append(f"Stream Network: {stream.value} km")
        if topo_parts:
            lines.append(f"- **Spatial Attributes:** {', '.join(topo_parts)}.")

        if interv:
            lines.append("")
            lines.append(f"**Recommended Intervention:** {interv.value}")

        if bundle.disclosed_gaps:
            lines.append("")
            lines.append("**Disclosed Limitations & Data Provenance:**")
            for gap in bundle.disclosed_gaps:
                lines.append(f"- {gap}")

        if reason:
            lines.append("")
            lines.append(f"*(Note: {reason})*")

        return "\n".join(lines)

    @classmethod
    def validate(
        cls,
        raw_output: Any,
        bundle: WatershedEvidenceBundle,
    ) -> Tuple[bool, ValidationDetails, List[ClaimItem], str, List[str]]:
        """
        Validates model output against the evidence bundle.

        Returns:
            passed (bool): Whether all checks succeeded.
            details (ValidationDetails): Breakdown of checks.
            verified_claims (List[ClaimItem]): Verified claims.
            final_answer (str): The verified answer OR safe deterministic fallback.
            final_disclosures (List[str]): Verified disclosures.
        """
        reasons: List[str] = []
        schema_valid = True
        evidence_ids_valid = True
        numerical_claims_valid = True
        risk_category_valid = True
        disclosures_valid = True
        unsupported_claims_rejected = True

        verified_claims: List[ClaimItem] = []
        final_disclosures = list(bundle.disclosed_gaps)

        # 1. Schema Validation
        if not isinstance(raw_output, dict):
            schema_valid = False
            reasons.append(f"Model output is not a JSON object (type={type(raw_output).__name__}).")
            fallback = cls.build_deterministic_fallback(
                bundle, reason="Response failed schema validation; fallback constructed from trusted data."
            )
            details = ValidationDetails(
                schema_valid=False,
                evidence_ids_valid=False,
                numerical_claims_valid=False,
                risk_category_valid=False,
                disclosures_valid=False,
                unsupported_claims_rejected=False,
                reasons=reasons,
            )
            return False, details, [], fallback, final_disclosures

        answer = raw_output.get("answer")
        if not isinstance(answer, str) or not answer.strip():
            schema_valid = False
            reasons.append("Field 'answer' is missing or empty in model output.")

        raw_claims = raw_output.get("claims", [])
        if not isinstance(raw_claims, list):
            schema_valid = False
            reasons.append("Field 'claims' is not a list in model output.")
            raw_claims = []

        if not schema_valid:
            fallback = cls.build_deterministic_fallback(
                bundle, reason="Response schema invalid; fallback constructed from trusted data."
            )
            details = ValidationDetails(
                schema_valid=False,
                evidence_ids_valid=False,
                numerical_claims_valid=False,
                risk_category_valid=False,
                disclosures_valid=False,
                unsupported_claims_rejected=False,
                reasons=reasons,
            )
            return False, details, [], fallback, final_disclosures

        # 2. Evidence ID and Claim Verification
        for idx, claim_data in enumerate(raw_claims):
            if not isinstance(claim_data, dict):
                schema_valid = False
                reasons.append(f"Claim #{idx} is not an object.")
                continue

            claim_text = str(claim_data.get("claim_text", "")).strip()
            ev_id = str(claim_data.get("evidence_id", "")).strip()
            claimed_val = claim_data.get("claimed_value")

            if not ev_id:
                unsupported_claims_rejected = False
                reasons.append(f"Claim '{claim_text}' has missing evidence_id.")
                continue

            if not bundle.contains(ev_id):
                evidence_ids_valid = False
                reasons.append(f"Referenced evidence ID '{ev_id}' not found in retrieved project evidence.")
                verified_claims.append(
                    ClaimItem(
                        claim_text=claim_text,
                        evidence_id=ev_id,
                        claimed_value=claimed_val,
                        verified=False,
                        verification_notes=f"Evidence ID '{ev_id}' does not exist in verified catalog.",
                    )
                )
                continue

            ev_item = bundle.get(ev_id)
            claim_verified = True
            verification_note = "Verified against trusted project evidence."

            # 3. Numerical Verification
            if claimed_val is not None:
                claimed_num = parse_float(claimed_val)
                actual_num = parse_float(ev_item.value)

                if claimed_num is not None and actual_num is not None:
                    abs_diff = abs(claimed_num - actual_num)
                    rel_tol = max(ROUNDING_TOLERANCE_ABSOLUTE, abs(actual_num) * ROUNDING_TOLERANCE_RELATIVE)
                    if abs_diff > rel_tol:
                        numerical_claims_valid = False
                        claim_verified = False
                        verification_note = (
                            f"Numerical discrepancy: claimed {claimed_num}, actual evidence value is {actual_num}."
                        )
                        reasons.append(
                            f"Numerical claim for {ev_id} ('{claim_text}'): claimed {claimed_num} diverges from verified evidence {actual_num}."
                        )

            # Categorical Verification (e.g. for strings)
            elif isinstance(ev_item.value, str):
                actual_str = ev_item.value.lower()
                claimed_str = str(claim_data.get("claimed_value", "")).lower()
                if claimed_str and claimed_str not in actual_str and actual_str not in claimed_str:
                    claim_verified = False
                    verification_note = f"Value mismatch: claimed '{claimed_str}', evidence has '{ev_item.value}'."
                    reasons.append(f"Categorical claim for {ev_id} contradicts evidence: '{ev_item.value}'.")

            verified_claims.append(
                ClaimItem(
                    claim_text=claim_text,
                    evidence_id=ev_id,
                    claimed_value=claimed_val,
                    verified=claim_verified,
                    verification_notes=verification_note,
                )
            )

        # 4. Risk Category Agreement Check
        ev_cat = bundle.get("ev_risk_category")
        ev_risk = bundle.get("ev_final_risk")
        if ev_cat and ev_cat.value:
            official_cat = str(ev_cat.value).strip().upper()
            official_score = float(ev_risk.value) if ev_risk else None

            # Look for conflicting category claims in claims
            for claim in verified_claims:
                if claim.evidence_id in ("ev_risk_category", "ev_final_risk") and claim.claimed_value:
                    val_str = str(claim.claimed_value).strip().upper()
                    if val_str in ("CRITICAL", "HIGH", "MODERATE", "LOW") and val_str != official_cat:
                        risk_category_valid = False
                        reasons.append(
                            f"Risk category claim '{val_str}' conflicts with official category '{official_cat}'."
                        )

            # Scan the answer text for conflicting category declarations
            # e.g. "is categorized as LOW" when official is "HIGH"
            answer_upper = answer.upper()
            all_cats = ["CRITICAL", "HIGH", "MODERATE", "LOW"]
            other_cats = [c for c in all_cats if c != official_cat]
            for bad_cat in other_cats:
                # Patterns like: "LOW RISK CATEGORY", "CATEGORIZED AS LOW", "CLASSIFIED AS LOW", "CATEGORY: LOW"
                bad_patterns = [
                    rf"\b{bad_cat}\s+RISK\b",
                    rf"\bCATEGORIZED\s+AS\s+{bad_cat}\b",
                    rf"\bCLASSIFIED\s+AS\s+{bad_cat}\b",
                    rf"\bCATEGORY[:\s]+{bad_cat}\b",
                ]
                for pat in bad_patterns:
                    if re.search(pat, answer_upper):
                        # Make sure it's not a negated mention like "not low"
                        risk_category_valid = False
                        reasons.append(
                            f"Answer asserts incorrect risk category '{bad_cat}', while official category is '{official_cat}'."
                        )
                        break

        # 5. Missing / Low-coverage Disclosures Check
        model_disclosures = raw_output.get("disclosed_gaps", [])
        if isinstance(model_disclosures, list):
            for d in model_disclosures:
                d_str = str(d).strip()
                if d_str and d_str not in final_disclosures:
                    final_disclosures.append(d_str)

        # Check overall validation result
        passed = (
            schema_valid
            and evidence_ids_valid
            and numerical_claims_valid
            and risk_category_valid
            and unsupported_claims_rejected
        )

        details = ValidationDetails(
            schema_valid=schema_valid,
            evidence_ids_valid=evidence_ids_valid,
            numerical_claims_valid=numerical_claims_valid,
            risk_category_valid=risk_category_valid,
            disclosures_valid=disclosures_valid,
            unsupported_claims_rejected=unsupported_claims_rejected,
            reasons=reasons,
        )

        if not passed:
            fallback = cls.build_deterministic_fallback(
                bundle,
                reason="Deterministic safeguard active: Model output contained unverified claims or contradicted official evidence. Displaying verified project data."
            )
            return False, details, verified_claims, fallback, final_disclosures

        return True, details, verified_claims, answer, final_disclosures
