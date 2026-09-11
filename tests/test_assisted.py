"""
Tests for the Assisted Mode endpoints under /api/assisted/*.
All storage is in-memory — no Supabase calls.
"""
from __future__ import annotations

import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

import pytest
from fastapi.testclient import TestClient

from backend.main import app

client = TestClient(app)


# ─── helpers ──────────────────────────────────────────────────────────────────


def _create(name="Ramesh Kumar", worker="worker1", phone=None, notes=None):
    body = {"worker_id": worker, "citizen_name": name}
    if phone:
        body["citizen_phone"] = phone
    if notes:
        body["notes"] = notes
    return client.post("/api/assisted/citizens", json=body)


# ─── POST /api/assisted/citizens ─────────────────────────────────────────────


class TestCreateCitizen:

    def test_creates_session_and_returns_metadata(self):
        r = _create("Sita Devi", "worker_a", phone="9999900000")
        assert r.status_code == 201
        d = r.json()
        assert d["citizen_name"] == "Sita Devi"
        assert d["worker_id"] == "worker_a"
        assert d["citizen_phone"] == "9999900000"
        assert "session_id" in d
        assert len(d["session_id"]) == 36  # UUID

    def test_optional_fields_nullable(self):
        r = _create("Arjun", "w1")
        assert r.status_code == 201
        d = r.json()
        assert d["citizen_phone"] is None
        assert d["notes"] is None

    def test_blank_name_returns_422(self):
        r = client.post("/api/assisted/citizens", json={"worker_id": "w1", "citizen_name": "  "})
        assert r.status_code == 422

    def test_blank_worker_id_returns_422(self):
        r = client.post("/api/assisted/citizens", json={"worker_id": "", "citizen_name": "Ramesh"})
        assert r.status_code == 422

    def test_missing_required_fields_422(self):
        r = client.post("/api/assisted/citizens", json={"citizen_name": "Only Name"})
        assert r.status_code == 422

    def test_each_create_unique_session(self):
        r1 = _create("Alice", "w2")
        r2 = _create("Bob", "w2")
        assert r1.json()["session_id"] != r2.json()["session_id"]

    def test_notes_stored(self):
        r = _create("Meena", "w3", notes="BPL household, near Anganwadi")
        assert r.json()["notes"] == "BPL household, near Anganwadi"


# ─── GET /api/assisted/citizens ──────────────────────────────────────────────


class TestListCitizens:

    def test_returns_only_worker_citizens(self):
        _create("Ram", "list_worker")
        _create("Shyam", "list_worker")
        _create("Other", "other_worker")
        r = client.get("/api/assisted/citizens", params={"worker_id": "list_worker"})
        assert r.status_code == 200
        names = {c["citizen_name"] for c in r.json()}
        assert "Ram" in names
        assert "Shyam" in names
        assert "Other" not in names

    def test_empty_list_for_unknown_worker(self):
        r = client.get("/api/assisted/citizens", params={"worker_id": "ghost_worker_xyz"})
        assert r.status_code == 200
        assert r.json() == []

    def test_missing_worker_id_400(self):
        r = client.get("/api/assisted/citizens")
        assert r.status_code in (400, 422)

    def test_blank_worker_id_400(self):
        r = client.get("/api/assisted/citizens", params={"worker_id": "  "})
        assert r.status_code == 400


# ─── GET /api/assisted/citizens/{session_id} ─────────────────────────────────


class TestGetCitizen:

    def test_returns_correct_citizen(self):
        created = _create("Geeta", "wg").json()
        sid = created["session_id"]
        r = client.get(f"/api/assisted/citizens/{sid}")
        assert r.status_code == 200
        assert r.json()["citizen_name"] == "Geeta"

    def test_404_for_unknown_session(self):
        r = client.get("/api/assisted/citizens/nonexistent-session-id")
        assert r.status_code == 404


# ─── PUT /api/assisted/citizens/{session_id}/followup/{scheme_id} ─────────────


class TestSetFollowup:

    def _session(self):
        return _create("TestFollowup", "fw").json()["session_id"]

    def test_creates_followup(self):
        sid = self._session()
        r = client.put(
            f"/api/assisted/citizens/{sid}/followup/scheme_001",
            json={"scheme_name": "PM Kisan", "status": "will_apply"},
        )
        assert r.status_code == 200
        d = r.json()
        assert d["scheme_id"] == "scheme_001"
        assert d["scheme_name"] == "PM Kisan"
        assert d["status"] == "will_apply"
        assert d["session_id"] == sid

    def test_updates_existing_followup(self):
        sid = self._session()
        client.put(
            f"/api/assisted/citizens/{sid}/followup/scheme_002",
            json={"scheme_name": "Ujjwala", "status": "will_apply"},
        )
        r = client.put(
            f"/api/assisted/citizens/{sid}/followup/scheme_002",
            json={"scheme_name": "Ujjwala", "status": "applied", "notes": "Submitted at CSC"},
        )
        assert r.status_code == 200
        d = r.json()
        assert d["status"] == "applied"
        assert d["notes"] == "Submitted at CSC"

    def test_all_valid_statuses_accepted(self):
        sid = self._session()
        for i, status in enumerate(
            ["will_apply", "applied", "received", "rejected", "not_applicable"]
        ):
            r = client.put(
                f"/api/assisted/citizens/{sid}/followup/s{i}",
                json={"scheme_name": "Test", "status": status},
            )
            assert r.status_code == 200, f"failed for status={status}"

    def test_invalid_status_422(self):
        sid = self._session()
        r = client.put(
            f"/api/assisted/citizens/{sid}/followup/scheme_bad",
            json={"scheme_name": "X", "status": "pending"},
        )
        assert r.status_code == 422

    def test_unknown_session_404(self):
        r = client.put(
            "/api/assisted/citizens/ghost_session/followup/scheme_x",
            json={"scheme_name": "X", "status": "will_apply"},
        )
        assert r.status_code == 404


# ─── GET /api/assisted/citizens/{session_id}/followup ─────────────────────────


class TestListFollowups:

    def _session(self):
        return _create("FUListTest", "flu").json()["session_id"]

    def test_lists_all_followups(self):
        sid = self._session()
        client.put(
            f"/api/assisted/citizens/{sid}/followup/s1",
            json={"scheme_name": "Scheme A", "status": "will_apply"},
        )
        client.put(
            f"/api/assisted/citizens/{sid}/followup/s2",
            json={"scheme_name": "Scheme B", "status": "applied"},
        )
        r = client.get(f"/api/assisted/citizens/{sid}/followup")
        assert r.status_code == 200
        ids = {f["scheme_id"] for f in r.json()}
        assert {"s1", "s2"}.issubset(ids)

    def test_empty_list_before_any_followup(self):
        sid = self._session()
        r = client.get(f"/api/assisted/citizens/{sid}/followup")
        assert r.status_code == 200
        assert r.json() == []

    def test_404_for_unknown_session(self):
        r = client.get("/api/assisted/citizens/no_such_session/followup")
        assert r.status_code == 404


# ─── GET /api/assisted/citizens/{session_id}/followup/{scheme_id} ─────────────


class TestGetFollowup:

    def _session(self):
        return _create("FUSingleTest", "fus").json()["session_id"]

    def test_returns_followup(self):
        sid = self._session()
        client.put(
            f"/api/assisted/citizens/{sid}/followup/pm_kisan",
            json={"scheme_name": "PM Kisan", "status": "received", "notes": "Got ₹4000"},
        )
        r = client.get(f"/api/assisted/citizens/{sid}/followup/pm_kisan")
        assert r.status_code == 200
        d = r.json()
        assert d["status"] == "received"
        assert d["notes"] == "Got ₹4000"

    def test_404_if_followup_not_set(self):
        sid = self._session()
        r = client.get(f"/api/assisted/citizens/{sid}/followup/nonexistent_scheme")
        assert r.status_code == 404

    def test_404_if_session_unknown(self):
        r = client.get("/api/assisted/citizens/ghost/followup/any")
        assert r.status_code == 404
