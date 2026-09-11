-- Assisted mode: citizen metadata and scheme follow-up tracking
-- Run this in the Supabase SQL editor before enabling USE_SUPABASE=true

CREATE TABLE IF NOT EXISTS citizen_metadata (
  session_id   TEXT        PRIMARY KEY,
  worker_id    TEXT        NOT NULL,
  citizen_name TEXT        NOT NULL,
  citizen_phone TEXT,
  notes        TEXT,
  created_at   TIMESTAMPTZ DEFAULT NOW()
);

CREATE INDEX IF NOT EXISTS citizen_metadata_worker_id_idx
  ON citizen_metadata (worker_id);

CREATE TABLE IF NOT EXISTS scheme_followup (
  session_id   TEXT NOT NULL,
  scheme_id    TEXT NOT NULL,
  scheme_name  TEXT NOT NULL,
  status       TEXT NOT NULL CHECK (
    status IN ('will_apply','applied','received','rejected','not_applicable')
  ),
  notes        TEXT,
  updated_at   TIMESTAMPTZ DEFAULT NOW(),
  PRIMARY KEY (session_id, scheme_id)
);
