"""
Comprehensive boundary tests for the near-miss feature.

Covers every threshold point for every field type:
  - Age minimum boundary (gte):  exactly at, 1 below, 2 below (boundary), 3 below
  - Age maximum boundary (lte):  exactly at, 1 above, 2 above (boundary), 3 above
  - Income ceiling boundary (lte): exactly at, 1 rupee over, 10% over (boundary), >10% over
  - State / categorical: never near_miss, always FAIL
  - Caste / category:    never near_miss, always FAIL
  - Gender:              never near_miss, always FAIL
  - Domicile:            never near_miss, always FAIL
  - Occupation:          never near_miss, always FAIL
  - Marital status:      never near_miss, always FAIL
  - Boolean flags:       never near_miss, always FAIL
  - Compound conditions: near_miss + definite-fail → ineligible (not near_miss)
  - Gap / note fields:   correct content for each near-miss type

All eligibility decisions are made by the deterministic rule engine.
The LLM is never called.
"""
from __future__ import annotations

import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

import pytest
from fastapi.testclient import TestClient

from backend.main import app
from backend.models.citizen_profile import CitizenProfile
from backend.models.scheme import EligibilityRules
from backend.services.formatter import explain_conditions, _near_miss_gap, _near_miss_note
from backend.services.rule_engine import evaluate, _NEAR_MISS_AGE_YEARS, _NEAR_MISS_INCOME_FRACTION

client = TestClient(app)

# Near-miss thresholds (imported from engine so tests stay in sync with implementation)
AGE_WINDOW = _NEAR_MISS_AGE_YEARS            # 2
INCOME_WINDOW = _NEAR_MISS_INCOME_FRACTION   # 0.10


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------

def verdict(profile: CitizenProfile, rules: EligibilityRules) -> str:
    return evaluate(profile, rules).verdict


def conditions(profile: CitizenProfile, rules: EligibilityRules):
    return evaluate(profile, rules).conditions


def cond_for(field: str, profile: CitizenProfile, rules: EligibilityRules):
    return next((c for c in conditions(profile, rules) if c.field == field), None)


def create_session() -> str:
    r = client.post("/api/profile")
    assert r.status_code == 201
    return r.json()["session_id"]


def fill_and_match(fields: dict) -> dict:
    sid = create_session()
    if fields:
        r = client.patch(f"/api/profile/{sid}", json=fields)
        assert r.status_code == 200, r.text
    r = client.post("/api/match", json={"session_id": sid})
    assert r.status_code == 200, r.text
    return r.json()


def find_scheme(data: dict, scheme_id: str) -> dict:
    for group in ("eligible", "near_miss", "insufficient_information", "ineligible"):
        for s in data[group]:
            if s["scheme_id"] == scheme_id:
                return s
    raise AssertionError(f"{scheme_id} not found in any group")


# ---------------------------------------------------------------------------
# Age minimum boundary  (AGE_WINDOW = 2)
#
# Rule: min_age = 18  (pm-daksh also requires caste=[SC,OBC,EWS]; we use SC)
# Boundary:  18 → pass
#            17 → near_miss (shortfall 1, 0 < 1 ≤ 2)
#            16 → near_miss (shortfall 2, exactly at window edge)
#            15 → ineligible (shortfall 3, beyond window)
# ---------------------------------------------------------------------------

class TestAgeMinBoundary:
    RULES = EligibilityRules(min_age=18)

    def _profile(self, age: int) -> CitizenProfile:
        return CitizenProfile(age=age)

    def test_exactly_at_min_age_passes(self):
        assert verdict(self._profile(18), self.RULES) == "eligible"

    def test_one_below_min_age_is_near_miss(self):
        result = evaluate(self._profile(17), self.RULES)
        assert result.verdict == "near_miss"
        c = cond_for("age", self._profile(17), self.RULES)
        assert c.is_near_miss is True

    def test_two_below_min_age_is_near_miss(self):
        # age = min_age - AGE_WINDOW → exactly at boundary → still near_miss
        age = 18 - AGE_WINDOW  # 16
        result = evaluate(self._profile(age), self.RULES)
        assert result.verdict == "near_miss"
        c = cond_for("age", self._profile(age), self.RULES)
        assert c.is_near_miss is True

    def test_three_below_min_age_is_ineligible(self):
        age = 18 - AGE_WINDOW - 1  # 15
        result = evaluate(self._profile(age), self.RULES)
        assert result.verdict == "ineligible"
        c = cond_for("age", self._profile(age), self.RULES)
        assert c.is_near_miss is False

    def test_near_miss_condition_passed_is_false(self):
        c = cond_for("age", self._profile(17), self.RULES)
        assert c.passed is False

    def test_near_miss_condition_is_near_miss_true(self):
        c = cond_for("age", self._profile(17), self.RULES)
        assert c.is_near_miss is True

    def test_well_above_min_age_passes(self):
        assert verdict(self._profile(40), self.RULES) == "eligible"


# ---------------------------------------------------------------------------
# Age maximum boundary  (AGE_WINDOW = 2)
#
# Rule: max_age = 35  (isolating just this condition)
# Boundary:  35 → pass
#            36 → near_miss (excess 1)
#            37 → near_miss (excess 2, boundary)
#            38 → ineligible (excess 3)
# ---------------------------------------------------------------------------

class TestAgeMaxBoundary:
    RULES = EligibilityRules(max_age=35)

    def _profile(self, age: int) -> CitizenProfile:
        return CitizenProfile(age=age)

    def test_exactly_at_max_age_passes(self):
        assert verdict(self._profile(35), self.RULES) == "eligible"

    def test_one_above_max_age_is_near_miss(self):
        result = evaluate(self._profile(36), self.RULES)
        assert result.verdict == "near_miss"

    def test_two_above_max_age_is_near_miss(self):
        # age = max_age + AGE_WINDOW → exactly at boundary → still near_miss
        age = 35 + AGE_WINDOW  # 37
        result = evaluate(self._profile(age), self.RULES)
        assert result.verdict == "near_miss"
        c = cond_for("age", self._profile(age), self.RULES)
        assert c.is_near_miss is True

    def test_three_above_max_age_is_ineligible(self):
        age = 35 + AGE_WINDOW + 1  # 38
        result = evaluate(self._profile(age), self.RULES)
        assert result.verdict == "ineligible"
        c = cond_for("age", self._profile(age), self.RULES)
        assert c.is_near_miss is False

    def test_ten_years_above_max_is_ineligible(self):
        assert verdict(self._profile(45), self.RULES) == "ineligible"

    def test_well_below_max_age_passes(self):
        assert verdict(self._profile(20), self.RULES) == "eligible"


# ---------------------------------------------------------------------------
# Income ceiling boundary  (INCOME_WINDOW = 10 %)
#
# Rule: max_income = 250_000
# Near-miss range: 250_001 … 275_000  (up to 10 % above)
# Boundary points:
#   250_000 → pass (at limit)
#   250_001 → near_miss (1 rupee over)
#   275_000 → near_miss (10% over — fraction=0.10, 0 < 0.10 ≤ 0.10)
#   275_001 → ineligible (fraction > 0.10)
# ---------------------------------------------------------------------------

class TestIncomeBoundary:
    MAX = 250_000
    RULES = EligibilityRules(max_annual_income=MAX)

    def _profile(self, income: int) -> CitizenProfile:
        return CitizenProfile(annual_income=income)

    def _ten_pct(self) -> int:
        return int(self.MAX * (1 + INCOME_WINDOW))  # 275_000

    def test_exactly_at_limit_passes(self):
        assert verdict(self._profile(self.MAX), self.RULES) == "eligible"

    def test_one_rupee_over_is_near_miss(self):
        result = evaluate(self._profile(self.MAX + 1), self.RULES)
        assert result.verdict == "near_miss"

    def test_ten_percent_over_is_near_miss(self):
        # Fraction = (275000 - 250000) / 250000 = 0.10 → 0 < 0.10 ≤ 0.10 → True
        result = evaluate(self._profile(self._ten_pct()), self.RULES)
        assert result.verdict == "near_miss"
        c = cond_for("annual_income", self._profile(self._ten_pct()), self.RULES)
        assert c.is_near_miss is True

    def test_ten_percent_plus_one_rupee_is_ineligible(self):
        result = evaluate(self._profile(self._ten_pct() + 1), self.RULES)
        assert result.verdict == "ineligible"
        c = cond_for("annual_income", self._profile(self._ten_pct() + 1), self.RULES)
        assert c.is_near_miss is False

    def test_fifty_percent_over_is_ineligible(self):
        assert verdict(self._profile(int(self.MAX * 1.5)), self.RULES) == "ineligible"

    def test_well_below_limit_passes(self):
        assert verdict(self._profile(100_000), self.RULES) == "eligible"

    def test_nmmss_income_boundary_via_api(self):
        # nmmss max_income = 350_000; 10% = 385_000
        at_boundary = 385_000
        data = fill_and_match({"annual_income": at_boundary})
        nmmss = find_scheme(data, "nmmss")
        assert nmmss["verdict"] == "near_miss"

    def test_nmmss_income_one_over_boundary_via_api(self):
        over_boundary = 385_001
        data = fill_and_match({"annual_income": over_boundary})
        nmmss = find_scheme(data, "nmmss")
        assert nmmss["verdict"] == "ineligible"

    def test_near_miss_condition_has_is_near_miss_true(self):
        c = cond_for("annual_income", self._profile(self.MAX + 1), self.RULES)
        assert c.is_near_miss is True


# ---------------------------------------------------------------------------
# State (categorical) — NEVER near_miss
# ---------------------------------------------------------------------------

class TestStateNeverNearMiss:
    RULES = EligibilityRules(states=["Haryana"])

    def test_wrong_state_is_fail_not_near_miss(self):
        profile = CitizenProfile(state="Maharashtra")
        c = cond_for("state", profile, self.RULES)
        assert c.passed is False
        assert c.is_near_miss is False

    def test_wrong_state_verdict_is_ineligible(self):
        assert verdict(CitizenProfile(state="Punjab"), self.RULES) == "ineligible"

    def test_adjacent_state_is_not_near_miss(self):
        # Punjab borders Haryana — still no near_miss
        c = cond_for("state", CitizenProfile(state="Punjab"), self.RULES)
        assert c.is_near_miss is False

    def test_correct_state_passes(self):
        assert verdict(CitizenProfile(state="Haryana"), self.RULES) == "eligible"

    def test_ysrrb_wrong_state_is_ineligible_via_api(self):
        data = fill_and_match({"state": "Maharashtra", "occupation": "farmer"})
        ysrrb = find_scheme(data, "ysrrb")
        assert ysrrb["verdict"] == "ineligible"
        # No near_miss rules expected for a state mismatch
        assert len(ysrrb["near_miss_rules"]) == 0

    def test_ysrrb_wrong_state_explanation_shows_fail(self):
        data = fill_and_match({"state": "Maharashtra", "occupation": "farmer"})
        ysrrb = find_scheme(data, "ysrrb")
        state_exp = next(
            (e for e in ysrrb["explanation"] if e["field"] == "state"), None
        )
        assert state_exp is not None
        assert state_exp["status"] == "FAIL"
        assert state_exp["gap"] is None


# ---------------------------------------------------------------------------
# Caste (categorical) — NEVER near_miss
# ---------------------------------------------------------------------------

class TestCasteNeverNearMiss:
    RULES = EligibilityRules(caste=["ST"])

    def test_wrong_caste_is_fail_not_near_miss(self):
        c = cond_for("caste", CitizenProfile(caste="OBC"), self.RULES)
        assert c.passed is False
        assert c.is_near_miss is False

    def test_general_caste_is_fail_not_near_miss(self):
        c = cond_for("caste", CitizenProfile(caste="general"), self.RULES)
        assert c.is_near_miss is False

    def test_sc_caste_is_fail_not_near_miss(self):
        # SC and ST are distinct; SC does not "nearly" satisfy ST
        c = cond_for("caste", CitizenProfile(caste="SC"), self.RULES)
        assert c.is_near_miss is False

    def test_correct_caste_passes(self):
        assert verdict(CitizenProfile(caste="ST"), self.RULES) == "eligible"

    def test_wrong_caste_verdict_is_ineligible(self):
        assert verdict(CitizenProfile(caste="OBC"), self.RULES) == "ineligible"


# ---------------------------------------------------------------------------
# Gender (categorical) — NEVER near_miss
# ---------------------------------------------------------------------------

class TestGenderNeverNearMiss:
    RULES = EligibilityRules(gender=["female"])

    def test_male_is_fail_not_near_miss(self):
        c = cond_for("gender", CitizenProfile(gender="male"), self.RULES)
        assert c.passed is False
        assert c.is_near_miss is False

    def test_transgender_is_fail_not_near_miss(self):
        c = cond_for("gender", CitizenProfile(gender="transgender"), self.RULES)
        assert c.is_near_miss is False

    def test_female_passes(self):
        assert verdict(CitizenProfile(gender="female"), self.RULES) == "eligible"

    def test_male_verdict_is_ineligible(self):
        assert verdict(CitizenProfile(gender="male"), self.RULES) == "ineligible"

    def test_mssc_male_ineligible_no_near_miss_via_api(self):
        data = fill_and_match({"gender": "male"})
        mssc = find_scheme(data, "mssc")
        assert mssc["verdict"] == "ineligible"
        assert len(mssc["near_miss_rules"]) == 0


# ---------------------------------------------------------------------------
# Other categoricals — NEVER near_miss
# ---------------------------------------------------------------------------

class TestOtherCategoricalsNeverNearMiss:

    def test_wrong_domicile_is_fail(self):
        rules = EligibilityRules(domicile=["rural"])
        c = cond_for("domicile", CitizenProfile(domicile="urban"), rules)
        assert c.passed is False
        assert c.is_near_miss is False

    def test_wrong_occupation_is_fail(self):
        rules = EligibilityRules(occupation=["farmer"])
        c = cond_for("occupation", CitizenProfile(occupation="student"), rules)
        assert c.passed is False
        assert c.is_near_miss is False

    def test_wrong_marital_status_is_fail(self):
        rules = EligibilityRules(marital_status=["single"])
        c = cond_for("marital_status", CitizenProfile(marital_status="married"), rules)
        assert c.passed is False
        assert c.is_near_miss is False

    def test_pmay_g_urban_is_ineligible_not_near_miss_via_api(self):
        data = fill_and_match({"domicile": "urban"})
        pmay = find_scheme(data, "pmay-g")
        assert pmay["verdict"] == "ineligible"
        assert all(r["is_near_miss"] is False for r in pmay["failed_rules"])


# ---------------------------------------------------------------------------
# Boolean flags — NEVER near_miss
# ---------------------------------------------------------------------------

class TestBooleanNeverNearMiss:

    def test_missing_disability_flag_is_fail(self):
        rules = EligibilityRules(disability_required=True)
        c = cond_for("is_disabled", CitizenProfile(is_disabled=False), rules)
        assert c.passed is False
        assert c.is_near_miss is False

    def test_missing_bpl_flag_is_fail(self):
        rules = EligibilityRules(bpl_required=True)
        c = cond_for("has_bpl_card", CitizenProfile(has_bpl_card=False), rules)
        assert c.passed is False
        assert c.is_near_miss is False

    def test_disability_required_false_profile_verdict_is_ineligible(self):
        rules = EligibilityRules(disability_required=True)
        assert verdict(CitizenProfile(is_disabled=False), rules) == "ineligible"

    def test_disability_required_true_profile_verdict_is_eligible(self):
        rules = EligibilityRules(disability_required=True)
        assert verdict(CitizenProfile(is_disabled=True), rules) == "eligible"

    def test_bpl_required_false_profile_verdict_is_ineligible(self):
        rules = EligibilityRules(bpl_required=True)
        assert verdict(CitizenProfile(has_bpl_card=False), rules) == "ineligible"

    def test_boolean_explanation_shows_fail_no_gap(self):
        rules = EligibilityRules(disability_required=True)
        result = evaluate(CitizenProfile(is_disabled=False), rules)
        exps = explain_conditions(result.conditions)
        dis_exp = next(e for e in exps if e.field == "is_disabled")
        assert dis_exp.status == "FAIL"
        assert dis_exp.gap is None
        assert dis_exp.note is None


# ---------------------------------------------------------------------------
# Compound conditions — near_miss only when ALL failures are near_miss
# ---------------------------------------------------------------------------

class TestCompoundConditions:

    def test_near_miss_age_with_passing_state_gives_near_miss(self):
        # max_age=35, actual=36 → near_miss; state=Haryana passes
        rules = EligibilityRules(max_age=35, states=["Haryana"])
        profile = CitizenProfile(age=36, state="Haryana")
        assert verdict(profile, rules) == "near_miss"

    def test_near_miss_age_with_failing_state_gives_ineligible(self):
        # max_age=35, actual=36 → near_miss; state=Haryana but citizen in Punjab → FAIL
        rules = EligibilityRules(max_age=35, states=["Haryana"])
        profile = CitizenProfile(age=36, state="Punjab")
        assert verdict(profile, rules) == "ineligible"

    def test_near_miss_income_with_passing_caste_gives_near_miss(self):
        rules = EligibilityRules(max_annual_income=250_000, caste=["SC"])
        profile = CitizenProfile(annual_income=260_000, caste="SC")
        assert verdict(profile, rules) == "near_miss"

    def test_near_miss_income_with_failing_caste_gives_ineligible(self):
        rules = EligibilityRules(max_annual_income=250_000, caste=["SC"])
        profile = CitizenProfile(annual_income=260_000, caste="OBC")
        assert verdict(profile, rules) == "ineligible"

    def test_two_near_miss_conditions_both_age_bounds(self):
        # min_age=20, max_age=30, actual=32 → max_age near_miss; min_age passes
        rules = EligibilityRules(min_age=20, max_age=30)
        profile = CitizenProfile(age=32)
        result = evaluate(profile, rules)
        assert result.verdict == "near_miss"
        # Exactly one near-miss condition (max_age)
        assert len(result.near_miss_conditions) == 1
        assert result.near_miss_conditions[0].field == "age"

    def test_two_definite_fails_gives_ineligible(self):
        rules = EligibilityRules(gender=["female"], caste=["SC"])
        profile = CitizenProfile(gender="male", caste="OBC")
        assert verdict(profile, rules) == "ineligible"

    def test_definite_fail_overrides_near_miss_in_verdict(self):
        rules = EligibilityRules(max_age=35, gender=["female"])
        profile = CitizenProfile(age=36, gender="male")  # age=near_miss, gender=fail
        result = evaluate(profile, rules)
        assert result.verdict == "ineligible"
        assert any(c.is_near_miss for c in result.conditions)   # near_miss condition exists
        assert any(c.passed is False and not c.is_near_miss for c in result.conditions)  # definite fail too

    def test_sys_near_miss_age_wrong_state_ineligible_via_api(self):
        # sys: max_age=35, state=Haryana; age=36 (near_miss) + state=Punjab (fail) → ineligible
        data = fill_and_match({
            "state": "Punjab", "age": 36, "annual_income": 200_000
        })
        sys_scheme = find_scheme(data, "sys")
        assert sys_scheme["verdict"] == "ineligible"

    def test_sys_near_miss_age_correct_state_near_miss_via_api(self):
        # sys: max_age=35, state=Haryana; age=36 (near_miss) + state=Haryana (pass) → near_miss
        data = fill_and_match({
            "state": "Haryana", "age": 36, "annual_income": 200_000
        })
        sys_scheme = find_scheme(data, "sys")
        assert sys_scheme["verdict"] == "near_miss"


# ---------------------------------------------------------------------------
# Near-miss gap and note content
# ---------------------------------------------------------------------------

class TestNearMissGapAndNote:

    # --- _near_miss_gap ---

    def test_gap_age_lte_one_above(self):
        assert _near_miss_gap("age", "lte", 35, 36) == "1 year above the maximum age"

    def test_gap_age_lte_two_above(self):
        assert _near_miss_gap("age", "lte", 35, 37) == "2 years above the maximum age"

    def test_gap_age_gte_one_below(self):
        assert _near_miss_gap("age", "gte", 18, 17) == "1 year below the minimum age"

    def test_gap_age_gte_two_below(self):
        assert _near_miss_gap("age", "gte", 18, 16) == "2 years below the minimum age"

    def test_gap_income(self):
        gap = _near_miss_gap("annual_income", "lte", 250_000, 275_000)
        assert gap == "₹25,000 above the income limit"

    def test_gap_income_fifty_thousand(self):
        gap = _near_miss_gap("annual_income", "lte", 250_000, 300_000)
        assert gap == "₹50,000 above the income limit"

    def test_gap_returns_none_for_categorical(self):
        assert _near_miss_gap("caste", "in", ["SC"], "OBC") is None

    def test_gap_returns_none_for_state(self):
        assert _near_miss_gap("state", "in", ["Haryana"], "Punjab") is None

    def test_gap_returns_none_for_boolean(self):
        assert _near_miss_gap("is_disabled", "boolean", True, False) is None

    # --- _near_miss_note ---

    def test_note_age_lte(self):
        note = _near_miss_note("age", "lte", 35, 36)
        assert "1 year" in note
        assert "35" in note
        assert "above" in note

    def test_note_age_gte(self):
        note = _near_miss_note("age", "gte", 18, 17)
        assert "1 year" in note
        assert "18" in note
        assert "below" in note

    def test_note_income_format(self):
        note = _near_miss_note("annual_income", "lte", 250_000, 300_000)
        assert "₹50,000" in note          # gap amount
        assert "₹2,50,000" in note        # the limit
        assert "above" in note

    def test_note_income_matches_example(self):
        # User's example: income limit ₹2,50,000; citizen ₹3,00,000 → ₹50,000 above
        note = _near_miss_note("annual_income", "lte", 250_000, 300_000)
        assert note == "Your income is ₹50,000 above the stated limit of ₹2,50,000"

    def test_note_returns_none_for_categorical(self):
        assert _near_miss_note("caste", "in", ["SC"], "OBC") is None

    # --- API integration: gap and note fields in response ---

    def test_api_near_miss_has_gap_field(self):
        data = fill_and_match({"state": "Haryana", "age": 36, "annual_income": 200_000})
        sys_scheme = find_scheme(data, "sys")
        nm_exp = [e for e in sys_scheme["explanation"] if e["status"] == "NEAR_MISS"]
        assert len(nm_exp) > 0
        assert nm_exp[0]["gap"] is not None

    def test_api_near_miss_age_gap_content(self):
        data = fill_and_match({"state": "Haryana", "age": 36, "annual_income": 200_000})
        sys_scheme = find_scheme(data, "sys")
        nm_exp = next(e for e in sys_scheme["explanation"] if e["status"] == "NEAR_MISS")
        assert "1 year" in nm_exp["gap"]
        assert "maximum" in nm_exp["gap"]

    def test_api_near_miss_income_gap_content(self):
        # nmmss max_income=350_000; citizen income=385_000 → near_miss; gap=₹35,000
        data = fill_and_match({"annual_income": 385_000})
        nmmss = find_scheme(data, "nmmss")
        nm_exp = [e for e in nmmss["explanation"] if e["status"] == "NEAR_MISS"]
        assert len(nm_exp) > 0
        assert "₹35,000" in nm_exp[0]["gap"]

    def test_api_pass_has_no_gap(self):
        data = fill_and_match({"gender": "female"})
        mssc = find_scheme(data, "mssc")
        pass_exp = [e for e in mssc["explanation"] if e["status"] == "PASS"]
        assert all(e["gap"] is None for e in pass_exp)

    def test_api_fail_has_no_gap(self):
        data = fill_and_match({"gender": "male"})
        mssc = find_scheme(data, "mssc")
        fail_exp = [e for e in mssc["explanation"] if e["status"] == "FAIL"]
        assert all(e["gap"] is None for e in fail_exp)

    def test_api_not_provided_has_no_gap(self):
        data = fill_and_match({})  # empty profile
        mssc = find_scheme(data, "mssc")
        np_exp = [e for e in mssc["explanation"] if e["status"] == "NOT_PROVIDED"]
        assert all(e["gap"] is None for e in np_exp)

    def test_api_near_miss_has_note_field(self):
        data = fill_and_match({"annual_income": 385_000})
        nmmss = find_scheme(data, "nmmss")
        nm_exp = [e for e in nmmss["explanation"] if e["status"] == "NEAR_MISS"]
        assert len(nm_exp) > 0
        assert nm_exp[0]["note"] is not None
        # Note should mention the ₹35,000 excess
        assert "₹35,000" in nm_exp[0]["note"]

    def test_api_income_near_miss_note_matches_expected_format(self):
        # nmmss max_income=350_000; income=400_000 → excess=50_000
        data = fill_and_match({"annual_income": 400_000})
        nmmss = find_scheme(data, "nmmss")
        # 400_000 is more than 10% above 350_000 → ineligible, not near_miss
        # Use 380_000 instead: (380_000 - 350_000)/350_000 ≈ 8.6% → near_miss
        data = fill_and_match({"annual_income": 380_000})
        nmmss = find_scheme(data, "nmmss")
        nm_exp = [e for e in nmmss["explanation"] if e["status"] == "NEAR_MISS"]
        assert nm_exp[0]["note"] == "Your income is ₹30,000 above the stated limit of ₹3,50,000"