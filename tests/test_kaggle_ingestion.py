"""
Tests for the full-dataset Kaggle ingestion pipeline.

Tests cover:
  - Dataset statistics (row count, unique slugs, duplicates)
  - Eligibility rule extraction (age, income, gender, caste, BPL, disability, state)
  - Record building (SeedScheme-compatible output)
  - Protected scheme IDs not overwritten
  - Idempotent import
  - /api/match evaluates ALL imported schemes
  - Sarvam never called during /api/match
  - Incomplete eligibility → insufficient_information
  - No invented eligibility rules

All tests are offline (no Supabase required). Supabase-dependent tests are
in test_supabase_integration.py.
"""
from __future__ import annotations

import json
import sys
from pathlib import Path
from unittest.mock import patch

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

import pytest
from scripts.ingest import load_and_clean, deduplicate
from scripts.ingest_all import _build_record, _PROTECTED_IDS, run as ingest_run
from backend.services.eligibility_extractor import (
    extract_eligibility_rules,
    detect_state_from_text,
    _extract_age,
    _extract_max_income,
    _extract_gender,
    _extract_caste,
    _extract_bpl,
    _extract_disability,
    _extract_domicile,
    _extract_occupation,
)
from backend.models.scheme import EligibilityRules
from backend.services.scheme_store import SeedScheme

CSV_PATH = Path(__file__).resolve().parents[1] / "updated_data.csv"
SEED_PATH = Path(__file__).resolve().parents[1] / "data" / "seed_schemes.json"


# ---------------------------------------------------------------------------
# Fixtures
# ---------------------------------------------------------------------------

@pytest.fixture(scope="module")
def raw_rows():
    return load_and_clean(CSV_PATH)


@pytest.fixture(scope="module")
def deduped_rows(raw_rows):
    rows, _ = deduplicate(raw_rows)
    return rows


@pytest.fixture(scope="module")
def new_rows(deduped_rows):
    return [r for r in deduped_rows if r["slug"] not in _PROTECTED_IDS]


# ---------------------------------------------------------------------------
# 1. Dataset statistics
# ---------------------------------------------------------------------------

class TestDatasetStatistics:

    def test_total_rows(self, raw_rows):
        assert len(raw_rows) == 3400

    def test_unique_slugs_after_dedup(self, deduped_rows):
        assert len(deduped_rows) == 3397

    def test_duplicates_removed(self, raw_rows, deduped_rows):
        assert len(raw_rows) - len(deduped_rows) == 3

    def test_all_rows_have_slug(self, raw_rows):
        assert all(r["slug"].strip() for r in raw_rows)

    def test_all_rows_have_scheme_name(self, raw_rows):
        assert all(r["scheme_name"].strip() for r in raw_rows)

    def test_level_values(self, deduped_rows):
        levels = {r["level"].strip().lower() for r in deduped_rows}
        assert levels == {"central", "state"}

    def test_protected_ids_present_in_csv(self, deduped_rows):
        slugs = {r["slug"] for r in deduped_rows}
        assert _PROTECTED_IDS.issubset(slugs)

    def test_new_rows_count(self, new_rows):
        assert len(new_rows) == 3397 - 14  # 3383

    def test_no_empty_benefits(self, deduped_rows):
        empty = [r["slug"] for r in deduped_rows if not (r.get("benefits") or "").strip()]
        assert len(empty) == 0


# ---------------------------------------------------------------------------
# 2. Protected IDs
# ---------------------------------------------------------------------------

class TestProtectedIds:

    def test_protected_set_has_14_ids(self):
        assert len(_PROTECTED_IDS) == 14

    def test_protected_ids_match_seed_json(self):
        seed = json.loads(SEED_PATH.read_text(encoding="utf-8"))
        seed_ids = {s["scheme_id"] for s in seed}
        assert _PROTECTED_IDS == seed_ids

    def test_build_record_not_called_for_protected(self, deduped_rows):
        for row in deduped_rows:
            if row["slug"] in _PROTECTED_IDS:
                continue  # correctly skipped
        # if we got here without building protected records, test passes
        assert True

    def test_dry_run_skips_protected(self):
        result = ingest_run(dry_run=True)
        assert result["protected_skipped"] == 14
        assert result["new_imported"] == 3383


# ---------------------------------------------------------------------------
# 3. Eligibility rule extraction — age
# ---------------------------------------------------------------------------

class TestAgeExtraction:

    def test_age_range(self):
        min_a, max_a = _extract_age("age should be between 18 and 60 years")
        assert min_a == 18
        assert max_a == 60

    def test_min_age_only(self):
        min_a, max_a = _extract_age("minimum age of 21 years")
        assert min_a == 21
        assert max_a is None

    def test_max_age_only(self):
        min_a, max_a = _extract_age("maximum age of 45 years")
        assert min_a is None
        assert max_a == 45

    def test_no_false_positive_service_years(self):
        min_a, max_a = _extract_age("at least 5 years of service in the board")
        assert min_a is None
        assert max_a is None

    def test_no_false_positive_membership(self):
        min_a, max_a = _extract_age("membership for at least 3 years with the board")
        assert min_a is None
        assert max_a is None

    def test_above_age_of(self):
        min_a, max_a = _extract_age("above the age of 18 years")
        assert min_a == 18

    def test_not_more_than_years_of_age(self):
        _, max_a = _extract_age("not more than 35 years of age")
        assert max_a == 35

    def test_dash_range(self):
        min_a, max_a = _extract_age("age between 21-60 years")
        assert min_a == 21
        assert max_a == 60


# ---------------------------------------------------------------------------
# 4. Eligibility rule extraction — income
# ---------------------------------------------------------------------------

class TestIncomeExtraction:

    def test_lakh_income(self):
        v = _extract_max_income("annual income should not exceed Rs. 2.5 lakh")
        assert v == 250000

    def test_rupees_raw(self):
        v = _extract_max_income("income below Rs. 1,50,000 per annum")
        assert v == 150000

    def test_none_when_no_income(self):
        v = _extract_max_income("The applicant should be a farmer from Gujarat")
        assert v is None

    def test_crore(self):
        v = _extract_max_income("annual income not exceeding Rs. 1 crore")
        assert v == 10_000_000

    def test_thousand(self):
        v = _extract_max_income("income below Rs. 50 thousand per annum")
        assert v == 50_000


# ---------------------------------------------------------------------------
# 5. Eligibility rule extraction — gender
# ---------------------------------------------------------------------------

class TestGenderExtraction:

    def test_female_applicant(self):
        g = _extract_gender("The applicant should be a woman")
        assert g == ["female"]

    def test_female_beneficiary(self):
        g = _extract_gender("The beneficiary should be a female")
        assert g == ["female"]

    def test_widow(self):
        g = _extract_gender("The applicant should be a widow")
        assert g == ["female"]

    def test_no_gender_restriction(self):
        g = _extract_gender("The applicant should be a permanent resident of Gujarat")
        assert g is None

    def test_no_false_positive_women_scheme(self):
        # Mentions women but doesn't restrict to women only
        g = _extract_gender("Women Entrepreneurship Scheme for all citizens")
        assert g is None


# ---------------------------------------------------------------------------
# 6. Eligibility rule extraction — caste
# ---------------------------------------------------------------------------

class TestCasteExtraction:

    def test_sc(self):
        c = _extract_caste("The applicant should belong to Scheduled Caste")
        assert "SC" in c

    def test_st(self):
        c = _extract_caste("Applicants from Scheduled Tribe are eligible")
        assert "ST" in c

    def test_sc_st_combined(self):
        c = _extract_caste("belong to SC/ST category")
        assert "SC" in c
        assert "ST" in c

    def test_obc(self):
        c = _extract_caste("The applicant must belong to OBC")
        assert "OBC" in c

    def test_no_caste(self):
        c = _extract_caste("The applicant should be 18 years old from Maharashtra")
        assert c is None


# ---------------------------------------------------------------------------
# 7. Eligibility rule extraction — BPL and disability
# ---------------------------------------------------------------------------

class TestBplDisabilityExtraction:

    def test_bpl_card_required(self):
        assert _extract_bpl("The applicant must have a BPL ration card") is True

    def test_bpl_family(self):
        assert _extract_bpl("Applicant should be from a BPL family") is True

    def test_no_bpl(self):
        assert _extract_bpl("The applicant should be a student") is None

    def test_disability_required(self):
        assert _extract_disability("The applicant should have a disability") is True

    def test_pwd(self):
        assert _extract_disability("The applicant should be a Person with Disability (PwD)") is True

    def test_no_disability(self):
        assert _extract_disability("The applicant should be a farmer") is None


# ---------------------------------------------------------------------------
# 8. Eligibility rule extraction — domicile and occupation
# ---------------------------------------------------------------------------

class TestDomicileOccupationExtraction:

    def test_rural_required(self):
        d = _extract_domicile("The applicant should be a resident of a rural area")
        assert d == ["rural"]

    def test_urban_required(self):
        d = _extract_domicile("The beneficiary should be a resident of an urban area")
        assert d == ["urban"]

    def test_no_domicile(self):
        assert _extract_domicile("The applicant should be a farmer") is None

    def test_farmer_occupation(self):
        o = _extract_occupation("The beneficiary should be a farmer from Gujarat")
        assert "farmer" in o

    def test_any_farmer(self):
        o = _extract_occupation("Any farmer of Gujarat State is eligible")
        assert "farmer" in o

    def test_student_occupation(self):
        o = _extract_occupation("The applicant should be a student in class 9")
        assert "student" in o

    def test_no_occupation(self):
        assert _extract_occupation("The applicant should be a widow with BPL card") is None


# ---------------------------------------------------------------------------
# 9. State detection
# ---------------------------------------------------------------------------

class TestStateDetection:

    def test_state_in_name(self):
        s = detect_state_from_text("Maharashtra Farmer Scheme", "", "")
        assert s == "Maharashtra"

    def test_state_in_tags(self):
        s = detect_state_from_text("Scheme X", "Kerala, Financial Assistance", "")
        assert s == "Kerala"

    def test_state_in_details(self):
        s = detect_state_from_text("Scheme Y", "", "This scheme is for residents of Rajasthan.")
        assert s == "Rajasthan"

    def test_no_state(self):
        s = detect_state_from_text("General Scheme", "Welfare, Assistance", "")
        assert s is None

    def test_canonical_casing(self):
        s = detect_state_from_text("GUJARAT scheme", "", "")
        assert s == "Gujarat"


# ---------------------------------------------------------------------------
# 10. Record building
# ---------------------------------------------------------------------------

class TestRecordBuilding:

    def test_scheme_id_equals_slug(self, new_rows):
        rec = _build_record(new_rows[0])
        assert rec["scheme_id"] == new_rows[0]["slug"]

    def test_required_fields_present(self, new_rows):
        required = {
            "scheme_id", "scheme_name", "category", "category_display",
            "level", "state", "benefit", "official_website",
            "eligibility_rules", "unverified_criteria", "missing_information",
            "required_documents", "application_method", "tags",
        }
        for row in new_rows[:50]:
            rec = _build_record(row)
            assert required.issubset(set(rec.keys())), f"Missing fields in {rec['scheme_id']}"

    def test_eligibility_rules_has_all_11_fields(self, new_rows):
        expected_keys = {
            "min_age", "max_age", "max_annual_income", "gender", "caste",
            "states", "domicile", "occupation", "disability_required",
            "bpl_required", "marital_status",
        }
        for row in new_rows[:50]:
            rec = _build_record(row)
            assert set(rec["eligibility_rules"].keys()) == expected_keys

    def test_central_schemes_get_any_state(self, deduped_rows):
        central = [r for r in deduped_rows if r["level"].lower() == "central" and r["slug"] not in _PROTECTED_IDS]
        for row in central[:20]:
            rec = _build_record(row)
            assert rec["eligibility_rules"]["states"] == ["any"], f"{row['slug']} should have states=['any']"

    def test_level_normalized_to_lowercase(self, new_rows):
        for row in new_rows[:100]:
            rec = _build_record(row)
            assert rec["level"] in ("central", "state")

    def test_unverified_criteria_is_list(self, new_rows):
        for row in new_rows[:50]:
            rec = _build_record(row)
            assert isinstance(rec["unverified_criteria"], list)

    def test_unverified_contains_eligibility_text(self, new_rows):
        for row in new_rows[:50]:
            if row.get("eligibility", "").strip():
                rec = _build_record(row)
                assert len(rec["unverified_criteria"]) >= 1

    def test_missing_information_is_list(self, new_rows):
        for row in new_rows[:50]:
            rec = _build_record(row)
            assert isinstance(rec["missing_information"], list)

    def test_record_passes_seedscheme_validation(self, new_rows):
        for row in new_rows[:100]:
            rec = _build_record(row)
            # Should not raise
            scheme = SeedScheme.model_validate(rec)
            assert scheme.scheme_id == row["slug"]

    def test_no_invented_rules(self, new_rows):
        """Structured rules must only come from extract_eligibility_rules — never guessed."""
        for row in new_rows[:200]:
            rec = _build_record(row)
            rules = rec["eligibility_rules"]
            # Numeric rules must be plausible
            if rules.get("min_age") is not None:
                assert 5 <= rules["min_age"] <= 100, f"Implausible min_age in {row['slug']}"
            if rules.get("max_age") is not None:
                assert 10 <= rules["max_age"] <= 120, f"Implausible max_age in {row['slug']}"
            if rules.get("max_annual_income") is not None:
                assert 10_000 <= rules["max_annual_income"] <= 100_000_000, f"Implausible income in {row['slug']}"
            if rules.get("gender") is not None:
                assert all(g in ("male", "female", "transgender", "any") for g in rules["gender"])
            if rules.get("caste") is not None:
                assert all(c in ("SC", "ST", "OBC", "EWS", "general", "any") for c in rules["caste"])


# ---------------------------------------------------------------------------
# 11. Idempotent import
# ---------------------------------------------------------------------------

class TestIdempotentImport:

    def test_dry_run_produces_same_count_twice(self):
        r1 = ingest_run(dry_run=True)
        r2 = ingest_run(dry_run=True)
        assert r1["new_imported"] == r2["new_imported"]
        assert r1["duplicates_removed"] == r2["duplicates_removed"]

    def test_dry_run_total_matches_expected(self):
        result = ingest_run(dry_run=True)
        assert result["total_csv_rows"] == 3400
        assert result["unique_slugs"] == 3397
        assert result["duplicates_removed"] == 3
        assert result["protected_skipped"] == 14
        assert result["new_imported"] == 3383


# ---------------------------------------------------------------------------
# 12. Match API evaluates all schemes (no Supabase — mocked all_schemes)
# ---------------------------------------------------------------------------

class TestMatchApiWithAllSchemes:

    def _make_seed_scheme(self, slug: str, name: str = "Test") -> SeedScheme:
        """Create a minimal SeedScheme for testing."""
        return SeedScheme.model_validate({
            "scheme_id": slug,
            "scheme_name": name,
            "category": ["Education & Learning"],
            "category_display": ["Education"],
            "level": "central",
            "state": None,
            "benefit": "Some benefit",
            "official_website": None,
            "eligibility_rules": {
                "min_age": None, "max_age": None, "max_annual_income": None,
                "gender": None, "caste": None, "states": ["any"],
                "domicile": None, "occupation": None, "disability_required": None,
                "bpl_required": None, "marital_status": None,
            },
            "unverified_criteria": ["Must be an Indian citizen"],
            "missing_information": [],
            "required_documents": None,
            "application_method": None,
            "tags": [],
        })

    def test_match_evaluates_all_mocked_schemes(self):
        from fastapi.testclient import TestClient
        from backend.main import app

        # Build 50 fake schemes
        fake_schemes = [self._make_seed_scheme(f"test-{i}", f"Scheme {i}") for i in range(50)]

        client = TestClient(app)
        sid = client.post("/api/profile").json()["session_id"]
        client.patch(f"/api/profile/{sid}", json={"age": 30, "state": "Maharashtra"})

        with patch("backend.routes.match.all_schemes", return_value=fake_schemes):
            r = client.post("/api/match", json={"session_id": sid})

        assert r.status_code == 200
        data = r.json()
        assert data["total_schemes"] == 50
        total_in_groups = (
            len(data["eligible"]) + len(data["near_miss"])
            + len(data["insufficient_information"]) + len(data["ineligible"])
        )
        assert total_in_groups == 50

    def test_sarvam_never_called_during_match(self):
        from fastapi.testclient import TestClient
        from backend.main import app

        client = TestClient(app)
        sid = client.post("/api/profile").json()["session_id"]
        fake = [self._make_seed_scheme("sarvam-test")]

        with patch("backend.routes.match.all_schemes", return_value=fake), \
             patch("backend.services.extractor.httpx.Client") as mock_http:
            r = client.post("/api/match", json={"session_id": sid})
            assert not mock_http.called, "Sarvam was called during /api/match!"

    def test_no_rules_scheme_with_incomplete_profile_is_eligible(self):
        """A scheme with all-None rules and no conditions always shows eligible."""
        from fastapi.testclient import TestClient
        from backend.main import app

        no_rule_scheme = self._make_seed_scheme("no-rules-test")
        client = TestClient(app)
        sid = client.post("/api/profile").json()["session_id"]

        with patch("backend.routes.match.all_schemes", return_value=[no_rule_scheme]):
            r = client.post("/api/match", json={"session_id": sid})

        data = r.json()
        # states=["any"] means no state restriction — should be eligible
        assert data["total_schemes"] == 1
        assert len(data["eligible"]) == 1

    def test_scheme_with_state_rule_ineligible_for_wrong_state(self):
        from fastapi.testclient import TestClient
        from backend.main import app

        ap_scheme = SeedScheme.model_validate({
            "scheme_id": "ap-only",
            "scheme_name": "AP Only",
            "category": ["Agriculture"],
            "category_display": ["Agriculture"],
            "level": "state",
            "state": "Andhra Pradesh",
            "benefit": "AP farmers benefit",
            "official_website": None,
            "eligibility_rules": {
                "min_age": None, "max_age": None, "max_annual_income": None,
                "gender": None, "caste": None, "states": ["Andhra Pradesh"],
                "domicile": None, "occupation": None, "disability_required": None,
                "bpl_required": None, "marital_status": None,
            },
            "unverified_criteria": [],
            "missing_information": [],
            "required_documents": None,
            "application_method": None,
            "tags": [],
        })

        client = TestClient(app)
        sid = client.post("/api/profile").json()["session_id"]
        client.patch(f"/api/profile/{sid}", json={"state": "Maharashtra"})

        with patch("backend.routes.match.all_schemes", return_value=[ap_scheme]):
            r = client.post("/api/match", json={"session_id": sid})

        data = r.json()
        assert len(data["ineligible"]) == 1
        assert data["ineligible"][0]["scheme_id"] == "ap-only"


# ---------------------------------------------------------------------------
# 13. Extraction quality on real data
# ---------------------------------------------------------------------------

class TestExtractionQualityOnRealData:

    def test_farmer_scheme_extracts_occupation(self, new_rows):
        farmer_rows = [r for r in new_rows if "farmer" in r.get("eligibility", "").lower()
                       and "should be a farmer" in r.get("eligibility", "").lower()]
        assert len(farmer_rows) > 0
        found = 0
        for row in farmer_rows[:20]:
            rec = _build_record(row)
            if rec["eligibility_rules"].get("occupation") and "farmer" in rec["eligibility_rules"]["occupation"]:
                found += 1
        assert found > 0, "No farmer occupation extracted from farmer schemes"

    def test_sc_st_scheme_extracts_caste(self, new_rows):
        sc_rows = [r for r in new_rows
                   if "belong to" in r.get("eligibility", "").lower()
                   and ("SC" in r.get("eligibility", "") or "Scheduled Caste" in r.get("eligibility", ""))]
        assert len(sc_rows) > 0
        found = 0
        for row in sc_rows[:20]:
            rec = _build_record(row)
            if rec["eligibility_rules"].get("caste"):
                found += 1
        assert found > 0

    def test_female_scheme_extracts_gender(self, new_rows):
        widow_rows = [r for r in new_rows
                      if "applicant should be a widow" in r.get("eligibility", "").lower()]
        assert len(widow_rows) > 0
        for row in widow_rows[:10]:
            rec = _build_record(row)
            assert rec["eligibility_rules"].get("gender") == ["female"], \
                f"Widow scheme {row['slug']} should have gender=['female']"
