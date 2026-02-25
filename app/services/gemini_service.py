from typing import Dict, Any
import json
import re
import asyncio
import logging
from google import genai
from google.genai import types
from ..config import settings


class GeminiService:

    def __init__(self):
        if not settings.GEMINI_API_KEY:
            raise RuntimeError("GEMINI_API_KEY is not set")

        self.client = genai.Client(api_key=settings.GEMINI_API_KEY)
        self.model_name = "gemini-2.5-flash"
        self.max_attempts = 3
        self.base_backoff_seconds = 1.5

    async def extract_section_a(self, file_bytes: bytes, prompt: str) -> Dict[str, Any]:
        """
        Accepts raw PDF bytes + prompt.
        Returns cleaned JSON.
        """

        if not file_bytes:
            raise ValueError("Empty PDF bytes provided")

        last_error: Exception | None = None

        for attempt in range(1, self.max_attempts + 1):
            try:
                # SDK call is blocking; run it in a worker thread to avoid
                # blocking the event loop used by FastAPI background work.
                response = await asyncio.to_thread(
                    self.client.models.generate_content,
                    model=self.model_name,
                    contents=[
                        types.Part.from_bytes(
                            data=file_bytes,
                            mime_type="application/pdf"
                        ),
                        prompt
                    ]
                )

                if not response or not response.text:
                    raise RuntimeError("Gemini returned empty response")

                # Match script flow:
                # 1) parse JSON if possible
                # 2) clean markdown-fenced raw responses
                # 3) normalize stock_exchange_listing token(s)
                parsed = self._parse_or_raw(response.text)
                parsed = self._clean_gemini_response(parsed)
                parsed = self._normalize_stock_exchange_listing(parsed)
                return parsed
            except Exception as e:
                last_error = e
                if attempt >= self.max_attempts or not self._is_retryable_error(e):
                    break
                backoff = self.base_backoff_seconds * (2 ** (attempt - 1))
                logging.warning(
                    "Gemini call attempt %s/%s failed with retryable error: %s. Retrying in %.1fs",
                    attempt,
                    self.max_attempts,
                    str(e),
                    backoff,
                )
                await asyncio.sleep(backoff)

        raise RuntimeError(f"Gemini extraction failed: {str(last_error)}")

    # =========================
    # INTERNAL CLEANER
    # =========================

    def _parse_or_raw(self, response_text: str) -> Dict[str, Any]:
        # Script-equivalent: try strict JSON parse first; fallback to raw text.
        try:
            return json.loads(response_text)
        except Exception:
            return {"raw_response": response_text}

    def _clean_gemini_response(self, result: Dict[str, Any]) -> Dict[str, Any]:
        """
        Script-equivalent cleaner:
        if `raw_response` exists, strip markdown fences and parse JSON.
        """
        if isinstance(result, dict) and "raw_response" in result:
            raw = str(result["raw_response"])
            clean = re.sub(r'```(?:json)?\s*', '', raw, flags=re.IGNORECASE)
            clean = re.sub(r'\s*```$', '', clean)
            clean = clean.strip()
            try:
                return json.loads(clean)
            except json.JSONDecodeError:
                return {"raw_response": clean}
        return result

    def _normalize_stock_exchange_listing(self, result: Dict[str, Any]) -> Dict[str, Any]:
        """
        Script-equivalent normalization:
        - only BSE -> BSE
        - only NSE -> NSE
        - both -> BSENSE
        - keep any other exchanges as uppercase tokens after the above.
        """
        if not isinstance(result, dict):
            return result

        ent = result.get("entity_details")
        if not isinstance(ent, dict):
            return result

        val = ent.get("stock_exchange_listing")
        if val is None:
            return result

        if isinstance(val, list):
            raw = " ".join(str(x) for x in val)
        elif isinstance(val, dict):
            raw = " ".join(str(v) for v in val.values())
        else:
            raw = str(val)

        s = raw.strip()
        if s == "":
            ent["stock_exchange_listing"] = ""
            result["entity_details"] = ent
            return result

        lowered = s.lower()
        bse_present = bool(re.search(r"\bbse\b", lowered) or "bombay" in lowered)
        nse_present = bool(re.search(r"\bnse\b", lowered) or "national stock exchange" in lowered)

        cleaned = lowered
        cleaned = re.sub(r"bombay stock exchange", "", cleaned)
        cleaned = re.sub(r"\bbse\b", "", cleaned)
        cleaned = re.sub(r"national stock exchange", "", cleaned)
        cleaned = re.sub(r"\bnse\b", "", cleaned)

        parts = re.split(r"[,;/\\\n]+|\s{2,}|\s", cleaned)
        others = []
        for p in parts:
            token = p.strip()
            if not token:
                continue
            token_up = token.upper()
            if token_up not in ("BSE", "NSE") and token_up not in others:
                others.append(token_up)

        result_tokens = []
        if bse_present and nse_present:
            result_tokens.append("BSENSE")
        elif bse_present:
            result_tokens.append("BSE")
        elif nse_present:
            result_tokens.append("NSE")

        for o in others:
            if o and o not in result_tokens:
                result_tokens.append(o)

        ent["stock_exchange_listing"] = " ".join(result_tokens)
        result["entity_details"] = ent
        return result

    def _is_retryable_error(self, err: Exception) -> bool:
        msg = str(err).lower()
        retry_markers = [
            "winerror 10054",
            "forcibly closed by the remote host",
            "connection reset",
            "timed out",
            "timeout",
            "temporarily unavailable",
            "service unavailable",
            "too many requests",
            "429",
            "503",
            "500",
        ]
        return any(marker in msg for marker in retry_markers)
