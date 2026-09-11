"""
MVP seed data — 14 hand-verified schemes spanning all major categories.

Eligibility rules are populated ONLY from text explicitly present in the
CSV 'eligibility' column.  Nothing is invented.

Every field is tagged:
  VERIFIED   — value read directly from the eligibility text
  UNVERIFIED — present in text but cannot be modelled by current EligibilityRules
  MISSING    — not mentioned anywhere in the eligibility text

Run with --dry-run to inspect output without hitting Supabase.
Run without flags to upsert into the 'schemes' table.
"""

from __future__ import annotations

import csv
import json
import re
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

from scripts.ingest import _clean_text, _parse_categories, _parse_tags, _normalise_level
from backend.models.scheme import EligibilityRules, Scheme

CSV_PATH = Path(__file__).resolve().parents[1] / "updated_data.csv"

# ---------------------------------------------------------------------------
# Verified eligibility rules — one entry per selected scheme
#
# Field-level annotations (in comments) are the audit trail.
# None  = MISSING: field not mentioned in the eligibility text.
# ["any"] = VERIFIED: text confirms no restriction on this dimension.
# ---------------------------------------------------------------------------

VERIFIED_RULES: dict[str, EligibilityRules] = {

    # ------------------------------------------------------------------
    # EDUCATION
    # ------------------------------------------------------------------

    "nmmss": EligibilityRules(
        # VERIFIED: "parental income should be ₹3,50,000 per annum"
        max_annual_income=350_000,
        # VERIFIED: central scheme — no state restriction
        states=["any"],
        # VERIFIED: no caste exclusion; SC/ST get marks relaxation but are not excluded
        caste=["any"],
        # MISSING: no age range stated (grade-based, not age-based)
        min_age=None,
        max_age=None,
        # MISSING: gender not mentioned
        gender=None,
        # MISSING: domicile not mentioned
        domicile=None,
        # MISSING: disability not mentioned
        disability_required=None,
        # MISSING: BPL not mentioned
        bpl_required=None,
        # MISSING: marital status not mentioned
        marital_status=None,
        # UNVERIFIED: must be "regular student entering class 9th" — grade/school type
        #             not representable in current EligibilityRules
        occupation=None,
    ),

    "post-st": EligibilityRules(
        # VERIFIED: "only those candidates who belong to Scheduled Tribes"
        caste=["ST"],
        # VERIFIED: "income from all sources does not exceed ₹2,00,000/- per annum"
        max_annual_income=200_000,
        # VERIFIED: "scholarships are open to nationals of India" — central scheme
        states=["any"],
        # MISSING: gender not mentioned
        gender=None,
        # MISSING: age not stated
        min_age=None,
        max_age=None,
        # MISSING: domicile not mentioned
        domicile=None,
        # MISSING: disability not mentioned
        disability_required=None,
        # MISSING: BPL not mentioned
        bpl_required=None,
        # MISSING: marital status not mentioned
        marital_status=None,
        # UNVERIFIED: "must have passed Matriculation" — qualification, not in model
        occupation=None,
    ),

    # ------------------------------------------------------------------
    # EMPLOYMENT / SKILLS
    # ------------------------------------------------------------------

    "pm-daksh": EligibilityRules(
        # VERIFIED: "aged between 18 and 45 years"
        min_age=18,
        max_age=45,
        # VERIFIED: "SC, OBC, EWS" explicitly listed
        # NOTE: DNT (Denotified & Nomadic Tribes) and Safai Mitras are
        # additional target groups not in our caste vocabulary — UNVERIFIED
        caste=["SC", "OBC", "EWS"],
        # VERIFIED: central scheme
        states=["any"],
        # MISSING: gender not mentioned
        gender=None,
        # UNVERIFIED: income limit is conditional on caste
        #   OBC/EWS: < ₹3,00,000 | SC/DNT/Safai Mitras: no limit
        #   Cannot model conditional rules — omitted
        max_annual_income=None,
        # MISSING: domicile not mentioned
        domicile=None,
        # MISSING: disability not mentioned
        disability_required=None,
        # MISSING: BPL not mentioned
        bpl_required=None,
        # MISSING: marital status not mentioned
        marital_status=None,
        # UNVERIFIED: must register on Skill India Digital Hub, Aadhaar required
        occupation=None,
    ),

    "sys": EligibilityRules(
        # VERIFIED: "domicile of Haryana"
        states=["Haryana"],
        # VERIFIED: "18 to 35 years for 10+2 and 21 to 35 years for graduate/post-graduate"
        # Using the lower bound (18) and common upper bound (35)
        min_age=18,
        max_age=35,
        # VERIFIED: "annual family income of applicant shall not exceed ₹3,00,000/-"
        max_annual_income=300_000,
        # MISSING: gender not mentioned
        gender=None,
        # MISSING: caste not mentioned (no caste restriction)
        caste=None,
        # MISSING: domicile not mentioned
        domicile=None,
        # MISSING: disability not mentioned
        disability_required=None,
        # MISSING: BPL not mentioned
        bpl_required=None,
        # MISSING: marital status not mentioned
        marital_status=None,
        # UNVERIFIED: must be registered in Employment Exchange; must be unemployed;
        #   must have 10+2 / graduation — qualification criteria, not in model
        occupation=None,
    ),

    # ------------------------------------------------------------------
    # HOUSING
    # ------------------------------------------------------------------

    "pmay-g": EligibilityRules(
        # VERIFIED: "Gramin" = rural; scheme specifically for rural houseless households
        domicile=["rural"],
        # VERIFIED: central scheme
        states=["any"],
        # MISSING: gender not a hard gate (female-headed households get priority score)
        gender=None,
        # MISSING: income not stated as eligibility criterion (SECC-data based)
        max_annual_income=None,
        # MISSING: age not mentioned as gate
        min_age=None,
        max_age=None,
        # MISSING: caste not a hard gate (SC/ST get quota allocation, not exclusion)
        caste=None,
        # MISSING: disability not mentioned as eligibility gate
        disability_required=None,
        # MISSING: BPL not stated
        bpl_required=None,
        # MISSING: marital status not mentioned
        marital_status=None,
        # UNVERIFIED: must be houseless / kutcha walls+roof (housing deprivation score);
        #   must be in SECC data — not representable in current EligibilityRules
        occupation=None,
    ),

    "daay": EligibilityRules(
        # VERIFIED: "native of Gujarat"
        states=["Gujarat"],
        # VERIFIED: "belong to the Scheduled Caste category"
        caste=["SC"],
        # VERIFIED: "age of the beneficiary will be at least 21 years"
        min_age=21,
        # VERIFIED: "annual income should not exceed ₹6,00,000/-"
        max_annual_income=600_000,
        # MISSING: gender not mentioned
        gender=None,
        # MISSING: max age not stated
        max_age=None,
        # MISSING: domicile not stated (separate limits for rural/urban, same ceiling)
        domicile=None,
        # MISSING: disability not mentioned
        disability_required=None,
        # MISSING: BPL mentioned as preference ("below poverty line") but not hard gate
        bpl_required=None,
        # MISSING: marital status not mentioned
        marital_status=None,
        # UNVERIFIED: must not own a residential home; must not have received housing
        #   benefit before — ownership criteria, not in model
        occupation=None,
    ),

    # ------------------------------------------------------------------
    # HEALTH
    # ------------------------------------------------------------------

    "ab-pmjay": EligibilityRules(
        # VERIFIED: central scheme — Pradhan Mantri Jan Arogya Yojana
        states=["any"],
        # MISSING: gender not mentioned as gate
        gender=None,
        # MISSING: age not mentioned as gate
        min_age=None,
        max_age=None,
        # MISSING: income not mentioned (SECC deprivation-criteria based)
        max_annual_income=None,
        # MISSING: caste not a hard gate
        caste=None,
        # MISSING: domicile — scheme has separate rural/urban criteria but both eligible
        domicile=None,
        # MISSING: disability not mentioned as gate
        disability_required=None,
        # MISSING: BPL not stated as formal gate
        bpl_required=None,
        # MISSING: marital status not mentioned
        marital_status=None,
        # UNVERIFIED: rural — SECC deprivation criteria (kutcha house, no adult 16-59, etc.)
        #   urban — 11 occupational categories (ragpicker, domestic worker, etc.)
        #   Complex multi-criteria eligibility not representable in current EligibilityRules
        occupation=None,
    ),

    "gms": EligibilityRules(
        # VERIFIED: "permanent resident of Goa"
        states=["Goa"],
        # VERIFIED: "income of the applicant should be less than ₹1,50,000/- per annum"
        # NOTE: retired state government employees are exempt from this income criterion
        max_annual_income=150_000,
        # MISSING: gender not mentioned
        gender=None,
        # MISSING: age not mentioned
        min_age=None,
        max_age=None,
        # MISSING: caste not mentioned
        caste=None,
        # MISSING: domicile not mentioned
        domicile=None,
        # MISSING: disability not mentioned
        disability_required=None,
        # MISSING: BPL — ration card required but not BPL card specifically
        bpl_required=None,
        # MISSING: marital status not mentioned
        marital_status=None,
        # UNVERIFIED: must require treatment not available in Goa govt hospital;
        #   must suffer from one of the listed specific ailments — medical criteria
        occupation=None,
    ),

    "dayalu": EligibilityRules(
        # VERIFIED: "must be a resident of Haryana"
        states=["Haryana"],
        # VERIFIED: "family income of the beneficiary must be less than ₹1.80 lakh per annum"
        max_annual_income=180_000,
        # VERIFIED: "above 6 years and up to 60 years of age"
        min_age=6,
        max_age=60,
        # MISSING: gender not mentioned
        gender=None,
        # MISSING: caste not mentioned
        caste=None,
        # MISSING: domicile not mentioned
        domicile=None,
        # MISSING: disability not a gate (it's one of the triggering events, not eligibility)
        disability_required=None,
        # MISSING: BPL not mentioned
        bpl_required=None,
        # MISSING: marital status not mentioned
        marital_status=None,
        # UNVERIFIED: claim must be for death or permanent disability (≥ 70% from accident);
        #   must have Family ID / Parivar Pehchaan Patra — event-based, not in model
        occupation=None,
    ),

    # ------------------------------------------------------------------
    # WOMEN / CHILD
    # ------------------------------------------------------------------

    "subhadra": EligibilityRules(
        # VERIFIED: "must be a resident of Odisha"
        states=["Odisha"],
        # VERIFIED: text uses "her" throughout; SUBHADRA is a women-only scheme
        gender=["female"],
        # VERIFIED: "age should be 21 years or more"
        min_age=21,
        # VERIFIED: "less than 60 years" → effective max is 59
        max_age=59,
        # VERIFIED: income path for non-NFSA holders: "family income is not more than ₹2,50,000/-"
        # NOTE: NFSA/SFSS card holders qualify regardless of income — conditional rule
        max_annual_income=250_000,
        # MISSING: caste not mentioned — scheme is universal for women of Odisha
        caste=None,
        # MISSING: domicile not mentioned
        domicile=None,
        # MISSING: disability not mentioned
        disability_required=None,
        # UNVERIFIED: NFSA/SFSS card is an alternative eligibility path, not BPL card
        bpl_required=None,
        # MISSING: marital status not mentioned
        marital_status=None,
        occupation=None,
    ),

    "wbrupashree": EligibilityRules(
        # VERIFIED: "family residing in West Bengal" / "resident of West Bengal"
        states=["West Bengal"],
        # VERIFIED: "any woman who proposes to be married"
        gender=["female"],
        # VERIFIED: "attained the age of 18 years"
        min_age=18,
        # VERIFIED: "family's annual income should be less than or equal to Rs. 1.5 lakhs"
        max_annual_income=150_000,
        # VERIFIED: "unmarried on the date of submitting her application"
        #           "proposed marriage is her first marriage"
        marital_status=["single"],
        # MISSING: caste not mentioned — no caste restriction
        caste=None,
        # MISSING: max age not stated
        max_age=None,
        # MISSING: domicile not mentioned
        domicile=None,
        # MISSING: disability not mentioned
        disability_required=None,
        # MISSING: BPL not mentioned
        bpl_required=None,
        occupation=None,
        # UNVERIFIED: groom must be ≥ 21; family ≤ 2 daughters; 10th standard passed;
        #   active sole-holder bank account — criteria about other parties / qualifications
    ),

    # ------------------------------------------------------------------
    # FINANCIAL ASSISTANCE
    # ------------------------------------------------------------------

    "mssc": EligibilityRules(
        # VERIFIED: "only for women and girl children" / "Any Individual Woman can apply"
        gender=["female"],
        # VERIFIED: central scheme — Post Office Savings
        states=["any"],
        # VERIFIED: "no upper age limit and women of all ages can avail the benefits"
        # (no minimum age stated for adult women; guardian can open for minor girl)
        # MISSING: min_age and max_age not stated
        min_age=None,
        max_age=None,
        # MISSING: income not mentioned
        max_annual_income=None,
        # MISSING: caste not mentioned
        caste=None,
        # MISSING: domicile not mentioned
        domicile=None,
        # MISSING: disability not mentioned
        disability_required=None,
        # MISSING: BPL not mentioned
        bpl_required=None,
        # MISSING: marital status not mentioned
        marital_status=None,
        occupation=None,
    ),

    "dalit-bandhu": EligibilityRules(
        # VERIFIED: "only to families belonging to the SC community"
        caste=["SC"],
        # VERIFIED: "must be a resident of Telangana"
        states=["Telangana"],
        # VERIFIED: "annual income of less than Rs. 2.5 lakh"
        max_annual_income=250_000,
        # VERIFIED: "between the ages of 25 and 50"
        min_age=25,
        max_age=50,
        # MISSING: gender not mentioned — no restriction
        gender=None,
        # MISSING: domicile not mentioned
        domicile=None,
        # MISSING: disability not mentioned
        disability_required=None,
        # MISSING: BPL not mentioned as formal criterion
        bpl_required=None,
        # MISSING: marital status not mentioned
        marital_status=None,
        # UNVERIFIED: must have passed 10th standard; must have viable business plan;
        #   must not own > 3 acres land; must not have prior govt loan/subsidy;
        #   must contribute 10% project cost — conditions outside current model
        occupation=None,
    ),

    # ------------------------------------------------------------------
    # AGRICULTURE
    # ------------------------------------------------------------------

    "ysrrb": EligibilityRules(
        # VERIFIED: State-level scheme — Andhra Pradesh (YSR = Y.S. Rajasekhara Reddy)
        states=["Andhra Pradesh"],
        # VERIFIED: "landholder farmer families" / "landless cultivators/tenant farmers"
        occupation=["farmer"],
        # MISSING: gender not mentioned — land-record holder gets benefit
        gender=None,
        # MISSING: age not stated
        min_age=None,
        max_age=None,
        # MISSING: income not mentioned
        max_annual_income=None,
        # MISSING: caste not a gate (SC/ST/BC/Minority get priority for tenant slots)
        caste=None,
        # MISSING: domicile not stated (agriculture is implicitly rural)
        domicile=None,
        # MISSING: disability not mentioned
        disability_required=None,
        # MISSING: BPL not mentioned
        bpl_required=None,
        # MISSING: marital status not mentioned
        marital_status=None,
        # UNVERIFIED: must own cultivable land OR have lease agreement with min area;
        #   tenants must not own their own agricultural land — land-holding criteria
    ),
}

# ---------------------------------------------------------------------------
# Schemes with no verifiable rules at all (kept for display/search only)
# ---------------------------------------------------------------------------
# ab-pmjay and pmay-g have eligibility based on SECC deprivation scores and
# complex multi-criteria logic that cannot be mapped to current EligibilityRules.
# Their rules are set above with only the fields we can confirm.


# ---------------------------------------------------------------------------
# Loader: pull from CSV and combine with verified rules
# ---------------------------------------------------------------------------

def _load_csv() -> dict[str, dict]:
    with open(CSV_PATH, newline="", encoding="utf-8") as fh:
        reader = csv.DictReader(fh)
        rows = {row["slug"]: row for row in reader}
    return rows


def _strip_zws(text: str) -> str:
    return re.sub(r"[​‌‍­﻿]", "", text).strip()


def build_seed_schemes() -> list[Scheme]:
    raw = _load_csv()
    schemes: list[Scheme] = []

    for slug, rules in VERIFIED_RULES.items():
        row = raw.get(slug)
        if row is None:
            print(f"  [warn] slug {slug!r} not found in CSV — skipping")
            continue

        scheme = Scheme(
            slug=slug,
            scheme_name=_strip_zws(row["scheme_name"]),
            details=_strip_zws(row["details"]),
            benefits=_strip_zws(row["benefits"]),
            eligibility_text=_strip_zws(row["eligibility"]),
            application=_strip_zws(row["application"]) or None,
            documents=_strip_zws(row["documents"]) or None,
            level=_normalise_level(row["level"]),
            scheme_categories=_parse_categories(_strip_zws(row["schemeCategory"])),
            tags=_parse_tags(_strip_zws(row["tags"])),
            eligibility_rules=rules,
            # Fields not in CSV — left None intentionally
            hindi_name=None,
            state=None,
            beneficiary=None,
            official_website=None,
            source=None,
            last_verified_date=None,
        )
        schemes.append(scheme)

    return schemes


def upsert_to_supabase(schemes: list[Scheme]) -> None:
    from backend.db.supabase import get_client

    client = get_client()
    payload = []
    for s in schemes:
        d = s.model_dump()
        # Convert EligibilityRules to plain dict for JSONB column
        if d.get("eligibility_rules") is not None:
            d["eligibility_rules"] = s.eligibility_rules.model_dump()
        payload.append(d)

    client.table("schemes").upsert(payload, on_conflict="slug").execute()
    print(f"  upserted {len(payload)} seed schemes")


# ---------------------------------------------------------------------------
# CLI
# ---------------------------------------------------------------------------

if __name__ == "__main__":
    import argparse

    parser = argparse.ArgumentParser(description="Upsert MVP seed schemes into Supabase")
    parser.add_argument("--dry-run", action="store_true", help="Print JSON without upserting")
    args = parser.parse_args()

    schemes = build_seed_schemes()
    print(f"Built {len(schemes)} seed schemes")

    if args.dry_run:
        for s in schemes:
            print(f"\n--- {s.slug} ---")
            print(f"  name: {s.scheme_name[:70]}")
            print(f"  level: {s.level}")
            print(f"  categories: {s.scheme_categories}")
            rules = s.eligibility_rules
            verified = {k: v for k, v in rules.model_dump().items() if v is not None}
            missing = [k for k, v in rules.model_dump().items() if v is None]
            print(f"  VERIFIED rules: {json.dumps(verified, ensure_ascii=False)}")
            print(f"  MISSING fields: {missing}")
    else:
        upsert_to_supabase(schemes)