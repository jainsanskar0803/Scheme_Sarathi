"""
Tests for the MVP seed data.

Validates that:
- All 14 schemes load from the CSV without error
- Verified rules contain exactly the expected values
- Missing fields are None (not invented)
- The rule engine produces plausible verdicts for representative profiles
"""
from __future__ import annotations

import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

import pytest
from scripts.seed_schemes import build_seed_schemes, VERIFIED_RULES
from backend.models.citizen_profile import CitizenProfile
from backend.services.rule_engine import evaluate


@pytest.fixture(scope="module")
def schemes():
    return {s.slug: s for s in build_seed_schemes()}


# ---------------------------------------------------------------------------
# All 14 slugs present and valid
# ---------------------------------------------------------------------------

class TestSeedLoads:
    EXPECTED_SLUGS = {
        "nmmss", "post-st", "pm-daksh", "sys",
        "pmay-g", "daay",
        "ab-pmjay", "gms", "dayalu",
        "subhadra", "wbrupashree", "mssc",
        "dalit-bandhu", "ysrrb",
    }

    def test_all_slugs_present(self, schemes):
        assert set(schemes.keys()) == self.EXPECTED_SLUGS

    def test_all_have_scheme_name(self, schemes):
        assert all(s.scheme_name for s in schemes.values())

    def test_all_have_eligibility_text(self, schemes):
        assert all(s.eligibility_text for s in schemes.values())

    def test_all_have_eligibility_rules(self, schemes):
        assert all(s.eligibility_rules is not None for s in schemes.values())

    def test_all_have_categories(self, schemes):
        assert all(len(s.scheme_categories) >= 1 for s in schemes.values())

    def test_level_values_valid(self, schemes):
        for s in schemes.values():
            assert s.level in ("central", "state")


# ---------------------------------------------------------------------------
# Verified rules — exact values
# ---------------------------------------------------------------------------

class TestVerifiedRules:

    # NMMSS
    def test_nmmss_income(self, schemes):
        assert schemes["nmmss"].eligibility_rules.max_annual_income == 350_000

    def test_nmmss_caste_any(self, schemes):
        assert schemes["nmmss"].eligibility_rules.caste == ["any"]

    def test_nmmss_age_missing(self, schemes):
        r = schemes["nmmss"].eligibility_rules
        assert r.min_age is None and r.max_age is None

    # post-st
    def test_post_st_caste(self, schemes):
        assert schemes["post-st"].eligibility_rules.caste == ["ST"]

    def test_post_st_income(self, schemes):
        assert schemes["post-st"].eligibility_rules.max_annual_income == 200_000

    # pm-daksh
    def test_pm_daksh_age(self, schemes):
        r = schemes["pm-daksh"].eligibility_rules
        assert r.min_age == 18 and r.max_age == 45

    def test_pm_daksh_caste(self, schemes):
        r = schemes["pm-daksh"].eligibility_rules
        assert set(r.caste) == {"SC", "OBC", "EWS"}

    def test_pm_daksh_income_missing(self, schemes):
        # income is conditional on caste — not modelled
        assert schemes["pm-daksh"].eligibility_rules.max_annual_income is None

    # sys
    def test_sys_state(self, schemes):
        assert schemes["sys"].eligibility_rules.states == ["Haryana"]

    def test_sys_age(self, schemes):
        r = schemes["sys"].eligibility_rules
        assert r.min_age == 18 and r.max_age == 35

    def test_sys_income(self, schemes):
        assert schemes["sys"].eligibility_rules.max_annual_income == 300_000

    # pmay-g
    def test_pmay_g_domicile(self, schemes):
        assert schemes["pmay-g"].eligibility_rules.domicile == ["rural"]

    def test_pmay_g_income_missing(self, schemes):
        assert schemes["pmay-g"].eligibility_rules.max_annual_income is None

    # daay
    def test_daay_caste(self, schemes):
        assert schemes["daay"].eligibility_rules.caste == ["SC"]

    def test_daay_state(self, schemes):
        assert schemes["daay"].eligibility_rules.states == ["Gujarat"]

    def test_daay_min_age(self, schemes):
        assert schemes["daay"].eligibility_rules.min_age == 21

    def test_daay_income(self, schemes):
        assert schemes["daay"].eligibility_rules.max_annual_income == 600_000

    # ab-pmjay — only state verified
    def test_ab_pmjay_states_any(self, schemes):
        assert schemes["ab-pmjay"].eligibility_rules.states == ["any"]

    def test_ab_pmjay_income_missing(self, schemes):
        assert schemes["ab-pmjay"].eligibility_rules.max_annual_income is None

    # gms
    def test_gms_state(self, schemes):
        assert schemes["gms"].eligibility_rules.states == ["Goa"]

    def test_gms_income(self, schemes):
        assert schemes["gms"].eligibility_rules.max_annual_income == 150_000

    # dayalu
    def test_dayalu_state(self, schemes):
        assert schemes["dayalu"].eligibility_rules.states == ["Haryana"]

    def test_dayalu_income(self, schemes):
        assert schemes["dayalu"].eligibility_rules.max_annual_income == 180_000

    def test_dayalu_age(self, schemes):
        r = schemes["dayalu"].eligibility_rules
        assert r.min_age == 6 and r.max_age == 60

    # subhadra
    def test_subhadra_gender(self, schemes):
        assert schemes["subhadra"].eligibility_rules.gender == ["female"]

    def test_subhadra_state(self, schemes):
        assert schemes["subhadra"].eligibility_rules.states == ["Odisha"]

    def test_subhadra_age(self, schemes):
        r = schemes["subhadra"].eligibility_rules
        assert r.min_age == 21 and r.max_age == 59

    def test_subhadra_income(self, schemes):
        assert schemes["subhadra"].eligibility_rules.max_annual_income == 250_000

    # wbrupashree
    def test_wbrupashree_gender(self, schemes):
        assert schemes["wbrupashree"].eligibility_rules.gender == ["female"]

    def test_wbrupashree_state(self, schemes):
        assert schemes["wbrupashree"].eligibility_rules.states == ["West Bengal"]

    def test_wbrupashree_marital(self, schemes):
        assert schemes["wbrupashree"].eligibility_rules.marital_status == ["single"]

    def test_wbrupashree_min_age(self, schemes):
        assert schemes["wbrupashree"].eligibility_rules.min_age == 18

    def test_wbrupashree_income(self, schemes):
        assert schemes["wbrupashree"].eligibility_rules.max_annual_income == 150_000

    # mssc
    def test_mssc_gender(self, schemes):
        assert schemes["mssc"].eligibility_rules.gender == ["female"]

    def test_mssc_income_missing(self, schemes):
        assert schemes["mssc"].eligibility_rules.max_annual_income is None

    # dalit-bandhu
    def test_dalit_bandhu_caste(self, schemes):
        assert schemes["dalit-bandhu"].eligibility_rules.caste == ["SC"]

    def test_dalit_bandhu_state(self, schemes):
        assert schemes["dalit-bandhu"].eligibility_rules.states == ["Telangana"]

    def test_dalit_bandhu_age(self, schemes):
        r = schemes["dalit-bandhu"].eligibility_rules
        assert r.min_age == 25 and r.max_age == 50

    def test_dalit_bandhu_income(self, schemes):
        assert schemes["dalit-bandhu"].eligibility_rules.max_annual_income == 250_000

    # ysrrb
    def test_ysrrb_state(self, schemes):
        assert schemes["ysrrb"].eligibility_rules.states == ["Andhra Pradesh"]

    def test_ysrrb_occupation(self, schemes):
        assert schemes["ysrrb"].eligibility_rules.occupation == ["farmer"]


# ---------------------------------------------------------------------------
# Nothing is invented — no field should have a non-None value
# that doesn't come from the text
# ---------------------------------------------------------------------------

class TestNothingInvented:

    def test_nmmss_gender_not_invented(self, schemes):
        assert schemes["nmmss"].eligibility_rules.gender is None

    def test_pm_daksh_income_not_invented(self, schemes):
        assert schemes["pm-daksh"].eligibility_rules.max_annual_income is None

    def test_pmay_g_income_not_invented(self, schemes):
        assert schemes["pmay-g"].eligibility_rules.max_annual_income is None

    def test_pmay_g_caste_not_invented(self, schemes):
        assert schemes["pmay-g"].eligibility_rules.caste is None

    def test_ab_pmjay_income_not_invented(self, schemes):
        assert schemes["ab-pmjay"].eligibility_rules.max_annual_income is None

    def test_ysrrb_income_not_invented(self, schemes):
        assert schemes["ysrrb"].eligibility_rules.max_annual_income is None

    def test_mssc_income_not_invented(self, schemes):
        assert schemes["mssc"].eligibility_rules.max_annual_income is None

    def test_gms_age_not_invented(self, schemes):
        r = schemes["gms"].eligibility_rules
        assert r.min_age is None and r.max_age is None

    def test_sys_caste_not_invented(self, schemes):
        assert schemes["sys"].eligibility_rules.caste is None


# ---------------------------------------------------------------------------
# Rule engine integration — representative citizen profiles
# ---------------------------------------------------------------------------

class TestRuleEngineWithSeedSchemes:

    def test_st_student_eligible_for_post_st(self, schemes):
        profile = CitizenProfile(caste="ST", annual_income=150_000)
        result = evaluate(profile, schemes["post-st"].eligibility_rules)
        assert result.verdict == "eligible"

    def test_general_student_ineligible_for_post_st(self, schemes):
        profile = CitizenProfile(caste="general", annual_income=150_000)
        result = evaluate(profile, schemes["post-st"].eligibility_rules)
        assert result.verdict == "ineligible"

    def test_rich_st_student_ineligible_for_post_st(self, schemes):
        profile = CitizenProfile(caste="ST", annual_income=300_000)
        result = evaluate(profile, schemes["post-st"].eligibility_rules)
        assert result.verdict == "ineligible"

    def test_sc_telangana_youth_eligible_for_dalit_bandhu(self, schemes):
        profile = CitizenProfile(caste="SC", state="Telangana",
                                 annual_income=200_000, age=30)
        result = evaluate(profile, schemes["dalit-bandhu"].eligibility_rules)
        assert result.verdict == "eligible"

    def test_obc_telangana_ineligible_for_dalit_bandhu(self, schemes):
        profile = CitizenProfile(caste="OBC", state="Telangana",
                                 annual_income=200_000, age=30)
        result = evaluate(profile, schemes["dalit-bandhu"].eligibility_rules)
        assert result.verdict == "ineligible"

    def test_haryana_youth_eligible_for_sys(self, schemes):
        profile = CitizenProfile(state="Haryana", age=25, annual_income=250_000)
        result = evaluate(profile, schemes["sys"].eligibility_rules)
        assert result.verdict == "eligible"

    def test_haryana_youth_too_old_for_sys(self, schemes):
        # age 38 is 3 years above max_age 35 — beyond near_miss threshold
        profile = CitizenProfile(state="Haryana", age=38, annual_income=250_000)
        result = evaluate(profile, schemes["sys"].eligibility_rules)
        assert result.verdict == "ineligible"

    def test_odisha_woman_eligible_for_subhadra(self, schemes):
        profile = CitizenProfile(state="Odisha", gender="female",
                                 age=30, annual_income=200_000)
        result = evaluate(profile, schemes["subhadra"].eligibility_rules)
        assert result.verdict == "eligible"

    def test_male_ineligible_for_subhadra(self, schemes):
        profile = CitizenProfile(state="Odisha", gender="male", age=30)
        result = evaluate(profile, schemes["subhadra"].eligibility_rules)
        assert result.verdict == "ineligible"

    def test_wrong_state_ineligible_for_subhadra(self, schemes):
        profile = CitizenProfile(state="Maharashtra", gender="female", age=30)
        result = evaluate(profile, schemes["subhadra"].eligibility_rules)
        assert result.verdict == "ineligible"

    def test_woman_eligible_for_mssc(self, schemes):
        profile = CitizenProfile(gender="female")
        result = evaluate(profile, schemes["mssc"].eligibility_rules)
        assert result.verdict == "eligible"

    def test_man_ineligible_for_mssc(self, schemes):
        profile = CitizenProfile(gender="male")
        result = evaluate(profile, schemes["mssc"].eligibility_rules)
        assert result.verdict == "ineligible"

    def test_ap_farmer_eligible_for_ysrrb(self, schemes):
        profile = CitizenProfile(state="Andhra Pradesh", occupation="farmer")
        result = evaluate(profile, schemes["ysrrb"].eligibility_rules)
        assert result.verdict == "eligible"

    def test_ap_non_farmer_ineligible_for_ysrrb(self, schemes):
        profile = CitizenProfile(state="Andhra Pradesh", occupation="student")
        result = evaluate(profile, schemes["ysrrb"].eligibility_rules)
        assert result.verdict == "ineligible"

    def test_insufficient_info_when_state_missing(self, schemes):
        profile = CitizenProfile(caste="SC", annual_income=200_000, age=30)
        result = evaluate(profile, schemes["dalit-bandhu"].eligibility_rules)
        assert result.verdict == "insufficient_information"

    def test_rural_resident_eligible_for_pmay_g(self, schemes):
        profile = CitizenProfile(domicile="rural")
        result = evaluate(profile, schemes["pmay-g"].eligibility_rules)
        assert result.verdict == "eligible"

    def test_urban_resident_ineligible_for_pmay_g(self, schemes):
        profile = CitizenProfile(domicile="urban")
        result = evaluate(profile, schemes["pmay-g"].eligibility_rules)
        assert result.verdict == "ineligible"

    def test_near_miss_age_for_dalit_bandhu(self, schemes):
        # Age 52 — above max_age 50 by 2 years → near_miss
        profile = CitizenProfile(caste="SC", state="Telangana",
                                 annual_income=200_000, age=52)
        result = evaluate(profile, schemes["dalit-bandhu"].eligibility_rules)
        assert result.verdict == "near_miss"

    def test_west_bengal_single_woman_eligible_rupashree(self, schemes):
        profile = CitizenProfile(state="West Bengal", gender="female",
                                 age=20, annual_income=120_000,
                                 marital_status="single")
        result = evaluate(profile, schemes["wbrupashree"].eligibility_rules)
        assert result.verdict == "eligible"

    def test_married_woman_ineligible_rupashree(self, schemes):
        profile = CitizenProfile(state="West Bengal", gender="female",
                                 age=20, annual_income=120_000,
                                 marital_status="married")
        result = evaluate(profile, schemes["wbrupashree"].eligibility_rules)
        assert result.verdict == "ineligible"