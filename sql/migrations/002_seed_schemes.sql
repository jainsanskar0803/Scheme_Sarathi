-- Migration 002: seed_schemes
-- Run once in the Supabase SQL editor.
-- Mirrors the structure of data/seed_schemes.json exactly.
-- Populated by scripts/seed_supabase.py; never modified at runtime.

CREATE TABLE IF NOT EXISTS seed_schemes (
    scheme_id           TEXT         PRIMARY KEY,
    scheme_name         TEXT         NOT NULL,
    category            JSONB        NOT NULL DEFAULT '[]',
    category_display    JSONB        NOT NULL DEFAULT '[]',
    level               TEXT         NOT NULL CHECK (level IN ('central', 'state')),
    state               TEXT,
    benefit             TEXT         NOT NULL,
    official_website    TEXT,
    eligibility_rules   JSONB        NOT NULL DEFAULT '{}',
    unverified_criteria JSONB        NOT NULL DEFAULT '[]',
    missing_information JSONB        NOT NULL DEFAULT '[]',
    required_documents  TEXT,
    application_method  TEXT,
    tags                JSONB        NOT NULL DEFAULT '[]',
    created_at          TIMESTAMPTZ  NOT NULL DEFAULT NOW()
);

-- Index for rule engine access
CREATE INDEX IF NOT EXISTS idx_seed_schemes_level
    ON seed_schemes (level);

CREATE INDEX IF NOT EXISTS idx_seed_schemes_state
    ON seed_schemes (state);

CREATE INDEX IF NOT EXISTS idx_seed_schemes_rules
    ON seed_schemes USING GIN (eligibility_rules);
