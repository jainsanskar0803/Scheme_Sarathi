"""
Deterministic eligibility rule engine.

This module NEVER calls the LLM.  Every decision is a pure Python computation
over structured data.

Verdict semantics
-----------------
eligible                All evaluable conditions pass.
near_miss               All failing conditions fail by a small margin only
                        (age within 2 years, income within 10 %).
ineligible              At least one condition fails by a clear margin.
insufficient_information No condition definitively fails, but at least one
                        condition cannot be evaluated because the citizen
                        profile is missing the required field.
"""

from __future__ import annotations

from typing import Any

from backend.models.citizen_profile import CitizenProfile
from backend.models.match_result import (
    ConditionResult,
    MatchResult,
    Operator,
    Verdict,
)
from backend.models.scheme import EligibilityRules

# ---------------------------------------------------------------------------
# Near-miss thresholds
# ---------------------------------------------------------------------------

_NEAR_MISS_AGE_YEARS: int = 2
_NEAR_MISS_INCOME_FRACTION: float = 0.10  # 10 % above the income ceiling


# ---------------------------------------------------------------------------
# Low-level operator evaluation
# ---------------------------------------------------------------------------

def evaluate_operator(operator: Operator, actual: Any, required: Any) -> bool:
    """
    Evaluate a single comparison.  Raises ValueError for unknown operators.
    The caller is responsible for ensuring actual is not None before calling.
    """
    if operator == "equals":
        return actual == required
    if operator == "not_equals":
        return actual != required
    if operator == "gt":
        return actual > required
    if operator == "gte":
        return actual >= required
    if operator == "lt":
        return actual < required
    if operator == "lte":
        return actual <= required
    if operator == "in":
        return actual in required
    if operator == "not_in":
        return actual not in required
    if operator == "boolean":
        return bool(actual) == bool(required)
    raise ValueError(f"Unknown operator: {operator!r}")


# ---------------------------------------------------------------------------
# Near-miss detection (only called when a condition has already failed)
# ---------------------------------------------------------------------------

def _is_near_miss(
    field: str,
    operator: Operator,
    required: Any,
    actual: Any,
) -> bool:
    """Return True if a failing condition fails only by a small margin."""
    if field == "age":
        if operator == "gte" and isinstance(actual, int) and isinstance(required, int):
            shortfall = required - actual
            return 0 < shortfall <= _NEAR_MISS_AGE_YEARS
        if operator == "lte" and isinstance(actual, int) and isinstance(required, int):
            excess = actual - required
            return 0 < excess <= _NEAR_MISS_AGE_YEARS
    if field == "annual_income" and operator == "lte":
        if isinstance(actual, (int, float)) and isinstance(required, (int, float)) and required > 0:
            excess_fraction = (actual - required) / required
            return 0 < excess_fraction <= _NEAR_MISS_INCOME_FRACTION
    return False


# ---------------------------------------------------------------------------
# Single condition builder
# ---------------------------------------------------------------------------

def _make_condition(
    field: str,
    operator: Operator,
    required_value: Any,
    actual_value: Any,
) -> ConditionResult:
    """
    Build and evaluate one ConditionResult.

    If actual_value is None the condition cannot be evaluated → passed=None.
    """
    if actual_value is None:
        return ConditionResult(
            field=field,
            operator=operator,
            required_value=required_value,
            actual_value=None,
            passed=None,
            is_near_miss=False,
            reason=f"'{field}' not provided in citizen profile",
        )

    passed = evaluate_operator(operator, actual_value, required_value)
    near_miss = False if passed else _is_near_miss(field, operator, required_value, actual_value)
    reason = _build_reason(field, operator, required_value, actual_value, passed, near_miss)

    return ConditionResult(
        field=field,
        operator=operator,
        required_value=required_value,
        actual_value=actual_value,
        passed=passed,
        is_near_miss=near_miss,
        reason=reason,
    )


def _auto_pass(field: str, operator: Operator, required_value: Any, actual_value: Any) -> ConditionResult:
    """Return a pre-passed condition (used when the rule value is ['any'])."""
    return ConditionResult(
        field=field,
        operator=operator,
        required_value=required_value,
        actual_value=actual_value,
        passed=True,
        is_near_miss=False,
        reason=f"No restriction on '{field}'",
    )


# ---------------------------------------------------------------------------
# Human-readable reason strings
# ---------------------------------------------------------------------------

def _build_reason(
    field: str,
    operator: Operator,
    required: Any,
    actual: Any,
    passed: bool,
    near_miss: bool,
) -> str:
    op_symbols = {
        "equals": "==", "not_equals": "!=",
        "gt": ">", "gte": ">=", "lt": "<", "lte": "<=",
        "in": "in", "not_in": "not in", "boolean": "==",
    }
    symbol = op_symbols.get(operator, operator)
    status = "Pass" if passed else ("Near miss" if near_miss else "Fail")
    return f"[{status}] {field} {actual!r} {symbol} {required!r}"


# ---------------------------------------------------------------------------
# Condition builder — maps EligibilityRules fields → ConditionResult list
# ---------------------------------------------------------------------------

def _build_conditions(profile: CitizenProfile, rules: EligibilityRules) -> list[ConditionResult]:
    conditions: list[ConditionResult] = []

    # --- Numeric range checks ---
    if rules.min_age is not None:
        conditions.append(_make_condition("age", "gte", rules.min_age, profile.age))

    if rules.max_age is not None:
        conditions.append(_make_condition("age", "lte", rules.max_age, profile.age))

    if rules.max_annual_income is not None:
        conditions.append(
            _make_condition("annual_income", "lte", rules.max_annual_income, profile.annual_income)
        )

    # --- Categorical list checks ---
    # Each list field: ["any"] → auto-pass; real list → 'in' check
    _list_fields: list[tuple[str, str]] = [
        ("gender",         "gender"),
        ("caste",          "caste"),
        ("states",         "state"),
        ("domicile",       "domicile"),
        ("occupation",     "occupation"),
        ("marital_status", "marital_status"),
    ]
    for rule_attr, profile_attr in _list_fields:
        rule_val: list[str] | None = getattr(rules, rule_attr)
        if rule_val is None:
            continue  # not extracted yet → skip
        actual = getattr(profile, profile_attr)
        if "any" in rule_val:
            conditions.append(_auto_pass(profile_attr, "in", rule_val, actual))
        else:
            conditions.append(_make_condition(profile_attr, "in", rule_val, actual))

    # --- Boolean flag checks ---
    # Only add a condition when the scheme REQUIRES the flag to be True.
    # False means "not required" — no restriction to enforce.
    if rules.disability_required is True:
        conditions.append(
            _make_condition("is_disabled", "boolean", True, profile.is_disabled)
        )

    if rules.bpl_required is True:
        conditions.append(
            _make_condition("has_bpl_card", "boolean", True, profile.has_bpl_card)
        )

    return conditions


# ---------------------------------------------------------------------------
# Verdict logic (AND across all conditions)
# ---------------------------------------------------------------------------

def _determine_verdict(conditions: list[ConditionResult]) -> Verdict:
    """
    All conditions are implicitly ANDed.

    Priority (high → low):
      1. Any definite fail (not near_miss) → ineligible
      2. Any near_miss fail                → near_miss
      3. Any skipped (passed=None)         → insufficient_information
      4. All passed                        → eligible
    """
    definite_fails = [c for c in conditions if c.passed is False and not c.is_near_miss]
    near_miss_fails = [c for c in conditions if c.passed is False and c.is_near_miss]
    skipped = [c for c in conditions if c.passed is None]

    if definite_fails:
        return "ineligible"
    if near_miss_fails:
        return "near_miss"
    if skipped:
        return "insufficient_information"
    return "eligible"


# ---------------------------------------------------------------------------
# Public API
# ---------------------------------------------------------------------------

def evaluate(profile: CitizenProfile, rules: EligibilityRules) -> MatchResult:
    """
    Evaluate a citizen profile against a scheme's eligibility rules.

    Returns a MatchResult — never raises.
    The LLM is never called here.
    """
    conditions = _build_conditions(profile, rules)
    verdict = _determine_verdict(conditions)

    passed = [c for c in conditions if c.passed is True]
    failed = [c for c in conditions if c.passed is False]
    skipped = [c for c in conditions if c.passed is None]
    near_miss = [c for c in conditions if c.is_near_miss]

    return MatchResult(
        verdict=verdict,
        conditions=conditions,
        passed_count=len(passed),
        failed_count=len(failed),
        skipped_count=len(skipped),
        near_miss_conditions=near_miss,
    )


def evaluate_batch(
    profile: CitizenProfile,
    schemes: list[tuple[str, EligibilityRules]],
) -> list[tuple[str, MatchResult]]:
    """
    Evaluate one profile against many schemes.

    Args:
        profile:  The citizen profile.
        schemes:  List of (slug, EligibilityRules) pairs.

    Returns list of (slug, MatchResult) in the same order.
    """
    return [(slug, evaluate(profile, rules)) for slug, rules in schemes]