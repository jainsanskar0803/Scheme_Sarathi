"""
Batch translation endpoint — English → Hindi via Sarvam AI translate API.

POST /api/translate
  Body: { "texts": ["text1", "text2", ...] }
  Response: { "translations": ["अनुवाद1", "अनुवाद2", ...] }

Empty strings and strings that are already non-English (numbers, codes) are
returned as-is. The endpoint fans out to Sarvam in parallel (up to 20
concurrent requests) and preserves the original order.
"""
from __future__ import annotations

import asyncio
import os
from typing import Optional

import httpx
from fastapi import APIRouter, HTTPException
from pydantic import BaseModel

router = APIRouter(prefix="/translate", tags=["translate"])

_SARVAM_TRANSLATE = "https://api.sarvam.ai/translate"
_MAX_TEXTS = 300
_CONCURRENCY = 20
_CHAR_LIMIT = 900          # Sarvam per-input cap (leave headroom)


class TranslateRequest(BaseModel):
    texts: list[Optional[str]]


class TranslateResponse(BaseModel):
    translations: list[Optional[str]]


def _key() -> str:
    k = os.environ.get("SARVAM_API_KEY", "")
    if not k:
        raise HTTPException(status_code=503, detail="SARVAM_API_KEY not configured")
    return k


async def _translate_one(client: httpx.AsyncClient, api_key: str, text: str) -> str:
    """Translate a single English text to Hindi. Returns original on error."""
    if not text or not text.strip():
        return text
    try:
        resp = await client.post(
            _SARVAM_TRANSLATE,
            headers={
                "api-subscription-key": api_key,
                "Content-Type": "application/json",
            },
            json={
                "input": text[:_CHAR_LIMIT],
                "source_language_code": "en-IN",
                "target_language_code": "hi-IN",
                "speaker_gender": "Female",
                "mode": "formal",
                "model": "mayura:v1",
                "enable_preprocessing": False,
            },
        )
        if resp.is_success:
            return resp.json().get("translated_text", text)
    except Exception:
        pass
    return text  # fallback to original on any error


@router.post("", response_model=TranslateResponse)
async def batch_translate(body: TranslateRequest) -> TranslateResponse:
    """
    Translate up to 300 texts from English to Hindi using Sarvam AI.
    Skips empty/None strings and returns them unchanged.
    Processes the rest in parallel (max 20 concurrent) for speed.
    """
    api_key = _key()
    texts = body.texts[:_MAX_TEXTS]

    sem = asyncio.Semaphore(_CONCURRENCY)

    async def limited(text: Optional[str]) -> Optional[str]:
        if text is None:
            return None
        async with sem:
            async with httpx.AsyncClient(timeout=15) as client:
                return await _translate_one(client, api_key, text)

    translations = await asyncio.gather(*[limited(t) for t in texts])
    return TranslateResponse(translations=list(translations))
