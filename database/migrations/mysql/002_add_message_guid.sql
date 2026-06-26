-- Add GUID column to messages table (MySQL/MariaDB)
-- Version: 0.2.0
-- Created: 2025-11-11

ALTER TABLE messages ADD COLUMN guid VARCHAR(36);

CREATE INDEX idx_messages_guid ON messages(guid);
