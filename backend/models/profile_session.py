from __future__ import annotations
from typing import Optional
from pydantic import BaseModel
from backend.models.citizen_profile import CitizenProfile

# Fields the rule engine actively uses — ask these first
CORE_FIELDS: list[str] = [
    "age", "gender", "state", "caste",
    "annual_income", "occupation", "domicile",
    "is_disabled", "has_bpl_card", "marital_status",
]

# Fields that enrich the profile but are not directly evaluated by the engine
ENRICHMENT_FIELDS: list[str] = [
    "district", "land_holding_acres", "num_children",
    "has_electricity_connection", "owns_house", "owns_vehicle",
    "is_student", "is_farmer", "is_artisan", "is_business_owner",
]


class Completeness(BaseModel):
    filled: list[str]           # all non-None field names
    missing_core: list[str]     # core fields still None
    missing_enrichment: list[str]
    core_percent: float         # 0.0 – 1.0
    total_percent: float


class ProfileSession(BaseModel):
    session_id: str
    profile: CitizenProfile
    completeness: Completeness


def compute_completeness(profile: CitizenProfile) -> Completeness:
    data = profile.model_dump()
    filled = [k for k, v in data.items() if v is not None]
    missing_core = [f for f in CORE_FIELDS if data.get(f) is None]
    missing_enrichment = [f for f in ENRICHMENT_FIELDS if data.get(f) is None]
    all_fields = CORE_FIELDS + ENRICHMENT_FIELDS
    return Completeness(
        filled=filled,
        missing_core=missing_core,
        missing_enrichment=missing_enrichment,
        core_percent=round(1 - len(missing_core) / len(CORE_FIELDS), 2),
        total_percent=round(
            (len(CORE_FIELDS) - len(missing_core) +
             len(ENRICHMENT_FIELDS) - len(missing_enrichment)) / len(all_fields), 2
        ),
    )