-- Add metadata_json column to deliveries table (MySQL/MariaDB)
-- Version: 0.4.0
-- Created: 2025-12-10
-- Purpose: Store destination preferences and other metadata for each delivery

ALTER TABLE deliveries ADD COLUMN metadata_json TEXT;
