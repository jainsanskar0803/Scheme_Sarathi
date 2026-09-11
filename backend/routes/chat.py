from __future__ import annotations

import json

from fastapi import APIRouter, HTTPException
from pydantic import BaseModel, ValidationError

from backend.models.profile_session import compute_completeness
from backend.routes.profile import _get_or_404, _save
from backend.services.extractor import extract_profile_fields
from backend.services.interviewer import next_question

router = APIRouter(prefix="/chat", tags=["chat"])

# Persists language preference across turns per session.
# Avoids language flipping when user gives short English answers ("ST", "no")
# in what is otherwise a Hindi conversation.
_session_languages: dict[str, str] = {}


def _resolve_language(session_id: str, message: str) -> str:
    stored = _session_languages.get(session_id, "en")
    if any("ऀ" <= ch <= "ॿ" for ch in message):
        _session_languages[session_id] = "hi"
        return "hi"
    if len(message.split()) <= 3:
        # Short answer ("ST", "yes", "25") — keep stored language
        return stored
    _session_languages[session_id] = "en"
    return "en"


def _ack(extracted: dict, language: str) -> str:
    """
    Build a brief acknowledgment sentence confirming what was just extracted.
    Returns '' for bare yes/no turns — no need to echo back a boolean.
    """
    if not extracted:
        return ""

    # Boolean-only turns (answering yes/no questions) get no ack
    if all(isinstance(v, bool) for v in extracted.values()):
        return ""

    parts: list[str] = []

    if "age" in extracted:
        parts.append(
            f"{extracted['age']} साल के" if language == "hi" else f"{extracted['age']} years old"
        )

    if "gender" in extracted:
        g = str(extracted["gender"])
        hi_map = {"male": "पुरुष", "female": "महिला", "transgender": "ट्रांसजेंडर"}
        parts.append(hi_map.get(g, g) if language == "hi" else g.capitalize())

    if "occupation" in extracted:
        occ = str(extracted["occupation"])
        if language == "hi":
            occ = {"farmer": "किसान", "student": "छात्र", "artisan": "कारीगर",
                   "business_owner": "व्यवसायी"}.get(occ, occ)
        parts.append(occ)

    if "state" in extracted:
        s = str(extracted["state"])
        parts.append(f"{s} से" if language == "hi" else f"from {s}")

    if "district" in extracted:
        d = str(extracted["district"])
        parts.append(f"जिला {d}" if language == "hi" else f"{d} district")

    if "domicile" in extracted:
        d = str(extracted["domicile"])
        label = {"rural": "ग्रामीण", "urban": "शहरी"}.get(d, d) if language == "hi" else d
        parts.append(f"{label} क्षेत्र" if language == "hi" else f"{label} area")

    if "caste" in extracted:
        cat = str(extracted["caste"]).upper()
        parts.append(f"{cat} वर्ग" if language == "hi" else f"{cat} category")

    if "annual_income" in extracted:
        v = int(extracted["annual_income"])
        s = f"₹{v / 100000:.1f}L" if v >= 100000 else f"₹{v:,}"
        parts.append(f"आय {s}" if language == "hi" else f"income {s}")

    if "marital_status" in extracted:
        ms = str(extracted["marital_status"])
        hi_map = {"single": "अविवाहित", "married": "विवाहित", "widow": "विधवा", "divorced": "तलाकशुदा"}
        parts.append(hi_map.get(ms, ms) if language == "hi" else ms)

    if "num_children" in extracted:
        n = extracted["num_children"]
        parts.append(f"{n} बच्चे" if language == "hi" else f"{n} child" if n == 1 else f"{n} children")

    if "land_holding_acres" in extracted:
        a = extracted["land_holding_acres"]
        parts.append(f"{a} एकड़ जमीन" if language == "hi" else f"{a} acres land")

    if not parts:
        return ""

    if language == "hi":
        return "समझ गया — " + ", ".join(parts) + "।"
    return "Got it — " + ", ".join(parts) + "."


class ChatRequest(BaseModel):
    session_id: str
    message: str


class ChatResponse(BaseModel):
    session_id: str
    extracted: dict
    profile: dict
    completeness: dict
    next_question: str | None
    language: str


@router.post("", response_model=ChatResponse)
def chat(body: ChatRequest) -> ChatResponse:
    existing = _get_or_404(body.session_id)
    language = _resolve_language(body.session_id, body.message)

    # The question that was just asked — used as context so the LLM can
    # interpret short answers ("yes", "no", "ST") correctly.
    current_q = next_question(existing.model_dump(), language)

    # ── 1. Extract profile fields from the user's message ───────────────────
    try:
        extracted = extract_profile_fields(body.message, context_question=current_q)
    except json.JSONDecodeError as exc:
        raise HTTPException(status_code=502, detail=f"LLM returned invalid JSON: {exc}")
    except Exception as exc:
        raise HTTPException(status_code=502, detail=f"Extraction failed: {exc}")

    # ── 2. Merge into profile ────────────────────────────────────────────────
    try:
        updated = existing.merge(extracted)
    except ValidationError as exc:
        raise HTTPException(status_code=422, detail=json.loads(exc.json()))

    _save(body.session_id, updated)

    # ── 3. Next question + conversational acknowledgment ─────────────────────
    completeness = compute_completeness(updated)
    profile_dict = updated.model_dump()
    nq = next_question(profile_dict, language)

    # Prepend a brief ack so the response feels like a conversation, not a form.
    # e.g. "Got it — 35 years old, farmer, from Maharashtra. What is your caste…?"
    ack = _ack(extracted, language)
    full_response: str | None
    if nq is not None:
        full_response = f"{ack} {nq}".strip() if ack else nq
    else:
        full_response = None  # interview complete — frontend shows the done message

    return ChatResponse(
        session_id=body.session_id,
        extracted=extracted,
        profile=profile_dict,
        completeness=completeness.model_dump(),
        next_question=full_response,
        language=language,
    )
