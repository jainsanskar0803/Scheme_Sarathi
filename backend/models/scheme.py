from __future__ import annotations
from datetime import date
from typing import Optional
from pydantic import BaseModel, field_validator


class EligibilityRules(BaseModel):
    """
    Machine-readable eligibility rules extracted from eligibility_text by the
    preprocessing script.  Every field is Optional:

      None          = not yet extracted from the prose
      ["any"]       = extracted; scheme places no restriction on this dimension
      actual values = restriction applies and the rule engine must check it

    This model is intentionally never pre-filled — values come only from the
    LLM extraction step in scripts/extract_eligibility.py.
    """

    # Age
    min_age: Optional[int] = None          # years
    max_age: Optional[int] = None          # years

    # Income
    max_annual_income: Optional[int] = None  # INR per year

    # Identity
    gender: Optional[list[str]] = None
    # allowed values: "male" | "female" | "transgender" | "any"

    caste: Optional[list[str]] = None
    # allowed values: "SC" | "ST" | "OBC" | "EWS" | "general" | "any"

    # Geography
    states: Optional[list[str]] = None
    # state names as they appear in India, or "any" for central schemes

    domicile: Optional[list[str]] = None
    # allowed values: "rural" | "urban" | "any"

    # Occupation / sector
    occupation: Optional[list[str]] = None
    # e.g. "farmer" | "construction_worker" | "fisherman" | "student" | "any"

    # Special status flags
    disability_required: Optional[bool] = None
    bpl_required: Optional[bool] = None    # BPL card holder

    # Marital status
    marital_status: Optional[list[str]] = None
    # allowed values: "single" | "married" | "widow" | "divorced" | "any"


class Scheme(BaseModel):
    """
    Full scheme record.  Fields sourced from the CSV are always populated.
    Fields marked '# not in CSV' start as None and are populated by later
    enrichment steps — they are never invented.
    """

    # --- Identifiers ---
    slug: str                               # from CSV; unique key used for upsert

    # --- Names ---
    scheme_name: str                        # from CSV
    hindi_name: Optional[str] = None       # not in CSV

    # --- Description ---
    details: str                            # from CSV (long-form description)

    # --- Classification ---
    scheme_categories: list[str]           # parsed from CSV schemeCategory
    tags: list[str]                        # parsed from CSV tags
    level: str                             # "central" | "state"
    state: Optional[str] = None           # not in CSV; populated for state-level schemes

    # --- Beneficiary ---
    beneficiary: Optional[str] = None     # not in CSV; extracted from eligibility prose

    # --- What the scheme provides ---
    benefits: str                          # from CSV

    # --- Eligibility ---
    eligibility_text: str                  # from CSV (raw prose, unchanged)
    eligibility_rules: Optional[EligibilityRules] = None  # not in CSV; set by extract step

    # --- How to apply ---
    application: Optional[str] = None     # from CSV (missing for 2 rows)
    documents: Optional[str] = None       # from CSV (missing for 10 rows)

    # --- External references ---
    official_website: Optional[str] = None  # not in CSV
    source: Optional[str] = None            # not in CSV
    last_verified_date: Optional[date] = None  # not in CSV

    @field_validator("level")
    @classmethod
    def validate_level(cls, v: str) -> str:
        if v not in ("central", "state"):
            raise ValueError(f"level must be 'central' or 'state', got {v!r}")
        return v