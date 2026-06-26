-- Notification Storage and Media Files Schema (Postgres)
-- Version: 0.3.0
-- Created: 2025-12-01
-- Purpose: Add tables for tracking stored files (PDFs, images, media) and PDF preferences

-- Notification storage tracking table
CREATE TABLE IF NOT EXISTS notification_storage (
    id SERIAL PRIMARY KEY,
    message_id INTEGER,
    delivery_id INTEGER,
    file_type TEXT NOT NULL,
    storage_path TEXT NOT NULL,
    storage_uri TEXT,
    access_url TEXT,
    file_size INTEGER,
    mime_type TEXT,
    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
    FOREIGN KEY (message_id) REFERENCES messages(id) ON DELETE CASCADE,
    FOREIGN KEY (delivery_id) REFERENCES deliveries(id) ON DELETE CASCADE
);

CREATE INDEX IF NOT EXISTS idx_notification_storage_message_id ON notification_storage(message_id);
CREATE INDEX IF NOT EXISTS idx_notification_storage_delivery_id ON notification_storage(delivery_id);
CREATE INDEX IF NOT EXISTS idx_notification_storage_file_type ON notification_storage(file_type);
CREATE INDEX IF NOT EXISTS idx_notification_storage_created_at ON notification_storage(created_at);

-- Media files tracking table
CREATE TABLE IF NOT EXISTS media_files (
    id SERIAL PRIMARY KEY,
    message_id INTEGER NOT NULL,
    media_type TEXT NOT NULL,
    format TEXT,
    storage_method TEXT NOT NULL,
    original_uri TEXT,
    cached_path TEXT,
    file_size INTEGER,
    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
    FOREIGN KEY (message_id) REFERENCES messages(id) ON DELETE CASCADE
);

CREATE INDEX IF NOT EXISTS idx_media_files_message_id ON media_files(message_id);
CREATE INDEX IF NOT EXISTS idx_media_files_media_type ON media_files(media_type);
CREATE INDEX IF NOT EXISTS idx_media_files_storage_method ON media_files(storage_method);

-- Add PDF preference to users table
ALTER TABLE users ADD COLUMN pdf_preference VARCHAR(50) DEFAULT NULL;

-- Add PDF preference to channels table
ALTER TABLE channels ADD COLUMN pdf_preference VARCHAR(50) DEFAULT NULL;

CREATE INDEX IF NOT EXISTS idx_users_pdf_preference ON users(pdf_preference);
CREATE INDEX IF NOT EXISTS idx_channels_pdf_preference ON channels(pdf_preference);
