from __future__ import annotations

from backend.models.profile_session import CORE_FIELDS, ENRICHMENT_FIELDS

# Ask CORE_FIELDS in eligibility-priority order, then ENRICHMENT_FIELDS
_PRIORITY: list[str] = [
    "state",
    "age",
    "gender",
    "caste",
    "annual_income",
    "occupation",
    "domicile",
    "is_disabled",
    "has_bpl_card",
    "marital_status",
    # enrichment
    "district",
    "land_holding_acres",
    "num_children",
    "has_electricity_connection",
    "owns_house",
    "owns_vehicle",
    "is_student",
    "is_farmer",
    "is_artisan",
    "is_business_owner",
]

_EN: dict[str, str] = {
    "age":                      "How old are you?",
    "gender":                   "What is your gender? (male / female / transgender)",
    "state":                    "Which state do you live in?",
    "district":                 "Which district are you from?",
    "domicile":                 "Do you live in a rural area or an urban area?",
    "caste":                    "What is your caste category? (SC / ST / OBC / EWS / General)",
    "annual_income":            "What is your approximate annual household income?",
    "occupation":               "What is your primary occupation? (e.g. farmer, student, artisan, business owner)",
    "marital_status":           "What is your marital status? (single / married / widowed / divorced)",
    "num_children":             "How many children do you have?",
    "is_disabled":              "Do you have any disability?",
    "has_bpl_card":             "Do you have a BPL (Below Poverty Line) ration card?",
    "has_electricity_connection": "Does your home have an electricity connection?",
    "owns_house":               "Do you own the house you live in?",
    "owns_vehicle":             "Do you own any vehicle? (none / two-wheeler / four-wheeler)",
    "land_holding_acres":       "How much agricultural land do you own (in acres)?",
    "is_student":               "Are you currently a student?",
    "is_farmer":                "Are you a farmer?",
    "is_artisan":               "Are you an artisan or craftsperson?",
    "is_business_owner":        "Do you own a business?",
}

_HI: dict[str, str] = {
    "age":                      "आपकी उम्र क्या है?",
    "gender":                   "आपका लिंग क्या है? (पुरुष / महिला / ट्रांसजेंडर)",
    "state":                    "आप किस राज्य में रहते हैं?",
    "district":                 "आप किस जिले से हैं?",
    "domicile":                 "आप ग्रामीण क्षेत्र में रहते हैं या शहरी क्षेत्र में?",
    "caste":                    "आपकी जाति श्रेणी क्या है? (SC / ST / OBC / EWS / सामान्य)",
    "annual_income":            "आपकी वार्षिक घरेलू आय लगभग कितनी है?",
    "occupation":               "आपका मुख्य व्यवसाय क्या है? (जैसे किसान, छात्र, कारीगर, व्यवसायी)",
    "marital_status":           "आपकी वैवाहिक स्थिति क्या है? (अविवाहित / विवाहित / विधवा / तलाकशुदा)",
    "num_children":             "आपके कितने बच्चे हैं?",
    "is_disabled":              "क्या आपको कोई विकलांगता है?",
    "has_bpl_card":             "क्या आपके पास BPL (गरीबी रेखा से नीचे) राशन कार्ड है?",
    "has_electricity_connection": "क्या आपके घर में बिजली कनेक्शन है?",
    "owns_house":               "क्या आपके पास अपना मकान है?",
    "owns_vehicle":             "क्या आपके पास कोई वाहन है? (नहीं / दोपहिया / चौपहिया)",
    "land_holding_acres":       "आपके पास कृषि भूमि कितने एकड़ है?",
    "is_student":               "क्या आप वर्तमान में छात्र/छात्रा हैं?",
    "is_farmer":                "क्या आप किसान हैं?",
    "is_artisan":               "क्या आप कारीगर या शिल्पकार हैं?",
    "is_business_owner":        "क्या आपका कोई व्यवसाय है?",
}

# Occupation values that automatically imply the corresponding boolean flag,
# making it redundant to ask separately.
_OCC_TO_FLAG: dict[str, str] = {
    "farmer":        "is_farmer",
    "student":       "is_student",
    "artisan":       "is_artisan",
    "business_owner": "is_business_owner",
}
_FLAG_TO_OCC: dict[str, str] = {v: k for k, v in _OCC_TO_FLAG.items()}


def detect_language(text: str) -> str:
    """Return 'hi' if the text contains Devanagari characters, else 'en'."""
    return "hi" if any("ऀ" <= ch <= "ॿ" for ch in text) else "en"


def _already_covered(field: str, profile: dict) -> bool:
    """
    Return True if *field* is already implied by other filled fields and
    asking about it would be redundant.
    """
    occ = profile.get("occupation")

    # If occupation is set for a known role, its boolean flag is redundant
    if field in _FLAG_TO_OCC and occ == _FLAG_TO_OCC[field]:
        return True

    # If a boolean flag is True and we already know occupation from it,
    # asking occupation is redundant
    if field == "occupation":
        for flag, role in _FLAG_TO_OCC.items():
            if profile.get(flag) is True and occ == role:
                return True

    return False


def next_question(profile: dict, language: str = "en") -> str | None:
    """
    Return the next most-important question to ask the user, or None when
    all tracked fields are filled.
    """
    bank = _HI if language == "hi" else _EN
    for field in _PRIORITY:
        if profile.get(field) is None and not _already_covered(field, profile):
            return bank.get(field)
    return None