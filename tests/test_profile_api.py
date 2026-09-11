"""
Tests for the citizen profile API.

Uses FastAPI TestClient — no running server needed.
"""
from __future__ import annotations

import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

import pytest
from fastapi.testclient import TestClient
from backend.main import app

client = TestClient(app)


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------

def create_session() -> str:
    r = client.post("/api/profile")
    assert r.status_code == 201
    return r.json()["session_id"]


# ---------------------------------------------------------------------------
# Health check
# ---------------------------------------------------------------------------

def test_health():
    r = client.get("/health")
    assert r.status_code == 200
    assert r.json() == {"status": "ok"}


# ---------------------------------------------------------------------------
# POST /api/profile — create session
# ---------------------------------------------------------------------------

class TestCreateProfile:
    def test_returns_201(self):
        r = client.post("/api/profile")
        assert r.status_code == 201

    def test_response_has_session_id(self):
        r = client.post("/api/profile")
        assert "session_id" in r.json()

    def test_response_has_profile(self):
        r = client.post("/api/profile")
        assert "profile" in r.json()

    def test_response_has_completeness(self):
        r = client.post("/api/profile")
        assert "completeness" in r.json()

    def test_new_profile_all_fields_none(self):
        r = client.post("/api/profile")
        profile = r.json()["profile"]
        assert all(v is None for v in profile.values())

    def test_new_profile_zero_core_percent(self):
        r = client.post("/api/profile")
        assert r.json()["completeness"]["core_percent"] == 0.0

    def test_all_core_fields_in_missing(self):
        r = client.post("/api/profile")
        missing = r.json()["completeness"]["missing_core"]
        for field in ["age", "gender", "state", "caste", "annual_income"]:
            assert field in missing

    def test_each_session_has_unique_id(self):
        ids = {client.post("/api/profile").json()["session_id"] for _ in range(5)}
        assert len(ids) == 5


# ---------------------------------------------------------------------------
# GET /api/profile/{session_id}
# ---------------------------------------------------------------------------

class TestGetProfile:
    def test_get_existing_session(self):
        sid = create_session()
        r = client.get(f"/api/profile/{sid}")
        assert r.status_code == 200

    def test_get_unknown_session_404(self):
        r = client.get("/api/profile/does-not-exist")
        assert r.status_code == 404

    def test_get_returns_same_session_id(self):
        sid = create_session()
        r = client.get(f"/api/profile/{sid}")
        assert r.json()["session_id"] == sid


# ---------------------------------------------------------------------------
# PATCH /api/profile/{session_id} — incremental updates
# ---------------------------------------------------------------------------

class TestUpdateProfile:

    def test_patch_single_field(self):
        sid = create_session()
        r = client.patch(f"/api/profile/{sid}", json={"age": 30})
        assert r.status_code == 200
        assert r.json()["profile"]["age"] == 30

    def test_patch_multiple_fields(self):
        sid = create_session()
        r = client.patch(f"/api/profile/{sid}", json={
            "age": 25, "gender": "female", "state": "Rajasthan"
        })
        p = r.json()["profile"]
        assert p["age"] == 25
        assert p["gender"] == "female"
        assert p["state"] == "Rajasthan"

    def test_patch_preserves_previous_fields(self):
        sid = create_session()
        client.patch(f"/api/profile/{sid}", json={"age": 30})
        client.patch(f"/api/profile/{sid}", json={"gender": "male"})
        r = client.get(f"/api/profile/{sid}")
        p = r.json()["profile"]
        assert p["age"] == 30       # preserved
        assert p["gender"] == "male"

    def test_patch_all_fields_sequentially(self):
        sid = create_session()
        fields = [
            {"age": 28},
            {"gender": "female"},
            {"state": "Maharashtra"},
            {"district": "Pune"},
            {"domicile": "urban"},
            {"caste": "OBC"},
            {"annual_income": 250000},
            {"occupation": "farmer"},
            {"is_farmer": True},
            {"is_student": False},
            {"is_artisan": False},
            {"is_business_owner": False},
            {"land_holding_acres": 2.5},
            {"marital_status": "married"},
            {"num_children": 2},
            {"is_disabled": False},
            {"has_bpl_card": False},
            {"has_electricity_connection": True},
            {"owns_house": True},
            {"owns_vehicle": "two_wheeler"},
        ]
        for payload in fields:
            r = client.patch(f"/api/profile/{sid}", json=payload)
            assert r.status_code == 200

        r = client.get(f"/api/profile/{sid}")
        p = r.json()["profile"]
        assert p["age"] == 28
        assert p["gender"] == "female"
        assert p["land_holding_acres"] == 2.5
        assert p["num_children"] == 2
        assert p["has_electricity_connection"] is True
        assert p["owns_house"] is True
        assert p["owns_vehicle"] == "two_wheeler"

    def test_patch_unknown_session_404(self):
        r = client.patch("/api/profile/ghost", json={"age": 25})
        assert r.status_code == 404

    def test_patch_invalid_age_422(self):
        sid = create_session()
        r = client.patch(f"/api/profile/{sid}", json={"age": 999})
        assert r.status_code == 422

    def test_patch_invalid_age_negative_422(self):
        sid = create_session()
        r = client.patch(f"/api/profile/{sid}", json={"age": -5})
        assert r.status_code == 422

    def test_patch_invalid_gender_422(self):
        sid = create_session()
        r = client.patch(f"/api/profile/{sid}", json={"gender": "alien"})
        assert r.status_code == 422

    def test_patch_invalid_caste_422(self):
        sid = create_session()
        r = client.patch(f"/api/profile/{sid}", json={"caste": "xyz"})
        assert r.status_code == 422

    def test_patch_invalid_vehicle_422(self):
        sid = create_session()
        r = client.patch(f"/api/profile/{sid}", json={"owns_vehicle": "tank"})
        assert r.status_code == 422

    def test_patch_invalid_income_422(self):
        sid = create_session()
        r = client.patch(f"/api/profile/{sid}", json={"annual_income": -1000})
        assert r.status_code == 422

    def test_patch_invalid_land_422(self):
        sid = create_session()
        r = client.patch(f"/api/profile/{sid}", json={"land_holding_acres": -1.0})
        assert r.status_code == 422


# ---------------------------------------------------------------------------
# Completeness tracking
# ---------------------------------------------------------------------------

class TestCompleteness:

    def test_core_percent_increases_as_fields_filled(self):
        sid = create_session()
        initial = client.get(f"/api/profile/{sid}").json()["completeness"]["core_percent"]

        client.patch(f"/api/profile/{sid}", json={"age": 30})
        after_one = client.get(f"/api/profile/{sid}").json()["completeness"]["core_percent"]

        assert after_one > initial

    def test_filled_list_grows(self):
        sid = create_session()
        client.patch(f"/api/profile/{sid}", json={"age": 30, "gender": "male"})
        r = client.get(f"/api/profile/{sid}")
        filled = r.json()["completeness"]["filled"]
        assert "age" in filled
        assert "gender" in filled

    def test_missing_core_shrinks(self):
        sid = create_session()
        before = set(client.get(f"/api/profile/{sid}").json()["completeness"]["missing_core"])
        client.patch(f"/api/profile/{sid}", json={"age": 30})
        after = set(client.get(f"/api/profile/{sid}").json()["completeness"]["missing_core"])
        assert "age" not in after
        assert len(after) == len(before) - 1

    def test_full_core_gives_100_percent(self):
        sid = create_session()
        client.patch(f"/api/profile/{sid}", json={
            "age": 30, "gender": "female", "state": "Kerala",
            "caste": "general", "annual_income": 300000,
            "occupation": "student", "domicile": "urban",
            "is_disabled": False, "has_bpl_card": False,
            "marital_status": "single",
        })
        r = client.get(f"/api/profile/{sid}")
        assert r.json()["completeness"]["core_percent"] == 1.0
        assert r.json()["completeness"]["missing_core"] == []

    def test_enrichment_fields_tracked_separately(self):
        sid = create_session()
        client.patch(f"/api/profile/{sid}", json={"district": "Pune"})
        r = client.get(f"/api/profile/{sid}")
        comp = r.json()["completeness"]
        assert "district" not in comp["missing_enrichment"]


# ---------------------------------------------------------------------------
# Occupation ↔ flag sync
# ---------------------------------------------------------------------------

class TestOccupationSync:

    def test_setting_occupation_farmer_sets_is_farmer(self):
        sid = create_session()
        client.patch(f"/api/profile/{sid}", json={"occupation": "farmer"})
        r = client.get(f"/api/profile/{sid}")
        assert r.json()["profile"]["is_farmer"] is True

    def test_setting_is_farmer_sets_occupation(self):
        sid = create_session()
        client.patch(f"/api/profile/{sid}", json={"is_farmer": True})
        r = client.get(f"/api/profile/{sid}")
        assert r.json()["profile"]["occupation"] == "farmer"

    def test_setting_occupation_student_sets_is_student(self):
        sid = create_session()
        client.patch(f"/api/profile/{sid}", json={"occupation": "student"})
        r = client.get(f"/api/profile/{sid}")
        assert r.json()["profile"]["is_student"] is True

    def test_setting_is_artisan_sets_occupation(self):
        sid = create_session()
        client.patch(f"/api/profile/{sid}", json={"is_artisan": True})
        r = client.get(f"/api/profile/{sid}")
        assert r.json()["profile"]["occupation"] == "artisan"


# ---------------------------------------------------------------------------
# DELETE /api/profile/{session_id}
# ---------------------------------------------------------------------------

class TestDeleteProfile:

    def test_delete_returns_204(self):
        sid = create_session()
        r = client.delete(f"/api/profile/{sid}")
        assert r.status_code == 204

    def test_deleted_session_returns_404_on_get(self):
        sid = create_session()
        client.delete(f"/api/profile/{sid}")
        r = client.get(f"/api/profile/{sid}")
        assert r.status_code == 404

    def test_delete_unknown_session_404(self):
        r = client.delete("/api/profile/ghost-session")
        assert r.status_code == 404