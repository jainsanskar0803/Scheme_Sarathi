"""
Voice endpoints — speech-to-text and text-to-speech via Sarvam AI.

POST /api/voice/transcribe
  Accepts audio file (multipart/form-data), returns transcript + language code.
  Supported browser formats: WebM (Chrome), MP4 (Safari/iOS), OGG (Firefox).

POST /api/voice/speak
  Accepts { text, language } JSON, returns base64-encoded WAV audio.
  Uses Sarvam bulbul:v3 (TTS model) with speaker "priya" (hi-IN and en-IN).
"""
from __future__ import annotations

import os

import httpx
from fastapi import APIRouter, File, HTTPException, UploadFile
from pydantic import BaseModel

router = APIRouter(prefix="/voice", tags=["voice"])

_SARVAM_STT  = "https://api.sarvam.ai/speech-to-text"
_SARVAM_TTS  = "https://api.sarvam.ai/text-to-speech"
_STT_MODEL   = "saaras:v3"      # current model; saarika:v2 deprecated
_TTS_MODEL   = "bulbul:v3"
_TTS_SPEAKER = "priya"           # works for both hi-IN and en-IN
_TTS_RATE    = 8000              # Hz — smaller payload, adequate quality

# Sarvam rejects "audio/webm;codecs=opus" — strip codec suffix before forwarding
_CT_STRIP = {
    "audio/webm;codecs=opus": "audio/webm",
    "audio/webm;codecs=vp8": "audio/webm",
    "audio/ogg;codecs=opus": "audio/ogg",
}


def _clean_ct(content_type: str) -> str:
    return _CT_STRIP.get(content_type, content_type)


def _key() -> str:
    k = os.environ.get("SARVAM_API_KEY", "")
    if not k:
        raise HTTPException(status_code=503, detail="SARVAM_API_KEY not configured")
    return k


# ─── Response / Request models ────────────────────────────────────────────────

class TranscribeResponse(BaseModel):
    text: str
    language_code: str   # e.g. "hi-IN", "en-IN"


class SpeakRequest(BaseModel):
    text: str
    language: str = "en"   # "en" | "hi"


class SpeakResponse(BaseModel):
    audio_base64: str
    content_type: str = "audio/wav"


# ─── Endpoints ─────────────────────────────────────────────────────────────────

@router.post("/transcribe", response_model=TranscribeResponse)
async def transcribe(file: UploadFile = File(...)) -> TranscribeResponse:
    """Convert speech audio to text.  Accepts WebM, MP4, OGG, WAV."""
    api_key = _key()
    audio_bytes = await file.read()

    raw_ct = file.content_type or "audio/webm"
    clean_ct = _clean_ct(raw_ct)

    with httpx.Client(timeout=30) as client:
        resp = client.post(
            _SARVAM_STT,
            headers={"api-subscription-key": api_key},
            files={
                "file": (
                    file.filename or "recording.webm",
                    audio_bytes,
                    clean_ct,
                )
            },
            data={"model": _STT_MODEL},
        )

    if not resp.is_success:
        raise HTTPException(
            status_code=502,
            detail=f"Sarvam STT error {resp.status_code}: {resp.text[:300]}",
        )

    body = resp.json()
    return TranscribeResponse(
        text=body.get("transcript", "").strip(),
        language_code=body.get("language_code", "en-IN"),
    )


@router.post("/speak", response_model=SpeakResponse)
def speak(body: SpeakRequest) -> SpeakResponse:
    """Convert text to speech.  Returns base64-encoded WAV."""
    api_key = _key()
    lang_code = "hi-IN" if body.language == "hi" else "en-IN"
    text = body.text.strip()[:500]   # Sarvam per-input cap

    with httpx.Client(timeout=30) as client:
        resp = client.post(
            _SARVAM_TTS,
            headers={
                "api-subscription-key": api_key,
                "Content-Type": "application/json",
            },
            json={
                "inputs": [text],
                "target_language_code": lang_code,
                "speaker": _TTS_SPEAKER,
                "pitch": 0,
                "pace": 1.0,
                "loudness": 1.5,
                "speech_sample_rate": _TTS_RATE,
                "enable_preprocessing": True,
                "model": _TTS_MODEL,
            },
        )

    if not resp.is_success:
        raise HTTPException(
            status_code=502,
            detail=f"Sarvam TTS error {resp.status_code}: {resp.text[:300]}",
        )

    audios = resp.json().get("audios", [])
    if not audios:
        raise HTTPException(status_code=502, detail="Sarvam TTS returned no audio")

    return SpeakResponse(audio_base64=audios[0])
