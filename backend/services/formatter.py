"""
Deterministic explainability formatter.

Converts ConditionResult objects (raw rule-engine output) into
ConditionExplanation objects (human-readable display rows).

This module NEVER calls the LLM.  All strings are generated from
structured data using pure Python string templates.
"""
from __future__ import annotations

from typing import Any

from backend.models.match_result import ConditionResult
from backend.models.match_response import ConditionExplanation

# ---------------------------------------------------------------------------
# Field metadata
# ---------------------------------------------------------------------------

_LABELS: dict[str, str] = {
    "age":                      "Age",
    "annual_income":            "Annual Income",
    "gender":                   "Gender",
    "caste":                    "Caste Category",
    "state":                    "State of Residence",
    "domicile":                 "Residence Type",
    "occupation":               "Occupation",
    "marital_status":           "Marital Status",
    "is_disabled":              "Disability Status",
    "has_bpl_card":             "BPL Ration Card",
}

# Status ordering for sorting (lower = shown first)
_STATUS_ORDER = {"PASS": 0, "NEAR_MISS": 1, "FAIL": 2, "NOT_PROVIDED": 3}


# ---------------------------------------------------------------------------
# INR formatter (Indian numbering system: 3-2-2-2 grouping)
# ---------------------------------------------------------------------------

def _fmt_inr(v: int | float) -> str:
    """Format an integer amount in Indian Rupee notation (₹X,XX,XXX)."""
    s = str(int(v))
    if len(s) <= 3:
        return f"₹{s}"
    last3 = s[-3:]
    rest = s[:-3]
    groups: list[str] = []
    while len(rest) > 2:
        groups.insert(0, rest[-2:])
        rest = rest[:-2]
    if rest:
        groups.insert(0, rest)
    return "₹" + ",".join(groups) + "," + last3


# ---------------------------------------------------------------------------
# Requirement string builders
# ---------------------------------------------------------------------------

def _join_or(values: list[str]) -> str:
    """Join a list with commas, last two with ' or '."""
    if len(values) == 1:
        return values[0]
    return ", ".join(values[:-1]) + " or " + values[-1]


def _format_requirement(field: str, operator: str, required: Any) -> str:
    """Produce a single human-readable requirement sentence."""
    if field == "age":
        if operator == "gte":
            return f"At least {required} years old"
        if operator == "lte":
            return f"{required} years old or younger"

    if field == "annual_income" and operator == "lte":
        return f"Annual income at most {_fmt_inr(required)}"

    if operator == "in":
        # Filter out "any" — should not appear here but guard anyway
        vals = [v for v in required if v != "any"]
        label = _LABELS.get(field, field.replace("_", " ").title())
        return f"{label}: {_join_or(vals)}"

    if operator == "boolean":
        if field == "is_disabled":
            return "Must have a recognized disability"
        if field == "has_bpl_card":
            return "Must hold a BPL (Below Poverty Line) ration card"

    # Fallback
    return f"{field} {operator} {required!r}"


# ---------------------------------------------------------------------------
# Citizen value display
# ---------------------------------------------------------------------------

def _format_citizen_value(field: str, value: Any) -> str:
    if value is None:
        return "Not provided"
    if field == "age":
        return f"{value} years"
    if field == "annual_income":
        return _fmt_inr(value)
    if field in ("is_disabled", "has_bpl_card"):
        return "Yes" if value else "No"
    return str(value)


# ---------------------------------------------------------------------------
# Near-miss detail builders
# ---------------------------------------------------------------------------

def _near_miss_gap(field: str, operator: str, required: Any, actual: Any) -> str | None:
    """
    Compact gap string shown alongside the status badge.
    e.g. "₹50,000 above the limit" | "2 years above maximum"
    """
    if field == "age":
        if operator == "lte":
            excess = int(actual) - int(required)
            unit = "year" if excess == 1 else "years"
            return f"{excess} {unit} above the maximum age"
        if operator == "gte":
            shortfall = int(required) - int(actual)
            unit = "year" if shortfall == 1 else "years"
            return f"{shortfall} {unit} below the minimum age"
    if field == "annual_income" and operator == "lte":
        excess = int(actual) - int(required)
        return f"{_fmt_inr(excess)} above the income limit"
    return None


def _near_miss_note(field: str, operator: str, required: Any, actual: Any) -> str | None:
    """
    Full explanatory sentence for a near-miss condition.
    e.g. "Your income is ₹50,000 above the stated limit of ₹2,50,000"
    """
    if field == "age":
        if operator == "lte":
            excess = int(actual) - int(required)
            unit = "year" if excess == 1 else "years"
            return f"You are {excess} {unit} above the maximum age of {required}"
        if operator == "gte":
            shortfall = int(required) - int(actual)
            unit = "year" if shortfall == 1 else "years"
            return f"You are {shortfall} {unit} below the minimum age of {required}"
    if field == "annual_income" and operator == "lte":
        excess = int(actual) - int(required)
        return (
            f"Your income is {_fmt_inr(excess)} above the stated limit of {_fmt_inr(required)}"
        )
    return None


# ---------------------------------------------------------------------------
# Status mapping
# ---------------------------------------------------------------------------

def _status(cond: ConditionResult) -> str:
    if cond.passed is None:
        return "NOT_PROVIDED"
    if cond.passed:
        return "PASS"
    return "NEAR_MISS" if cond.is_near_miss else "FAIL"


# ---------------------------------------------------------------------------
# Public API
# ---------------------------------------------------------------------------

def explain_condition(cond: ConditionResult) -> ConditionExplanation:
    """Convert one ConditionResult into a human-readable ConditionExplanation."""
    status = _status(cond)
    gap = note = None
    if cond.is_near_miss:
        gap = _near_miss_gap(cond.field, cond.operator, cond.required_value, cond.actual_value)
        note = _near_miss_note(cond.field, cond.operator, cond.required_value, cond.actual_value)
    return ConditionExplanation(
        field=cond.field,
        label=_LABELS.get(cond.field, cond.field.replace("_", " ").title()),
        requirement=_format_requirement(cond.field, cond.operator, cond.required_value),
        citizen_value_display=_format_citizen_value(cond.field, cond.actual_value),
        status=status,
        gap=gap,
        note=note,
    )


def explain_conditions(conditions: list[ConditionResult]) -> list[ConditionExplanation]:
    """
    Format all conditions for display.

    Auto-pass "no restriction" conditions (required_value contains "any") are
    excluded — they carry no information the user needs to see.

    Results are ordered: PASS → NEAR_MISS → FAIL → NOT_PROVIDED.
    """
    explanations = [
        explain_condition(c)
        for c in conditions
        if not (
            isinstance(c.required_value, list)
            and "any" in c.required_value
            and c.passed is True
        )
    ]
    return sorted(explanations, key=lambda e: _STATUS_ORDER[e.status])