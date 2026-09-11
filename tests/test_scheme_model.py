"""
Tests for the expanded Scheme model and EligibilityRules.
"""

import sys
from datetime import date
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

import pytest
from pydantic import ValidationError
from backend.models.scheme import Scheme, EligibilityRules


def _base_scheme(**overrides) -> dict:
    defaults = dict(
        slug="test-slug",
        scheme_name="Test Scheme",
        details="Some details",
        scheme_categories=["Education & Learning"],
        tags=["Student"],
        level="central",
        benefits="Some benefit",
        eligibility_text="Must be Indian citizen.",
    )
    defaults.update(overrides)
    return defaults


# ---------------------------------------------------------------------------
# EligibilityRules
# ---------------------------------------------------------------------------

class TestEligibilityRules:
    def test_all_none_by_default(self):
        r = EligibilityRules()
        assert r.min_age is None
        assert r.max_age is None
        assert r.max_annual_income is None
        assert r.gender is None
        assert r.caste is None
        assert r.states is None
        assert r.domicile is None
        assert r.occupation is None
        assert r.disability_required is None
        assert r.bpl_required is None
        assert r.marital_status is None

    def test_full_population(self):
        r = EligibilityRules(
            min_age=18,
            max_age=60,
            max_annual_income=200000,
            gender=["female"],
            caste=["SC", "ST", "OBC"],
            states=["Rajasthan"],
            domicile=["rural"],
            occupation=["farmer"],
            disability_required=False,
            bpl_required=True,
            marital_status=["widow"],
        )
        assert r.min_age == 18
        assert r.max_age == 60
        assert r.max_annual_income == 200000
        assert r.gender == ["female"]
        assert "SC" in r.caste
        assert r.states == ["Rajasthan"]
        assert r.bpl_required is True

    def test_any_sentinel_allowed(self):
        r = EligibilityRules(gender=["any"], caste=["any"], states=["any"])
        assert r.gender == ["any"]
        assert r.caste == ["any"]
        assert r.states == ["any"]

    def test_serialises_to_dict(self):
        r = EligibilityRules(min_age=21)
        d = r.model_dump()
        assert d["min_age"] == 21
        assert d["max_age"] is None


# ---------------------------------------------------------------------------
# Scheme — nullable fields default to None
# ---------------------------------------------------------------------------

class TestSchemeNullableFields:
    def test_hindi_name_defaults_none(self):
        s = Scheme(**_base_scheme())
        assert s.hindi_name is None

    def test_state_defaults_none(self):
        s = Scheme(**_base_scheme())
        assert s.state is None

    def test_beneficiary_defaults_none(self):
        s = Scheme(**_base_scheme())
        assert s.beneficiary is None

    def test_eligibility_rules_defaults_none(self):
        s = Scheme(**_base_scheme())
        assert s.eligibility_rules is None

    def test_official_website_defaults_none(self):
        s = Scheme(**_base_scheme())
        assert s.official_website is None

    def test_source_defaults_none(self):
        s = Scheme(**_base_scheme())
        assert s.source is None

    def test_last_verified_date_defaults_none(self):
        s = Scheme(**_base_scheme())
        assert s.last_verified_date is None

    def test_application_defaults_none(self):
        s = Scheme(**_base_scheme())
        assert s.application is None

    def test_documents_defaults_none(self):
        s = Scheme(**_base_scheme())
        assert s.documents is None


# ---------------------------------------------------------------------------
# Scheme — nullable fields accept values when provided
# ---------------------------------------------------------------------------

class TestSchemeNullableFieldsWithValues:
    def test_hindi_name_accepted(self):
        s = Scheme(**_base_scheme(hindi_name="परीक्षण योजना"))
        assert s.hindi_name == "परीक्षण योजना"

    def test_state_accepted(self):
        s = Scheme(**_base_scheme(state="Rajasthan"))
        assert s.state == "Rajasthan"

    def test_beneficiary_accepted(self):
        s = Scheme(**_base_scheme(beneficiary="SC/ST students"))
        assert s.beneficiary == "SC/ST students"

    def test_eligibility_rules_accepted(self):
        rules = EligibilityRules(min_age=18, gender=["female"])
        s = Scheme(**_base_scheme(eligibility_rules=rules))
        assert s.eligibility_rules is not None
        assert s.eligibility_rules.min_age == 18

    def test_last_verified_date_accepted(self):
        s = Scheme(**_base_scheme(last_verified_date=date(2025, 1, 1)))
        assert s.last_verified_date == date(2025, 1, 1)

    def test_official_website_accepted(self):
        s = Scheme(**_base_scheme(official_website="https://example.gov.in"))
        assert s.official_website == "https://example.gov.in"


# ---------------------------------------------------------------------------
# Scheme — required fields and level validation
# ---------------------------------------------------------------------------

class TestSchemeRequiredFields:
    def test_missing_scheme_name_raises(self):
        data = _base_scheme()
        del data["scheme_name"]
        with pytest.raises(ValidationError):
            Scheme(**data)

    def test_missing_details_raises(self):
        data = _base_scheme()
        del data["details"]
        with pytest.raises(ValidationError):
            Scheme(**data)

    def test_missing_eligibility_text_raises(self):
        data = _base_scheme()
        del data["eligibility_text"]
        with pytest.raises(ValidationError):
            Scheme(**data)

    def test_invalid_level_raises(self):
        with pytest.raises(ValidationError):
            Scheme(**_base_scheme(level="national"))

    def test_central_level_accepted(self):
        s = Scheme(**_base_scheme(level="central"))
        assert s.level == "central"

    def test_state_level_accepted(self):
        s = Scheme(**_base_scheme(level="state"))
        assert s.level == "state"


# ---------------------------------------------------------------------------
# Scheme — eligibility_text is never modified
# ---------------------------------------------------------------------------

class TestEligibilityTextPreservation:
    def test_raw_prose_stored_unchanged(self):
        raw = "Must be a resident of Kerala. Age: 18-60. Income < ₹2,00,000/year."
        s = Scheme(**_base_scheme(eligibility_text=raw))
        assert s.eligibility_text == raw

    def test_eligibility_rules_independent_of_text(self):
        raw = "Must be a resident of Kerala."
        rules = EligibilityRules(states=["Kerala"])
        s = Scheme(**_base_scheme(eligibility_text=raw, eligibility_rules=rules))
        assert s.eligibility_text == raw
        assert s.eligibility_rules.states == ["Kerala"]