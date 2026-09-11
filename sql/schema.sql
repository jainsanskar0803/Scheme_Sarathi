-- Scheme Sarathi: schemes table
-- Run once in the Supabase SQL editor before ingestion.
--
-- Column presence policy:
--   Columns sourced from the CSV are NOT NULL where the CSV has no gaps.
--   Columns not present in the CSV are NULL and populated by enrichment steps.

CREATE TABLE IF NOT EXISTS schemes (
    -- Identifiers
    id                  UUID        PRIMARY KEY DEFAULT gen_random_uuid(),
    slug                TEXT        NOT NULL UNIQUE,

    -- Names
    scheme_name         TEXT        NOT NULL,
    hindi_name          TEXT,                          -- not in CSV

    -- Description
    details             TEXT        NOT NULL,

    -- Classification
    scheme_categories   TEXT[]      NOT NULL DEFAULT '{}',
    tags                TEXT[]      NOT NULL DEFAULT '{}',
    level               TEXT        NOT NULL CHECK (level IN ('central', 'state')),
    state               TEXT,                          -- not in CSV; set for state-level schemes

    -- Beneficiary
    beneficiary         TEXT,                          -- not in CSV

    -- What the scheme provides
    benefits            TEXT        NOT NULL,

    -- Eligibility
    eligibility_text    TEXT        NOT NULL,          -- original prose, never modified
    eligibility_rules   JSONB,                         -- not in CSV; set by extract_eligibility script

    -- How to apply
    application         TEXT,                          -- 2 rows missing in CSV
    documents           TEXT,                          -- 10 rows missing in CSV

    -- External references
    official_website    TEXT,                          -- not in CSV
    source              TEXT,                          -- not in CSV
    last_verified_date  DATE,                          -- not in CSV

    -- Audit
    created_at          TIMESTAMPTZ NOT NULL DEFAULT NOW()
);

-- Indexes for the rule engine and frontend filters
CREATE INDEX IF NOT EXISTS idx_schemes_level      ON schemes (level);
CREATE INDEX IF NOT EXISTS idx_schemes_state      ON schemes (state);
CREATE INDEX IF NOT EXISTS idx_schemes_cats       ON schemes USING GIN (scheme_categories);
CREATE INDEX IF NOT EXISTS idx_schemes_tags       ON schemes USING GIN (tags);
CREATE INDEX IF NOT EXISTS idx_schemes_rules      ON schemes USING GIN (eligibility_rules);