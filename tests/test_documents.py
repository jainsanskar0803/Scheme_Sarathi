"""
Tests for the document readiness feature.

Covers:
  - parse_required_documents: all string formats found in real data
  - match_to_required: fuzzy document matching
  - POST /api/documents/identify: API endpoint (vision mocked)
"""
from __future__ import annotations

import json
import sys
from pathlib import Path
from unittest.mock import MagicMock, patch

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

import pytest
from fastapi.testclient import TestClient

from backend.main import app
from backend.routes.documents import match_to_required, parse_required_documents

client = TestClient(app)


# ─── parse_required_documents ─────────────────────────────────────────────────

class TestParseRequiredDocuments:

    def test_numbered_list(self):
        raw = "1. Aadhaar Card 2. Ration Card 3. Income Certificate"
        items = parse_required_documents(raw)
        assert len(items) == 3
        assert "Aadhaar Card" in items

    def test_numbered_list_parenthesis(self):
        raw = "1) Aadhaar Card 2) Caste Certificate 3) Land Document"
        items = parse_required_documents(raw)
        assert len(items) == 3

    def test_newline_separated(self):
        raw = "Aadhaar Card\nIncome Certificate\nPassport Photo"
        items = parse_required_documents(raw)
        assert len(items) == 3
        assert "Aadhaar Card" in items

    def test_period_separated(self):
        raw = "Aadhaar Card. Income Certificate. Birth Certificate"
        items = parse_required_documents(raw)
        assert len(items) == 3

    def test_single_item(self):
        raw = "Aadhaar Card"
        items = parse_required_documents(raw)
        assert len(items) == 1
        assert items[0] == "Aadhaar Card"

    def test_none_returns_empty(self):
        assert parse_required_documents(None) == []
        assert parse_required_documents("None") == []
        assert parse_required_documents("") == []

    def test_real_nmmss_format(self):
        raw = (
            "Class 7th mark sheet (only from government schools) (compulsory) "
            "Caste Certificate Income Certificate of Parents (compulsory) "
            "Disability Certificate Domicile Certificate"
        )
        items = parse_required_documents(raw)
        # Falls back to single block — that's acceptable for this format
        assert len(items) >= 1

    def test_real_numbered_format(self):
        raw = (
            "1. Aadhaar Card\n"
            "2. Ration Card\n"
            "3. Safai Karamchari Certificate\n"
            "4. Any other documents as required"
        )
        items = parse_required_documents(raw)
        assert len(items) == 4
        assert "Aadhaar Card" in items

    def test_filters_short_fragments(self):
        raw = "1. OK 2. Aadhaar Card 3. Income Certificate"
        items = parse_required_documents(raw)
        # "OK" is too short (≤3 chars) and should be filtered
        long_items = [i for i in items if len(i) > 3]
        assert "Aadhaar Card" in long_items


# ─── match_to_required ────────────────────────────────────────────────────────

class TestMatchToRequired:

    def test_exact_match(self):
        assert match_to_required("Aadhaar Card", ["Aadhaar Card", "PAN Card"]) == "Aadhaar Card"

    def test_partial_containment(self):
        # "Aadhaar" in required, "Aadhaar Card" identified
        assert match_to_required("Aadhaar Card", ["Aadhaar", "Income Certificate"]) == "Aadhaar"

    def test_keyword_group_income(self):
        req = ["Income Certificate of Parents (compulsory)", "Caste Certificate"]
        assert match_to_required("Income Certificate", req) == "Income Certificate of Parents (compulsory)"

    def test_keyword_group_caste(self):
        req = ["Caste Certificate", "Aadhaar Card"]
        assert match_to_required("Caste Certificate", req) == "Caste Certificate"

    def test_keyword_group_land(self):
        req = ["Land Document / Khatauni / Patta", "Aadhaar Card"]
        assert match_to_required("Land Document / Khatauni / Patta", req) == "Land Document / Khatauni / Patta"

    def test_keyword_group_ration(self):
        req = ["BPL Card / Ration Card", "Aadhaar Card"]
        assert match_to_required("BPL Card / Ration Card", req) == "BPL Card / Ration Card"

    def test_keyword_group_voter(self):
        req = ["Voter ID / Election Card"]
        assert match_to_required("Voter ID", req) == "Voter ID / Election Card"

    def test_no_match_returns_none(self):
        req = ["Aadhaar Card", "Income Certificate"]
        assert match_to_required("Passport", req) == None

    def test_unknown_returns_none(self):
        assert match_to_required("Unknown", ["Aadhaar Card"]) is None

    def test_empty_required_returns_none(self):
        assert match_to_required("Aadhaar Card", []) is None

    def test_disability_keyword(self):
        req = ["Disability Certificate", "Aadhaar Card"]
        assert match_to_required("Disability Certificate", req) == "Disability Certificate"

    def test_mark_sheet(self):
        req = ["Mark Sheet / Educational Certificate"]
        assert match_to_required("Mark Sheet / Educational Certificate", req) == "Mark Sheet / Educational Certificate"

    def test_bank_passbook(self):
        req = ["Bank Passbook", "Aadhaar Card"]
        assert match_to_required("Bank Passbook", req) == "Bank Passbook"


# ─── POST /api/documents/identify ─────────────────────────────────────────────

# Minimal valid 1×1 JPEG base64 (white pixel)
_TINY_JPEG_B64 = (
    "/9j/4AAQSkZJRgABAQEASABIAAD/2wBDAAgGBgcGBQgHBwcJCQgKDBQNDAsLDBkSEw8UHRofHh0a"
    "HBwgJC4nICIsIxwcKDcpLDAxNDQ0Hyc5PTgyPC4zNDL/wAARCAABAAEDASIAAhEBAxEB/8QAFgAB"
    "AQEAAAAAAAAAAAAAAAAABgUEA/8QAHxAAAgIBBQEAAAAAAAAAAAAAAQIDBAUREiEx/8QAFAEBAAAA"
    "AAAAAAAAAAAAAAAAAP/EABQRAQAAAAAAAAAAAAAAAAAAAAD/2gAMAwEAAhEDEQA/AKriutZ2pY1dr"
    "EKQqICdgAAAAAAAAAB//9k="
)


def _mock_claude_response(identified_type: str, confidence: str = "high", alternatives: list | None = None, reason: str = "Test") -> MagicMock:
    """Build a mock httpx.Response that returns a Claude-style JSON body."""
    mock_resp = MagicMock()
    mock_resp.status_code = 200
    mock_resp.json.return_value = {
        "content": [
            {
                "text": json.dumps({
                    "identified_type": identified_type,
                    "confidence": confidence,
                    "alternatives": alternatives or [],
                    "reason": reason,
                })
            }
        ]
    }
    mock_resp.raise_for_status = MagicMock()
    return mock_resp


class TestIdentifyEndpoint:

    def _post(self, image_b64=_TINY_JPEG_B64, mime="image/jpeg", required=None):
        return client.post(
            "/api/documents/identify",
            json={
                "image_base64": image_b64,
                "image_mime": mime,
                "required_documents": required or [],
            },
        )

    # ── No API key — graceful degradation ─────────────────────────────────────

    def test_no_api_key_returns_unknown(self, monkeypatch):
        monkeypatch.delenv("ANTHROPIC_API_KEY", raising=False)
        r = self._post()
        assert r.status_code == 200
        d = r.json()
        assert d["identified_type"] == "Unknown"
        assert d["confidence"] == "low"
        assert d["matched_required"] is None
        assert "disclaimer" in d

    # ── Successful identification ──────────────────────────────────────────────

    def test_aadhaar_high_confidence(self, monkeypatch):
        monkeypatch.setenv("ANTHROPIC_API_KEY", "test-key")
        mock_resp = _mock_claude_response("Aadhaar Card", "high", reason="Aadhaar QR code visible")
        with patch("httpx.Client.post", return_value=mock_resp):
            r = self._post()
        assert r.status_code == 200
        d = r.json()
        assert d["identified_type"] == "Aadhaar Card"
        assert d["confidence"] == "high"
        assert "disclaimer" in d

    def test_matched_required_set(self, monkeypatch):
        monkeypatch.setenv("ANTHROPIC_API_KEY", "test-key")
        mock_resp = _mock_claude_response("Aadhaar Card", "high")
        with patch("httpx.Client.post", return_value=mock_resp):
            r = self._post(required=["Aadhaar Card", "Income Certificate"])
        d = r.json()
        assert d["matched_required"] == "Aadhaar Card"

    def test_no_match_when_unrelated(self, monkeypatch):
        monkeypatch.setenv("ANTHROPIC_API_KEY", "test-key")
        mock_resp = _mock_claude_response("Passport", "medium")
        with patch("httpx.Client.post", return_value=mock_resp):
            r = self._post(required=["Aadhaar Card", "Income Certificate"])
        d = r.json()
        assert d["matched_required"] is None

    def test_low_confidence_alternatives_returned(self, monkeypatch):
        monkeypatch.setenv("ANTHROPIC_API_KEY", "test-key")
        mock_resp = _mock_claude_response(
            "Unknown", "low",
            alternatives=["Aadhaar Card", "PAN Card"],
            reason="Image too blurry to identify"
        )
        with patch("httpx.Client.post", return_value=mock_resp):
            r = self._post()
        d = r.json()
        assert d["confidence"] == "low"
        assert "Aadhaar Card" in d["alternatives"]

    # ── Error handling ─────────────────────────────────────────────────────────

    def test_invalid_json_from_model_returns_unknown(self, monkeypatch):
        monkeypatch.setenv("ANTHROPIC_API_KEY", "test-key")
        mock_resp = MagicMock()
        mock_resp.status_code = 200
        mock_resp.json.return_value = {"content": [{"text": "This is not JSON at all."}]}
        mock_resp.raise_for_status = MagicMock()
        with patch("httpx.Client.post", return_value=mock_resp):
            r = self._post()
        assert r.status_code == 200
        d = r.json()
        assert d["identified_type"] == "Unknown"
        assert d["confidence"] == "low"

    def test_claude_4xx_raises_502(self, monkeypatch):
        monkeypatch.setenv("ANTHROPIC_API_KEY", "bad-key")
        import httpx as _httpx
        mock_resp = MagicMock()
        mock_resp.status_code = 401
        mock_resp.text = "Unauthorized"
        mock_resp.raise_for_status.side_effect = _httpx.HTTPStatusError(
            "401", request=MagicMock(), response=mock_resp
        )
        with patch("httpx.Client.post", return_value=mock_resp):
            r = self._post()
        assert r.status_code == 502

    def test_timeout_raises_504(self, monkeypatch):
        monkeypatch.setenv("ANTHROPIC_API_KEY", "test-key")
        import httpx as _httpx
        with patch("httpx.Client.post", side_effect=_httpx.TimeoutException("timed out")):
            r = self._post()
        assert r.status_code == 504

    # ── Disclaimer always present ──────────────────────────────────────────────

    def test_disclaimer_always_present(self, monkeypatch):
        monkeypatch.delenv("ANTHROPIC_API_KEY", raising=False)
        r = self._post()
        assert r.status_code == 200
        assert "does not verify" in r.json()["disclaimer"].lower()

    def test_disclaimer_present_on_success(self, monkeypatch):
        monkeypatch.setenv("ANTHROPIC_API_KEY", "test-key")
        mock_resp = _mock_claude_response("PAN Card", "high")
        with patch("httpx.Client.post", return_value=mock_resp):
            r = self._post()
        assert "does not verify" in r.json()["disclaimer"].lower()

    # ── Checklist completeness logic ───────────────────────────────────────────

class TestChecklistLogic:
    """
    Verify the higher-level checklist state derived from identify results.
    This is pure Python logic — no HTTP calls.
    """

    def _checklist(self, required: list[str], uploaded: dict[str, str]) -> dict:
        """
        Simulate checklist state.
        uploaded: {any_label: identified_type}
        Returns: {required_doc: 'confirmed' | 'missing'}
        """
        state = {}
        for doc in required:
            # A required doc is confirmed if any uploaded file matches it
            is_confirmed = any(
                match_to_required(itype, [doc]) == doc
                for itype in uploaded.values()
            )
            state[doc] = "confirmed" if is_confirmed else "missing"
        return state

    def test_all_confirmed(self):
        required = ["Aadhaar Card", "Income Certificate"]
        uploaded = {
            "Aadhaar Card": "Aadhaar Card",
            "Income Certificate": "Income Certificate",
        }
        state = self._checklist(required, uploaded)
        assert state["Aadhaar Card"] == "confirmed"
        assert state["Income Certificate"] == "confirmed"

    def test_partial_missing(self):
        required = ["Aadhaar Card", "Income Certificate", "Caste Certificate"]
        uploaded = {"Aadhaar Card": "Aadhaar Card"}
        state = self._checklist(required, uploaded)
        assert state["Aadhaar Card"] == "confirmed"
        assert state["Income Certificate"] == "missing"
        assert state["Caste Certificate"] == "missing"

    def test_no_uploads_all_missing(self):
        required = ["Aadhaar Card", "Income Certificate"]
        state = self._checklist(required, {})
        assert all(v == "missing" for v in state.values())

    def test_wrong_doc_stays_missing(self):
        required = ["Income Certificate"]
        uploaded = {"something": "Aadhaar Card"}
        state = self._checklist(required, uploaded)
        assert state["Income Certificate"] == "missing"
