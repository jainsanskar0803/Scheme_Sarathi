"""
Tests for POST /api/match — scheme matching API.

The rule engine is always called directly; no LLM mock is needed because the
match endpoint never touches the extractor.  Every verdict is determined by
pure Python comparisons.

Scheme active rules (from seed_schemes.json — used to design test profiles):
  nmmss        central  income ≤ 3,50,000
  post-st      central  caste=ST, income ≤ 2,00,000
  pm-daksh     central  age 18-45, caste in [SC,OBC,EWS]
  sys          state    age 18-35, income ≤ 3,00,000, state=Haryana
  pmay-g       central  domicile=rural
  daay         state    age ≥ 21, income ≤ 6,00,000, caste=SC, state=Gujarat
  ab-pmjay     central  (no encoded rules — always eligible)
  gms          state    income ≤ 1,50,000, state=Goa
  dayalu       state    age 6-60, income ≤ 1,80,000, state=Haryana
  subhadra     state    age 21-59, income ≤ 2,50,000, gender=female, state=Odisha
  wbrupashree  state    age ≥ 18, income ≤ 1,50,000, gender=female, state=West Bengal, marital=single
  mssc         central  gender=female
  dalit-bandhu state    age 25-50, income ≤ 2,50,000, caste=SC, state=Telangana
  ysrrb        state    state=Andhra Pradesh, occupation=farmer
"""
from __future__ import annotations

import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

import pytest
from fastapi.testclient import TestClient

from backend.main import app
from backend.models.citizen_profile import CitizenProfile
from backend.routes.match import run_match

client = TestClient(app)


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------

def create_session() -> str:
    r = client.post("/api/profile")
    assert r.status_code == 201
    return r.json()["session_id"]


def fill_session(sid: str, fields: dict) -> None:
    r = client.patch(f"/api/profile/{sid}", json=fields)
    assert r.status_code == 200, r.text


def match_session(sid: str) -> dict:
    r = client.post("/api/match", json={"session_id": sid})
    assert r.status_code == 200, r.text
    return r.json()


def scheme_ids_in(results: list[dict]) -> set[str]:
    return {s["scheme_id"] for s in results}


def find_scheme(results: list[dict], scheme_id: str) -> dict | None:
    return next((s for s in results if s["scheme_id"] == scheme_id), None)


# ---------------------------------------------------------------------------
# Basic endpoint behaviour
# ---------------------------------------------------------------------------

class TestMatchEndpoint:

    def test_returns_200(self):
        sid = create_session()
        r = client.post("/api/match", json={"session_id": sid})
        assert r.status_code == 200

    def test_unknown_session_404(self):
        r = client.post("/api/match", json={"session_id": "ghost-session"})
        assert r.status_code == 404

    def test_missing_session_id_422(self):
        r = client.post("/api/match", json={})
        assert r.status_code == 422

    def test_response_has_all_verdict_groups(self):
        sid = create_session()
        data = match_session(sid)
        for key in ("eligible", "near_miss", "insufficient_information", "ineligible"):
            assert key in data

    def test_total_schemes_at_least_14(self):
        sid = create_session()
        data = match_session(sid)
        assert data["total_schemes"] >= 14

    def test_total_equals_sum_of_groups(self):
        sid = create_session()
        data = match_session(sid)
        total = (
            len(data["eligible"])
            + len(data["near_miss"])
            + len(data["insufficient_information"])
            + len(data["ineligible"])
        )
        assert total == data["total_schemes"]

    def test_response_includes_profile(self):
        sid = create_session()
        data = match_session(sid)
        assert "profile" in data

    def test_response_includes_completeness(self):
        sid = create_session()
        data = match_session(sid)
        assert "completeness" in data

    def test_session_id_echoed(self):
        sid = create_session()
        data = match_session(sid)
        assert data["session_id"] == sid


# ---------------------------------------------------------------------------
# Eligible verdict
# ---------------------------------------------------------------------------

class TestEligibleVerdict:

    def test_farmer_in_ap_eligible_for_ysrrb(self):
        sid = create_session()
        fill_session(sid, {"state": "Andhra Pradesh", "occupation": "farmer"})
        data = match_session(sid)
        assert "ysrrb" in scheme_ids_in(data["eligible"])

    def test_female_eligible_for_mssc(self):
        sid = create_session()
        fill_session(sid, {"gender": "female"})
        data = match_session(sid)
        assert "mssc" in scheme_ids_in(data["eligible"])

    def test_rural_eligible_for_pmay_g(self):
        sid = create_session()
        fill_session(sid, {"domicile": "rural"})
        data = match_session(sid)
        assert "pmay-g" in scheme_ids_in(data["eligible"])

    def test_st_low_income_eligible_for_post_st(self):
        sid = create_session()
        fill_session(sid, {"caste": "ST", "annual_income": 150000})
        data = match_session(sid)
        assert "post-st" in scheme_ids_in(data["eligible"])

    def test_ab_pmjay_always_eligible_no_rules(self):
        # ab-pmjay has no encoded rules; rule engine returns eligible for any profile
        sid = create_session()
        data = match_session(sid)
        assert "ab-pmjay" in scheme_ids_in(data["eligible"])

    def test_haryana_youth_eligible_for_sys(self):
        sid = create_session()
        fill_session(sid, {
            "state": "Haryana", "age": 25, "annual_income": 200000
        })
        data = match_session(sid)
        assert "sys" in scheme_ids_in(data["eligible"])

    def test_odisha_female_eligible_for_subhadra(self):
        sid = create_session()
        fill_session(sid, {
            "state": "Odisha", "gender": "female",
            "age": 30, "annual_income": 200000,
        })
        data = match_session(sid)
        assert "subhadra" in scheme_ids_in(data["eligible"])

    def test_sc_gujarat_eligible_for_daay(self):
        sid = create_session()
        fill_session(sid, {
            "state": "Gujarat", "caste": "SC",
            "age": 25, "annual_income": 400000,
        })
        data = match_session(sid)
        assert "daay" in scheme_ids_in(data["eligible"])

    def test_goa_low_income_eligible_for_gms(self):
        sid = create_session()
        fill_session(sid, {"state": "Goa", "annual_income": 100000})
        data = match_session(sid)
        assert "gms" in scheme_ids_in(data["eligible"])


# ---------------------------------------------------------------------------
# Ineligible verdict
# ---------------------------------------------------------------------------

class TestIneligibleVerdict:

    def test_male_ineligible_for_mssc(self):
        sid = create_session()
        fill_session(sid, {"gender": "male"})
        data = match_session(sid)
        assert "mssc" in scheme_ids_in(data["ineligible"])

    def test_non_ap_farmer_ineligible_for_ysrrb(self):
        sid = create_session()
        fill_session(sid, {"state": "Maharashtra", "occupation": "farmer"})
        data = match_session(sid)
        assert "ysrrb" in scheme_ids_in(data["ineligible"])

    def test_general_caste_ineligible_for_post_st(self):
        sid = create_session()
        fill_session(sid, {"caste": "general", "annual_income": 150000})
        data = match_session(sid)
        assert "post-st" in scheme_ids_in(data["ineligible"])

    def test_urban_ineligible_for_pmay_g(self):
        sid = create_session()
        fill_session(sid, {"domicile": "urban"})
        data = match_session(sid)
        assert "pmay-g" in scheme_ids_in(data["ineligible"])

    def test_high_income_ineligible_for_gms(self):
        # GMS: income ≤ 1,50,000 and state=Goa
        sid = create_session()
        fill_session(sid, {"state": "Goa", "annual_income": 500000})
        data = match_session(sid)
        assert "gms" in scheme_ids_in(data["ineligible"])

    def test_too_old_for_sys(self):
        # sys max_age=35; age=38 is 3 years above → ineligible (exceeds 2-year near-miss window)
        sid = create_session()
        fill_session(sid, {
            "state": "Haryana", "age": 38, "annual_income": 200000
        })
        data = match_session(sid)
        assert "sys" in scheme_ids_in(data["ineligible"])

    def test_wrong_state_ineligible_for_dayalu(self):
        # dayalu requires state=Haryana
        sid = create_session()
        fill_session(sid, {
            "state": "Punjab", "age": 30, "annual_income": 100000
        })
        data = match_session(sid)
        assert "dayalu" in scheme_ids_in(data["ineligible"])

    def test_sc_caste_required_for_dalit_bandhu(self):
        sid = create_session()
        fill_session(sid, {
            "state": "Telangana", "caste": "OBC",
            "age": 30, "annual_income": 200000,
        })
        data = match_session(sid)
        assert "dalit-bandhu" in scheme_ids_in(data["ineligible"])

    def test_wb_rupashree_married_woman_ineligible(self):
        # wbrupashree requires marital_status=single
        sid = create_session()
        fill_session(sid, {
            "state": "West Bengal", "gender": "female",
            "age": 25, "annual_income": 100000,
            "marital_status": "married",
        })
        data = match_session(sid)
        assert "wbrupashree" in scheme_ids_in(data["ineligible"])


# ---------------------------------------------------------------------------
# Near-miss verdict
# ---------------------------------------------------------------------------

class TestNearMissVerdict:

    def test_age_one_above_sys_max_is_near_miss(self):
        # sys max_age=35; age=36 → excess=1 ≤ 2 → near_miss
        sid = create_session()
        fill_session(sid, {
            "state": "Haryana", "age": 36, "annual_income": 200000
        })
        data = match_session(sid)
        assert "sys" in scheme_ids_in(data["near_miss"])

    def test_age_two_above_sys_max_is_near_miss(self):
        # sys max_age=35; age=37 → excess=2 ≤ 2 → near_miss (boundary)
        sid = create_session()
        fill_session(sid, {
            "state": "Haryana", "age": 37, "annual_income": 200000
        })
        data = match_session(sid)
        assert "sys" in scheme_ids_in(data["near_miss"])

    def test_age_three_above_sys_max_is_ineligible(self):
        # sys max_age=35; age=38 → excess=3 > 2 → ineligible
        sid = create_session()
        fill_session(sid, {
            "state": "Haryana", "age": 38, "annual_income": 200000
        })
        data = match_session(sid)
        assert "sys" in scheme_ids_in(data["ineligible"])

    def test_income_10pct_above_ceiling_is_near_miss(self):
        # nmmss income ≤ 3,50,000; 10% above = 3,85,000 → near_miss
        sid = create_session()
        fill_session(sid, {"annual_income": 385000})
        data = match_session(sid)
        assert "nmmss" in scheme_ids_in(data["near_miss"])

    def test_income_just_above_10pct_is_ineligible(self):
        # nmmss income ≤ 3,50,000; 11% above = ~3,88,500 → ineligible
        sid = create_session()
        fill_session(sid, {"annual_income": 390000})
        data = match_session(sid)
        assert "nmmss" in scheme_ids_in(data["ineligible"])

    def test_near_miss_result_has_near_miss_rules(self):
        sid = create_session()
        fill_session(sid, {
            "state": "Haryana", "age": 36, "annual_income": 200000
        })
        data = match_session(sid)
        sys_result = find_scheme(data["near_miss"], "sys")
        assert sys_result is not None
        assert len(sys_result["near_miss_rules"]) > 0

    def test_near_miss_near_miss_rules_are_in_failed_rules(self):
        sid = create_session()
        fill_session(sid, {
            "state": "Haryana", "age": 36, "annual_income": 200000
        })
        data = match_session(sid)
        sys_result = find_scheme(data["near_miss"], "sys")
        nm_fields = {c["field"] for c in sys_result["near_miss_rules"]}
        failed_fields = {c["field"] for c in sys_result["failed_rules"]}
        assert nm_fields.issubset(failed_fields)


# ---------------------------------------------------------------------------
# Insufficient information verdict
# ---------------------------------------------------------------------------

class TestInsufficientInformation:

    def test_empty_profile_has_insufficient_info(self):
        sid = create_session()
        data = match_session(sid)
        # With no profile fields, no condition can be evaluated
        # ab-pmjay has zero rules so it's always eligible; others should be II
        assert len(data["insufficient_information"]) > 0

    def test_no_scheme_in_both_eligible_and_ineligible(self):
        sid = create_session()
        data = match_session(sid)
        eligible_ids = scheme_ids_in(data["eligible"])
        ineligible_ids = scheme_ids_in(data["ineligible"])
        assert eligible_ids.isdisjoint(ineligible_ids)

    def test_each_scheme_in_exactly_one_group(self):
        sid = create_session()
        data = match_session(sid)
        all_ids = (
            scheme_ids_in(data["eligible"])
            | scheme_ids_in(data["near_miss"])
            | scheme_ids_in(data["insufficient_information"])
            | scheme_ids_in(data["ineligible"])
        )
        assert len(all_ids) == 14

    def test_scheme_with_unresolvable_field_is_insufficient(self):
        # ysrrb needs state=AP and occupation; only state given → occupation unknown
        # state=Maharashtra → ineligible (wrong state)
        # state=Andhra Pradesh, no occupation → insufficient for occupation check
        sid = create_session()
        fill_session(sid, {"state": "Andhra Pradesh"})
        data = match_session(sid)
        # ysrrb has occupation=["farmer"] rule; occupation is None → insufficient
        assert "ysrrb" in scheme_ids_in(data["insufficient_information"])


# ---------------------------------------------------------------------------
# Result structure
# ---------------------------------------------------------------------------

class TestResultStructure:

    def _get_any_result(self) -> dict:
        sid = create_session()
        fill_session(sid, {"gender": "female"})
        data = match_session(sid)
        # mssc is eligible for any female
        return find_scheme(data["eligible"], "mssc")

    def test_result_has_scheme_id(self):
        r = self._get_any_result()
        assert "scheme_id" in r

    def test_result_has_scheme_name(self):
        r = self._get_any_result()
        assert r["scheme_name"] != ""

    def test_result_has_verdict(self):
        r = self._get_any_result()
        assert r["verdict"] in ("eligible", "near_miss", "insufficient_information", "ineligible")

    def test_result_has_benefit(self):
        r = self._get_any_result()
        assert r["benefit"] != ""

    def test_result_has_passed_rules(self):
        r = self._get_any_result()
        assert "passed_rules" in r

    def test_result_has_failed_rules(self):
        r = self._get_any_result()
        assert "failed_rules" in r

    def test_result_has_near_miss_rules(self):
        r = self._get_any_result()
        assert "near_miss_rules" in r

    def test_result_has_skipped_count(self):
        r = self._get_any_result()
        assert "skipped_count" in r

    def test_result_has_unverified_criteria(self):
        r = self._get_any_result()
        assert "unverified_criteria" in r

    def test_result_has_missing_information(self):
        r = self._get_any_result()
        assert "missing_information" in r

    def test_result_has_required_documents(self):
        r = self._get_any_result()
        assert "required_documents" in r

    def test_result_has_application_method(self):
        r = self._get_any_result()
        assert "application_method" in r

    def test_result_has_source(self):
        r = self._get_any_result()
        assert r["source"] != ""

    def test_result_has_official_website(self):
        r = self._get_any_result()
        assert "official_website" in r

    def test_central_scheme_source_label(self):
        # mssc is a central scheme
        r = self._get_any_result()
        assert r["source"] == "Central Government"

    def test_state_scheme_source_label(self):
        # ysrrb is a state scheme for Andhra Pradesh
        sid = create_session()
        fill_session(sid, {"state": "Andhra Pradesh", "occupation": "farmer"})
        data = match_session(sid)
        r = find_scheme(data["eligible"], "ysrrb")
        assert "Andhra Pradesh" in r["source"]

    def test_eligible_result_has_no_failed_rules(self):
        r = self._get_any_result()
        assert r["failed_rules"] == []

    def test_ineligible_result_has_failed_rules(self):
        sid = create_session()
        fill_session(sid, {"gender": "male"})
        data = match_session(sid)
        r = find_scheme(data["ineligible"], "mssc")
        assert len(r["failed_rules"]) > 0

    def test_condition_result_has_reason_string(self):
        sid = create_session()
        fill_session(sid, {"gender": "male"})
        data = match_session(sid)
        r = find_scheme(data["ineligible"], "mssc")
        cond = r["failed_rules"][0]
        assert isinstance(cond["reason"], str)
        assert len(cond["reason"]) > 0

    def test_condition_result_has_field(self):
        sid = create_session()
        fill_session(sid, {"gender": "male"})
        data = match_session(sid)
        r = find_scheme(data["ineligible"], "mssc")
        cond = r["failed_rules"][0]
        assert cond["field"] == "gender"

    def test_condition_result_has_actual_value(self):
        sid = create_session()
        fill_session(sid, {"gender": "male"})
        data = match_session(sid)
        r = find_scheme(data["ineligible"], "mssc")
        cond = r["failed_rules"][0]
        assert cond["actual_value"] == "male"


# ---------------------------------------------------------------------------
# run_match pure function
# ---------------------------------------------------------------------------

class TestRunMatchPure:

    def test_all_schemes_evaluated(self):
        from backend.services.scheme_store import all_schemes
        profile = CitizenProfile()
        groups = run_match(profile)
        total = sum(len(v) for v in groups.values())
        assert total == len(all_schemes())

    def test_groups_keyed_correctly(self):
        profile = CitizenProfile()
        groups = run_match(profile)
        assert set(groups.keys()) == {
            "eligible", "near_miss", "insufficient_information", "ineligible"
        }

    def test_no_scheme_in_multiple_groups(self):
        profile = CitizenProfile()
        groups = run_match(profile)
        seen = set()
        for lst in groups.values():
            for item in lst:
                assert item.scheme_id not in seen
                seen.add(item.scheme_id)

    def test_eligible_sorted_by_passed_count_desc(self):
        profile = CitizenProfile(
            gender="female",
            state="Odisha",
            age=30,
            annual_income=200000,
        )
        groups = run_match(profile)
        counts = [len(s.passed_rules) for s in groups["eligible"]]
        assert counts == sorted(counts, reverse=True)

    def test_farmer_ap_ysrrb_eligible(self):
        profile = CitizenProfile(state="Andhra Pradesh", occupation="farmer")
        groups = run_match(profile)
        ids = {s.scheme_id for s in groups["eligible"]}
        assert "ysrrb" in ids

    def test_ab_pmjay_zero_conditions_eligible(self):
        profile = CitizenProfile()  # totally empty
        groups = run_match(profile)
        ids = {s.scheme_id for s in groups["eligible"]}
        assert "ab-pmjay" in ids

    def test_verdict_never_set_by_llm(self):
        # Structural: run_match imports no extractor module
        import backend.routes.match as match_module
        assert not hasattr(match_module, "extract_profile_fields"), \
            "match route must not import the LLM extractor"