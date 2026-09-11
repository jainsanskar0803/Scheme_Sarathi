"""
Tests for the adaptive AI interview endpoint POST /api/chat.

The LLM extractor is always mocked — these tests verify the routing,
profile merging, completeness tracking, next-question logic, and
language detection without making real Anthropic API calls.
"""
from __future__ import annotations

import sys
from pathlib import Path
from unittest.mock import patch

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

import pytest
from fastapi.testclient import TestClient
from backend.main import app

client = TestClient(app)

EXTRACTOR = "backend.routes.chat.extract_profile_fields"


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------

def create_session() -> str:
    r = client.post("/api/profile")
    assert r.status_code == 201
    return r.json()["session_id"]


def chat(sid: str, message: str, extracted: dict) -> dict:
    with patch(EXTRACTOR, return_value=extracted):
        r = client.post("/api/chat", json={"session_id": sid, "message": message})
    assert r.status_code == 200, r.text
    return r.json()


# ---------------------------------------------------------------------------
# Basic extraction → profile update flow
# ---------------------------------------------------------------------------

class TestChatBasic:

    def test_returns_200(self):
        sid = create_session()
        with patch(EXTRACTOR, return_value={"age": 30}):
            r = client.post("/api/chat", json={"session_id": sid, "message": "I am 30"})
        assert r.status_code == 200

    def test_response_has_required_keys(self):
        sid = create_session()
        data = chat(sid, "I am 30", {"age": 30})
        for key in ("session_id", "extracted", "profile", "completeness", "next_question", "language"):
            assert key in data

    def test_extracted_reflects_llm_output(self):
        sid = create_session()
        extracted = {"age": 42, "occupation": "farmer", "state": "Maharashtra", "annual_income": 180000}
        data = chat(sid, "I am 42, a farmer from Maharashtra and earn around 1.8 lakh per year.", extracted)
        assert data["extracted"] == extracted

    def test_profile_updated_with_extracted_fields(self):
        sid = create_session()
        data = chat(sid, "I am 42", {"age": 42})
        assert data["profile"]["age"] == 42

    def test_unknown_session_returns_404(self):
        with patch(EXTRACTOR, return_value={"age": 30}):
            r = client.post("/api/chat", json={"session_id": "ghost-999", "message": "hello"})
        assert r.status_code == 404

    def test_session_id_echoed_in_response(self):
        sid = create_session()
        data = chat(sid, "I am 30", {"age": 30})
        assert data["session_id"] == sid


# ---------------------------------------------------------------------------
# Multi-field extraction (the key demo scenario)
# ---------------------------------------------------------------------------

class TestMultiFieldExtraction:

    def test_four_fields_in_one_message(self):
        sid = create_session()
        extracted = {
            "age": 42,
            "occupation": "farmer",
            "state": "Maharashtra",
            "annual_income": 180000,
        }
        data = chat(sid, "I am 42, a farmer from Maharashtra and earn around 1.8 lakh per year.", extracted)
        p = data["profile"]
        assert p["age"] == 42
        assert p["occupation"] == "farmer"
        assert p["state"] == "Maharashtra"
        assert p["annual_income"] == 180000

    def test_occupation_farmer_sets_is_farmer_flag(self):
        sid = create_session()
        data = chat(sid, "I am a farmer", {"occupation": "farmer"})
        assert data["profile"]["is_farmer"] is True

    def test_occupation_student_sets_is_student_flag(self):
        sid = create_session()
        data = chat(sid, "I am a student", {"occupation": "student"})
        assert data["profile"]["is_student"] is True

    def test_income_in_lakh_stored_as_inr(self):
        sid = create_session()
        data = chat(sid, "I earn 1.8 lakh", {"annual_income": 180000})
        assert data["profile"]["annual_income"] == 180000

    def test_all_core_fields_in_one_shot(self):
        sid = create_session()
        extracted = {
            "age": 35, "gender": "female", "state": "Kerala",
            "caste": "OBC", "annual_income": 200000, "occupation": "farmer",
            "domicile": "rural", "is_disabled": False, "has_bpl_card": True,
            "marital_status": "married",
        }
        data = chat(sid, "...", extracted)
        assert data["completeness"]["core_percent"] == 1.0
        assert data["completeness"]["missing_core"] == []


# ---------------------------------------------------------------------------
# Incremental multi-turn conversation
# ---------------------------------------------------------------------------

class TestMultiTurn:

    def test_second_turn_preserves_first_turn_fields(self):
        sid = create_session()
        chat(sid, "I am 30", {"age": 30})
        data = chat(sid, "I live in UP", {"state": "Uttar Pradesh"})
        assert data["profile"]["age"] == 30
        assert data["profile"]["state"] == "Uttar Pradesh"

    def test_later_turn_overwrites_earlier_value(self):
        sid = create_session()
        chat(sid, "I am 30", {"age": 30})
        data = chat(sid, "Actually I am 31", {"age": 31})
        assert data["profile"]["age"] == 31

    def test_completeness_grows_across_turns(self):
        sid = create_session()
        d1 = chat(sid, "I am 30", {"age": 30})
        d2 = chat(sid, "I am female", {"gender": "female"})
        assert d2["completeness"]["core_percent"] > d1["completeness"]["core_percent"]

    def test_five_turn_conversation(self):
        sid = create_session()
        turns = [
            ("I am 28", {"age": 28}),
            ("I am from Rajasthan", {"state": "Rajasthan"}),
            ("I am OBC category", {"caste": "OBC"}),
            ("My income is 1.5 lakh", {"annual_income": 150000}),
            ("I am a farmer", {"occupation": "farmer", "is_farmer": True}),
        ]
        for msg, extracted in turns:
            chat(sid, msg, extracted)
        r = client.get(f"/api/profile/{sid}")
        p = r.json()["profile"]
        assert p["age"] == 28
        assert p["state"] == "Rajasthan"
        assert p["caste"] == "OBC"
        assert p["annual_income"] == 150000
        assert p["occupation"] == "farmer"


# ---------------------------------------------------------------------------
# Language detection
# ---------------------------------------------------------------------------

class TestLanguageDetection:

    def test_english_message_returns_en(self):
        sid = create_session()
        data = chat(sid, "I am 30 years old", {"age": 30})
        assert data["language"] == "en"

    def test_hindi_message_returns_hi(self):
        sid = create_session()
        data = chat(sid, "मैं 35 साल का किसान हूं", {"age": 35, "occupation": "farmer"})
        assert data["language"] == "hi"

    def test_hinglish_with_devanagari_returns_hi(self):
        sid = create_session()
        data = chat(sid, "I am farmer, मेरी उम्र 40 है", {"age": 40})
        assert data["language"] == "hi"

    def test_pure_english_returns_en(self):
        sid = create_session()
        data = chat(sid, "Maharashtra farmer 42 years 1.8 lakh income", {"age": 42})
        assert data["language"] == "en"


# ---------------------------------------------------------------------------
# Next-question logic
# ---------------------------------------------------------------------------

class TestNextQuestion:

    def test_fresh_profile_asks_state_first(self):
        sid = create_session()
        data = chat(sid, "hello", {})
        # state is the first priority field
        assert data["next_question"] is not None
        assert "state" in data["next_question"].lower() or "राज्य" in (data["next_question"] or "")

    def test_after_state_asks_age(self):
        sid = create_session()
        data = chat(sid, "I am from Maharashtra", {"state": "Maharashtra"})
        q = data["next_question"] or ""
        # English: "How old are you?", Hindi: "आपकी उम्र क्या है?"
        assert "old" in q.lower() or "उम्र" in q

    def test_next_question_is_none_when_all_fields_filled(self):
        sid = create_session()
        # Fill all priority fields
        all_fields = {
            "age": 30, "gender": "female", "state": "Kerala", "district": "Ernakulam",
            "domicile": "urban", "caste": "general", "annual_income": 300000,
            "occupation": "student", "marital_status": "single",
            "num_children": 0, "is_disabled": False, "has_bpl_card": False,
            "has_electricity_connection": True, "owns_house": True,
            "owns_vehicle": "two_wheeler", "land_holding_acres": 0.0,
            "is_student": True, "is_farmer": False, "is_artisan": False,
            "is_business_owner": False,
        }
        data = chat(sid, "...", all_fields)
        assert data["next_question"] is None

    def test_hindi_question_when_hindi_message(self):
        sid = create_session()
        data = chat(sid, "मैं महाराष्ट्र से हूं", {"state": "Maharashtra"})
        # Should ask next question in Hindi
        q = data["next_question"] or ""
        assert any("ऀ" <= ch <= "ॿ" for ch in q), \
            f"Expected Hindi question, got: {q!r}"

    def test_farmer_occupation_skips_is_farmer_question(self):
        sid = create_session()
        # After setting occupation=farmer, is_farmer is implied — should not be asked
        chat(sid, "I am a farmer", {"occupation": "farmer"})
        # Collect all future questions
        questions = []
        for _ in range(10):
            data = chat(sid, "", {})
            q = data["next_question"]
            if q is None:
                break
            questions.append(q)
        assert not any("farmer" in q.lower() for q in questions)

    def test_skips_already_filled_fields(self):
        sid = create_session()
        chat(sid, "I am 30", {"age": 30})
        data = chat(sid, "", {})
        q = data["next_question"] or ""
        assert "age" not in q.lower()


# ---------------------------------------------------------------------------
# Error handling
# ---------------------------------------------------------------------------

class TestErrorHandling:

    def test_llm_failure_returns_502(self):
        sid = create_session()
        with patch(EXTRACTOR, side_effect=RuntimeError("API down")):
            r = client.post("/api/chat", json={"session_id": sid, "message": "hello"})
        assert r.status_code == 502

    def test_llm_json_error_returns_502(self):
        import json
        sid = create_session()
        with patch(EXTRACTOR, side_effect=json.JSONDecodeError("bad", "", 0)):
            r = client.post("/api/chat", json={"session_id": sid, "message": "hello"})
        assert r.status_code == 502

    def test_invalid_extracted_field_returns_422(self):
        sid = create_session()
        # LLM returns an invalid value for a validated field
        with patch(EXTRACTOR, return_value={"age": 999}):
            r = client.post("/api/chat", json={"session_id": sid, "message": "I am 999"})
        assert r.status_code == 422

    def test_invalid_caste_returns_422(self):
        sid = create_session()
        with patch(EXTRACTOR, return_value={"caste": "xyz"}):
            r = client.post("/api/chat", json={"session_id": sid, "message": "I am xyz caste"})
        assert r.status_code == 422

    def test_empty_extraction_is_valid(self):
        """LLM confident about nothing — that's fine, no profile change."""
        sid = create_session()
        data = chat(sid, "I live somewhere in India", {})
        assert data["extracted"] == {}
        assert all(v is None for v in data["profile"].values())

    def test_missing_message_field_400(self):
        sid = create_session()
        r = client.post("/api/chat", json={"session_id": sid})
        assert r.status_code == 422  # FastAPI request validation

    def test_missing_session_id_field_400(self):
        r = client.post("/api/chat", json={"message": "hello"})
        assert r.status_code == 422


# ---------------------------------------------------------------------------
# Completeness tracking via chat
# ---------------------------------------------------------------------------

class TestCompletenessViaChat:

    def test_core_percent_starts_at_zero(self):
        sid = create_session()
        data = chat(sid, "hello", {})
        assert data["completeness"]["core_percent"] == 0.0

    def test_filling_one_core_field_increases_percent(self):
        sid = create_session()
        data = chat(sid, "I am 30", {"age": 30})
        assert data["completeness"]["core_percent"] > 0.0

    def test_filled_list_contains_extracted_field(self):
        sid = create_session()
        data = chat(sid, "I am 30", {"age": 30})
        assert "age" in data["completeness"]["filled"]

    def test_missing_core_shrinks_after_fill(self):
        sid = create_session()
        before = set(chat(sid, "", {})["completeness"]["missing_core"])
        data = chat(sid, "I am 30", {"age": 30})
        after = set(data["completeness"]["missing_core"])
        assert "age" not in after
        assert len(after) == len(before) - 1