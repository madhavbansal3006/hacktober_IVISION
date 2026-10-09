"""
Gemma 4 Client integration via Gemini API for Ask JalDrishti.

Connects to Google Generative Language API (Gemini API) to invoke supported Gemma models.
- Uses backend environment variables (GEMMA_API_KEY, fallback GEMINI_API_KEY).
- API key is never committed or exposed to client.
- Configurable model name (GEMMA_MODEL_NAME, default 'gemma-2-9b-it').
- Configurable timeout and robust error/timeout handling.
- Deterministic JSON response extraction and sanitation.
"""

import os
import json
import re
import logging
from typing import Dict, Any, Optional
import httpx
from .watershed_evidence import WatershedEvidenceBundle

logger = logging.getLogger(__name__)

GEMINI_API_ENDPOINT = "https://generativelanguage.googleapis.com/v1beta/models"

class GemmaError(Exception):
    """Base exception for Gemma client errors."""
    pass

class GemmaTimeoutError(GemmaError):
    """Raised when Gemma model API times out."""
    pass

class GemmaAPIError(GemmaError):
    """Raised when Gemma model API returns non-200 HTTP status."""
    def __init__(self, status_code: int, message: str):
        super().__init__(f"Gemma API error {status_code}: {message}")
        self.status_code = status_code
        self.message = message

class GemmaMalformedResponseError(GemmaError):
    """Raised when Gemma response cannot be parsed into expected JSON."""
    pass


class GemmaClient:
    """
    Client for calling Gemma 4 models through the Gemini API.
    """
    def __init__(
        self,
        api_key: Optional[str] = None,
        model_name: Optional[str] = None,
        timeout_seconds: Optional[float] = None
    ):
        self.api_key = (
            api_key
            or os.environ.get("GEMMA_API_KEY")
            or os.environ.get("GEMINI_API_KEY")
            or ""
        )
        self.model_name = (
            model_name
            or os.environ.get("GEMMA_MODEL_NAME")
            or "gemma-2-9b-it"
        )
        self.timeout_seconds = (
            timeout_seconds
            or float(os.environ.get("GEMMA_TIMEOUT_SECONDS", "30.0"))
        )

    def is_configured(self) -> bool:
        """Returns True if an API key is available."""
        return bool(self.api_key and self.api_key.strip())

    def generate_answer(
        self,
        question: str,
        bundle: WatershedEvidenceBundle
    ) -> Dict[str, Any]:
        """
        Sends the question and structured evidence bundle to Gemma.
        Returns parsed JSON dict with 'answer', 'claims', 'disclosed_gaps'.

        Raises:
            GemmaError subclasses on failure.
        """
        if not self.is_configured():
            raise GemmaAPIError(
                status_code=401,
                message="GEMMA_API_KEY or GEMINI_API_KEY environment variable is not configured on the backend."
            )

        prompt = self._construct_prompt(question, bundle)
        payload = {
            "contents": [
                {
                    "role": "user",
                    "parts": [{"text": prompt}]
                }
            ],
            "generationConfig": {
                "temperature": 0.1,
                "topP": 0.95,
                "maxOutputTokens": 2048,
                "responseMimeType": "application/json"
            }
        }

        url = f"{GEMINI_API_ENDPOINT}/{self.model_name}:generateContent?key={self.api_key}"

        try:
            with httpx.Client(timeout=self.timeout_seconds) as client:
                response = client.post(
                    url,
                    headers={"Content-Type": "application/json"},
                    json=payload
                )

            if response.status_code != 200:
                err_text = response.text
                logger.error(f"Gemma API call failed ({response.status_code}): {err_text}")
                raise GemmaAPIError(response.status_code, err_text)

            res_json = response.json()
            raw_text = self._extract_text_from_response(res_json)
            parsed_data = self._parse_json_from_text(raw_text)
            return parsed_data

        except httpx.TimeoutException as te:
            logger.error(f"Gemma API call timed out after {self.timeout_seconds}s: {te}")
            raise GemmaTimeoutError(f"Gemma model request timed out after {self.timeout_seconds} seconds.") from te
        except httpx.RequestError as re:
            logger.error(f"Gemma network connection error: {re}")
            raise GemmaAPIError(503, f"Network connection error contacting Gemma API: {re}") from re

    def _construct_prompt(self, question: str, bundle: WatershedEvidenceBundle) -> str:
        context = bundle.to_llm_context()
        return f"""You are 'Ask JalDrishti', the official AI assistant for the Shiggaon Watershed Intelligence System.
Your job is to answer user questions about micro-watershed '{bundle.mws_code}' ({bundle.mws_id}) using ONLY the provided verified project evidence.

Strict Rules:
1. Ground every statement strictly in the provided evidence.
2. NEVER invent values. If data is missing or marked as unavailable, explicitly disclose that.
3. NEVER replace missing data with zero.
4. Do NOT calculate an alternate risk score; always adhere to the official Model 2 Risk Engine score and category.
5. Clearly distinguish observed data from model-derived indicators and simulated telemetry (e.g., Water Quality WQI is synthetic simulation only).
6. Cite the exact evidence IDs in the 'claims' array for all numerical or categorical facts mentioned.
7. Return ONLY valid JSON matching this schema:
{{
  "answer": "Detailed, professional Markdown answer answering the user question...",
  "claims": [
    {{
      "claim_text": "Brief assertion made",
      "evidence_id": "exact_evidence_id_from_context",
      "claimed_value": number_or_string_matching_evidence
    }}
  ],
  "disclosed_gaps": [
    "List of disclosed data gaps or simulation limitations"
  ]
}}

EVIDENCE CONTEXT:
{context}

USER QUESTION:
{question}
"""

    def _extract_text_from_response(self, response_json: Dict[str, Any]) -> str:
        try:
            candidates = response_json.get("candidates", [])
            if not candidates:
                raise GemmaMalformedResponseError("No candidates returned by Gemma model.")
            parts = candidates[0].get("content", {}).get("parts", [])
            if not parts:
                raise GemmaMalformedResponseError("Candidate content has no parts.")
            text = parts[0].get("text", "")
            return text
        except (KeyError, IndexError) as e:
            raise GemmaMalformedResponseError(f"Malformed response format from Gemini API: {e}") from e

    def _parse_json_from_text(self, text: str) -> Dict[str, Any]:
        clean = text.strip()
        # Remove code blocks if present
        if clean.startswith("```"):
            clean = re.sub(r"^```(?:json)?\s*", "", clean)
            clean = re.sub(r"\s*```$", "", clean)
            clean = clean.strip()

        try:
            data = json.loads(clean)
            if not isinstance(data, dict):
                raise GemmaMalformedResponseError("Parsed model output is not a JSON dictionary.")
            return data
        except json.JSONDecodeError as jde:
            # Fallback regex search for JSON object
            match = re.search(r"\{.*\}", clean, re.DOTALL)
            if match:
                try:
                    data = json.loads(match.group(0))
                    if isinstance(data, dict):
                        return data
                except json.JSONDecodeError:
                    pass
            raise GemmaMalformedResponseError(f"Failed to decode model JSON: {jde}. Raw text: {clean[:200]}") from jde
