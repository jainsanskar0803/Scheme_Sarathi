"""
Session storage abstraction.

Selects backend at call time based on the USE_SUPABASE environment variable:

  USE_SUPABASE=true  → Supabase (interview_sessions table)
  (not set / false)  → in-memory dict  ← used by all automated tests

The public API is five functions that the profile route and its dependants call.
"""
from __future__ import annotations

import os
import threading
import uuid
from datetime import datetime, timezone
from typing import Optional

from backend.models.citizen_profile import CitizenProfile

_SESSIONS_TABLE = "interview_sessions"


# ---------------------------------------------------------------------------
# In-memory backend  (default; used by all automated tests)
# ---------------------------------------------------------------------------

_lock: threading.Lock = threading.Lock()
_mem: dict[str, dict] = {}          # session_id → profile dict (JSON-compatible)


def _mem_create() -> str:
    sid = str(uuid.uuid4())
    with _lock:
        _mem[sid] = {}
    return sid


def _mem_get(session_id: str) -> Optional[CitizenProfile]:
    with _lock:
        data = _mem.get(session_id)
    if data is None:
        return None
    return CitizenProfile.model_validate(data)


def _mem_save(session_id: str, profile: CitizenProfile) -> None:
    with _lock:
        _mem[session_id] = profile.model_dump()


def _mem_delete(session_id: str) -> None:
    with _lock:
        _mem.pop(session_id, None)


def _mem_exists(session_id: str) -> bool:
    with _lock:
        return session_id in _mem


# ---------------------------------------------------------------------------
# Supabase backend  (activated by USE_SUPABASE=true)
# ---------------------------------------------------------------------------

def _sb_create() -> str:
    from backend.db.supabase import get_client   # lazy — never imported in tests
    sid = str(uuid.uuid4())
    get_client().table(_SESSIONS_TABLE).insert(
        {"session_id": sid, "profile_data": {}}
    ).execute()
    return sid


def _sb_get(session_id: str) -> Optional[CitizenProfile]:
    from backend.db.supabase import get_client
    res = (
        get_client()
        .table(_SESSIONS_TABLE)
        .select("profile_data")
        .eq("session_id", session_id)
        .execute()
    )
    if not res.data:
        return None
    return CitizenProfile.model_validate(res.data[0]["profile_data"])


def _sb_save(session_id: str, profile: CitizenProfile) -> None:
    from backend.db.supabase import get_client
    get_client().table(_SESSIONS_TABLE).update(
        {
            "profile_data": profile.model_dump(),
            "updated_at": datetime.now(timezone.utc).isoformat(),
        }
    ).eq("session_id", session_id).execute()


def _sb_delete(session_id: str) -> None:
    from backend.db.supabase import get_client
    get_client().table(_SESSIONS_TABLE).delete().eq("session_id", session_id).execute()


def _sb_exists(session_id: str) -> bool:
    from backend.db.supabase import get_client
    res = (
        get_client()
        .table(_SESSIONS_TABLE)
        .select("session_id")
        .eq("session_id", session_id)
        .execute()
    )
    return bool(res.data)


# ---------------------------------------------------------------------------
# Dispatch
# ---------------------------------------------------------------------------

def _supabase() -> bool:
    return os.environ.get("USE_SUPABASE", "").lower() == "true"


def session_create() -> str:
    """Create a new empty session. Returns the new session_id."""
    return _sb_create() if _supabase() else _mem_create()


def session_get(session_id: str) -> Optional[CitizenProfile]:
    """Return the CitizenProfile for the session, or None if not found."""
    return _sb_get(session_id) if _supabase() else _mem_get(session_id)


def session_save(session_id: str, profile: CitizenProfile) -> None:
    """Persist an updated profile for an existing session."""
    if _supabase():
        _sb_save(session_id, profile)
    else:
        _mem_save(session_id, profile)


def session_delete(session_id: str) -> None:
    """Remove a session entirely."""
    if _supabase():
        _sb_delete(session_id)
    else:
        _mem_delete(session_id)


def session_exists(session_id: str) -> bool:
    """Return True if the session exists."""
    return _sb_exists(session_id) if _supabase() else _mem_exists(session_id)
