-- Add first-class description column to channels table (Postgres)
-- Platform-wide config-description rollout.
-- Additive + idempotent: IF NOT EXISTS makes a re-run a no-op. Existing rows keep NULL.
ALTER TABLE channels ADD COLUMN IF NOT EXISTS description TEXT;
