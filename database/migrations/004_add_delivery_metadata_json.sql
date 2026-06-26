-- Add metadata_json column to deliveries table
-- Version: 0.4.0
-- Created: 2025-12-10
-- Purpose: Store destination preferences and other metadata for each delivery

-- Add metadata_json column to deliveries table
ALTER TABLE deliveries ADD COLUMN metadata_json TEXT;

-- Note: metadata_json will store JSON data including:
-- - destination preferences (language, content_style, etc.)
-- - formatting metadata
-- - delivery-specific configuration

