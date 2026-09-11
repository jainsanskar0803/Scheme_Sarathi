"""Response models for POST /api/match."""
from __future__ import annotations

from typing import Literal, Optional

from pydantic import BaseModel

from backend.models.match_result import ConditionResult, Verdict

ExplanationStatus = Literal["PASS", "NEAR_MISS", "FAIL", "NOT_PROVIDED"]


class ConditionExplanation(BaseModel):
    """One row in the human-readable eligibility breakdown."""

    field: str                       # raw profile field name, e.g. "age"
    label: str                       # display label, e.g. "Age"
    requirement: str                 # e.g. "At least 18 years old"
    citizen_value_display: str       # e.g. "42 years" | "Not provided"
    status: ExplanationStatus        # PASS | NEAR_MISS | FAIL | NOT_PROVIDED

    # Near-miss detail fields (None unless status == "NEAR_MISS")
    gap: Optional[str] = None        # compact distance: "₹50,000 above the limit" | "2 years above maximum"
    note: Optional[str] = None       # full sentence: "Your income is ₹50,000 above the stated limit of ₹2,50,000"


class SchemeMatchResult(BaseModel):
    """Full eligibility result for one scheme."""

    # ── Identity ────────────────────────────────────────────────────────────
    scheme_id: str
    scheme_name: str
    category_display: list[str]
    tags: list[str]

    # ── Verdict ─────────────────────────────────────────────────────────────
    verdict: Verdict

    # ── What the scheme gives ────────────────────────────────────────────────
    benefit: str

    # ── Rule breakdown (raw) ────────────────────────────────────────────────
    passed_rules: list[ConditionResult]
    failed_rules: list[ConditionResult]   # includes near-miss failures
    near_miss_rules: list[ConditionResult]  # subset of failed_rules
    skipped_count: int                    # conditions the engine could not evaluate

    # ── Human-readable explanation ───────────────────────────────────────────
    explanation: list[ConditionExplanation]   # ordered: PASS → NEAR_MISS → FAIL → NOT_PROVIDED

    # ── Contextual information ───────────────────────────────────────────────
    unverified_criteria: list[str]        # things we know but couldn't encode as rules
    missing_information: list[str]        # eligibility info not available for this scheme

    # ── Next steps ──────────────────────────────────────────────────────────
    required_documents: Optional[str]
    application_method: Optional[str]
    source: str                           # "Central Government" | "State Government – X"
    official_website: Optional[str]


class MatchResponse(BaseModel):
    """Full response for POST /api/match."""

    session_id: Optional[str]
    profile: dict
    completeness: dict

    # Results grouped by verdict
    eligible: list[SchemeMatchResult]
    near_miss: list[SchemeMatchResult]
    insufficient_information: list[SchemeMatchResult]
    ineligible: list[SchemeMatchResult]

    total_schemes: int
