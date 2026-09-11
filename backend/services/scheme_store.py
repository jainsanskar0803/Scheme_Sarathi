"""
Scheme store — supplies the list of seed schemes to the rule engine.

Backend selection (USE_SUPABASE env var):
  true  → load once from Supabase seed_schemes table
  else  → load from data/seed_schemes.json  ← used by all automated tests

Both paths return the same SeedScheme objects; the rule engine never knows
which backend was used.
"""
from __future__ import annotations

import json
import os
from functools import lru_cache
from pathlib import Path
from typing import Optional

from pydantic import BaseModel

from backend.models.scheme import EligibilityRules

_SEED_PATH = Path(__file__).resolve().parents[2] / "data" / "seed_schemes.json"
_SEED_TABLE = "seed_schemes"


class SeedScheme(BaseModel):
    """Mirrors the shape of each object in data/seed_schemes.json."""

    scheme_id: str
    scheme_name: str
    category: list[str]
    category_display: list[str]
    level: str
    state: Optional[str]
    benefit: str
    official_website: Optional[str]
    eligibility_rules: EligibilityRules
    unverified_criteria: list[str]
    missing_information: list[str]
    required_documents: Optional[str]
    application_method: Optional[str]
    tags: list[str]

    @property
    def source(self) -> str:
        if self.level == "central":
            return "Central Government"
        return f"State Government – {self.state}" if self.state else "State Government"


# ---------------------------------------------------------------------------
# Loaders
# ---------------------------------------------------------------------------

def _load_from_json() -> list[SeedScheme]:
    raw: list[dict] = json.loads(_SEED_PATH.read_text(encoding="utf-8"))
    return [SeedScheme.model_validate(r) for r in raw]


def _load_from_supabase() -> list[SeedScheme]:
    from backend.db.supabase import get_client   # lazy — never imported in tests
    client = get_client()
    page_size = 1000
    all_rows: list[dict] = []
    offset = 0
    while True:
        res = (
            client.table(_SEED_TABLE)
            .select("*")
            .range(offset, offset + page_size - 1)
            .execute()
        )
        if not res.data:
            break
        all_rows.extend(res.data)
        if len(res.data) < page_size:
            break
        offset += page_size
    return [SeedScheme.model_validate(row) for row in all_rows]


# ---------------------------------------------------------------------------
# Public API  (cached after first call)
# ---------------------------------------------------------------------------

@lru_cache(maxsize=1)
def all_schemes() -> list[SeedScheme]:
    """
    Return all seed schemes, cached for the process lifetime.
    Source depends on USE_SUPABASE env var.
    """
    if os.environ.get("USE_SUPABASE", "").lower() == "true":
        return _load_from_supabase()
    return _load_from_json()
