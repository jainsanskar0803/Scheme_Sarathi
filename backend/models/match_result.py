from __future__ import annotations
from typing import Any, Literal, Optional
from pydantic import BaseModel

Verdict = Literal["eligible", "near_miss", "ineligible", "insufficient_information"]

Operator = Literal[
    "equals",
    "not_equals",
    "gt",
    "gte",
    "lt",
    "lte",
    "in",
    "not_in",
    "boolean",
]


class ConditionResult(BaseModel):
    """Result of evaluating a single eligibility condition."""

    field: str                      # citizen profile field that was checked
    operator: Operator              # comparison operator used
    required_value: Any             # value or list the rule demands
    actual_value: Any               # value from the citizen profile (None = unknown)
    passed: Optional[bool]          # True | False | None (None = could not evaluate)
    is_near_miss: bool = False      # True when passed=False but only barely
    reason: str                     # human-readable explanation


class MatchResult(BaseModel):
    """Aggregate result of evaluating all conditions for one scheme."""

    verdict: Verdict
    conditions: list[ConditionResult]

    # Convenience counts
    passed_count: int
    failed_count: int
    skipped_count: int              # conditions where passed is None

    # Conditions that failed by a small margin (subset of conditions)
    near_miss_conditions: list[ConditionResult]