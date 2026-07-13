-- Add first-class description column to channels table (MySQL/MariaDB)
-- Platform-wide config-description rollout.
-- Additive + idempotent: a re-run raises "Duplicate column name" which
-- db_manager._is_duplicate_error() catches and skips. Existing rows keep NULL.
ALTER TABLE channels ADD COLUMN description TEXT;
