"""
Supabase integration tests.

These tests run ONLY when USE_SUPABASE=true and valid credentials are present
in the environment (or .env file).  All other CI / local runs skip this file.

They verify the six points required by the task:
  1. Create interview session
  2. Save citizen profile
  3. Retrieve citizen profile
  4. Retrieve schemes from Supabase
  5. Run /api/match end-to-end
  6. Verify all 14 schemes are evaluated correctly
"""
from __future__ import annotations

import os
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

import pytest
from dotenv import load_dotenv

load_dotenv()

# ---------------------------------------------------------------------------
# Skip guard — must be the very first thing after imports
# ---------------------------------------------------------------------------

_SUPABASE_ENABLED = (
    os.environ.get("USE_SUPABASE", "").lower() == "true"
    and os.environ.get("SUPABASE_URL", "").startswith("https://")
    and bool(os.environ.get("SUPABASE_SERVICE_KEY", ""))
)

pytestmark = pytest.mark.skipif(
    not _SUPABASE_ENABLED,
    reason="Supabase integration tests require USE_SUPABASE=true and valid credentials",
)

# ---------------------------------------------------------------------------
# Imports that need Supabase available
# ---------------------------------------------------------------------------

from fastapi.testclient import TestClient
from backend.main import app
from backend.db import session_store
from backend.services.scheme_store import all_schemes

client = TestClient(app)


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------

def create_session() -> str:
    r = client.post("/api/profile")
    assert r.status_code == 201
    return r.json()["session_id"]


def patch_profile(sid: str, fields: dict) -> dict:
    r = client.patch(f"/api/profile/{sid}", json=fields)
    assert r.status_code == 200, r.text
    return r.json()


def match(sid: str) -> dict:
    r = client.post("/api/match", json={"session_id": sid})
    assert r.status_code == 200, r.text
    return r.json()


# ---------------------------------------------------------------------------
# 1. Create interview session
# ---------------------------------------------------------------------------

class TestCreateSession:

    def test_post_profile_returns_201(self):
        r = client.post("/api/profile")
        assert r.status_code == 201

    def test_response_has_session_id(self):
        r = client.post("/api/profile")
        assert "session_id" in r.json()

    def test_session_persisted_in_supabase(self):
        from backend.db.supabase import get_client
        sid = create_session()
        res = get_client().table("interview_sessions").select("session_id").eq("session_id", sid).execute()
        assert res.data, f"Session {sid} not found in Supabase"

    def test_new_session_has_empty_profile(self):
        sid = create_session()
        r = client.get(f"/api/profile/{sid}")
        assert r.status_code == 200
        profile = r.json()["profile"]
        assert all(v is None for v in profile.values())


# ---------------------------------------------------------------------------
# 2. Save citizen profile
# ---------------------------------------------------------------------------

class TestSaveProfile:

    def test_patch_saves_to_supabase(self):
        from backend.db.supabase import get_client
        sid = create_session()
        patch_profile(sid, {"age": 35, "state": "Maharashtra"})
        res = (
            get_client()
            .table("interview_sessions")
            .select("profile_data")
            .eq("session_id", sid)
            .execute()
        )
        assert res.data
        pd = res.data[0]["profile_data"]
        assert pd["age"] == 35
        assert pd["state"] == "Maharashtra"

    def test_incremental_patch_accumulates(self):
        sid = create_session()
        patch_profile(sid, {"age": 30})
        patch_profile(sid, {"gender": "female"})
        r = client.get(f"/api/profile/{sid}")
        p = r.json()["profile"]
        assert p["age"] == 30
        assert p["gender"] == "female"

    def test_invalid_field_returns_422_not_saved(self):
        from backend.db.supabase import get_client
        sid = create_session()
        r = client.patch(f"/api/profile/{sid}", json={"age": 999})
        assert r.status_code == 422
        # Profile should still be empty
        res = (
            get_client()
            .table("interview_sessions")
            .select("profile_data")
            .eq("session_id", sid)
            .execute()
        )
        assert res.data[0]["profile_data"].get("age") is None


# ---------------------------------------------------------------------------
# 3. Retrieve citizen profile
# ---------------------------------------------------------------------------

class TestRetrieveProfile:

    def test_get_returns_saved_profile(self):
        sid = create_session()
        patch_profile(sid, {"age": 42, "occupation": "farmer", "state": "Andhra Pradesh"})
        r = client.get(f"/api/profile/{sid}")
        assert r.status_code == 200
        p = r.json()["profile"]
        assert p["age"] == 42
        assert p["occupation"] == "farmer"
        assert p["state"] == "Andhra Pradesh"

    def test_unknown_session_returns_404(self):
        r = client.get("/api/profile/00000000-0000-0000-0000-000000000000")
        assert r.status_code == 404

    def test_profile_completeness_returned(self):
        sid = create_session()
        patch_profile(sid, {"age": 30, "gender": "female", "state": "Kerala",
                            "caste": "general", "annual_income": 300000})
        r = client.get(f"/api/profile/{sid}")
        comp = r.json()["completeness"]
        assert comp["core_percent"] > 0.0
        assert "age" in comp["filled"]

    def test_delete_removes_from_supabase(self):
        from backend.db.supabase import get_client
        sid = create_session()
        r = client.delete(f"/api/profile/{sid}")
        assert r.status_code == 204
        res = (
            get_client()
            .table("interview_sessions")
            .select("session_id")
            .eq("session_id", sid)
            .execute()
        )
        assert not res.data, "Session should be deleted from Supabase"


# ---------------------------------------------------------------------------
# 4. Retrieve schemes from Supabase
# ---------------------------------------------------------------------------

class TestRetrieveSchemes:

    def test_all_schemes_returns_at_least_14(self):
        # After full-dataset ingestion there will be 3397 schemes.
        # We require at least the original 14 curated ones to be present.
        all_schemes.cache_clear()
        schemes = all_schemes()
        assert len(schemes) >= 14

    def test_all_schemes_returns_full_dataset(self):
        # After running scripts/ingest_all.py, expect all 3397 unique schemes.
        all_schemes.cache_clear()
        schemes = all_schemes()
        assert len(schemes) == 3397, (
            f"Expected 3397 schemes after full ingestion, got {len(schemes)}. "
            "Run: python -m scripts.ingest_all"
        )

    def test_curated_scheme_ids_present(self):
        all_schemes.cache_clear()
        ids = {s.scheme_id for s in all_schemes()}
        curated = {
            "nmmss", "post-st", "pm-daksh", "sys", "pmay-g", "daay",
            "ab-pmjay", "gms", "dayalu", "subhadra", "wbrupashree",
            "mssc", "dalit-bandhu", "ysrrb",
        }
        assert curated.issubset(ids), f"Missing curated schemes: {curated - ids}"

    def test_eligibility_rules_loaded(self):
        all_schemes.cache_clear()
        schemes = {s.scheme_id: s for s in all_schemes()}
        # nmmss has max_annual_income=350000
        assert schemes["nmmss"].eligibility_rules.max_annual_income == 350000
        # mssc has gender=["female"]
        assert schemes["mssc"].eligibility_rules.gender == ["female"]
        # ysrrb has states=["Andhra Pradesh"]
        assert schemes["ysrrb"].eligibility_rules.states == ["Andhra Pradesh"]

    def test_scheme_names_not_empty(self):
        all_schemes.cache_clear()
        for s in all_schemes():
            assert s.scheme_name, f"{s.scheme_id} has empty scheme_name"

    def test_benefit_text_not_empty(self):
        all_schemes.cache_clear()
        for s in all_schemes():
            assert s.benefit, f"{s.scheme_id} has empty benefit"


# ---------------------------------------------------------------------------
# 5. Run /api/match end-to-end
# ---------------------------------------------------------------------------

class TestMatchEndToEnd:

    def test_match_returns_200(self):
        all_schemes.cache_clear()
        sid = create_session()
        r = client.post("/api/match", json={"session_id": sid})
        assert r.status_code == 200

    def test_match_evaluates_all_schemes(self):
        all_schemes.cache_clear()
        sid = create_session()
        data = match(sid)
        # After full ingestion this equals the total unique scheme count
        assert data["total_schemes"] >= 14

    def test_match_groups_sum_to_total(self):
        all_schemes.cache_clear()
        sid = create_session()
        data = match(sid)
        total = (
            len(data["eligible"])
            + len(data["near_miss"])
            + len(data["insufficient_information"])
            + len(data["ineligible"])
        )
        assert total == data["total_schemes"]

    def test_match_response_has_explanation(self):
        all_schemes.cache_clear()
        sid = create_session()
        patch_profile(sid, {"gender": "female"})
        data = match(sid)
        for group in ("eligible", "near_miss", "insufficient_information", "ineligible"):
            for scheme in data[group]:
                assert "explanation" in scheme


# ---------------------------------------------------------------------------
# 6. Verify all 14 schemes are evaluated correctly
# ---------------------------------------------------------------------------

class TestSchemeEvaluationCorrectness:
    """
    Profiles chosen so that the verdict for each named scheme is known.
    The rule engine is purely deterministic — results must match expected verdicts.
    """

    def _fill_and_match(self, fields: dict) -> dict:
        all_schemes.cache_clear()
        sid = create_session()
        if fields:
            patch_profile(sid, fields)
        return match(sid)

    def _find(self, data: dict, scheme_id: str) -> dict:
        for group in ("eligible", "near_miss", "insufficient_information", "ineligible"):
            for s in data[group]:
                if s["scheme_id"] == scheme_id:
                    return s
        raise AssertionError(f"{scheme_id} not found")

    def test_ysrrb_eligible_for_ap_farmer(self):
        data = self._fill_and_match({"state": "Andhra Pradesh", "occupation": "farmer"})
        assert self._find(data, "ysrrb")["verdict"] == "eligible"

    def test_ysrrb_ineligible_wrong_state(self):
        data = self._fill_and_match({"state": "Maharashtra", "occupation": "farmer"})
        assert self._find(data, "ysrrb")["verdict"] == "ineligible"

    def test_mssc_eligible_female(self):
        data = self._fill_and_match({"gender": "female"})
        assert self._find(data, "mssc")["verdict"] == "eligible"

    def test_mssc_ineligible_male(self):
        data = self._fill_and_match({"gender": "male"})
        assert self._find(data, "mssc")["verdict"] == "ineligible"

    def test_ab_pmjay_always_eligible(self):
        data = self._fill_and_match({})
        assert self._find(data, "ab-pmjay")["verdict"] == "eligible"

    def test_pmay_g_eligible_rural(self):
        data = self._fill_and_match({"domicile": "rural"})
        assert self._find(data, "pmay-g")["verdict"] == "eligible"

    def test_pmay_g_ineligible_urban(self):
        data = self._fill_and_match({"domicile": "urban"})
        assert self._find(data, "pmay-g")["verdict"] == "ineligible"

    def test_post_st_eligible_st_low_income(self):
        data = self._fill_and_match({"caste": "ST", "annual_income": 150000})
        assert self._find(data, "post-st")["verdict"] == "eligible"

    def test_post_st_ineligible_wrong_caste(self):
        data = self._fill_and_match({"caste": "OBC", "annual_income": 150000})
        assert self._find(data, "post-st")["verdict"] == "ineligible"

    def test_sys_near_miss_age_36(self):
        data = self._fill_and_match({"state": "Haryana", "age": 36, "annual_income": 200000})
        assert self._find(data, "sys")["verdict"] == "near_miss"

    def test_sys_ineligible_age_38(self):
        data = self._fill_and_match({"state": "Haryana", "age": 38, "annual_income": 200000})
        assert self._find(data, "sys")["verdict"] == "ineligible"

    def test_nmmss_near_miss_income_10pct_over(self):
        data = self._fill_and_match({"annual_income": 385000})
        assert self._find(data, "nmmss")["verdict"] == "near_miss"

    def test_subhadra_eligible(self):
        data = self._fill_and_match({
            "state": "Odisha", "gender": "female",
            "age": 30, "annual_income": 200000,
        })
        assert self._find(data, "subhadra")["verdict"] == "eligible"

    def test_dalit_bandhu_eligible(self):
        data = self._fill_and_match({
            "state": "Telangana", "caste": "SC",
            "age": 35, "annual_income": 200000,
        })
        assert self._find(data, "dalit-bandhu")["verdict"] == "eligible"

    def test_each_scheme_appears_exactly_once(self):
        data = self._fill_and_match({"gender": "female", "state": "Maharashtra"})
        seen: set[str] = set()
        for group in ("eligible", "near_miss", "insufficient_information", "ineligible"):
            for s in data[group]:
                assert s["scheme_id"] not in seen, f"{s['scheme_id']} in multiple groups"
                seen.add(s["scheme_id"])
        assert len(seen) == data["total_schemes"]
