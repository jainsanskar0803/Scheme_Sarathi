"""
Ingestion pipeline: updated_data.csv → Supabase schemes table.

Steps
  1. Load CSV (read-only, original file never modified)
  2. Clean   – strip zero-width / control characters from every text field
  3. Deduplicate – keep first occurrence of each slug
  4. Normalize – level to lowercase, schemeCategory → list, tags → list
  5. Validate – Pydantic Scheme model rejects malformed rows
  6. Upsert  – conflict on slug, so re-runs are idempotent
"""

from __future__ import annotations

import csv
import re
import sys
import os
from pathlib import Path
from typing import Optional

# Allow running from any directory
sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

from backend.models.scheme import Scheme

# ---------------------------------------------------------------------------
# Constants
# ---------------------------------------------------------------------------

CSV_PATH = Path(__file__).resolve().parents[1] / "updated_data.csv"

# "Science, IT & Communications" contains the same ", " delimiter used to
# separate multiple categories.  We swap it to a safe placeholder before
# splitting so that every other category (which never contains ", ") splits
# correctly, then restore the real name afterwards.
_SCIENCE_PLACEHOLDER = "\x00SCI_IT\x00"
_SCIENCE_CANON = "Science, IT & Communications"

# Characters to strip: zero-width space, zero-width non-joiner/joiner,
# soft hyphen, BOM (when it appears mid-string), non-breaking space → space.
_ZWS_RE = re.compile(r"[​‌‍­﻿]")


# ---------------------------------------------------------------------------
# Cleaning helpers
# ---------------------------------------------------------------------------

def _clean_text(value: str) -> str:
    """Remove zero-width / invisible characters; normalise whitespace."""
    value = _ZWS_RE.sub("", value)
    # collapse runs of whitespace but preserve intentional newlines
    value = re.sub(r"[ \t]+", " ", value)
    return value.strip()


def _clean_row(raw: dict[str, str]) -> dict[str, str]:
    return {k: _clean_text(v) for k, v in raw.items()}


# ---------------------------------------------------------------------------
# Normalisation helpers
# ---------------------------------------------------------------------------

def _parse_categories(raw: str) -> list[str]:
    """
    Split a schemeCategory string into a list of canonical category names.

    schemeCategory uses ", " as separator, but "Science, IT & Communications"
    itself contains ", ".  We handle this by substituting a placeholder
    before splitting.
    """
    protected = raw.replace(_SCIENCE_CANON, _SCIENCE_PLACEHOLDER)
    parts = [p.strip() for p in protected.split(", ") if p.strip()]
    return [p.replace(_SCIENCE_PLACEHOLDER, _SCIENCE_CANON) for p in parts]


def _parse_tags(raw: str) -> list[str]:
    return [t.strip() for t in raw.split(",") if t.strip()]


def _normalise_level(raw: str) -> str:
    return raw.strip().lower()


# ---------------------------------------------------------------------------
# Pipeline
# ---------------------------------------------------------------------------

def load_and_clean(csv_path: Path = CSV_PATH) -> list[dict]:
    """Load CSV, clean every cell, drop the phantom empty column."""
    with open(csv_path, newline="", encoding="utf-8") as fh:
        reader = csv.DictReader(fh)
        rows = [_clean_row(dict(row)) for row in reader]

    # Drop the entirely-blank phantom column that appears in the CSV header
    for row in rows:
        row.pop("", None)

    return rows


def deduplicate(rows: list[dict]) -> tuple[list[dict], int]:
    """Keep the first occurrence of each slug. Returns (deduped, removed_count)."""
    seen: set[str] = set()
    unique: list[dict] = []
    for row in rows:
        slug = row["slug"]
        if slug not in seen:
            seen.add(slug)
            unique.append(row)
    return unique, len(rows) - len(unique)


def normalise(rows: list[dict]) -> list[Scheme]:
    """Convert raw dicts to validated Scheme objects."""
    schemes: list[Scheme] = []
    errors: list[tuple[str, str]] = []

    for row in rows:
        try:
            scheme = Scheme(
                scheme_name=row["scheme_name"],
                slug=row["slug"],
                details=row["details"],
                benefits=row["benefits"],
                eligibility_text=row["eligibility"],
                application=row["application"] or None,
                documents=row["documents"] or None,
                level=_normalise_level(row["level"]),
                scheme_categories=_parse_categories(row["schemeCategory"]),
                tags=_parse_tags(row["tags"]),
            )
            schemes.append(scheme)
        except Exception as exc:
            errors.append((row.get("slug", "?"), str(exc)))

    if errors:
        print(f"  [warn] {len(errors)} rows failed validation and were skipped:")
        for slug, msg in errors:
            print(f"    slug={slug!r}: {msg}")

    return schemes


def upsert(schemes: list[Scheme], batch_size: int = 100) -> int:
    """Upsert schemes into Supabase in batches. Returns total upserted."""
    from backend.db.supabase import get_client

    client = get_client()
    total = 0

    for i in range(0, len(schemes), batch_size):
        batch = schemes[i : i + batch_size]
        payload = [s.model_dump() for s in batch]
        client.table("schemes").upsert(payload, on_conflict="slug").execute()
        total += len(batch)
        print(f"  upserted {total}/{len(schemes)}", end="\r")

    print()
    return total


def run(csv_path: Path = CSV_PATH, dry_run: bool = False) -> dict:
    """Full pipeline. Set dry_run=True to skip the Supabase upsert."""
    print("Loading CSV …")
    rows = load_and_clean(csv_path)
    print(f"  loaded   {len(rows)} rows")

    rows, removed = deduplicate(rows)
    print(f"  deduped  {removed} duplicates removed → {len(rows)} unique slugs")

    schemes = normalise(rows)
    print(f"  normalised {len(schemes)} schemes")

    if dry_run:
        print("  dry_run=True — skipping upsert")
    else:
        print("Upserting to Supabase …")
        upserted = upsert(schemes)
        print(f"  done — {upserted} rows upserted")

    return {
        "loaded": len(rows) + removed,
        "duplicates_removed": removed,
        "normalised": len(schemes),
    }


# ---------------------------------------------------------------------------
# CLI entry point
# ---------------------------------------------------------------------------

if __name__ == "__main__":
    import argparse

    parser = argparse.ArgumentParser(description="Ingest schemes CSV into Supabase")
    parser.add_argument("--dry-run", action="store_true", help="Skip Supabase upsert")
    parser.add_argument("--csv", default=str(CSV_PATH), help="Path to CSV file")
    args = parser.parse_args()

    result = run(csv_path=Path(args.csv), dry_run=args.dry_run)
    print(result)