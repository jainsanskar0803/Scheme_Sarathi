"""
Assisted-mode storage: citizen metadata and scheme follow-up status.

Same dual-backend pattern as session_store.py.
  USE_SUPABASE=true  → Supabase (citizen_metadata, scheme_followup tables)
  (not set / false)  → in-memory dicts  ← used by all automated tests
"""
from __future__ import annotations

import os
import threading
from datetime import datetime, timezone
from typing import Optional

_lock = threading.Lock()

# ----- in-memory stores -----
_citizen_meta: dict[str, dict] = {}        # session_id → metadata dict
_followups: dict[tuple[str, str], dict] = {}  # (session_id, scheme_id) → followup dict

_CITIZEN_TABLE = "citizen_metadata"
_FOLLOWUP_TABLE = "scheme_followup"

FOLLOWUP_STATUSES = {"will_apply", "applied", "received", "rejected", "not_applicable"}


# ---------------------------------------------------------------------------
# Citizen metadata
# ---------------------------------------------------------------------------

def citizen_create(
    session_id: str,
    worker_id: str,
    citizen_name: str,
    citizen_phone: Optional[str] = None,
    notes: Optional[str] = None,
) -> dict:
    record = {
        "session_id": session_id,
        "worker_id": worker_id,
        "citizen_name": citizen_name,
        "citizen_phone": citizen_phone,
        "notes": notes,
        "created_at": datetime.now(timezone.utc).isoformat(),
    }
    if _supabase():
        return _sb_citizen_create(record)
    with _lock:
        _citizen_meta[session_id] = record
    return record


def citizen_get(session_id: str) -> Optional[dict]:
    if _supabase():
        return _sb_citizen_get(session_id)
    with _lock:
        return _citizen_meta.get(session_id)


def citizen_list(worker_id: str) -> list[dict]:
    if _supabase():
        return _sb_citizen_list(worker_id)
    with _lock:
        return [v for v in _citizen_meta.values() if v["worker_id"] == worker_id]


# ---------------------------------------------------------------------------
# Scheme follow-up
# ---------------------------------------------------------------------------

def followup_set(
    session_id: str,
    scheme_id: str,
    scheme_name: str,
    status: str,
    notes: Optional[str] = None,
) -> dict:
    record = {
        "session_id": session_id,
        "scheme_id": scheme_id,
        "scheme_name": scheme_name,
        "status": status,
        "notes": notes,
        "updated_at": datetime.now(timezone.utc).isoformat(),
    }
    if _supabase():
        return _sb_followup_set(record)
    with _lock:
        _followups[(session_id, scheme_id)] = record
    return record


def followup_list(session_id: str) -> list[dict]:
    if _supabase():
        return _sb_followup_list(session_id)
    with _lock:
        return [v for k, v in _followups.items() if k[0] == session_id]


def followup_get(session_id: str, scheme_id: str) -> Optional[dict]:
    if _supabase():
        return _sb_followup_get(session_id, scheme_id)
    with _lock:
        return _followups.get((session_id, scheme_id))


# ---------------------------------------------------------------------------
# Supabase helpers
# ---------------------------------------------------------------------------

def _supabase() -> bool:
    return os.environ.get("USE_SUPABASE", "").lower() == "true"


def _sb_citizen_create(record: dict) -> dict:
    import logging
    from backend.db.supabase import get_client
    try:
        res = get_client().table(_CITIZEN_TABLE).insert(record).execute()
        return res.data[0] if res.data else record
    except Exception as exc:
        logging.error("Supabase insert into %s failed: %s", _CITIZEN_TABLE, exc)
        raise


def _sb_citizen_get(session_id: str) -> Optional[dict]:
    from backend.db.supabase import get_client
    res = (
        get_client()
        .table(_CITIZEN_TABLE)
        .select("*")
        .eq("session_id", session_id)
        .execute()
    )
    return res.data[0] if res.data else None


def _sb_citizen_list(worker_id: str) -> list[dict]:
    from backend.db.supabase import get_client
    res = (
        get_client()
        .table(_CITIZEN_TABLE)
        .select("*")
        .eq("worker_id", worker_id)
        .order("created_at", desc=True)
        .execute()
    )
    return res.data or []


def _sb_followup_set(record: dict) -> dict:
    from backend.db.supabase import get_client
    get_client().table(_FOLLOWUP_TABLE).upsert(record).execute()
    return record


def _sb_followup_list(session_id: str) -> list[dict]:
    from backend.db.supabase import get_client
    res = (
        get_client()
        .table(_FOLLOWUP_TABLE)
        .select("*")
        .eq("session_id", session_id)
        .execute()
    )
    return res.data or []


def _sb_followup_get(session_id: str, scheme_id: str) -> Optional[dict]:
    from backend.db.supabase import get_client
    res = (
        get_client()
        .table(_FOLLOWUP_TABLE)
        .select("*")
        .eq("session_id", session_id)
        .eq("scheme_id", scheme_id)
        .execute()
    )
    return res.data[0] if res.data else None
