"""
Unit tests for the deterministic rule engine.
No LLM calls, no database, no I/O.
"""
from __future__ import annotations

import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

import pytest
from backend.models.citizen_profile import CitizenProfile
from backend.models.match_result import ConditionResult
from backend.models.scheme import EligibilityRules
from backend.services.rule_engine import (
    _NEAR_MISS_AGE_YEARS,
    _NEAR_MISS_INCOME_FRACTION,
    _build_conditions,
    _determine_verdict,
    evaluate,
    evaluate_batch,
    evaluate_operator,
)


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------

def _profile(**kw) -> CitizenProfile:
    return CitizenProfile(**kw)


def _rules(**kw) -> EligibilityRules:
    return EligibilityRules(**kw)


def _cond(passed, near_miss=False) -> ConditionResult:
    return ConditionResult(
        field="x", operator="equals",
        required_value=1, actual_value=1,
        passed=passed, is_near_miss=near_miss, reason="",
    )


# ---------------------------------------------------------------------------
# evaluate_operator — all 9 operators
# ---------------------------------------------------------------------------

class TestEvaluateOperator:
    def test_equals_true(self):
        assert evaluate_operator("equals", "SC", "SC") is True

    def test_equals_false(self):
        assert evaluate_operator("equals", "OBC", "SC") is False

    def test_not_equals_true(self):
        assert evaluate_operator("not_equals", "male", "female") is True

    def test_not_equals_false(self):
        assert evaluate_operator("not_equals", "SC", "SC") is False

    def test_gt_true(self):
        assert evaluate_operator("gt", 19, 18) is True

    def test_gt_false_equal(self):
        assert evaluate_operator("gt", 18, 18) is False

    def test_gt_false_less(self):
        assert evaluate_operator("gt", 17, 18) is False

    def test_gte_true_equal(self):
        assert evaluate_operator("gte", 18, 18) is True

    def test_gte_true_greater(self):
        assert evaluate_operator("gte", 25, 18) is True

    def test_gte_false(self):
        assert evaluate_operator("gte", 17, 18) is False

    def test_lt_true(self):
        assert evaluate_operator("lt", 17, 18) is True

    def test_lt_false_equal(self):
        assert evaluate_operator("lt", 18, 18) is False

    def test_lte_true_equal(self):
        assert evaluate_operator("lte", 60, 60) is True

    def test_lte_true_less(self):
        assert evaluate_operator("lte", 55, 60) is True

    def test_lte_false(self):
        assert evaluate_operator("lte", 61, 60) is False

    def test_in_true(self):
        assert evaluate_operator("in", "SC", ["SC", "ST", "OBC"]) is True

    def test_in_false(self):
        assert evaluate_operator("in", "general", ["SC", "ST"]) is False

    def test_not_in_true(self):
        assert evaluate_operator("not_in", "general", ["SC", "ST"]) is True

    def test_not_in_false(self):
        assert evaluate_operator("not_in", "SC", ["SC", "ST"]) is False

    def test_boolean_true_true(self):
        assert evaluate_operator("boolean", True, True) is True

    def test_boolean_false_true(self):
        assert evaluate_operator("boolean", False, True) is False

    def test_boolean_truthy_value(self):
        assert evaluate_operator("boolean", 1, True) is True

    def test_unknown_operator_raises(self):
        with pytest.raises(ValueError, match="Unknown operator"):
            evaluate_operator("xor", 1, 1)


# ---------------------------------------------------------------------------
# _determine_verdict — all four verdict paths
# ---------------------------------------------------------------------------

class TestDetermineVerdict:
    def test_eligible_all_pass(self):
        assert _determine_verdict([_cond(True), _cond(True)]) == "eligible"

    def test_eligible_empty_conditions(self):
        # No rules extracted → nothing to fail
        assert _determine_verdict([]) == "eligible"

    def test_ineligible_one_clear_fail(self):
        assert _determine_verdict([_cond(True), _cond(False)]) == "ineligible"

    def test_ineligible_trumps_near_miss(self):
        assert _determine_verdict([_cond(False, near_miss=True), _cond(False)]) == "ineligible"

    def test_near_miss_all_near_misses(self):
        assert _determine_verdict([_cond(True), _cond(False, near_miss=True)]) == "near_miss"

    def test_near_miss_multiple(self):
        assert _determine_verdict([_cond(False, near_miss=True), _cond(False, near_miss=True)]) == "near_miss"

    def test_insufficient_information_all_skipped(self):
        assert _determine_verdict([_cond(None), _cond(None)]) == "insufficient_information"

    def test_insufficient_information_pass_plus_skipped(self):
        assert _determine_verdict([_cond(True), _cond(None)]) == "insufficient_information"

    def test_ineligible_overrides_skipped(self):
        # Definite fail + unknown → still ineligible
        assert _determine_verdict([_cond(False), _cond(None)]) == "ineligible"

    def test_near_miss_overrides_skipped(self):
        # Near miss + unknown → near_miss (no definite fail)
        assert _determine_verdict([_cond(False, near_miss=True), _cond(None)]) == "near_miss"


# ---------------------------------------------------------------------------
# evaluate — end-to-end verdict tests
# ---------------------------------------------------------------------------

class TestEvaluate:

    # --- eligible ---

    def test_eligible_all_rules_pass(self):
        profile = _profile(age=25, annual_income=150000, gender="female",
                           caste="SC", state="Rajasthan", domicile="rural",
                           occupation="farmer", marital_status="widow",
                           is_disabled=True, has_bpl_card=True)
        rules = _rules(
            min_age=18, max_age=60,
            max_annual_income=200000,
            gender=["female"],
            caste=["SC", "ST"],
            states=["Rajasthan"],
            domicile=["rural"],
            occupation=["farmer"],
            marital_status=["widow"],
            disability_required=True,
            bpl_required=True,
        )
        result = evaluate(profile, rules)
        assert result.verdict == "eligible"
        assert result.failed_count == 0
        assert result.skipped_count == 0

    def test_eligible_any_sentinel_always_passes(self):
        profile = _profile(age=30, gender="male", caste="general")
        rules = _rules(gender=["any"], caste=["any"], states=["any"])
        result = evaluate(profile, rules)
        assert result.verdict == "eligible"

    def test_eligible_with_empty_rules(self):
        profile = _profile(age=30)
        rules = _rules()  # all None → nothing to check
        result = evaluate(profile, rules)
        assert result.verdict == "eligible"
        assert result.passed_count == 0
        assert result.skipped_count == 0

    def test_eligible_exact_age_boundary(self):
        profile = _profile(age=18)
        rules = _rules(min_age=18)
        result = evaluate(profile, rules)
        assert result.verdict == "eligible"

    def test_eligible_exact_income_boundary(self):
        profile = _profile(annual_income=200000)
        rules = _rules(max_annual_income=200000)
        result = evaluate(profile, rules)
        assert result.verdict == "eligible"

    # --- ineligible ---

    def test_ineligible_age_below_minimum(self):
        profile = _profile(age=15)
        rules = _rules(min_age=18)
        result = evaluate(profile, rules)
        assert result.verdict == "ineligible"

    def test_ineligible_age_well_above_maximum(self):
        profile = _profile(age=65)
        rules = _rules(max_age=60)
        result = evaluate(profile, rules)
        assert result.verdict == "ineligible"

    def test_ineligible_income_too_high(self):
        profile = _profile(annual_income=400000)
        rules = _rules(max_annual_income=200000)
        result = evaluate(profile, rules)
        assert result.verdict == "ineligible"

    def test_ineligible_wrong_gender(self):
        profile = _profile(gender="male")
        rules = _rules(gender=["female"])
        result = evaluate(profile, rules)
        assert result.verdict == "ineligible"

    def test_ineligible_wrong_caste(self):
        profile = _profile(caste="general")
        rules = _rules(caste=["SC", "ST", "OBC"])
        result = evaluate(profile, rules)
        assert result.verdict == "ineligible"

    def test_ineligible_wrong_state(self):
        profile = _profile(state="Maharashtra")
        rules = _rules(states=["Rajasthan"])
        result = evaluate(profile, rules)
        assert result.verdict == "ineligible"

    def test_ineligible_disability_not_met(self):
        profile = _profile(is_disabled=False)
        rules = _rules(disability_required=True)
        result = evaluate(profile, rules)
        assert result.verdict == "ineligible"

    def test_ineligible_bpl_not_met(self):
        profile = _profile(has_bpl_card=False)
        rules = _rules(bpl_required=True)
        result = evaluate(profile, rules)
        assert result.verdict == "ineligible"

    def test_ineligible_one_fail_among_many_passes(self):
        profile = _profile(age=25, annual_income=150000, gender="male")
        rules = _rules(min_age=18, max_annual_income=200000, gender=["female"])
        result = evaluate(profile, rules)
        assert result.verdict == "ineligible"
        assert result.passed_count == 2
        assert result.failed_count == 1

    # --- near_miss ---

    def test_near_miss_age_just_below_minimum(self):
        profile = _profile(age=17)
        rules = _rules(min_age=18)
        result = evaluate(profile, rules)
        assert result.verdict == "near_miss"
        assert len(result.near_miss_conditions) == 1

    def test_near_miss_age_at_boundary(self):
        # age = min_age - NEAR_MISS_AGE_YEARS is the furthest still-near-miss age
        profile = _profile(age=18 - _NEAR_MISS_AGE_YEARS)
        rules = _rules(min_age=18)
        result = evaluate(profile, rules)
        assert result.verdict == "near_miss"

    def test_near_miss_age_too_far_below(self):
        profile = _profile(age=14)
        rules = _rules(min_age=18)
        result = evaluate(profile, rules)
        assert result.verdict == "ineligible"

    def test_near_miss_age_just_above_maximum(self):
        profile = _profile(age=61)
        rules = _rules(max_age=60)
        result = evaluate(profile, rules)
        assert result.verdict == "near_miss"

    def test_near_miss_age_too_far_above_max(self):
        profile = _profile(age=65)
        rules = _rules(max_age=60)
        result = evaluate(profile, rules)
        assert result.verdict == "ineligible"

    def test_near_miss_income_just_above_limit(self):
        profile = _profile(annual_income=210000)
        rules = _rules(max_annual_income=200000)
        result = evaluate(profile, rules)
        assert result.verdict == "near_miss"

    def test_near_miss_income_exactly_at_10_percent(self):
        profile = _profile(annual_income=220000)
        rules = _rules(max_annual_income=200000)  # 10% over
        result = evaluate(profile, rules)
        assert result.verdict == "near_miss"

    def test_near_miss_income_over_threshold(self):
        profile = _profile(annual_income=230000)
        rules = _rules(max_annual_income=200000)  # 15% over
        result = evaluate(profile, rules)
        assert result.verdict == "ineligible"

    def test_near_miss_categorical_is_not_near_miss(self):
        # Caste mismatch is binary — no near_miss
        profile = _profile(caste="general")
        rules = _rules(caste=["SC"])
        result = evaluate(profile, rules)
        assert result.verdict == "ineligible"
        assert len(result.near_miss_conditions) == 0

    # --- insufficient_information ---

    def test_insufficient_profile_missing_age(self):
        profile = _profile()  # age=None
        rules = _rules(min_age=18)
        result = evaluate(profile, rules)
        assert result.verdict == "insufficient_information"
        assert result.skipped_count == 1

    def test_insufficient_profile_missing_caste(self):
        profile = _profile(age=25)
        rules = _rules(min_age=18, caste=["SC", "ST"])
        result = evaluate(profile, rules)
        assert result.verdict == "insufficient_information"

    def test_insufficient_all_rules_null(self):
        # Rules exist but profile has none of the relevant fields
        profile = _profile()
        rules = _rules(min_age=18, gender=["female"])
        result = evaluate(profile, rules)
        assert result.verdict == "insufficient_information"
        assert result.skipped_count == 2

    def test_ineligible_overrides_insufficient(self):
        # One definite fail + one missing field → ineligible, not insufficient
        profile = _profile(age=15, caste=None)
        rules = _rules(min_age=18, caste=["SC"])
        result = evaluate(profile, rules)
        assert result.verdict == "ineligible"

    # --- condition detail checks ---

    def test_condition_fields_populated(self):
        profile = _profile(age=25)
        rules = _rules(min_age=18)
        result = evaluate(profile, rules)
        cond = result.conditions[0]
        assert cond.field == "age"
        assert cond.operator == "gte"
        assert cond.required_value == 18
        assert cond.actual_value == 25
        assert cond.passed is True

    def test_condition_near_miss_flagged(self):
        profile = _profile(age=17)
        rules = _rules(min_age=18)
        result = evaluate(profile, rules)
        cond = result.conditions[0]
        assert cond.passed is False
        assert cond.is_near_miss is True

    def test_condition_skipped_has_none_passed(self):
        profile = _profile()
        rules = _rules(min_age=18)
        result = evaluate(profile, rules)
        cond = result.conditions[0]
        assert cond.passed is None
        assert cond.actual_value is None

    def test_any_sentinel_condition_auto_passes(self):
        profile = _profile(gender="male")
        rules = _rules(gender=["any"])
        result = evaluate(profile, rules)
        cond = result.conditions[0]
        assert cond.passed is True
        assert "No restriction" in cond.reason

    def test_disability_false_not_required_adds_no_condition(self):
        profile = _profile(is_disabled=False)
        rules = _rules(disability_required=False)
        result = evaluate(profile, rules)
        assert result.verdict == "eligible"
        assert len(result.conditions) == 0

    def test_bpl_false_not_required_adds_no_condition(self):
        profile = _profile(has_bpl_card=False)
        rules = _rules(bpl_required=False)
        result = evaluate(profile, rules)
        assert len(result.conditions) == 0

    def test_counts_match_conditions(self):
        profile = _profile(age=25, gender="male")
        rules = _rules(min_age=18, gender=["female"], caste=["SC"])
        result = evaluate(profile, rules)
        total = result.passed_count + result.failed_count + result.skipped_count
        assert total == len(result.conditions)


# ---------------------------------------------------------------------------
# evaluate_batch
# ---------------------------------------------------------------------------

class TestEvaluateBatch:
    def test_returns_results_for_all_schemes(self):
        profile = _profile(age=25, gender="female")
        schemes = [
            ("scheme-a", _rules(min_age=18, gender=["female"])),
            ("scheme-b", _rules(min_age=30)),
            ("scheme-c", _rules(gender=["male"])),
        ]
        results = evaluate_batch(profile, schemes)
        assert len(results) == 3

    def test_results_in_same_order(self):
        profile = _profile(age=25)
        schemes = [("a", _rules(min_age=18)), ("b", _rules(min_age=30)), ("c", _rules())]
        results = evaluate_batch(profile, schemes)
        assert [slug for slug, _ in results] == ["a", "b", "c"]

    def test_batch_verdicts_correct(self):
        profile = _profile(age=25, gender="female")
        schemes = [
            ("eligible-scheme",     _rules(min_age=18, gender=["female"])),
            ("ineligible-scheme",   _rules(gender=["male"])),
            ("insufficient-scheme", _rules(min_age=18, caste=["SC"])),
        ]
        results = dict(evaluate_batch(profile, schemes))
        assert results["eligible-scheme"].verdict == "eligible"
        assert results["ineligible-scheme"].verdict == "ineligible"
        assert results["insufficient-scheme"].verdict == "insufficient_information"

    def test_empty_batch(self):
        profile = _profile(age=25)
        assert evaluate_batch(profile, []) == []