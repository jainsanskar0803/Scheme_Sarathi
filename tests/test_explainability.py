"""
Tests for the deterministic explainability formatter.

The formatter NEVER calls the LLM.  Every string is derived from
structured ConditionResult data using pure Python string templates.

Covers:
  - INR formatting (Indian numbering system)
  - Requirement sentence for every field/operator combination
  - Citizen value display (all types, None → "Not provided")
  - Status mapping (PASS / NEAR_MISS / FAIL / NOT_PROVIDED)
  - Near-miss notes for age and income
  - "any" auto-pass conditions are excluded from explanation
  - Sort order: PASS → NEAR_MISS → FAIL → NOT_PROVIDED
  - explain_conditions on a real MatchResult
  - API response includes explanation for every SchemeMatchResult
  - Explanation count matches non-"any" conditions
  - LLM module is never imported by the formatter
"""
from __future__ import annotations

import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

import pytest
from fastapi.testclient import TestClient

from backend.main import app
from backend.models.citizen_profile import CitizenProfile
from backend.models.match_result import ConditionResult
from backend.models.scheme import EligibilityRules
from backend.routes.match import run_match
from backend.services.formatter import (
    _fmt_inr,
    _format_requirement,
    _format_citizen_value,
    explain_condition,
    explain_conditions,
)
from backend.services.rule_engine import evaluate

client = TestClient(app)


# ---------------------------------------------------------------------------
# Helpers to build ConditionResult objects without going through the engine
# ---------------------------------------------------------------------------

def make_cond(
    field: str,
    operator: str,
    required_value,
    actual_value,
    passed: bool | None,
    is_near_miss: bool = False,
) -> ConditionResult:
    reason = f"[test] {field} {operator} {required_value!r}"
    return ConditionResult(
        field=field,
        operator=operator,
        required_value=required_value,
        actual_value=actual_value,
        passed=passed,
        is_near_miss=is_near_miss,
        reason=reason,
    )


def create_session() -> str:
    r = client.post("/api/profile")
    assert r.status_code == 201
    return r.json()["session_id"]


def fill_and_match(fields: dict) -> dict:
    sid = create_session()
    if fields:
        r = client.patch(f"/api/profile/{sid}", json=fields)
        assert r.status_code == 200
    r = client.post("/api/match", json={"session_id": sid})
    assert r.status_code == 200
    return r.json()


def find_scheme(data: dict, scheme_id: str) -> dict | None:
    for group in ("eligible", "near_miss", "insufficient_information", "ineligible"):
        for s in data[group]:
            if s["scheme_id"] == scheme_id:
                return s
    return None


# ---------------------------------------------------------------------------
# INR formatter
# ---------------------------------------------------------------------------

class TestFmtInr:

    def test_three_digits(self):
        assert _fmt_inr(500) == "₹500"

    def test_four_digits(self):
        assert _fmt_inr(1000) == "₹1,000"

    def test_one_lakh(self):
        assert _fmt_inr(100000) == "₹1,00,000"

    def test_one_point_five_lakh(self):
        assert _fmt_inr(150000) == "₹1,50,000"

    def test_one_point_eight_lakh(self):
        assert _fmt_inr(180000) == "₹1,80,000"

    def test_two_lakh(self):
        assert _fmt_inr(200000) == "₹2,00,000"

    def test_two_point_five_lakh(self):
        assert _fmt_inr(250000) == "₹2,50,000"

    def test_three_lakh(self):
        assert _fmt_inr(300000) == "₹3,00,000"

    def test_three_point_five_lakh(self):
        assert _fmt_inr(350000) == "₹3,50,000"

    def test_six_lakh(self):
        assert _fmt_inr(600000) == "₹6,00,000"

    def test_ten_lakh(self):
        assert _fmt_inr(1000000) == "₹10,00,000"

    def test_one_crore(self):
        assert _fmt_inr(10000000) == "₹1,00,00,000"

    def test_float_truncated(self):
        assert _fmt_inr(250000.99) == "₹2,50,000"


# ---------------------------------------------------------------------------
# Requirement string formatting
# ---------------------------------------------------------------------------

class TestFormatRequirement:

    def test_age_gte(self):
        assert _format_requirement("age", "gte", 18) == "At least 18 years old"

    def test_age_lte(self):
        assert _format_requirement("age", "lte", 35) == "35 years old or younger"

    def test_income_lte(self):
        r = _format_requirement("annual_income", "lte", 250000)
        assert "₹2,50,000" in r
        assert "Annual income" in r

    def test_gender_single(self):
        r = _format_requirement("gender", "in", ["female"])
        assert "female" in r
        assert "Gender" in r

    def test_gender_multiple(self):
        r = _format_requirement("gender", "in", ["male", "female"])
        assert "male" in r
        assert "female" in r

    def test_caste_single(self):
        r = _format_requirement("caste", "in", ["ST"])
        assert "ST" in r

    def test_caste_multiple(self):
        r = _format_requirement("caste", "in", ["SC", "OBC", "EWS"])
        assert "SC" in r
        assert "OBC" in r
        assert "EWS" in r

    def test_state_single(self):
        r = _format_requirement("state", "in", ["Haryana"])
        assert "Haryana" in r

    def test_domicile(self):
        r = _format_requirement("domicile", "in", ["rural"])
        assert "rural" in r

    def test_occupation(self):
        r = _format_requirement("occupation", "in", ["farmer"])
        assert "farmer" in r

    def test_marital_status(self):
        r = _format_requirement("marital_status", "in", ["single"])
        assert "single" in r

    def test_disability_boolean(self):
        r = _format_requirement("is_disabled", "boolean", True)
        assert "disability" in r.lower()

    def test_bpl_boolean(self):
        r = _format_requirement("has_bpl_card", "boolean", True)
        assert "BPL" in r


# ---------------------------------------------------------------------------
# Citizen value display
# ---------------------------------------------------------------------------

class TestFormatCitizenValue:

    def test_age_with_value(self):
        assert _format_citizen_value("age", 42) == "42 years"

    def test_age_none(self):
        assert _format_citizen_value("age", None) == "Not provided"

    def test_income_with_value(self):
        assert _format_citizen_value("annual_income", 180000) == "₹1,80,000"

    def test_income_none(self):
        assert _format_citizen_value("annual_income", None) == "Not provided"

    def test_boolean_true(self):
        assert _format_citizen_value("is_disabled", True) == "Yes"

    def test_boolean_false(self):
        assert _format_citizen_value("is_disabled", False) == "No"

    def test_boolean_none(self):
        assert _format_citizen_value("is_disabled", None) == "Not provided"

    def test_string_field(self):
        assert _format_citizen_value("gender", "female") == "female"

    def test_string_field_none(self):
        assert _format_citizen_value("gender", None) == "Not provided"

    def test_state_field(self):
        assert _format_citizen_value("state", "Maharashtra") == "Maharashtra"


# ---------------------------------------------------------------------------
# Status mapping
# ---------------------------------------------------------------------------

class TestExplainConditionStatus:

    def test_passed_gives_pass(self):
        c = make_cond("age", "gte", 18, 42, True)
        assert explain_condition(c).status == "PASS"

    def test_failed_gives_fail(self):
        c = make_cond("age", "gte", 18, 10, False)
        assert explain_condition(c).status == "FAIL"

    def test_near_miss_gives_near_miss(self):
        c = make_cond("age", "lte", 35, 36, False, is_near_miss=True)
        assert explain_condition(c).status == "NEAR_MISS"

    def test_none_gives_not_provided(self):
        c = make_cond("age", "gte", 18, None, None)
        assert explain_condition(c).status == "NOT_PROVIDED"


# ---------------------------------------------------------------------------
# Explanation fields on explain_condition
# ---------------------------------------------------------------------------

class TestExplainConditionFields:

    def test_field_preserved(self):
        c = make_cond("age", "gte", 18, 42, True)
        assert explain_condition(c).field == "age"

    def test_label_human_readable(self):
        c = make_cond("age", "gte", 18, 42, True)
        assert explain_condition(c).label == "Age"

    def test_income_label(self):
        c = make_cond("annual_income", "lte", 250000, 180000, True)
        assert explain_condition(c).label == "Annual Income"

    def test_requirement_string_present(self):
        c = make_cond("age", "gte", 18, 42, True)
        assert "18" in explain_condition(c).requirement

    def test_citizen_value_display_present(self):
        c = make_cond("age", "gte", 18, 42, True)
        assert explain_condition(c).citizen_value_display == "42 years"

    def test_not_provided_citizen_display(self):
        c = make_cond("age", "gte", 18, None, None)
        assert explain_condition(c).citizen_value_display == "Not provided"

    def test_income_citizen_display_formatted(self):
        c = make_cond("annual_income", "lte", 250000, 180000, True)
        assert explain_condition(c).citizen_value_display == "₹1,80,000"


# ---------------------------------------------------------------------------
# Near-miss notes
# ---------------------------------------------------------------------------

class TestNearMissNotes:

    def test_age_above_max_note(self):
        # age=36, max=35, excess=1
        c = make_cond("age", "lte", 35, 36, False, is_near_miss=True)
        note = explain_condition(c).note
        assert note is not None
        assert "1" in note
        assert "35" in note

    def test_age_two_years_above_note(self):
        # age=37, max=35, excess=2
        c = make_cond("age", "lte", 35, 37, False, is_near_miss=True)
        note = explain_condition(c).note
        assert "2" in note

    def test_income_near_miss_note(self):
        c = make_cond("annual_income", "lte", 350000, 385000, False, is_near_miss=True)
        note = explain_condition(c).note
        assert note is not None
        assert "₹3,50,000" in note

    def test_no_note_when_pass(self):
        c = make_cond("age", "gte", 18, 42, True)
        assert explain_condition(c).note is None

    def test_no_note_when_fail_not_near_miss(self):
        c = make_cond("age", "gte", 18, 10, False, is_near_miss=False)
        assert explain_condition(c).note is None


# ---------------------------------------------------------------------------
# explain_conditions — list-level behaviour
# ---------------------------------------------------------------------------

class TestExplainConditions:

    def test_any_condition_excluded(self):
        # auto-pass "any" condition should not appear in explanation
        c_any = make_cond("gender", "in", ["any"], "female", True)
        result = explain_conditions([c_any])
        assert result == []

    def test_real_condition_included(self):
        c = make_cond("age", "gte", 18, 42, True)
        result = explain_conditions([c])
        assert len(result) == 1

    def test_mixed_any_and_real(self):
        c_any = make_cond("caste", "in", ["any"], "OBC", True)
        c_real = make_cond("age", "gte", 18, 42, True)
        result = explain_conditions([c_any, c_real])
        assert len(result) == 1
        assert result[0].field == "age"

    def test_sort_order_pass_before_fail(self):
        c_fail = make_cond("caste", "in", ["SC"], "OBC", False)
        c_pass = make_cond("age", "gte", 18, 42, True)
        result = explain_conditions([c_fail, c_pass])
        assert result[0].status == "PASS"
        assert result[1].status == "FAIL"

    def test_sort_order_pass_near_miss_fail_not_provided(self):
        c_pass  = make_cond("age", "gte", 18, 42, True)
        c_nm    = make_cond("age", "lte", 35, 36, False, is_near_miss=True)
        c_fail  = make_cond("caste", "in", ["SC"], "OBC", False)
        c_skip  = make_cond("state", "in", ["Haryana"], None, None)
        result = explain_conditions([c_skip, c_fail, c_nm, c_pass])
        statuses = [e.status for e in result]
        assert statuses == ["PASS", "NEAR_MISS", "FAIL", "NOT_PROVIDED"]

    def test_empty_conditions_gives_empty_list(self):
        assert explain_conditions([]) == []


# ---------------------------------------------------------------------------
# Integration: explain_conditions on real rule-engine output
# ---------------------------------------------------------------------------

class TestExplainWithRealEngine:

    def test_eligible_scheme_has_only_pass_and_not_provided(self):
        # mssc: gender=female is the only rule
        profile = CitizenProfile(gender="female")
        rules = EligibilityRules(gender=["female"])
        result = evaluate(profile, rules)
        explanations = explain_conditions(result.conditions)
        statuses = {e.status for e in explanations}
        assert statuses.issubset({"PASS", "NOT_PROVIDED"})

    def test_ineligible_scheme_has_fail_status(self):
        profile = CitizenProfile(gender="male")
        rules = EligibilityRules(gender=["female"])
        result = evaluate(profile, rules)
        explanations = explain_conditions(result.conditions)
        assert any(e.status == "FAIL" for e in explanations)

    def test_near_miss_scheme_has_near_miss_status(self):
        # sys: max_age=35, age=36 → near_miss
        profile = CitizenProfile(state="Haryana", age=36, annual_income=200000)
        rules = EligibilityRules(min_age=18, max_age=35, max_annual_income=300000, states=["Haryana"])
        result = evaluate(profile, rules)
        explanations = explain_conditions(result.conditions)
        assert any(e.status == "NEAR_MISS" for e in explanations)

    def test_age_explanation_content(self):
        profile = CitizenProfile(age=42)
        rules = EligibilityRules(min_age=18)
        result = evaluate(profile, rules)
        explanations = explain_conditions(result.conditions)
        age_exp = next(e for e in explanations if e.field == "age")
        assert age_exp.status == "PASS"
        assert "18" in age_exp.requirement
        assert "42" in age_exp.citizen_value_display

    def test_income_explanation_content(self):
        profile = CitizenProfile(annual_income=180000)
        rules = EligibilityRules(max_annual_income=250000)
        result = evaluate(profile, rules)
        explanations = explain_conditions(result.conditions)
        inc_exp = next(e for e in explanations if e.field == "annual_income")
        assert inc_exp.status == "PASS"
        assert "₹2,50,000" in inc_exp.requirement
        assert "₹1,80,000" in inc_exp.citizen_value_display

    def test_not_provided_when_profile_field_missing(self):
        profile = CitizenProfile()  # no caste
        rules = EligibilityRules(caste=["SC"])
        result = evaluate(profile, rules)
        explanations = explain_conditions(result.conditions)
        caste_exp = next(e for e in explanations if e.field == "caste")
        assert caste_exp.status == "NOT_PROVIDED"
        assert caste_exp.citizen_value_display == "Not provided"


# ---------------------------------------------------------------------------
# API response — explanation field present and correct
# ---------------------------------------------------------------------------

class TestApiExplanation:

    def test_explanation_field_present_in_every_result(self):
        data = fill_and_match({"gender": "female", "state": "Maharashtra"})
        for group in ("eligible", "near_miss", "insufficient_information", "ineligible"):
            for scheme in data[group]:
                assert "explanation" in scheme, f"Missing in {scheme['scheme_id']}"

    def test_explanation_is_list(self):
        data = fill_and_match({"gender": "female"})
        mssc = find_scheme(data, "mssc")
        assert isinstance(mssc["explanation"], list)

    def test_eligible_result_explanation_has_pass(self):
        # mssc: gender=female → eligible, explanation has PASS for gender
        data = fill_and_match({"gender": "female"})
        mssc = find_scheme(data, "mssc")
        statuses = {e["status"] for e in mssc["explanation"]}
        assert "PASS" in statuses

    def test_ineligible_result_explanation_has_fail(self):
        data = fill_and_match({"gender": "male"})
        mssc = find_scheme(data, "mssc")
        statuses = {e["status"] for e in mssc["explanation"]}
        assert "FAIL" in statuses

    def test_near_miss_explanation_has_near_miss_status(self):
        # sys: max_age=35, age=36 → near_miss
        data = fill_and_match({"state": "Haryana", "age": 36, "annual_income": 200000})
        sys_scheme = find_scheme(data, "sys")
        statuses = {e["status"] for e in sys_scheme["explanation"]}
        assert "NEAR_MISS" in statuses

    def test_near_miss_explanation_has_note(self):
        data = fill_and_match({"state": "Haryana", "age": 36, "annual_income": 200000})
        sys_scheme = find_scheme(data, "sys")
        nm_items = [e for e in sys_scheme["explanation"] if e["status"] == "NEAR_MISS"]
        assert len(nm_items) > 0
        assert nm_items[0]["note"] is not None

    def test_not_provided_when_field_missing(self):
        # Profile with no caste; post-st requires caste=ST
        data = fill_and_match({"annual_income": 150000})
        post_st = find_scheme(data, "post-st")
        statuses = {e["status"] for e in post_st["explanation"]}
        assert "NOT_PROVIDED" in statuses

    def test_explanation_sorted_pass_before_fail(self):
        # subhadra: gender=female + state=Odisha; give state wrong → fail for state
        data = fill_and_match({"gender": "female", "state": "Maharashtra", "age": 30, "annual_income": 200000})
        subhadra = find_scheme(data, "subhadra")
        # state fails, gender would pass — PASS should come before FAIL
        statuses = [e["status"] for e in subhadra["explanation"]]
        pass_idx  = next((i for i, s in enumerate(statuses) if s == "PASS"),  999)
        fail_idx  = next((i for i, s in enumerate(statuses) if s == "FAIL"),  999)
        if pass_idx < 999 and fail_idx < 999:
            assert pass_idx < fail_idx

    def test_any_conditions_not_in_explanation(self):
        # nmmss has caste=["any"] and states=["any"] — these should not appear
        data = fill_and_match({"annual_income": 200000})
        nmmss = find_scheme(data, "nmmss")
        fields = [e["field"] for e in nmmss["explanation"]]
        # "any" auto-pass conditions are excluded; only real conditions show up
        for e in nmmss["explanation"]:
            if isinstance(e.get("required_value"), list):
                assert "any" not in e["required_value"], \
                    f"'any' condition leaked into explanation: {e}"

    def test_explanation_citizen_value_display_shows_inr_for_income(self):
        data = fill_and_match({"annual_income": 180000})
        nmmss = find_scheme(data, "nmmss")
        income_items = [e for e in nmmss["explanation"] if e["field"] == "annual_income"]
        assert len(income_items) == 1
        assert income_items[0]["citizen_value_display"] == "₹1,80,000"

    def test_explanation_citizen_value_shows_not_provided_for_none(self):
        data = fill_and_match({})  # empty profile
        post_st = find_scheme(data, "post-st")
        income_items = [e for e in post_st["explanation"] if e["field"] == "annual_income"]
        if income_items:
            assert income_items[0]["citizen_value_display"] == "Not provided"

    def test_no_llm_import_in_formatter(self):
        import backend.services.formatter as fmt_module
        assert not hasattr(fmt_module, "extract_profile_fields"), \
            "Formatter must not import the LLM extractor"
        # Also check the module source doesn't reference the extractor
        import inspect
        src = inspect.getsource(fmt_module)
        assert "extract_profile_fields" not in src
        assert "Anthropic" not in src
        assert "sarvam" not in src.lower()