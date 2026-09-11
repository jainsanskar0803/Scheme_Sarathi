"""
Full-dataset ingestion pipeline: Kaggle CSV → seed_schemes Supabase table.

Flow:
  updated_data.csv
    → load_and_clean  (reuses scripts/ingest.py)
    → deduplicate     (reuses scripts/ingest.py)
    → detect state    (for state-level schemes)
    → extract rules   (regex, no LLM)
    → convert to SeedScheme-compatible record
    → upsert into seed_schemes table

The 14 curated schemes (data/seed_schemes.json) are PROTECTED:
  - Their scheme_ids are never overwritten by this script.
  - Their full eligibility rules are preserved.

Idempotent: safe to run multiple times.

Usage (from project root):
    python -m scripts.ingest_all
    python -m scripts.ingest_all --dry-run
    python -m scripts.ingest_all --dry-run --limit 50
"""
from __future__ import annotations

import argparse
import json
import sys
from pathlib import Path

_ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(_ROOT))

from scripts.ingest import load_and_clean, deduplicate, _parse_categories, _parse_tags
from backend.services.eligibility_extractor import (
    detect_state_from_text,
    extract_eligibility_rules,
)

_CSV_PATH = _ROOT / "updated_data.csv"
_SEED_PATH = _ROOT / "data" / "seed_schemes.json"
_TABLE = "seed_schemes"

# Protected curated scheme IDs — never overwritten
_PROTECTED_IDS: frozenset[str] = frozenset(
    r["scheme_id"] for r in json.loads(_SEED_PATH.read_text(encoding="utf-8"))
)

# Canonical category → display name map
_DISPLAY_MAP: dict[str, str] = {
    "Agriculture": "Agriculture",
    "Agriculture,Rural & Environment": "Agriculture",
    "Banking, Financial Services and Insurance": "Banking & Finance",
    "Banking": "Banking & Finance",
    "Financial Services and Insurance": "Finance",
    "Business & Entrepreneurship": "Business",
    "Education & Learning": "Education",
    "Health & Wellness": "Health",
    "Housing & Shelter": "Housing",
    "IT & Communications": "IT & Comms",
    "Science, IT & Communications": "Science & IT",
    "Law & Justice": "Law & Justice",
    "Public Safety, Law & Justice": "Law & Justice",
    "Rural & Environment": "Rural & Environment",
    "Science": "Science",
    "Skills & Employment": "Skills & Employment",
    "Social welfare & Empowerment": "Social Welfare",
    "Sports & Culture": "Sports & Culture",
    "Transport & Infrastructure": "Transport",
    "Travel & Tourism": "Tourism",
    "Utility & Sanitation": "Utility",
    "Women and Child": "Women & Child",
}


def _category_display(categories: list[str]) -> list[str]:
    seen: set[str] = set()
    result: list[str] = []
    for c in categories:
        d = _DISPLAY_MAP.get(c, c[:20])
        if d not in seen:
            seen.add(d)
            result.append(d)
    return result or ["General"]


def _build_record(row: dict) -> dict:
    slug = row["slug"].strip()
    scheme_name = row["scheme_name"].strip()
    level = row["level"].strip().lower()

    categories = _parse_categories(row.get("schemeCategory", "") or "")
    tags = _parse_tags(row.get("tags", "") or "")

    # Detect state from text context for state-level schemes
    state: str | None = None
    if level == "state":
        state = detect_state_from_text(
            scheme_name,
            row.get("tags", "") or "",
            row.get("details", "") or "",
        )

    elig_text = (row.get("eligibility", "") or "").strip()
    rules_dict, unverified, missing = extract_eligibility_rules(
        elig_text, level, state, scheme_name
    )

    # Fill EligibilityRules defaults: all None means "not extracted"
    full_rules = {
        "min_age": None,
        "max_age": None,
        "max_annual_income": None,
        "gender": None,
        "caste": None,
        "states": None,
        "domicile": None,
        "occupation": None,
        "disability_required": None,
        "bpl_required": None,
        "marital_status": None,
    }
    full_rules.update(rules_dict)

    return {
        "scheme_id": slug,
        "scheme_name": scheme_name,
        "category": categories,
        "category_display": _category_display(categories),
        "level": level,
        "state": state,
        "benefit": (row.get("benefits", "") or "").strip(),
        "official_website": None,
        "eligibility_rules": full_rules,
        "unverified_criteria": unverified,
        "missing_information": missing,
        "required_documents": (row.get("documents") or None),
        "application_method": (row.get("application") or None),
        "tags": tags,
    }


def run(
    csv_path: Path = _CSV_PATH,
    dry_run: bool = False,
    limit: int | None = None,
    batch_size: int = 100,
) -> dict:
    """
    Full pipeline. Returns a summary dict.
    dry_run=True skips the Supabase upsert.
    limit=N processes only the first N non-protected rows (for testing).
    """
    print("Loading CSV …")
    rows = load_and_clean(csv_path)
    total_loaded = len(rows)
    print(f"  loaded   {total_loaded} rows")

    rows, removed = deduplicate(rows)
    unique_total = len(rows)
    print(f"  deduped  {removed} duplicates → {unique_total} unique slugs")

    # Separate protected vs new
    new_rows = [r for r in rows if r["slug"] not in _PROTECTED_IDS]
    protected_count = unique_total - len(new_rows)
    print(f"  protected {protected_count} curated schemes (will not overwrite)")
    print(f"  new rows to process: {len(new_rows)}")

    if limit is not None:
        new_rows = new_rows[:limit]
        print(f"  (limit={limit} applied)")

    print("Building records …")
    records = [_build_record(r) for r in new_rows]

    # Count how many have at least one structured rule
    with_rules = sum(
        1 for rec in records
        if any(
            v is not None and v != ["any"]
            for k, v in rec["eligibility_rules"].items()
            if k not in ("states",)  # states=["any"] is meaningful for central
        )
        or rec["eligibility_rules"].get("states") not in (None, ["any"])
    )
    print(f"  records with ≥1 extracted rule: {with_rules} / {len(records)}")

    if dry_run:
        print("dry_run=True — skipping Supabase upsert")
    else:
        # Load .env only at the point of actual Supabase access,
        # so importing this module never pollutes the test environment.
        try:
            from dotenv import load_dotenv
            load_dotenv()
        except ImportError:
            pass
        from backend.db.supabase import get_client
        client = get_client()
        print(f"Upserting {len(records)} records to '{_TABLE}' …")
        for i in range(0, len(records), batch_size):
            batch = records[i : i + batch_size]
            client.table(_TABLE).upsert(batch, on_conflict="scheme_id").execute()
            done = min(i + batch_size, len(records))
            print(f"  {done}/{len(records)}", end="\r")
        print()

        # Verify total
        check = client.table(_TABLE).select("scheme_id", count="exact").execute()
        total_in_db = check.count if hasattr(check, "count") and check.count else len(check.data)
        print(f"Total rows in '{_TABLE}': {total_in_db}")

    return {
        "total_csv_rows": total_loaded,
        "unique_slugs": unique_total,
        "duplicates_removed": removed,
        "protected_skipped": protected_count,
        "new_imported": len(records),
        "with_structured_rules": with_rules,
        "total_in_db": unique_total if not dry_run else None,
    }


if __name__ == "__main__":
    from dotenv import load_dotenv
    load_dotenv()

    parser = argparse.ArgumentParser(description="Ingest full Kaggle dataset into seed_schemes")
    parser.add_argument("--dry-run", action="store_true", help="Skip Supabase upsert")
    parser.add_argument("--limit", type=int, default=None, help="Only import first N new schemes")
    parser.add_argument("--csv", default=str(_CSV_PATH), help="Path to CSV")
    args = parser.parse_args()

    result = run(
        csv_path=Path(args.csv),
        dry_run=args.dry_run,
        limit=args.limit,
    )
    print("\n=== SUMMARY ===")
    for k, v in result.items():
        print(f"  {k}: {v}")
