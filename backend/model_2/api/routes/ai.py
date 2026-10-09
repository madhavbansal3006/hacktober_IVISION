"""
FastAPI route for Ask JalDrishti (Gemma 4 Q&A with Real Watershed Evidence).
Endpoint: POST /api/v1/ai/ask
"""

from fastapi import APIRouter, Request, HTTPException, status
import logging
from ..schemas import AskRequest, AskResponse
from ..services.watershed_evidence import WatershedEvidenceService
from ..services.gemma_client import (
    GemmaClient,
    GemmaError,
    GemmaTimeoutError,
    GemmaAPIError,
    GemmaMalformedResponseError,
)
from ..services.evidence_validator import EvidenceValidator

logger = logging.getLogger(__name__)

router = APIRouter(prefix="/ai", tags=["Ask JalDrishti AI"])

@router.post(
    "/ask",
    response_model=AskResponse,
    summary="Ask JalDrishti: Gemma 4 Q&A grounded in verified watershed evidence"
)
def ask_watershed_question(
    ask_req: AskRequest,
    request: Request
):
    """
    Answers natural language questions about a specific micro-watershed using
    Gemma 4 through the Gemini API, strictly verified against real project evidence.

    - Validates the micro-watershed ID against the official 66 GIS units.
    - Validates question presence.
    - Retrieves real multi-source evidence (Model 1 LULC, Model 2 Risk, terrain, GIS, water quality).
    - Submits evidence and question to Gemma 4.
    - Deterministically validates claims, risk categories, and numerical accuracy.
    - Automatically falls back to trusted deterministic explanations if the model fails or hallucinates.
    """
    # 1. Validate Question
    question = ask_req.question.strip() if ask_req.question else ""
    if not question:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Question cannot be empty or blank."
        )

    # 2. Validate Watershed Identifier
    mws_target = ask_req.mws_code or ask_req.mws_id
    if not mws_target or not mws_target.strip():
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Either 'mws_code' or 'mws_id' must be specified."
        )
    mws_target = mws_target.strip()

    # 3. Retrieve Evidence
    adapters = getattr(request.app.state, "adapters", {})
    evidence_service = WatershedEvidenceService(adapters)
    bundle = evidence_service.retrieve_evidence(mws_target)

    if not bundle:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=f"Micro-watershed '{mws_target}' not found among official 66 units."
        )

    # 4. Invoke Gemma Model Client
    client = GemmaClient()
    model_name = client.model_name
    fallback_used = False

    try:
        raw_model_output = client.generate_answer(question, bundle)
        # 5. Deterministic Validation
        (
            passed,
            val_details,
            claims,
            final_answer,
            disclosures
        ) = EvidenceValidator.validate(raw_model_output, bundle)

        fallback_used = not passed

    except GemmaError as ge:
        logger.warning(f"Gemma client error for MWS {mws_target}: {ge}")
        fallback_used = True
        err_msg = str(ge)
        final_answer = EvidenceValidator.build_deterministic_fallback(
            bundle,
            reason=f"AI model service unavailable or returned error ({err_msg}). Displaying authoritative deterministic data."
        )
        (
            _,
            val_details,
            claims,
            _,
            disclosures
        ) = EvidenceValidator.validate({}, bundle)
        val_details.reasons = [err_msg]
        passed = False

    except Exception as exc:
        logger.error(f"Unexpected error during Gemma execution for MWS {mws_target}: {exc}")
        fallback_used = True
        final_answer = EvidenceValidator.build_deterministic_fallback(
            bundle,
            reason=f"Internal processing failure ({exc}). Displaying authoritative deterministic data."
        )
        (
            _,
            val_details,
            claims,
            _,
            disclosures
        ) = EvidenceValidator.validate({}, bundle)
        val_details.reasons = [str(exc)]
        passed = False

    # Return structured response
    return AskResponse(
        status="available",
        mws_id=bundle.mws_id,
        mws_code=bundle.mws_code,
        question=question,
        answer=final_answer,
        evidence_used=bundle.to_evidence_records(),
        claims=claims,
        disclosures=disclosures,
        validation_passed=passed,
        validation_details=val_details,
        fallback_used=fallback_used,
        model_name=model_name,
    )
