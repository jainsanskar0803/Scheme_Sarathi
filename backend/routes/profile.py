from __future__ import annotations

import json
import uuid

from fastapi import APIRouter, HTTPException, status
from pydantic import BaseModel, ValidationError

from backend.db import session_store
from backend.models.citizen_profile import CitizenProfile
from backend.models.profile_session import (
    ProfileSession,
    compute_completeness,
)

router = APIRouter(prefix="/profile", tags=["profile"])


# ---------------------------------------------------------------------------
# Internal helpers  (imported by chat.py and match.py — keep signatures stable)
# ---------------------------------------------------------------------------

def _get_or_404(session_id: str) -> CitizenProfile:
    profile = session_store.session_get(session_id)
    if profile is None:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=f"Session '{session_id}' not found",
        )
    return profile


def _save(session_id: str, profile: CitizenProfile) -> None:
    session_store.session_save(session_id, profile)


# ---------------------------------------------------------------------------
# Request / response bodies
# ---------------------------------------------------------------------------

class ProfileUpdateRequest(BaseModel):
    """
    Partial update — only fields explicitly provided are merged.
    All fields are Optional so the client sends only what has changed.
    Unrecognised keys are ignored.
    """
    age: object = None
    gender: object = None
    state: object = None
    district: object = None
    domicile: object = None
    caste: object = None
    annual_income: object = None
    occupation: object = None
    is_student: object = None
    is_farmer: object = None
    is_artisan: object = None
    is_business_owner: object = None
    land_holding_acres: object = None
    marital_status: object = None
    num_children: object = None
    is_disabled: object = None
    has_bpl_card: object = None
    has_electricity_connection: object = None
    owns_house: object = None
    owns_vehicle: object = None


# ---------------------------------------------------------------------------
# Endpoints
# ---------------------------------------------------------------------------

@router.post(
    "",
    response_model=ProfileSession,
    status_code=status.HTTP_201_CREATED,
    summary="Create a new empty citizen profile session",
)
def create_profile() -> ProfileSession:
    session_id = session_store.session_create()
    profile = CitizenProfile()
    return ProfileSession(
        session_id=session_id,
        profile=profile,
        completeness=compute_completeness(profile),
    )


@router.get(
    "/{session_id}",
    response_model=ProfileSession,
    summary="Get the current profile for a session",
)
def get_profile(session_id: str) -> ProfileSession:
    profile = _get_or_404(session_id)
    return ProfileSession(
        session_id=session_id,
        profile=profile,
        completeness=compute_completeness(profile),
    )


@router.patch(
    "/{session_id}",
    response_model=ProfileSession,
    summary="Update one or more profile fields (incremental — sent fields are merged)",
)
def update_profile(session_id: str, body: ProfileUpdateRequest) -> ProfileSession:
    existing = _get_or_404(session_id)

    update_dict = {
        k: v for k, v in body.model_dump().items() if v is not None
    }

    try:
        updated = existing.merge(update_dict)
    except ValidationError as exc:
        raise HTTPException(
            status_code=422,
            detail=json.loads(exc.json()),
        )

    _save(session_id, updated)
    return ProfileSession(
        session_id=session_id,
        profile=updated,
        completeness=compute_completeness(updated),
    )


@router.delete(
    "/{session_id}",
    status_code=status.HTTP_204_NO_CONTENT,
    summary="Delete a session (useful for testing and UI reset)",
)
def delete_profile(session_id: str) -> None:
    _get_or_404(session_id)          # raises 404 if not found
    session_store.session_delete(session_id)
