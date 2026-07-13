-- Platform-wide config-description rollout: promote channel description to a
-- first-class column (previously only stored inside the config JSON blob).
-- Additive + idempotent: the ALTER raises a "duplicate column" error if the
-- column already exists, which db_manager._is_duplicate_error() catches and
-- skips (see apply_migration_file). Existing rows keep description NULL.
ALTER TABLE channels ADD COLUMN description TEXT;
