from __future__ import annotations

import json
import os

import httpx

_SARVAM_URL = "https://api.sarvam.ai/v1/chat/completions"
_MODEL = "sarvam-105b"

_SYSTEM = """\
You are a data-extraction assistant for an Indian government scheme eligibility system.

Extract ONLY the following fields from the user's message. Return a flat JSON object
containing ONLY the fields you can confidently determine. Do NOT include fields you
are unsure about. Do NOT invent or guess values.

Valid fields and their allowed values:
  age               : integer 0–120
  gender            : "male" | "female" | "transgender"
  state             : string — Indian state name in English, fully spelled out
                      (e.g. "UP" → "Uttar Pradesh", "MP" → "Madhya Pradesh",
                       "MH" → "Maharashtra", "RJ" → "Rajasthan")
  district          : string
  domicile          : "rural" | "urban"
                      (village / gram / gaon → "rural"; city / shahar → "urban")
  caste             : "SC" | "ST" | "OBC" | "EWS" | "general"
                      (सामान्य / General → "general")
  annual_income     : integer INR per year
                      Convert: "1.8 lakh" → 180000, "50 thousand" → 50000,
                               "1 crore" → 10000000
  occupation        : "farmer" | "student" | "artisan" | "business_owner" | free text
  is_student        : boolean
  is_farmer         : boolean
  is_artisan        : boolean
  is_business_owner : boolean
  land_holding_acres: float
  marital_status    : "single" | "married" | "widow" | "divorced"
  num_children      : integer
  is_disabled       : boolean
  has_bpl_card      : boolean
  has_electricity_connection : boolean
  owns_house        : boolean
  owns_vehicle      : "none" | "two_wheeler" | "four_wheeler"

Rules:
- The message may be in English, Hindi, or Hinglish. Understand all three.
- Only extract what is explicitly stated or unambiguously implied.
- Do not include a field if you are not confident.
- IMPORTANT: When a [Question] context is provided, use it to interpret short answers.
  A bare "yes" / "haan" / "ha" → true for the asked boolean field.
  A bare "no" / "nahi" / "nahi hai" / "nope" / "i dont have" / "nahin" → false for the asked boolean field.
- Return ONLY the JSON object — no markdown, no explanation.

Examples:

User: "I am 42, a farmer from Maharashtra and earn around 1.8 lakh per year."
Output: {"age": 42, "occupation": "farmer", "is_farmer": true, "state": "Maharashtra", "annual_income": 180000}

User: "मैं 35 साल का किसान हूं, राजस्थान से, मेरी आय 2 लाख है, SC वर्ग का हूं।"
Output: {"age": 35, "occupation": "farmer", "is_farmer": true, "state": "Rajasthan", "annual_income": 200000, "caste": "SC"}

User: "I'm a widow with 2 kids living in a village in UP, no vehicle."
Output: {"marital_status": "widow", "num_children": 2, "domicile": "rural", "state": "Uttar Pradesh", "owns_vehicle": "none"}

User: "main 28 saal ka hoon, Haryana se, kisan hoon, income 1.5 lakh hai."
Output: {"age": 28, "state": "Haryana", "occupation": "farmer", "is_farmer": true, "annual_income": 150000}

[Question: Do you have any disability?]
User: "no"
Output: {"is_disabled": false}

[Question: Do you have any disability?]
User: "nahi hai"
Output: {"is_disabled": false}

[Question: Do you have any disability?]
User: "i dont have"
Output: {"is_disabled": false}

[Question: Do you have a BPL (Below Poverty Line) ration card?]
User: "haan"
Output: {"has_bpl_card": true}

[Question: Do you own the house you live in?]
User: "yes"
Output: {"owns_house": true}

[Question: Are you currently a student?]
User: "no"
Output: {"is_student": false}
"""


def extract_profile_fields(message: str, context_question: str | None = None) -> dict:
    """
    Call Sarvam LLM to extract citizen profile fields from a natural-language message.
    Supports English, Hindi, and Hinglish natively.
    Returns a dict of only the fields that were confidently extracted.
    Raises ValueError if the LLM returns invalid JSON.
    Raises httpx.HTTPError on network/API failures.
    """
    api_key = os.environ.get("SARVAM_API_KEY", "")
    if not api_key:
        raise RuntimeError("SARVAM_API_KEY is not set in environment")

    user_content = f"[Question: {context_question}]\nUser: {message}" if context_question else message

    payload = {
        "model": _MODEL,
        "messages": [
            {"role": "system", "content": _SYSTEM},
            {"role": "user", "content": user_content},
        ],
        "temperature": 0.0,
        "max_tokens": 4096,
    }

    with httpx.Client(timeout=60) as client:
        response = client.post(
            _SARVAM_URL,
            headers={
                "api-subscription-key": api_key,
                "Content-Type": "application/json",
            },
            json=payload,
        )
        response.raise_for_status()

    raw = response.json()["choices"][0]["message"]["content"].strip()

    # Strip accidental markdown code fences
    if raw.startswith("```"):
        lines = raw.splitlines()
        raw = "\n".join(line for line in lines if not line.startswith("```"))

    return json.loads(raw)
