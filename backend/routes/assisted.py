"""
Assisted-mode API — used by CSC/NGO field workers to manage citizen sessions.

Endpoints (all under /api/assisted):
  POST   /citizens                          create citizen + session
  GET    /citizens?worker_id=...            list worker's citizens
  GET    /citizens/{session_id}             get citizen metadata
  PUT    /citizens/{session_id}/followup/{scheme_id}   upsert follow-up status
  GET    /citizens/{session_id}/followup               list all follow-ups
  GET    /citizens/{session_id}/followup/{scheme_id}   single follow-up
"""
from __future__ import annotations

from typing import Optional

from fastapi import APIRouter, HTTPException
from pydantic import BaseModel, field_validator

from backend.db.assisted_store import (
    FOLLOWUP_STATUSES,
    citizen_create,
    citizen_get,
    citizen_list,
    followup_get,
    followup_list,
    followup_set,
)
from backend.db.session_store import session_create

router = APIRouter(prefix="/assisted", tags=["assisted"])


# ─── Request / Response models ────────────────────────────────────────────────


class CreateCitizenRequest(BaseModel):
    worker_id: str
    citizen_name: str
    citizen_phone: Optional[str] = None
    notes: Optional[str] = None

    @field_validator("citizen_name")
    @classmethod
    def name_nonempty(cls, v: str) -> str:
        v = v.strip()
        if not v:
            raise ValueError("citizen_name cannot be blank")
        return v

    @field_validator("worker_id")
    @classmethod
    def worker_nonempty(cls, v: str) -> str:
        v = v.strip()
        if not v:
            raise ValueError("worker_id cannot be blank")
        return v


class CitizenResponse(BaseModel):
    session_id: str
    worker_id: str
    citizen_name: str
    citizen_phone: Optional[str]
    notes: Optional[str]
    created_at: str


class FollowupRequest(BaseModel):
    scheme_name: str
    status: str
    notes: Optional[str] = None

    @field_validator("status")
    @classmethod
    def valid_status(cls, v: str) -> str:
        if v not in FOLLOWUP_STATUSES:
            raise ValueError(f"status must be one of {sorted(FOLLOWUP_STATUSES)}")
        return v


class FollowupResponse(BaseModel):
    session_id: str
    scheme_id: str
    scheme_name: str
    status: str
    notes: Optional[str]
    updated_at: str


# ─── Helpers ──────────────────────────────────────────────────────────────────


def _citizen_or_404(session_id: str) -> dict:
    meta = citizen_get(session_id)
    if not meta:
        raise HTTPException(status_code=404, detail=f"Citizen session '{session_id}' not found")
    return meta


# ─── Endpoints ────────────────────────────────────────────────────────────────


@router.post("/citizens", response_model=CitizenResponse, status_code=201)
def create_citizen(body: CreateCitizenRequest) -> CitizenResponse:
    """
    Create a new citizen profile session and store worker metadata.
    Returns the new session_id so the caller can redirect to the interview.
    """
    session_id = session_create()
    record = citizen_create(
        session_id=session_id,
        worker_id=body.worker_id,
        citizen_name=body.citizen_name,
        citizen_phone=body.citizen_phone,
        notes=body.notes,
    )
    return CitizenResponse(**record)


@router.get("/citizens", response_model=list[CitizenResponse])
def list_citizens(worker_id: str) -> list[CitizenResponse]:
    """List all citizen sessions created by this worker."""
    if not worker_id.strip():
        raise HTTPException(status_code=400, detail="worker_id query param is required")
    records = citizen_list(worker_id.strip())
    return [CitizenResponse(**r) for r in records]


@router.get("/citizens/{session_id}", response_model=CitizenResponse)
def get_citizen(session_id: str) -> CitizenResponse:
    """Retrieve metadata for a single citizen session."""
    return CitizenResponse(**_citizen_or_404(session_id))


@router.put(
    "/citizens/{session_id}/followup/{scheme_id}",
    response_model=FollowupResponse,
)
def set_followup(
    session_id: str, scheme_id: str, body: FollowupRequest
) -> FollowupResponse:
    """Upsert follow-up status for one scheme for this citizen."""
    _citizen_or_404(session_id)
    record = followup_set(
        session_id=session_id,
        scheme_id=scheme_id,
        scheme_name=body.scheme_name,
        status=body.status,
        notes=body.notes,
    )
    return FollowupResponse(**record)


@router.get(
    "/citizens/{session_id}/followup",
    response_model=list[FollowupResponse],
)
def list_followups(session_id: str) -> list[FollowupResponse]:
    """List all scheme follow-ups for a citizen."""
    _citizen_or_404(session_id)
    return [FollowupResponse(**r) for r in followup_list(session_id)]


@router.get(
    "/citizens/{session_id}/followup/{scheme_id}",
    response_model=FollowupResponse,
)
def get_followup(session_id: str, scheme_id: str) -> FollowupResponse:
    """Get a single scheme follow-up record."""
    _citizen_or_404(session_id)
    record = followup_get(session_id, scheme_id)
    if not record:
        raise HTTPException(status_code=404, detail="Follow-up not found")
    return FollowupResponse(**record)
