"""
Document verification endpoint.

POST /api/documents/verify
  - Accepts a base64-encoded image or PDF
  - Uses Tesseract OCR (images) / pypdf (PDFs) to extract text
  - Sends extracted text to Sarvam sarvam-105b to identify type + extract fields
  - Compares extracted fields against the citizen's profile (via session_id)
  - Returns type_match, field_checks, overall_verified, rejection_reason

POST /api/documents/identify  (legacy — kept for backward compat)
  - Lighter endpoint: type identification only, no profile comparison

Design constraints:
  - Does NOT verify authenticity with any government database
  - Does NOT affect eligibility decisions
  - Always returns a disclaimer
  - Gracefully degrades if SARVAM_API_KEY is absent
"""
from __future__ import annotations

import base64
import io
import json
import os
import re
from datetime import date as _date

import httpx
from fastapi import APIRouter, HTTPException
from pydantic import BaseModel

router = APIRouter(prefix="/documents", tags=["documents"])

_SARVAM_URL = "https://api.sarvam.ai/v1/chat/completions"
_MODEL      = "sarvam-105b"

_DISCLAIMER = (
    "Document type and fields are identified from OCR text only. "
    "This does not verify authenticity, validity, or official eligibility. "
    "Scheme Sarathi does not connect to any government database."
)

KNOWN_DOC_TYPES: list[str] = [
    "Aadhaar Card",
    "PAN Card",
    "Voter ID / Election Card",
    "Passport",
    "Driving License",
    "Income Certificate",
    "Caste Certificate",
    "Domicile / Residence Certificate",
    "BPL Card / Ration Card",
    "Land Document / Khatauni / Patta",
    "Birth Certificate",
    "Bank Passbook",
    "Disability Certificate",
    "Mark Sheet / Educational Certificate",
    "Bonafide Certificate",
    "Marriage Certificate",
    "Death Certificate",
    "Electricity Bill",
    "Photograph",
    "Other",
]

_DOC_TYPE_LIST = "\n".join(f"- {d}" for d in KNOWN_DOC_TYPES)

# ─── Sarvam prompt ────────────────────────────────────────────────────────────

_VERIFY_SYSTEM = f"""You are a document verification assistant for Indian government scheme applications.

You will receive text that was extracted via OCR from a scanned document or PDF.
Your task has three parts — complete all three:

PART 1 — Reality check:
Is this extracted text from a real government document?
- If the text contains meaningful content (names, dates, IDs, official keywords, addresses) → is_real_document: true
- If the text is blank, just a few random characters, or clearly from a non-document source → is_real_document: false
- OCR text is often imperfect — be lenient with spelling errors and garbled characters

PART 2 — Document type:
Identify from this list ONLY:
{_DOC_TYPE_LIST}
If it matches none → "Unknown"

Key signals:
- "UIDAI", "Unique Identification Authority", 12-digit number → Aadhaar Card
- "Income Tax Department", PAN format (AAAAA9999A) → PAN Card
- "Election Commission", EPIC → Voter ID / Election Card
- "Republic of India", "Passport No" → Passport
- "Driving Licence", "Motor Vehicles Act" → Driving License

PART 3 — Field extraction:
Extract ONLY what is visible in the text. Never guess.
- name: full name as printed
- date_of_birth: as printed (DD/MM/YYYY or YYYY format)
- gender: "Male", "Female", or "Transgender"
- state: state name from the address or header
- document_number: the official ID number

Return ONLY valid JSON — no markdown, no explanation:
{{
  "is_real_document": true | false,
  "identified_type": "<type from list, or Unknown>",
  "confidence": "high" | "medium" | "low",
  "reason": "<one sentence: key evidence from the text>",
  "extracted_fields": {{
    "name": "<as printed or null>",
    "date_of_birth": "<as printed or null>",
    "gender": "<Male/Female/Transgender or null>",
    "state": "<state name or null>",
    "document_number": "<official number or null>"
  }}
}}"""


# ─── OCR + PDF text extraction ────────────────────────────────────────────────

def _extract_text(image_base64: str, image_mime: str) -> str:
    """Extract text from an image (via Tesseract OCR) or PDF (via pypdf)."""
    raw = base64.b64decode(image_base64)

    if image_mime == "application/pdf":
        try:
            import pypdf
            reader = pypdf.PdfReader(io.BytesIO(raw))
            parts = [page.extract_text() or "" for page in reader.pages]
            return "\n".join(parts).strip()
        except Exception:
            return ""

    # Image path — use Tesseract OCR
    try:
        import pytesseract
        from PIL import Image

        img = Image.open(io.BytesIO(raw))
        # Try English; Hindi tessdata not always present — degrade gracefully
        try:
            text = pytesseract.image_to_string(img, lang="eng+hin")
        except pytesseract.pytesseract.TesseractError:
            text = pytesseract.image_to_string(img, lang="eng")
        return text.strip()
    except Exception:
        return ""


# ─── Sarvam LLM call ─────────────────────────────────────────────────────────

def _call_sarvam(system: str, user_text: str) -> dict:
    api_key = os.environ.get("SARVAM_API_KEY", "")
    if not api_key:
        return {"_no_key": True}

    payload = {
        "model": _MODEL,
        "messages": [
            {"role": "system", "content": system},
            {"role": "user", "content": user_text},
        ],
        "temperature": 0.0,
        "max_tokens": 4096,
    }

    with httpx.Client(timeout=30) as client:
        resp = client.post(
            _SARVAM_URL,
            headers={"api-subscription-key": api_key, "Content-Type": "application/json"},
            json=payload,
        )
        resp.raise_for_status()

    body = resp.json()
    raw = (body["choices"][0]["message"]["content"] or "").strip()
    if not raw:
        raise ValueError(f"Sarvam returned empty content (finish_reason={body['choices'][0].get('finish_reason')})")
    if raw.startswith("```"):
        raw = "\n".join(ln for ln in raw.splitlines() if not ln.startswith("```"))
    return json.loads(raw)


# ─── Request / Response models ─────────────────────────────────────────────────

class IdentifyRequest(BaseModel):
    image_base64: str
    image_mime: str = "image/jpeg"
    required_documents: list[str] = []


class IdentifyResponse(BaseModel):
    identified_type: str
    confidence: str
    alternatives: list[str]
    reason: str
    matched_required: str | None
    disclaimer: str


class VerifyRequest(BaseModel):
    image_base64: str
    image_mime: str = "image/jpeg"
    required_document: str
    session_id: str | None = None


class FieldCheckModel(BaseModel):
    field: str
    label: str
    profile_value: str
    document_value: str | None
    match: bool | None


class VerifyResponse(BaseModel):
    is_real_document: bool
    identified_type: str
    confidence: str
    type_match: bool
    extracted_fields: dict
    field_checks: list[FieldCheckModel]
    overall_verified: bool
    rejection_reason: str | None
    disclaimer: str


# ─── Document type matching ───────────────────────────────────────────────────

_KEYWORDS: dict[str, list[str]] = {
    "aadhaar": ["aadhaar", "aadhar", "uid", "uidai"],
    "pan": ["pan card", "permanent account number", "income tax department"],
    "voter": ["voter id", "election card", "epic", "electoral"],
    "passport": ["passport"],
    "driving": ["driving license", "driving licence", "dl", "motor vehicle"],
    "income": ["income certificate", "income proof", "income tax return", "itr"],
    "caste": ["caste certificate", "sc certificate", "st certificate", "obc certificate", "community certificate"],
    "domicile": ["domicile", "residence certificate", "residential certificate", "local resident"],
    "ration": ["ration card", "bpl card", "food security", "antyodaya"],
    "land": ["land", "khatauni", "patta", "khasra", "land record", "revenue record", "property"],
    "birth": ["birth certificate"],
    "bank": ["bank passbook", "passbook", "bank statement", "bank account"],
    "disability": ["disability certificate", "divyang", "handicapped", "pwbd"],
    "mark": ["mark sheet", "marksheet", "educational certificate", "degree", "bonafide"],
    "marriage": ["marriage certificate", "nikah"],
    "death": ["death certificate"],
    "electricity": ["electricity bill", "power bill", "bescom", "mseb"],
    "photo": ["photograph", "passport size photo", "photo"],
}


def _keywords_for(text: str) -> set[str]:
    t = text.lower()
    return {group for group, terms in _KEYWORDS.items() if any(term in t for term in terms)}


def match_to_required(identified: str, required: list[str]) -> str | None:
    if not identified or identified.lower() == "unknown":
        return None
    id_lower = identified.lower()
    for req in required:
        req_lower = req.lower()
        if req_lower in id_lower or id_lower in req_lower:
            return req
    id_groups = _keywords_for(id_lower)
    for req in required:
        if id_groups & _keywords_for(req):
            return req
    return None


def parse_required_documents(raw: str | None) -> list[str]:
    if not raw or raw in ("None", "null", ""):
        return []
    numbered = re.split(r'\d+[.)]\s+', raw)
    if len(numbered) > 2:
        return [s.strip().rstrip('.').strip() for s in numbered if s.strip() and len(s.strip()) > 3]
    by_line = [s.strip() for s in raw.split('\n') if s.strip() and len(s.strip()) > 3]
    if len(by_line) > 1:
        return by_line
    by_period = [s.strip().rstrip('.') for s in raw.split('. ') if s.strip() and len(s.strip()) > 3]
    if len(by_period) > 1:
        return by_period
    return [raw.strip()]


# ─── Profile field comparison ─────────────────────────────────────────────────

_STATE_ALIASES: dict[str, str] = {
    "up": "uttar pradesh", "mp": "madhya pradesh", "mh": "maharashtra",
    "rj": "rajasthan", "hr": "haryana", "pb": "punjab", "gj": "gujarat",
    "dl": "delhi", "nd": "delhi", "ka": "karnataka", "kn": "karnataka",
    "tn": "tamil nadu", "ap": "andhra pradesh", "ts": "telangana",
    "wb": "west bengal", "or": "odisha", "od": "odisha", "br": "bihar",
    "jh": "jharkhand", "cg": "chhattisgarh", "ct": "chhattisgarh",
    "hp": "himachal pradesh", "uk": "uttarakhand", "ut": "uttarakhand",
    "ga": "goa", "kl": "kerala", "as": "assam", "mn": "manipur",
    "ml": "meghalaya", "mz": "mizoram", "nl": "nagaland", "tr": "tripura",
    "ar": "arunachal pradesh", "sk": "sikkim", "jk": "jammu and kashmir",
    "la": "ladakh", "ch": "chandigarh", "py": "puducherry",
    "pondicherry": "puducherry", "uttaranchal": "uttarakhand", "orissa": "odisha",
    "new delhi": "delhi",
}


def _norm_state(s: str) -> str:
    s = s.lower().strip().rstrip('.')
    return _STATE_ALIASES.get(s, s)


def _norm_gender(s: str) -> str:
    s = s.lower().strip()
    if s in ("m", "male"): return "male"
    if s in ("f", "female"): return "female"
    if "trans" in s: return "transgender"
    return s


def _age_from_dob(dob_str: str) -> int | None:
    today = _date.today()
    m = re.match(r'(\d{1,2})[/\-.](\d{1,2})[/\-.](\d{4})', dob_str.strip())
    if m:
        day, month, year = int(m.group(1)), int(m.group(2)), int(m.group(3))
        try:
            dob = _date(year, month, day)
            return today.year - dob.year - ((today.month, today.day) < (dob.month, dob.day))
        except ValueError:
            pass
    m2 = re.search(r'\b(\d{4})\b', dob_str.strip())
    if m2:
        year = int(m2.group(1))
        if 1900 < year <= today.year:
            return today.year - year
    return None


def _compare_with_profile(extracted: dict, profile) -> list[dict]:
    checks: list[dict] = []

    if profile.gender:
        doc_gender = extracted.get("gender")
        if doc_gender:
            checks.append({
                "field": "gender", "label": "Gender",
                "profile_value": profile.gender.capitalize(),
                "document_value": doc_gender,
                "match": _norm_gender(doc_gender) == _norm_gender(profile.gender),
            })
        else:
            checks.append({
                "field": "gender", "label": "Gender",
                "profile_value": profile.gender.capitalize(),
                "document_value": None, "match": None,
            })

    if profile.age:
        doc_dob = extracted.get("date_of_birth")
        if doc_dob:
            doc_age = _age_from_dob(str(doc_dob))
            if doc_age is not None:
                checks.append({
                    "field": "age", "label": "Age",
                    "profile_value": f"{profile.age} years",
                    "document_value": f"~{doc_age} yrs (DOB {doc_dob})",
                    "match": abs(doc_age - profile.age) <= 2,
                })
            else:
                checks.append({
                    "field": "age", "label": "Age",
                    "profile_value": f"{profile.age} years",
                    "document_value": doc_dob, "match": None,
                })
        else:
            checks.append({
                "field": "age", "label": "Age",
                "profile_value": f"{profile.age} years",
                "document_value": None, "match": None,
            })

    if profile.state:
        doc_state = extracted.get("state")
        if doc_state:
            checks.append({
                "field": "state", "label": "State",
                "profile_value": profile.state,
                "document_value": doc_state,
                "match": _norm_state(doc_state) == _norm_state(profile.state),
            })
        else:
            checks.append({
                "field": "state", "label": "State",
                "profile_value": profile.state,
                "document_value": None, "match": None,
            })

    return checks


# ─── Endpoints ─────────────────────────────────────────────────────────────────

@router.post("/identify", response_model=IdentifyResponse)
def identify_document(body: IdentifyRequest) -> IdentifyResponse:
    """Legacy lightweight identification endpoint."""
    text = _extract_text(body.image_base64, body.image_mime)

    if not text:
        return IdentifyResponse(
            identified_type="Unknown", confidence="low", alternatives=[],
            reason="Could not extract text from the document.",
            matched_required=None, disclaimer=_DISCLAIMER,
        )

    try:
        result = _call_sarvam(_VERIFY_SYSTEM, f"Extracted document text:\n{text[:3000]}")
    except (httpx.HTTPStatusError, httpx.TimeoutException, json.JSONDecodeError):
        result = {"identified_type": "Unknown", "confidence": "low", "alternatives": [], "reason": "Analysis failed."}

    if result.get("_no_key"):
        return IdentifyResponse(
            identified_type="Unknown", confidence="low", alternatives=[],
            reason="SARVAM_API_KEY not configured.", matched_required=None, disclaimer=_DISCLAIMER,
        )

    identified = result.get("identified_type", "Unknown")
    matched = match_to_required(identified, body.required_documents) if body.required_documents else None
    return IdentifyResponse(
        identified_type=identified,
        confidence=result.get("confidence", "low"),
        alternatives=result.get("alternatives", []),
        reason=result.get("reason", ""),
        matched_required=matched,
        disclaimer=_DISCLAIMER,
    )


@router.post("/verify", response_model=VerifyResponse)
def verify_document(body: VerifyRequest) -> VerifyResponse:
    """
    Full document verification:
    1. OCR / PDF text extraction
    2. Sarvam LLM identifies type + extracts fields
    3. Profile field comparison
    """
    # ── Step 1: Extract text ──────────────────────────────────────────────────
    text = _extract_text(body.image_base64, body.image_mime)

    if not text or len(text.strip()) < 20:
        return VerifyResponse(
            is_real_document=False,
            identified_type="Unknown",
            confidence="low",
            type_match=False,
            extracted_fields={},
            field_checks=[],
            overall_verified=False,
            rejection_reason="Could not read text from the document. Please upload a clearer photo or scan.",
            disclaimer=_DISCLAIMER,
        )

    # ── Step 2: Sarvam analysis ───────────────────────────────────────────────
    try:
        result = _call_sarvam(_VERIFY_SYSTEM, f"Extracted document text:\n{text[:3000]}")
    except httpx.HTTPStatusError as exc:
        raise HTTPException(status_code=502, detail=f"Sarvam API error {exc.response.status_code}")
    except httpx.TimeoutException:
        raise HTTPException(status_code=504, detail="Sarvam API timed out")
    except json.JSONDecodeError:
        result = {
            "is_real_document": False,
            "identified_type": "Unknown",
            "confidence": "low",
            "reason": "Could not parse analysis response.",
            "extracted_fields": {},
        }

    if result.get("_no_key"):
        return VerifyResponse(
            is_real_document=False,
            identified_type="Unknown",
            confidence="low",
            type_match=False,
            extracted_fields={},
            field_checks=[],
            overall_verified=False,
            rejection_reason="Document verification requires SARVAM_API_KEY to be configured.",
            disclaimer=_DISCLAIMER,
        )

    is_real = bool(result.get("is_real_document", False))
    identified = result.get("identified_type", "Unknown")
    extracted = result.get("extracted_fields") or {}
    confidence = result.get("confidence", "low")

    # ── Step 3: Reality check ─────────────────────────────────────────────────
    if not is_real:
        return VerifyResponse(
            is_real_document=False,
            identified_type=identified,
            confidence=confidence,
            type_match=False,
            extracted_fields=extracted,
            field_checks=[],
            overall_verified=False,
            rejection_reason="The upload does not appear to be a government document. Please upload a clear photo or scan of your document.",
            disclaimer=_DISCLAIMER,
        )

    # ── Step 4: Type match ────────────────────────────────────────────────────
    type_match = bool(match_to_required(identified, [body.required_document]))

    if not type_match:
        return VerifyResponse(
            is_real_document=True,
            identified_type=identified,
            confidence=confidence,
            type_match=False,
            extracted_fields=extracted,
            field_checks=[],
            overall_verified=False,
            rejection_reason=f'This appears to be "{identified}" but "{body.required_document}" is required. Please upload the correct document.',
            disclaimer=_DISCLAIMER,
        )

    # ── Step 5: Profile field comparison ─────────────────────────────────────
    field_checks_raw: list[dict] = []
    if body.session_id:
        from backend.db import session_store
        profile = session_store.session_get(body.session_id)
        if profile:
            field_checks_raw = _compare_with_profile(extracted, profile)

    field_checks = [FieldCheckModel(**c) for c in field_checks_raw]
    definite_mismatches = [c for c in field_checks if c.match is False]
    overall_verified = len(definite_mismatches) == 0

    rejection_reason = None
    if definite_mismatches:
        labels = ", ".join(c.label for c in definite_mismatches)
        rejection_reason = f"Details on the document don't match your profile: {labels}."

    return VerifyResponse(
        is_real_document=True,
        identified_type=identified,
        confidence=confidence,
        type_match=True,
        extracted_fields=extracted,
        field_checks=field_checks,
        overall_verified=overall_verified,
        rejection_reason=rejection_reason,
        disclaimer=_DISCLAIMER,
    )
