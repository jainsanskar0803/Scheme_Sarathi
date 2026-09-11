"""
Generates data/seed_schemes.json from:
  - updated_data.csv  (scheme text, documents, application)
  - VERIFIED_RULES    (verified eligibility rules from previous audit)
  - AUDIT_META        (unverified criteria and missing fields per scheme)

Nothing is invented.  Unverified and missing entries are documentation only —
they are never passed to the rule engine.
"""
from __future__ import annotations

import csv
import json
import re
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

from scripts.seed_schemes import VERIFIED_RULES

CSV_PATH   = Path(__file__).resolve().parents[1] / "updated_data.csv"
OUTPUT     = Path(__file__).resolve().parents[1] / "data" / "seed_schemes.json"

# ---------------------------------------------------------------------------
# Audit metadata — sourced from the eligibility text analysis
# ---------------------------------------------------------------------------
# "unverified": criteria present in the eligibility text that cannot be
#               expressed by the current EligibilityRules model.
# "missing":    EligibilityRules fields that are simply absent from the text.

AUDIT_META: dict[str, dict] = {
    "nmmss": {
        "scheme_state": None,   # central — applies to all states
        "unverified": [
            "Applicant must be entering class 9th as a regular student in a government, "
            "government-aided, or local body school",
            "Minimum 55% marks in Class 7th examination (relaxable by 5% for SC/ST students)",
            "Must pass both MAT and SAT tests with at least 40% aggregate marks "
            "(32% for SC/ST students)",
            "Cannot hold any other Central Government scholarship simultaneously",
        ],
        "missing": [
            "min_age: not stated — eligibility is grade-based (class 9th), not age-based",
            "max_age: not stated",
            "gender: not mentioned in eligibility text",
            "domicile: not mentioned",
            "occupation: not stated as a rule — student status is implied by grade requirement",
            "disability_required: not mentioned",
            "bpl_required: not mentioned",
            "marital_status: not mentioned",
        ],
    },

    "post-st": {
        "scheme_state": None,
        "unverified": [
            "Applicant must have passed Matriculation, Higher Secondary, or equivalent",
            "Must be enrolled in a recognized post-matriculation/post-secondary institution",
            "Cannot hold another scholarship/stipend simultaneously under this scheme",
            "Employed students must take leave without pay to qualify as full-time students",
        ],
        "missing": [
            "min_age: not stated",
            "max_age: not stated",
            "gender: not mentioned",
            "domicile: not mentioned",
            "occupation: student status implied but not stated as rule",
            "disability_required: not mentioned",
            "bpl_required: not mentioned",
            "marital_status: not mentioned",
        ],
    },

    "pm-daksh": {
        "scheme_state": None,
        "unverified": [
            "Income limit is caste-conditional: OBC/EWS must have family income "
            "< ₹3,00,000; SC/DNT/Safai Mitras have no income limit — "
            "conditional logic not supported by current EligibilityRules",
            "DNT (Denotified & Nomadic Tribes) is an eligible group not covered "
            "by the current caste vocabulary",
            "Safai Mitras (including Waste Pickers) are an occupational target group, "
            "not a caste category",
            "Must register on Skill India Digital Hub (SIDH)",
            "Must possess a valid Aadhaar card",
            "Biometric attendance > 70% required during training",
        ],
        "missing": [
            "max_annual_income: omitted — income criterion is caste-conditional "
            "and cannot be represented as a single threshold",
            "gender: not mentioned",
            "domicile: not mentioned",
            "disability_required: not mentioned",
            "bpl_required: not mentioned",
            "marital_status: not mentioned",
            "occupation: target groups described but not a simple field value",
        ],
    },

    "sys": {
        "scheme_state": "Haryana",
        "unverified": [
            "Applicant must be registered in the Live Register of the concerned "
            "Employment Exchange in Haryana",
            "10+2 must have been passed as a regular student from a recognized school "
            "in Haryana or UT Chandigarh",
            "Graduate/Post-graduate degree must be from a regular course from a "
            "recognized university in Haryana, UT Chandigarh, or NCT Delhi",
            "Applicant must not be in any employment (public/private/self-employed)",
            "Applicant must not be a regular student under a full-time course",
            "Honorarium paid for a maximum of 3 years or until age 35, whichever is earlier",
        ],
        "missing": [
            "gender: not mentioned",
            "caste: not mentioned — no caste restriction stated",
            "domicile: not mentioned",
            "disability_required: not mentioned",
            "bpl_required: not mentioned",
            "marital_status: not mentioned",
        ],
    },

    "pmay-g": {
        "scheme_state": None,
        "unverified": [
            "Beneficiary must be houseless or living in a house with kutcha walls "
            "and kutcha roof (zero, one, or two rooms) — housing deprivation criterion "
            "not in EligibilityRules model",
            "Eligibility is determined from SECC 2011 data — applicants must appear "
            "in SECC database",
            "Priority is assigned by a multi-layered deprivation score across "
            "houselessness, rooms, and socio-economic parameters",
            "SC/ST households receive 60% of state targets (quota, not eligibility gate)",
            "15% of funds earmarked for Minorities at the national level (quota)",
        ],
        "missing": [
            "min_age: not stated as eligibility criterion",
            "max_age: not stated",
            "max_annual_income: not stated — eligibility is SECC-data based, not income-based",
            "gender: not a hard gate (female-headed households get priority score only)",
            "caste: not a hard gate (SC/ST/Minorities receive quota allocation, not exclusion of others)",
            "occupation: not mentioned as eligibility criterion",
            "disability_required: disability adds deprivation score but is not a gate",
            "bpl_required: not stated as a formal criterion",
            "marital_status: widows mentioned as tie-breaker, not as eligibility criterion",
        ],
    },

    "daay": {
        "scheme_state": "Gujarat",
        "unverified": [
            "Applicant or any family member must not already own a residential home "
            "or have their own plot for residence",
            "Applicant or family must not have previously received benefits under "
            "any other government housing scheme",
            "Construction of house must be completed within 2 years of first instalment",
            "Beneficiary must construct a toilet (mandatory condition for assistance)",
        ],
        "missing": [
            "max_age: not stated",
            "gender: not mentioned",
            "domicile: separate rural/urban upper limits mentioned but both ₹6,00,000 "
            "— no eligibility distinction by domicile",
            "disability_required: not mentioned",
            "bpl_required: 'below poverty line' mentioned descriptively but not as a "
            "hard eligibility gate",
            "marital_status: not mentioned",
            "occupation: not mentioned",
        ],
    },

    "ab-pmjay": {
        "scheme_state": None,
        "unverified": [
            "Rural eligibility: family must meet at least one of six SECC deprivation "
            "criteria (kutcha house, no adult 16-59, female-headed with no adult male, "
            "disabled member with no able-bodied adult, SC/ST household, landless "
            "casual labour household)",
            "Urban eligibility: worker must belong to one of 11 occupational categories "
            "(ragpicker, beggar, domestic worker, street vendor, construction worker, "
            "sweeper, home-based artisan, transport worker, shop worker, electrician/mechanic, "
            "washer-man/chowkidar)",
            "Automatic inclusion for: destitute/living on alms, manual scavenger households, "
            "primitive tribal groups, legally released bonded labour",
        ],
        "missing": [
            "min_age: not stated",
            "max_age: not stated",
            "max_annual_income: not stated — eligibility is SECC deprivation-criteria based",
            "gender: not a hard gate",
            "caste: SC/ST household is one of the six SECC criteria but not the only gate",
            "domicile: scheme has rural and urban criteria — both are eligible paths",
            "occupation: urban eligibility is occupation-based but spans 11 categories "
            "not reducible to a single occupation value",
            "disability_required: disability is one of six SECC criteria, not a standalone gate",
            "bpl_required: not stated formally",
            "marital_status: not mentioned",
        ],
    },

    "gms": {
        "scheme_state": "Goa",
        "unverified": [
            "Applicant must have been residing in Goa for at least 15 years",
            "Applicant must appear in the voters' list",
            "Applicant must hold a permanent ration card",
            "Treatment required must not be available in a Goa government hospital "
            "(except NICU, Ventilatory Support, Kidney Dialysis — patient may opt for any empanelled hospital)",
            "Applicant must suffer from one of the specific listed ailments: dialysis, "
            "CAPD, plastic surgery, ICU, NICU, PICU, CABG/PTCA, open heart surgery, "
            "kidney transplant, neuro surgery, radiotherapy/chemotherapy, cochlear implant, "
            "cerebral palsy, skeletal deformities, bone marrow transplant",
            "Retired state government employees are exempt from the income criterion",
        ],
        "missing": [
            "min_age: not mentioned",
            "max_age: not mentioned",
            "gender: not mentioned",
            "caste: not mentioned — no caste restriction",
            "domicile: not mentioned",
            "occupation: not mentioned",
            "disability_required: not mentioned",
            "bpl_required: not mentioned",
            "marital_status: not mentioned",
        ],
    },

    "dayalu": {
        "scheme_state": "Haryana",
        "unverified": [
            "Applicant must possess a Family ID / Parivar Pehchaan Patra (PPP) number",
            "Claim must relate to a death (natural or accidental) or permanent disability "
            "(≥ 70% from accident, certified by Medical Authority) — event-triggered, "
            "not a standing eligibility criterion",
            "Scheme is effective from 1st April 2023 — claims for events before this date "
            "are not accepted",
            "Workers registered under HLWB or HBOCW are handled by those boards first; "
            "DAYALU pays only if the board rejects the claim",
        ],
        "missing": [
            "gender: not mentioned",
            "caste: not mentioned — no caste restriction",
            "domicile: not mentioned",
            "occupation: construction workers and industrial labour mentioned as examples "
            "but the scheme is not restricted to them",
            "disability_required: disability is a triggering event (not a pre-condition "
            "for eligibility)",
            "bpl_required: not mentioned",
            "marital_status: not mentioned",
        ],
    },

    "subhadra": {
        "scheme_state": "Odisha",
        "unverified": [
            "Applicant covered under NFSA/SFSS card qualifies regardless of income — "
            "income criterion of ₹2,50,000 applies only to non-NFSA/SFSS applicants "
            "(conditional rule, simplified to single income threshold in eligibility_rules)",
            "Applicant must not be a current/former MP or MLA",
            "Applicant must not be an Income Tax Payee",
            "Applicant must not be a regular or contractual government employee",
            "Applicant must not own a 4-wheeler motor vehicle (tractors and small commercial "
            "vehicles exempt)",
            "Applicant must not be an elected representative in a ULB or PRI "
            "(Ward Member/Councillor is exempt)",
            "Applicant must not already receive government financial assistance ≥ ₹1,500/month",
        ],
        "missing": [
            "caste: not mentioned — scheme is universal for women of Odisha",
            "domicile: not mentioned",
            "occupation: not mentioned",
            "disability_required: not mentioned",
            "bpl_required: NFSA/SFSS card is an alternate eligibility path, "
            "not equivalent to a BPL card",
            "marital_status: not mentioned",
        ],
    },

    "wbrupashree": {
        "scheme_state": "West Bengal",
        "unverified": [
            "Proposed groom must have attained the age of 21 years — third-party "
            "criterion, not verifiable from applicant's profile",
            "Applicant must have completed at least 10th standard or equivalent education",
            "Scheme applies only to families with one or two daughters",
            "Applicant must have an active sole-holder bank account with IFS and MICR codes",
            "Application must be submitted at least 30 days before and within 1 year "
            "after the marriage date",
        ],
        "missing": [
            "max_age: not stated",
            "caste: not mentioned — no caste restriction",
            "domicile: not mentioned",
            "occupation: not mentioned",
            "disability_required: not mentioned",
            "bpl_required: not mentioned",
        ],
    },

    "mssc": {
        "scheme_state": None,
        "unverified": [
            "Applicant must be an Indian citizen",
            "Minor girl account can be opened by a guardian on her behalf",
            "Maximum deposit limit of ₹2,00,000 per account or across all accounts held",
            "Time gap of at least 3 months required between opening successive accounts",
        ],
        "missing": [
            "min_age: no minimum age stated — guardian can open for a minor girl",
            "max_age: explicitly no upper age limit",
            "max_annual_income: not mentioned — this is a savings scheme, not means-tested",
            "caste: not mentioned — no caste restriction",
            "domicile: not mentioned",
            "occupation: not mentioned",
            "disability_required: not mentioned",
            "bpl_required: not mentioned",
            "marital_status: not mentioned",
        ],
    },

    "dalit-bandhu": {
        "scheme_state": "Telangana",
        "unverified": [
            "Applicant must have passed at least the 10th standard",
            "Applicant must have a viable business plan or entrepreneurial idea",
            "Family must not own more than 3 acres of agricultural land or "
            "more than one residential house",
            "Applicant must not have previously availed any government loan or subsidy",
            "Applicant must contribute 10% of the project cost",
            "Applicant must not have a criminal record or conviction",
            "Applicant must possess an Aadhaar card",
        ],
        "missing": [
            "gender: not mentioned — no gender restriction",
            "domicile: not mentioned",
            "occupation: applicant is expected to start a business; "
            "no specific prior occupation requirement stated",
            "disability_required: not mentioned",
            "bpl_required: not mentioned as a formal criterion",
            "marital_status: not mentioned",
        ],
    },

    "ysrrb": {
        "scheme_state": "Andhra Pradesh",
        "unverified": [
            "Land owner farmer: must own cultivable land as recorded in land records",
            "Landless tenant farmer: must have a lease agreement for minimum cultivable area "
            "(1.0 acre for general crops; 0.5 acre for vegetables/flowers; "
            "0.1 acre for Betel Vine)",
            "Tenant farmer must not own any agricultural/horticulture/sericulture land",
            "In case of joint holdings, benefit goes to the family member with the "
            "highest land quantum",
            "Only one tenant/cultivator per land-owner family receives benefits; "
            "SC/ST/BC/Minority tenants are prioritised over general category tenants",
        ],
        "missing": [
            "min_age: not stated",
            "max_age: not stated",
            "max_annual_income: not stated",
            "gender: not mentioned — land-record holder (any gender) receives benefit",
            "caste: not a hard gate; SC/ST/BC/Minority tenants receive priority, "
            "not exclusivity",
            "domicile: not stated explicitly; agriculture implies rural",
            "disability_required: not mentioned",
            "bpl_required: not mentioned",
            "marital_status: not mentioned",
        ],
    },
}

# ---------------------------------------------------------------------------
# Category → short name map (for display)
# ---------------------------------------------------------------------------

CATEGORY_SHORT: dict[str, str] = {
    "Agriculture,Rural & Environment":        "Agriculture",
    "Education & Learning":                   "Education",
    "Social welfare & Empowerment":           "Social Welfare",
    "Business & Entrepreneurship":            "Entrepreneurship",
    "Women and Child":                        "Women & Child",
    "Health & Wellness":                      "Health",
    "Skills & Employment":                    "Employment",
    "Banking,Financial Services and Insurance": "Financial Services",
    "Housing & Shelter":                      "Housing",
    "Science, IT & Communications":           "Science & IT",
    "Sports & Culture":                       "Sports & Culture",
    "Transport & Infrastructure":             "Infrastructure",
    "Utility & Sanitation":                   "Sanitation",
    "Travel & Tourism":                       "Tourism",
    "Public Safety,Law & Justice":            "Public Safety",
}

# ---------------------------------------------------------------------------
# Text cleaning
# ---------------------------------------------------------------------------

_ZWS = re.compile(r"[​‌‍­﻿]")

def _clean(text: str) -> str:
    return re.sub(r"[ \t]+", " ", _ZWS.sub("", text)).strip()


def _parse_cats(raw: str) -> list[str]:
    protected = raw.replace("Science, IT & Communications", "\x00SCI_IT\x00")
    parts = [p.strip() for p in protected.split(", ") if p.strip()]
    return [p.replace("\x00SCI_IT\x00", "Science, IT & Communications") for p in parts]


def _parse_tags(raw: str) -> list[str]:
    return [t.strip() for t in raw.split(",") if t.strip()]


# ---------------------------------------------------------------------------
# Main builder
# ---------------------------------------------------------------------------

def build() -> list[dict]:
    with open(CSV_PATH, newline="", encoding="utf-8") as fh:
        raw_rows = {row["slug"]: row for row in csv.DictReader(fh)}

    records: list[dict] = []

    for slug, rules in VERIFIED_RULES.items():
        row = raw_rows[slug]
        meta = AUDIT_META[slug]
        cats = _parse_cats(_clean(row["schemeCategory"]))

        record = {
            "scheme_id": slug,
            "scheme_name": _clean(row["scheme_name"]),
            "category": cats,
            "category_display": [CATEGORY_SHORT.get(c, c) for c in cats],
            "level": row["level"].strip().lower(),
            "state": meta["scheme_state"],

            # What the scheme provides — from CSV, unchanged
            "benefit": _clean(row["benefits"]),

            # Not in CSV — never invented
            "official_website": None,

            # Verified machine-readable rules (only fields with non-None values
            # are actively enforced by the rule engine)
            "eligibility_rules": rules.model_dump(),

            # Criteria present in the eligibility text but not modelable by
            # current EligibilityRules — for display only, never evaluated
            "unverified_criteria": meta["unverified"],

            # EligibilityRules fields absent from the eligibility text entirely
            "missing_information": meta["missing"],

            # From CSV — cleaned but not altered
            "required_documents": _clean(row["documents"]) if row.get("documents") else None,
            "application_method": _clean(row["application"]) if row.get("application") else None,

            # Tags from CSV
            "tags": _parse_tags(_clean(row["tags"])),
        }
        records.append(record)

    return records


if __name__ == "__main__":
    records = build()
    OUTPUT.parent.mkdir(parents=True, exist_ok=True)
    with open(OUTPUT, "w", encoding="utf-8") as fh:
        json.dump(records, fh, ensure_ascii=False, indent=2)
    print(f"Written {len(records)} schemes → {OUTPUT}")