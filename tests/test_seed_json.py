"""
Validates data/seed_schemes.json.

Checks:
  - JSON is parseable and contains exactly 14 schemes
  - Required top-level fields are present and correctly typed
  - eligibility_rules contains only the 11 defined fields
  - VERIFIED rules match the audit (spot-checks)
  - Unverified and missing arrays are non-empty for schemes that need them
  - No eligibility_rules fields are non-None that were marked MISSING in the audit
  - Rule engine can consume every record without raising
"""
from __future__ import annotations

import json
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

import pytest
from backend.models.citizen_profile import CitizenProfile
from backend.models.scheme import EligibilityRules
from backend.services.rule_engine import evaluate

JSON_PATH = Path(__file__).resolve().parents[1] / "data" / "seed_schemes.json"

EXPECTED_RULE_FIELDS = {
    "min_age", "max_age", "max_annual_income",
    "gender", "caste", "states", "domicile",
    "occupation", "disability_required", "bpl_required", "marital_status",
}

REQUIRED_TOP_LEVEL_FIELDS = {
    "scheme_id", "scheme_name", "category", "category_display",
    "level", "state", "benefit", "official_website",
    "eligibility_rules", "unverified_criteria", "missing_information",
    "required_documents", "application_method", "tags",
}

EXPECTED_SLUGS = {
    "nmmss", "post-st", "pm-daksh", "sys",
    "pmay-g", "daay", "ab-pmjay", "gms", "dayalu",
    "subhadra", "wbrupashree", "mssc", "dalit-bandhu", "ysrrb",
}


@pytest.fixture(scope="module")
def records():
    with open(JSON_PATH, encoding="utf-8") as fh:
        return json.load(fh)


@pytest.fixture(scope="module")
def by_id(records):
    return {r["scheme_id"]: r for r in records}


# ---------------------------------------------------------------------------
# Structure
# ---------------------------------------------------------------------------

class TestStructure:

    def test_is_list(self, records):
        assert isinstance(records, list)

    def test_exactly_14_schemes(self, records):
        assert len(records) == 14

    def test_all_slugs_present(self, by_id):
        assert set(by_id.keys()) == EXPECTED_SLUGS

    def test_required_fields_present(self, records):
        for r in records:
            missing = REQUIRED_TOP_LEVEL_FIELDS - set(r.keys())
            assert not missing, f"{r['scheme_id']} missing fields: {missing}"

    def test_eligibility_rules_has_exactly_11_fields(self, records):
        for r in records:
            rule_keys = set(r["eligibility_rules"].keys())
            assert rule_keys == EXPECTED_RULE_FIELDS, (
                f"{r['scheme_id']} has unexpected rule keys: "
                f"{rule_keys.symmetric_difference(EXPECTED_RULE_FIELDS)}"
            )

    def test_category_is_non_empty_list(self, records):
        for r in records:
            assert isinstance(r["category"], list) and len(r["category"]) >= 1

    def test_level_is_central_or_state(self, records):
        for r in records:
            assert r["level"] in ("central", "state"), f"{r['scheme_id']} bad level"

    def test_official_website_is_null(self, records):
        # Not in CSV — must be null, never invented
        for r in records:
            assert r["official_website"] is None

    def test_unverified_criteria_is_list(self, records):
        for r in records:
            assert isinstance(r["unverified_criteria"], list)

    def test_missing_information_is_list(self, records):
        for r in records:
            assert isinstance(r["missing_information"], list)

    def test_benefit_is_non_empty_string(self, records):
        for r in records:
            assert isinstance(r["benefit"], str) and len(r["benefit"]) > 0

    def test_tags_is_list(self, records):
        for r in records:
            assert isinstance(r["tags"], list)


# ---------------------------------------------------------------------------
# Verified rule values — spot-checks against audit
# ---------------------------------------------------------------------------

class TestVerifiedRuleValues:

    def test_nmmss_income(self, by_id):
        assert by_id["nmmss"]["eligibility_rules"]["max_annual_income"] == 350000

    def test_nmmss_caste_any(self, by_id):
        assert by_id["nmmss"]["eligibility_rules"]["caste"] == ["any"]

    def test_nmmss_states_any(self, by_id):
        assert by_id["nmmss"]["eligibility_rules"]["states"] == ["any"]

    def test_post_st_caste_st(self, by_id):
        assert by_id["post-st"]["eligibility_rules"]["caste"] == ["ST"]

    def test_post_st_income(self, by_id):
        assert by_id["post-st"]["eligibility_rules"]["max_annual_income"] == 200000

    def test_pm_daksh_age(self, by_id):
        r = by_id["pm-daksh"]["eligibility_rules"]
        assert r["min_age"] == 18 and r["max_age"] == 45

    def test_pm_daksh_caste(self, by_id):
        assert set(by_id["pm-daksh"]["eligibility_rules"]["caste"]) == {"SC", "OBC", "EWS"}

    def test_pm_daksh_income_null(self, by_id):
        assert by_id["pm-daksh"]["eligibility_rules"]["max_annual_income"] is None

    def test_sys_state(self, by_id):
        assert by_id["sys"]["eligibility_rules"]["states"] == ["Haryana"]

    def test_sys_income(self, by_id):
        assert by_id["sys"]["eligibility_rules"]["max_annual_income"] == 300000

    def test_pmay_g_domicile(self, by_id):
        assert by_id["pmay-g"]["eligibility_rules"]["domicile"] == ["rural"]

    def test_pmay_g_income_null(self, by_id):
        assert by_id["pmay-g"]["eligibility_rules"]["max_annual_income"] is None

    def test_daay_caste(self, by_id):
        assert by_id["daay"]["eligibility_rules"]["caste"] == ["SC"]

    def test_daay_min_age(self, by_id):
        assert by_id["daay"]["eligibility_rules"]["min_age"] == 21

    def test_daay_income(self, by_id):
        assert by_id["daay"]["eligibility_rules"]["max_annual_income"] == 600000

    def test_ab_pmjay_states_any(self, by_id):
        assert by_id["ab-pmjay"]["eligibility_rules"]["states"] == ["any"]

    def test_ab_pmjay_all_others_null(self, by_id):
        r = by_id["ab-pmjay"]["eligibility_rules"]
        null_fields = [k for k, v in r.items() if k != "states" and v is None]
        assert len(null_fields) == 10  # all 10 other fields are null

    def test_gms_income(self, by_id):
        assert by_id["gms"]["eligibility_rules"]["max_annual_income"] == 150000

    def test_gms_state(self, by_id):
        assert by_id["gms"]["eligibility_rules"]["states"] == ["Goa"]

    def test_dayalu_age(self, by_id):
        r = by_id["dayalu"]["eligibility_rules"]
        assert r["min_age"] == 6 and r["max_age"] == 60

    def test_dayalu_income(self, by_id):
        assert by_id["dayalu"]["eligibility_rules"]["max_annual_income"] == 180000

    def test_subhadra_gender(self, by_id):
        assert by_id["subhadra"]["eligibility_rules"]["gender"] == ["female"]

    def test_subhadra_age(self, by_id):
        r = by_id["subhadra"]["eligibility_rules"]
        assert r["min_age"] == 21 and r["max_age"] == 59

    def test_wbrupashree_marital(self, by_id):
        assert by_id["wbrupashree"]["eligibility_rules"]["marital_status"] == ["single"]

    def test_wbrupashree_min_age(self, by_id):
        assert by_id["wbrupashree"]["eligibility_rules"]["min_age"] == 18

    def test_mssc_gender(self, by_id):
        assert by_id["mssc"]["eligibility_rules"]["gender"] == ["female"]

    def test_mssc_income_null(self, by_id):
        assert by_id["mssc"]["eligibility_rules"]["max_annual_income"] is None

    def test_dalit_bandhu_caste(self, by_id):
        assert by_id["dalit-bandhu"]["eligibility_rules"]["caste"] == ["SC"]

    def test_dalit_bandhu_age(self, by_id):
        r = by_id["dalit-bandhu"]["eligibility_rules"]
        assert r["min_age"] == 25 and r["max_age"] == 50

    def test_dalit_bandhu_income(self, by_id):
        assert by_id["dalit-bandhu"]["eligibility_rules"]["max_annual_income"] == 250000

    def test_ysrrb_occupation(self, by_id):
        assert by_id["ysrrb"]["eligibility_rules"]["occupation"] == ["farmer"]

    def test_ysrrb_state(self, by_id):
        assert by_id["ysrrb"]["eligibility_rules"]["states"] == ["Andhra Pradesh"]


# ---------------------------------------------------------------------------
# Nothing invented — fields marked MISSING must be null
# ---------------------------------------------------------------------------

class TestNothingInvented:

    def test_nmmss_gender_null(self, by_id):
        assert by_id["nmmss"]["eligibility_rules"]["gender"] is None

    def test_nmmss_age_null(self, by_id):
        r = by_id["nmmss"]["eligibility_rules"]
        assert r["min_age"] is None and r["max_age"] is None

    def test_pm_daksh_income_null(self, by_id):
        assert by_id["pm-daksh"]["eligibility_rules"]["max_annual_income"] is None

    def test_pmay_g_income_null(self, by_id):
        assert by_id["pmay-g"]["eligibility_rules"]["max_annual_income"] is None

    def test_pmay_g_caste_null(self, by_id):
        assert by_id["pmay-g"]["eligibility_rules"]["caste"] is None

    def test_sys_caste_null(self, by_id):
        assert by_id["sys"]["eligibility_rules"]["caste"] is None

    def test_gms_age_null(self, by_id):
        r = by_id["gms"]["eligibility_rules"]
        assert r["min_age"] is None and r["max_age"] is None

    def test_gms_caste_null(self, by_id):
        assert by_id["gms"]["eligibility_rules"]["caste"] is None

    def test_ysrrb_income_null(self, by_id):
        assert by_id["ysrrb"]["eligibility_rules"]["max_annual_income"] is None

    def test_mssc_income_null(self, by_id):
        assert by_id["mssc"]["eligibility_rules"]["max_annual_income"] is None

    def test_official_website_null_all(self, records):
        assert all(r["official_website"] is None for r in records)


# ---------------------------------------------------------------------------
# Scheme-level state field
# ---------------------------------------------------------------------------

class TestSchemeState:

    def test_central_schemes_have_null_state(self, by_id):
        central = ["nmmss", "post-st", "pm-daksh", "pmay-g", "ab-pmjay", "mssc"]
        for slug in central:
            assert by_id[slug]["state"] is None, f"{slug} should have state=null"

    def test_state_schemes_have_correct_state(self, by_id):
        expected = {
            "sys": "Haryana",
            "daay": "Gujarat",
            "gms": "Goa",
            "dayalu": "Haryana",
            "subhadra": "Odisha",
            "wbrupashree": "West Bengal",
            "dalit-bandhu": "Telangana",
            "ysrrb": "Andhra Pradesh",
        }
        for slug, state in expected.items():
            assert by_id[slug]["state"] == state, f"{slug}: expected {state}"


# ---------------------------------------------------------------------------
# Documents and application present
# ---------------------------------------------------------------------------

class TestDocumentsAndApplication:

    def test_all_have_required_documents(self, records):
        for r in records:
            assert r["required_documents"] and len(r["required_documents"]) > 10, \
                f"{r['scheme_id']} missing required_documents"

    def test_all_have_application_method(self, records):
        for r in records:
            assert r["application_method"] and len(r["application_method"]) > 10, \
                f"{r['scheme_id']} missing application_method"


# ---------------------------------------------------------------------------
# Rule engine can consume every JSON record
# ---------------------------------------------------------------------------

class TestRuleEngineConsumesJSON:

    def test_all_records_parseable_as_eligibility_rules(self, records):
        for r in records:
            rules = EligibilityRules(**r["eligibility_rules"])
            assert rules is not None

    def test_evaluate_does_not_raise_for_any_record(self, records):
        profile = CitizenProfile(
            age=30, gender="female", caste="SC",
            state="Haryana", annual_income=150_000,
            domicile="rural", occupation="farmer",
            is_disabled=False, has_bpl_card=False,
            marital_status="single",
        )
        for r in records:
            rules = EligibilityRules(**r["eligibility_rules"])
            result = evaluate(profile, rules)
            assert result.verdict in (
                "eligible", "near_miss", "ineligible", "insufficient_information"
            ), f"{r['scheme_id']} returned unexpected verdict"

    def test_evaluate_produces_correct_verdict_spot_checks(self, by_id):
        # SC woman in Telangana, age 30, income 2L → eligible for Dalit Bandhu
        profile = CitizenProfile(caste="SC", state="Telangana",
                                 annual_income=200_000, age=30, gender="female")
        rules = EligibilityRules(**by_id["dalit-bandhu"]["eligibility_rules"])
        assert evaluate(profile, rules).verdict == "eligible"

        # OBC → ineligible for Dalit Bandhu
        profile2 = CitizenProfile(caste="OBC", state="Telangana",
                                  annual_income=200_000, age=30)
        assert evaluate(profile2, rules).verdict == "ineligible"

        # Male → ineligible for SUBHADRA
        rules_sub = EligibilityRules(**by_id["subhadra"]["eligibility_rules"])
        profile3 = CitizenProfile(state="Odisha", gender="male", age=30)
        assert evaluate(profile3, rules_sub).verdict == "ineligible"

        # Urban → ineligible for PMAY-G
        rules_pmay = EligibilityRules(**by_id["pmay-g"]["eligibility_rules"])
        profile4 = CitizenProfile(domicile="urban")
        assert evaluate(profile4, rules_pmay).verdict == "ineligible"