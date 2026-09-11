from __future__ import annotations
from typing import Literal, Optional
from pydantic import BaseModel, field_validator, model_validator

Gender        = Literal["male", "female", "transgender"]
Caste         = Literal["SC", "ST", "OBC", "EWS", "general"]
Domicile      = Literal["rural", "urban"]
MaritalStatus = Literal["single", "married", "widow", "divorced"]
VehicleType   = Literal["none", "two_wheeler", "four_wheeler"]


class CitizenProfile(BaseModel):
    """
    Incrementally populated citizen profile.

    Every field is Optional.  None means "not yet collected" — the LLM
    fills fields one conversation-turn at a time.  The rule engine treats
    None as "unknown" (skips the check rather than failing it).
    """

    # ── Demographics ────────────────────────────────────────────────────────
    age: Optional[int] = None

    gender: Optional[Gender] = None

    # ── Geography ───────────────────────────────────────────────────────────
    state: Optional[str] = None         # state of residence
    district: Optional[str] = None      # district within the state

    domicile: Optional[Domicile] = None  # "rural" | "urban"

    # ── Socio-economic identity ──────────────────────────────────────────────
    caste: Optional[Caste] = None

    annual_income: Optional[int] = None  # INR per year, household total

    # ── Occupation ──────────────────────────────────────────────────────────
    # occupation: primary value used by the rule engine ("farmer", "student", …)
    occupation: Optional[str] = None

    # Role flags — a person may hold multiple roles simultaneously
    is_student: Optional[bool] = None
    is_farmer: Optional[bool] = None
    is_artisan: Optional[bool] = None
    is_business_owner: Optional[bool] = None

    # ── Land ────────────────────────────────────────────────────────────────
    land_holding_acres: Optional[float] = None  # total cultivable land owned

    # ── Family ──────────────────────────────────────────────────────────────
    marital_status: Optional[MaritalStatus] = None
    num_children: Optional[int] = None

    # ── Status flags ────────────────────────────────────────────────────────
    is_disabled: Optional[bool] = None
    has_bpl_card: Optional[bool] = None
    has_electricity_connection: Optional[bool] = None

    # ── Assets ──────────────────────────────────────────────────────────────
    owns_house: Optional[bool] = None
    owns_vehicle: Optional[VehicleType] = None  # highest vehicle class owned

    # ── Validators ──────────────────────────────────────────────────────────

    @field_validator("age")
    @classmethod
    def age_in_range(cls, v: Optional[int]) -> Optional[int]:
        if v is not None and not (0 <= v <= 120):
            raise ValueError(f"age must be between 0 and 120, got {v}")
        return v

    @field_validator("annual_income")
    @classmethod
    def income_non_negative(cls, v: Optional[int]) -> Optional[int]:
        if v is not None and v < 0:
            raise ValueError("annual_income cannot be negative")
        return v

    @field_validator("land_holding_acres")
    @classmethod
    def land_non_negative(cls, v: Optional[float]) -> Optional[float]:
        if v is not None and v < 0:
            raise ValueError("land_holding_acres cannot be negative")
        return v

    @field_validator("num_children")
    @classmethod
    def children_non_negative(cls, v: Optional[int]) -> Optional[int]:
        if v is not None and v < 0:
            raise ValueError("num_children cannot be negative")
        return v

    @model_validator(mode="after")
    def sync_occupation_flags(self) -> CitizenProfile:
        """
        If occupation is set, mirror it into the matching boolean flag.
        If a flag is set True and occupation is still None, set occupation.
        Flags and occupation are kept consistent — whichever is set first wins.
        """
        _map = {
            "farmer":        "is_farmer",
            "student":       "is_student",
            "artisan":       "is_artisan",
            "business_owner": "is_business_owner",
        }
        if self.occupation and self.occupation in _map:
            flag = _map[self.occupation]
            if getattr(self, flag) is None:
                object.__setattr__(self, flag, True)

        if self.occupation is None:
            for occ, flag in _map.items():
                if getattr(self, flag) is True:
                    object.__setattr__(self, "occupation", occ)
                    break
        return self

    def merge(self, update: dict) -> CitizenProfile:
        """Return a new profile with the supplied fields merged in."""
        current = self.model_dump()
        current.update({k: v for k, v in update.items() if v is not None})
        return CitizenProfile.model_validate(current)