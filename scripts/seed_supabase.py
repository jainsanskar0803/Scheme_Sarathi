"""
Seed the 14 curated schemes from data/seed_schemes.json into Supabase.

Usage (from project root):
    python -m scripts.seed_supabase

Requires:
    SUPABASE_URL and SUPABASE_SERVICE_KEY set in .env or environment.

Behaviour:
    Upserts on scheme_id — safe to run multiple times.
    Never modifies eligibility rules or any scheme data.
"""
from __future__ import annotations

import json
import sys
from pathlib import Path

from dotenv import load_dotenv

load_dotenv()

_ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(_ROOT))

from backend.db.supabase import get_client

_SEED_PATH = _ROOT / "data" / "seed_schemes.json"
_TABLE = "seed_schemes"


def seed() -> None:
    raw: list[dict] = json.loads(_SEED_PATH.read_text(encoding="utf-8"))
    client = get_client()

    print(f"Seeding {len(raw)} schemes into '{_TABLE}' …")
    for scheme in raw:
        res = client.table(_TABLE).upsert(scheme, on_conflict="scheme_id").execute()
        status = "OK" if res.data else "WARN (no data returned)"
        print(f"  {scheme['scheme_id']:20s} {status}")

    # Verify
    check = client.table(_TABLE).select("scheme_id").execute()
    print(f"\nTotal rows in '{_TABLE}': {len(check.data)}")
    if len(check.data) != len(raw):
        print("WARNING: row count does not match source — check for errors above.")
    else:
        print("All schemes seeded successfully.")


if __name__ == "__main__":
    seed()
