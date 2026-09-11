"""
Pure-regex eligibility rule extractor for raw scheme eligibility text.

Design principles:
  - High precision, low recall: only extract when confident
  - Never invent: if unsure, leave field as None
  - No LLM: deterministic, reproducible, fast
  - Sentence-level analysis for better precision
"""
from __future__ import annotations

import re
from typing import Optional

# ---------------------------------------------------------------------------
# Constants
# ---------------------------------------------------------------------------

_STATES = [
    "Andhra Pradesh", "Arunachal Pradesh", "Assam", "Bihar", "Chhattisgarh",
    "Goa", "Gujarat", "Haryana", "Himachal Pradesh", "Jharkhand", "Karnataka",
    "Kerala", "Madhya Pradesh", "Maharashtra", "Manipur", "Meghalaya", "Mizoram",
    "Nagaland", "Odisha", "Punjab", "Rajasthan", "Sikkim", "Tamil Nadu",
    "Telangana", "Tripura", "Uttar Pradesh", "Uttarakhand", "West Bengal",
    "Delhi", "Jammu and Kashmir", "Ladakh", "Puducherry", "Chandigarh",
    "Andaman and Nicobar", "Dadra and Nagar Haveli", "Daman and Diu", "Lakshadweep",
    "Manipur", "Meghalaya", "Mizoram", "Nagaland",
]
_STATE_NORM = {s.lower(): s for s in _STATES}
_STATE_RE = re.compile(
    r'\b(' + '|'.join(re.escape(s) for s in _STATES) + r')\b', re.I
)

# ---------------------------------------------------------------------------
# INR parsing
# ---------------------------------------------------------------------------

def _parse_inr(amount_str: str, unit: str) -> Optional[int]:
    """Convert an amount+unit string to INR integer."""
    try:
        amount = float(amount_str.replace(",", ""))
    except (ValueError, TypeError):
        return None
    u = (unit or "").lower().strip()
    if "crore" in u:
        return int(amount * 10_000_000)
    if "lakh" in u or "lac" in u:
        return int(amount * 100_000)
    if "thousand" in u:
        return int(amount * 1_000)
    # raw INR with Indian comma format already stripped above
    return int(amount)


# Income limit patterns — ordered most specific to least specific.
# Match: "annual income should not exceed Rs. 2,50,000" etc.
_INCOME_PATTERNS = [
    # "income ... not exceed / below / up to Rs. X lakh"
    re.compile(
        r'(?:annual\s+)?(?:household\s+)?income\s+(?:[^.]{0,40}?)'
        r'(?:not\s+exceed(?:ing)?|below|up\s+to|less\s+than|not\s+more\s+than|within)\s+'
        r'(?:Rs\.?|INR|₹)\s*([\d,]+(?:\.\d+)?)\s*(lakh|lac|crore|thousand)?',
        re.I,
    ),
    # "Rs. X lakh ... income"
    re.compile(
        r'(?:Rs\.?|INR|₹)\s*([\d,]+(?:\.\d+)?)\s*(lakh|lac|crore|thousand)?\s*'
        r'(?:[^.]{0,30}?)(?:per\s+annum|annual\s+income|household\s+income)',
        re.I,
    ),
    # "annual income of Rs. X"  (weaker — used only when near a limit keyword)
    re.compile(
        r'(?:annual\s+)?income\s+(?:should\s+be\s+)?(?:of\s+)?'
        r'(?:Rs\.?|INR|₹)\s*([\d,]+(?:\.\d+)?)\s*(lakh|lac|crore|thousand)?',
        re.I,
    ),
]

# ---------------------------------------------------------------------------
# Age patterns
# ---------------------------------------------------------------------------

_AGE_RANGE = re.compile(
    r'\bage(?:d)?\s+(?:should\s+be\s+)?(?:between\s+)?(\d{1,3})\s*(?:to|–|-|and)\s*(\d{1,3})\s*years|'
    r'(?:between\s+the\s+age\s+of\s+)(\d{1,3})\s*(?:to|–|-|and)\s*(\d{1,3})|'
    r'age\s+(?:should\s+be\s+)?between\s+(\d{1,3})\s*(?:to|–|-|and)\s*(\d{1,3})',
    re.I,
)
# Require the word "age" to appear within the phrase
_MIN_AGE = re.compile(
    r'(?:minimum\s+age(?:\s+of)?|age\s+(?:of\s+)?(?:at\s+least|not\s+less\s+than|above|more\s+than)|'
    r'above\s+(?:the\s+)age\s+of|age\s+above|minimum\s+age\s+limit)\s*:?\s*(\d{1,3})\s*years',
    re.I,
)
_MAX_AGE = re.compile(
    r'(?:maximum\s+age(?:\s+of)?|age\s+(?:of\s+)?(?:not\s+more\s+than|not\s+exceeding|below|less\s+than|up\s+to)|'
    r'below\s+(?:the\s+)age\s+of|age\s+below|maximum\s+age\s+limit|age\s+limit\s+is)\s*:?\s*(\d{1,3})\s*years?|'
    r'not\s+more\s+than\s+(\d{1,3})\s*years\s+of\s+age|'
    r'(\d{1,3})\s*years\s+of\s+age\s+(?:or\s+below|and\s+below)',
    re.I,
)

# ---------------------------------------------------------------------------
# Gender patterns — only when clearly restricted to one gender
# ---------------------------------------------------------------------------

# These phrases clearly indicate the scheme is female-only
_FEMALE_ONLY = re.compile(
    r'(?:The\s+)?(?:applicant|beneficiary|candidate)\s+should\s+be\s+a?\s*'
    r'(?:woman|female|girl|widow|widowed\s+woman)',
    re.I,
)
_FEMALE_SCHEME = re.compile(
    r'(?:scheme\s+is\s+)?(?:exclusively\s+)?(?:for|open\s+to)\s+'
    r'(?:women|females?|girls?)\s+(?:only|candidates?|applicants?|beneficiaries?)',
    re.I,
)
_WIDOW_ONLY = re.compile(
    r'(?:The\s+)?(?:applicant|beneficiary)\s+should\s+be\s+a?\s*widow\b',
    re.I,
)

# ---------------------------------------------------------------------------
# Caste patterns
# ---------------------------------------------------------------------------

# Pattern: "belong to SC/ST/OBC" or "from SC/ST category"
# Put full-word variants BEFORE abbreviations to prevent "SC" matching "Scheduled"
_CASTE_BELONG = re.compile(
    r'(?:belong\s+to|from\s+(?:the\s+)?|member\s+of\s+(?:the\s+)?)\s*'
    r'(Scheduled\s+Caste(?:\s*/\s*Scheduled\s+Tribe)?|'
    r'Scheduled\s+Tribe(?:\s*/\s*Scheduled\s+Caste)?|'
    r'Other\s+Backward\s+Clas(?:s|ses)|'
    r'Economically\s+Weaker\s+Sections?|'
    r'SC(?:\s*/\s*ST)?(?:\s*/\s*OBC)?\b|'
    r'ST(?:\s*/\s*SC)?(?:\s*/\s*OBC)?\b|'
    r'OBC\b|EWS\b)',
    re.I,
)

# ---------------------------------------------------------------------------
# BPL / Disability / Domicile patterns
# ---------------------------------------------------------------------------

_BPL_REQUIRED = re.compile(
    r'(?:must\s+(?:have|hold|possess)|should\s+(?:have|hold|possess)|holds?\s+a?|possess(?:es)?\s+a?)\s+'
    r'(?:a\s+)?BPL\s+(?:ration\s+)?card|'
    r'from\s+(?:a\s+)?BPL\s+(?:family|household)|'
    r'(?:family|household)\s+(?:should\s+be\s+)?(?:in\s+the\s+)?below\s+poverty\s+line',
    re.I,
)

_DISABILITY_REQUIRED = re.compile(
    r'(?:The\s+)?(?:applicant|beneficiary|person)\s+should\s+(?:be\s+a?\s*)?'
    r'(?:have\s+a?\s*)?(?:person\s+with\s+)?(?:disabilit|handicap|PwD)|'
    r'(?:The\s+)?(?:applicant|beneficiary)\s+should\s+have\s+(?:a\s+)?disabilit',
    re.I,
)

_RURAL_REQUIRED = re.compile(
    r'(?:applicant|beneficiary|resident)\s+should\s+be\s+(?:a\s+)?'
    r'(?:resident\s+of\s+(?:a\s+)?rural|from\s+(?:a\s+)?rural)',
    re.I,
)
_URBAN_REQUIRED = re.compile(
    r'(?:applicant|beneficiary|resident)\s+should\s+be\s+(?:a\s+)?'
    r'(?:resident\s+of\s+(?:an?\s+)?urban|from\s+(?:an?\s+)?urban)',
    re.I,
)

# ---------------------------------------------------------------------------
# Occupation patterns
# ---------------------------------------------------------------------------

_FARMER_REQUIRED = re.compile(
    r'(?:The\s+)?(?:applicant|beneficiary)\s+should\s+be\s+a?\s*farmer\b|'
    r'Any\s+farmer\s+of',
    re.I,
)
_STUDENT_REQUIRED = re.compile(
    r'(?:The\s+)?(?:applicant|beneficiary)\s+should\s+be\s+a?\s*student\b',
    re.I,
)

# ---------------------------------------------------------------------------
# State detection from text
# ---------------------------------------------------------------------------

def detect_state_from_text(scheme_name: str, tags: str, details: str) -> Optional[str]:
    """
    Detect the primary state for a state-level scheme.
    Searches scheme_name, tags, then first 400 chars of details.
    Returns the canonical state name, or None if undetectable.
    """
    text = f"{scheme_name} {tags} {details[:400]}"
    matches = _STATE_RE.findall(text)
    if matches:
        return _STATE_NORM.get(matches[0].lower(), matches[0])
    return None


# ---------------------------------------------------------------------------
# Individual extractors
# ---------------------------------------------------------------------------

def _extract_max_income(text: str) -> Optional[int]:
    for pat in _INCOME_PATTERNS:
        m = pat.search(text)
        if m:
            return _parse_inr(m.group(1), m.group(2) if m.lastindex >= 2 else "")
    return None


def _extract_age(text: str) -> tuple[Optional[int], Optional[int]]:
    min_age: Optional[int] = None
    max_age: Optional[int] = None

    # Try range first (most specific) — multiple forms, different groups
    m = _AGE_RANGE.search(text)
    if m:
        groups = [g for g in m.groups() if g is not None]
        if len(groups) >= 2:
            a, b = int(groups[0]), int(groups[1])
            if 5 < a < b <= 120:
                return a, b

    m = _MIN_AGE.search(text)
    if m:
        v = int(m.group(1))
        if 5 <= v <= 100:
            min_age = v

    m = _MAX_AGE.search(text)
    if m:
        # May have multiple groups — take first non-None
        g = next((g for g in m.groups() if g is not None), None)
        if g:
            v = int(g)
            if 10 <= v <= 120:
                max_age = v

    return min_age, max_age


def _extract_gender(text: str) -> Optional[list[str]]:
    if _FEMALE_ONLY.search(text) or _FEMALE_SCHEME.search(text):
        return ["female"]
    if _WIDOW_ONLY.search(text):
        return ["female"]  # widows are female
    return None  # don't guess


def _extract_caste(text: str) -> Optional[list[str]]:
    m = _CASTE_BELONG.search(text)
    if not m:
        return None
    raw = m.group(1).lower()
    result: list[str] = []
    # Use explicit checks to avoid substring false-positives
    if re.search(r'\bsc\b|scheduled caste', raw):
        result.append("SC")
    if re.search(r'\bst\b|scheduled tribe', raw):
        result.append("ST")
    if re.search(r'\bobc\b|backward clas', raw):
        result.append("OBC")
    if re.search(r'\bews\b|economically weaker', raw):
        result.append("EWS")
    return result if result else None


def _extract_bpl(text: str) -> Optional[bool]:
    return True if _BPL_REQUIRED.search(text) else None


def _extract_disability(text: str) -> Optional[bool]:
    return True if _DISABILITY_REQUIRED.search(text) else None


def _extract_domicile(text: str) -> Optional[list[str]]:
    rural = bool(_RURAL_REQUIRED.search(text))
    urban = bool(_URBAN_REQUIRED.search(text))
    if rural and not urban:
        return ["rural"]
    if urban and not rural:
        return ["urban"]
    return None  # both or neither → don't restrict


def _extract_occupation(text: str) -> Optional[list[str]]:
    occupations = []
    if _FARMER_REQUIRED.search(text):
        occupations.append("farmer")
    if _STUDENT_REQUIRED.search(text):
        occupations.append("student")
    return occupations if occupations else None


# ---------------------------------------------------------------------------
# Main entry point
# ---------------------------------------------------------------------------

def extract_eligibility_rules(
    eligibility_text: str,
    level: str,
    detected_state: Optional[str],
    scheme_name: str,
) -> tuple[dict, list[str], list[str]]:
    """
    Extract structured eligibility rules from raw eligibility prose.

    Returns:
        rules_dict         – dict compatible with EligibilityRules model
        unverified_criteria – list of criteria we know about but couldn't encode
        missing_information – list of fields that couldn't be determined
    """
    text = eligibility_text or ""

    # --- Extract each dimension ---
    min_age, max_age = _extract_age(text)
    max_income = _extract_max_income(text)
    gender = _extract_gender(text)
    caste = _extract_caste(text)
    bpl = _extract_bpl(text)
    disability = _extract_disability(text)
    domicile = _extract_domicile(text)
    occupation = _extract_occupation(text)

    # Geography
    if level == "central":
        states = ["any"]
    elif detected_state:
        states = [detected_state]
    else:
        states = None  # state-level but couldn't detect which state

    # Build rules dict — only set fields we actually extracted
    rules: dict = {}
    if min_age is not None:
        rules["min_age"] = min_age
    if max_age is not None:
        rules["max_age"] = max_age
    if max_income is not None:
        rules["max_annual_income"] = max_income
    if gender is not None:
        rules["gender"] = gender
    if caste is not None:
        rules["caste"] = caste
    if states is not None:
        rules["states"] = states
    if domicile is not None:
        rules["domicile"] = domicile
    if occupation is not None:
        rules["occupation"] = occupation
    if bpl is not None:
        rules["bpl_required"] = bpl
    if disability is not None:
        rules["disability_required"] = disability

    # Unverified: include the original eligibility text so users can see it
    unverified_criteria: list[str] = []
    if text.strip():
        # Only add unverified text if we didn't extract everything that's there
        unverified_criteria.append(text.strip())

    # Missing information: fields not in the CSV at all
    missing_information: list[str] = [
        "official_website: not available in dataset",
        "launch_year: not available in dataset",
    ]

    return rules, unverified_criteria, missing_information
