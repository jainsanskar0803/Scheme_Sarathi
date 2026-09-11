"""
POST /api/match

Runs the deterministic rule engine against all seed schemes for a given
citizen profile.  The LLM is NEVER called here — every eligibility
decision is made by pure Python comparisons.
"""
from __future__ import annotations

from fastapi import APIRouter, HTTPException
from pydantic import BaseModel

from backend.models.citizen_profile import CitizenProfile
from backend.models.match_response import MatchResponse, SchemeMatchResult
from backend.models.match_result import MatchResult
from backend.models.profile_session import compute_completeness
from backend.routes.profile import _get_or_404
from backend.services.formatter import explain_conditions
from backend.services.rule_engine import evaluate
from backend.services.scheme_store import SeedScheme, all_schemes

router = APIRouter(prefix="/match", tags=["match"])


class MatchRequest(BaseModel):
    session_id: str


# ---------------------------------------------------------------------------
# Internal helpers
# ---------------------------------------------------------------------------

def _to_scheme_result(scheme: SeedScheme, result: MatchResult) -> SchemeMatchResult:
    passed = [c for c in result.conditions if c.passed is True]
    failed = [c for c in result.conditions if c.passed is False]
    near_miss = [c for c in result.conditions if c.is_near_miss]

    return SchemeMatchResult(
        scheme_id=scheme.scheme_id,
        scheme_name=scheme.scheme_name,
        category_display=scheme.category_display,
        tags=scheme.tags,
        verdict=result.verdict,
        benefit=scheme.benefit,
        passed_rules=passed,
        failed_rules=failed,
        near_miss_rules=near_miss,
        skipped_count=result.skipped_count,
        explanation=explain_conditions(result.conditions),
        unverified_criteria=scheme.unverified_criteria,
        missing_information=scheme.missing_information,
        required_documents=scheme.required_documents,
        application_method=scheme.application_method,
        source=scheme.source,
        official_website=scheme.official_website,
    )


def run_match(profile: CitizenProfile) -> dict[str, list[SchemeMatchResult]]:
    """
    Pure function: evaluate profile against all seed schemes.
    Returns a dict with verdict-keyed lists, each sorted by passed_count desc.
    The rule engine never calls the LLM.
    """
    groups: dict[str, list[SchemeMatchResult]] = {
        "eligible": [],
        "near_miss": [],
        "insufficient_information": [],
        "ineligible": [],
    }

    for scheme in all_schemes():
        result = evaluate(profile, scheme.eligibility_rules)
        item = _to_scheme_result(scheme, result)
        groups[result.verdict].append(item)

    # Within each group sort by number of passed rules (descending) so the
    # best-matching schemes appear first.
    for lst in groups.values():
        lst.sort(key=lambda x: len(x.passed_rules), reverse=True)

    return groups


# ---------------------------------------------------------------------------
# Endpoint
# ---------------------------------------------------------------------------

@router.post("", response_model=MatchResponse)
def match(body: MatchRequest) -> MatchResponse:
    """
    Evaluate the citizen profile stored in the given session against all seed
    schemes.  Returns schemes grouped by verdict.

    Verdict definitions:
      eligible                – all evaluable conditions pass
      near_miss               – fails only by small margin (age ±2 yrs, income ±10%)
      insufficient_information – profile is missing fields needed to decide
      ineligible              – at least one condition fails definitively
    """
    profile = _get_or_404(body.session_id)
    completeness = compute_completeness(profile)
    groups = run_match(profile)

    return MatchResponse(
        session_id=body.session_id,
        profile=profile.model_dump(),
        completeness=completeness.model_dump(),
        **groups,
        total_schemes=sum(len(v) for v in groups.values()),
    )
