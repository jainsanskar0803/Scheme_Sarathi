-- Migration 001: interview_sessions
-- Run once in the Supabase SQL editor.
-- Stores citizen profile sessions; profile_data is updated incrementally.

CREATE TABLE IF NOT EXISTS interview_sessions (
    session_id   UUID         PRIMARY KEY DEFAULT gen_random_uuid(),
    profile_data JSONB        NOT NULL DEFAULT '{}',
    created_at   TIMESTAMPTZ  NOT NULL DEFAULT NOW(),
    updated_at   TIMESTAMPTZ  NOT NULL DEFAULT NOW()
);

-- Auto-update updated_at on every row change
CREATE OR REPLACE FUNCTION _update_updated_at()
RETURNS TRIGGER LANGUAGE plpgsql AS $$
BEGIN
    NEW.updated_at = NOW();
    RETURN NEW;
END;
$$;

DROP TRIGGER IF EXISTS trg_interview_sessions_updated_at ON interview_sessions;

CREATE TRIGGER trg_interview_sessions_updated_at
BEFORE UPDATE ON interview_sessions
FOR EACH ROW EXECUTE FUNCTION _update_updated_at();