"""
Tests for POST /api/voice/transcribe and POST /api/voice/speak.
Sarvam is mocked — no real API calls.
"""
from __future__ import annotations

import base64
import sys
import wave
import struct
import io
from pathlib import Path
from unittest.mock import MagicMock, patch

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

import pytest
from fastapi.testclient import TestClient

from backend.main import app

client = TestClient(app)

# ── helpers ────────────────────────────────────────────────────────────────────

def _silent_wav(seconds: float = 0.5, rate: int = 16000) -> bytes:
    """Return a minimal valid WAV with silence."""
    num = int(rate * seconds)
    buf = io.BytesIO()
    with wave.open(buf, "wb") as wf:
        wf.setnchannels(1)
        wf.setsampwidth(2)
        wf.setframerate(rate)
        wf.writeframes(struct.pack("<" + "h" * num, *([0] * num)))
    return buf.getvalue()


def _stt_mock(transcript: str, lang: str = "en-IN") -> MagicMock:
    m = MagicMock()
    m.is_success = True
    m.json.return_value = {"transcript": transcript, "language_code": lang, "language_probability": 0.9}
    return m


def _tts_mock(audio_b64: str = "") -> MagicMock:
    m = MagicMock()
    m.is_success = True
    m.json.return_value = {"audios": [audio_b64 or base64.b64encode(b"fake-wav").decode()]}
    return m


def _err_mock(status: int, text: str = "error") -> MagicMock:
    m = MagicMock()
    m.is_success = False
    m.status_code = status
    m.text = text
    return m


# ── /api/voice/transcribe ──────────────────────────────────────────────────────

class TestTranscribe:

    def _upload(self, data: bytes = b"audio", filename: str = "audio.wav", ct: str = "audio/wav"):
        return client.post(
            "/api/voice/transcribe",
            files={"file": (filename, data, ct)},
        )

    def test_no_api_key_503(self, monkeypatch):
        monkeypatch.delenv("SARVAM_API_KEY", raising=False)
        r = self._upload()
        assert r.status_code == 503
        assert "SARVAM_API_KEY" in r.json()["detail"]

    def test_successful_english_transcript(self, monkeypatch):
        monkeypatch.setenv("SARVAM_API_KEY", "test-key")
        with patch("httpx.Client.post", return_value=_stt_mock("I am 35 years old", "en-IN")):
            r = self._upload(_silent_wav())
        assert r.status_code == 200
        d = r.json()
        assert d["text"] == "I am 35 years old"
        assert d["language_code"] == "en-IN"

    def test_successful_hindi_transcript(self, monkeypatch):
        monkeypatch.setenv("SARVAM_API_KEY", "test-key")
        with patch("httpx.Client.post", return_value=_stt_mock("मैं 35 साल का हूं", "hi-IN")):
            r = self._upload(_silent_wav())
        assert r.status_code == 200
        assert r.json()["text"] == "मैं 35 साल का हूं"
        assert r.json()["language_code"] == "hi-IN"

    def test_empty_transcript_returned_as_empty_string(self, monkeypatch):
        monkeypatch.setenv("SARVAM_API_KEY", "test-key")
        with patch("httpx.Client.post", return_value=_stt_mock("", "kn-IN")):
            r = self._upload(_silent_wav())
        assert r.status_code == 200
        assert r.json()["text"] == ""

    def test_transcript_stripped_of_whitespace(self, monkeypatch):
        monkeypatch.setenv("SARVAM_API_KEY", "test-key")
        with patch("httpx.Client.post", return_value=_stt_mock("  hello  ", "en-IN")):
            r = self._upload(_silent_wav())
        assert r.json()["text"] == "hello"

    def test_sarvam_4xx_returns_502(self, monkeypatch):
        monkeypatch.setenv("SARVAM_API_KEY", "bad-key")
        with patch("httpx.Client.post", return_value=_err_mock(401, "Unauthorized")):
            r = self._upload(_silent_wav())
        assert r.status_code == 502
        assert "401" in r.json()["detail"]

    def test_sarvam_5xx_returns_502(self, monkeypatch):
        monkeypatch.setenv("SARVAM_API_KEY", "test-key")
        with patch("httpx.Client.post", return_value=_err_mock(500, "Internal Server Error")):
            r = self._upload(_silent_wav())
        assert r.status_code == 502

    def test_webm_content_type_accepted(self, monkeypatch):
        monkeypatch.setenv("SARVAM_API_KEY", "test-key")
        with patch("httpx.Client.post", return_value=_stt_mock("test")) as mock_post:
            r = self._upload(b"fake-webm", "rec.webm", "audio/webm")
        assert r.status_code == 200
        call_files = mock_post.call_args[1]["files"]
        _name, _data, ct = call_files["file"]
        assert ct == "audio/webm"

    def test_webm_opus_codec_stripped(self, monkeypatch):
        """Chrome sends audio/webm;codecs=opus — Sarvam rejects codec suffix."""
        monkeypatch.setenv("SARVAM_API_KEY", "test-key")
        with patch("httpx.Client.post", return_value=_stt_mock("hello")) as mock_post:
            r = self._upload(b"fake-webm", "rec.webm", "audio/webm;codecs=opus")
        assert r.status_code == 200
        call_files = mock_post.call_args[1]["files"]
        _name, _data, ct = call_files["file"]
        assert ct == "audio/webm"   # codec suffix stripped

    def test_saaras_model_sent(self, monkeypatch):
        """Verify saaras:v3 model is forwarded to Sarvam."""
        monkeypatch.setenv("SARVAM_API_KEY", "test-key")
        with patch("httpx.Client.post", return_value=_stt_mock("hi")) as mock_post:
            r = self._upload(_silent_wav())
        assert r.status_code == 200
        sent_data = mock_post.call_args[1]["data"]
        assert sent_data.get("model") == "saaras:v3"

    def test_mp4_content_type_accepted(self, monkeypatch):
        monkeypatch.setenv("SARVAM_API_KEY", "test-key")
        with patch("httpx.Client.post", return_value=_stt_mock("test mp4")) as mock_post:
            r = self._upload(b"fake-mp4", "rec.mp4", "audio/mp4")
        assert r.status_code == 200


# ── /api/voice/speak ──────────────────────────────────────────────────────────

class TestSpeak:

    def _post(self, text: str = "Hello", language: str = "en"):
        return client.post("/api/voice/speak", json={"text": text, "language": language})

    def test_no_api_key_503(self, monkeypatch):
        monkeypatch.delenv("SARVAM_API_KEY", raising=False)
        r = self._post()
        assert r.status_code == 503

    def test_english_tts(self, monkeypatch):
        monkeypatch.setenv("SARVAM_API_KEY", "test-key")
        fake = base64.b64encode(b"wav-data").decode()
        with patch("httpx.Client.post", return_value=_tts_mock(fake)) as mock_post:
            r = self._post("How old are you?", "en")
        assert r.status_code == 200
        d = r.json()
        assert d["audio_base64"] == fake
        assert d["content_type"] == "audio/wav"
        # Verify correct language code sent
        sent = mock_post.call_args[1]["json"]
        assert sent["target_language_code"] == "en-IN"
        assert sent["model"] == "bulbul:v3"
        assert sent["speaker"] == "priya"

    def test_hindi_tts(self, monkeypatch):
        monkeypatch.setenv("SARVAM_API_KEY", "test-key")
        with patch("httpx.Client.post", return_value=_tts_mock()) as mock_post:
            r = self._post("आपकी उम्र क्या है?", "hi")
        assert r.status_code == 200
        sent = mock_post.call_args[1]["json"]
        assert sent["target_language_code"] == "hi-IN"

    def test_long_text_truncated_to_500(self, monkeypatch):
        monkeypatch.setenv("SARVAM_API_KEY", "test-key")
        with patch("httpx.Client.post", return_value=_tts_mock()) as mock_post:
            r = self._post("A" * 1000, "en")
        assert r.status_code == 200
        sent_text = mock_post.call_args[1]["json"]["inputs"][0]
        assert len(sent_text) == 500

    def test_text_within_limit_not_truncated(self, monkeypatch):
        monkeypatch.setenv("SARVAM_API_KEY", "test-key")
        text = "Short question?"
        with patch("httpx.Client.post", return_value=_tts_mock()) as mock_post:
            r = self._post(text, "en")
        sent_text = mock_post.call_args[1]["json"]["inputs"][0]
        assert sent_text == text

    def test_sarvam_error_returns_502(self, monkeypatch):
        monkeypatch.setenv("SARVAM_API_KEY", "test-key")
        with patch("httpx.Client.post", return_value=_err_mock(400, "bad speaker")):
            r = self._post()
        assert r.status_code == 502

    def test_empty_audios_returns_502(self, monkeypatch):
        monkeypatch.setenv("SARVAM_API_KEY", "test-key")
        m = MagicMock()
        m.is_success = True
        m.json.return_value = {"audios": []}
        with patch("httpx.Client.post", return_value=m):
            r = self._post()
        assert r.status_code == 502

    def test_whitespace_text_stripped(self, monkeypatch):
        monkeypatch.setenv("SARVAM_API_KEY", "test-key")
        with patch("httpx.Client.post", return_value=_tts_mock()) as mock_post:
            r = self._post("  Hello world  ", "en")
        sent_text = mock_post.call_args[1]["json"]["inputs"][0]
        assert sent_text == "Hello world"
