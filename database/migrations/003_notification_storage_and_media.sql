-- Notification Storage and Media Files Schema
-- Version: 0.3.0
-- Created: 2025-12-01
-- Purpose: Add tables for tracking stored files (PDFs, images, media) and PDF preferences

-- Notification storage tracking table
-- Tracks all files stored in the notification storage system
CREATE TABLE IF NOT EXISTS notification_storage (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    message_id INTEGER,
    delivery_id INTEGER,
    file_type TEXT NOT NULL,  -- 'pdf', 'image', 'text', 'markdown', 'html'
    storage_path TEXT NOT NULL,  -- Relative path in storage (e.g., "pdf/2025/12/01/filename.pdf")
    storage_uri TEXT,  -- Full URI (file:// or http://)
    access_url TEXT,  -- Public access URL (if base_url configured)
    file_size INTEGER,  -- File size in bytes
    mime_type TEXT,  -- MIME type (e.g., "application/pdf", "image/png")
    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
    FOREIGN KEY (message_id) REFERENCES messages(id) ON DELETE CASCADE,
    FOREIGN KEY (delivery_id) REFERENCES deliveries(id) ON DELETE CASCADE
);

-- Create indexes for fast lookups
CREATE INDEX IF NOT EXISTS idx_notification_storage_message_id ON notification_storage(message_id);
CREATE INDEX IF NOT EXISTS idx_notification_storage_delivery_id ON notification_storage(delivery_id);
CREATE INDEX IF NOT EXISTS idx_notification_storage_file_type ON notification_storage(file_type);
CREATE INDEX IF NOT EXISTS idx_notification_storage_created_at ON notification_storage(created_at);

-- Media files tracking table
-- Tracks embedded/referenced media files (images) in messages
CREATE TABLE IF NOT EXISTS media_files (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    message_id INTEGER NOT NULL,
    media_type TEXT NOT NULL,  -- 'image' (future: 'video', 'audio')
    format TEXT,  -- 'png', 'gif', 'jpeg', 'jpg'
    storage_method TEXT NOT NULL,  -- 'uuencoded', 'uri', 'local_cache'
    original_uri TEXT,  -- Original URI if storage_method is 'uri'
    cached_path TEXT,  -- Path in local cache if storage_method is 'local_cache'
    file_size INTEGER,  -- File size in bytes
    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
    FOREIGN KEY (message_id) REFERENCES messages(id) ON DELETE CASCADE
);

-- Create indexes for fast lookups
CREATE INDEX IF NOT EXISTS idx_media_files_message_id ON media_files(message_id);
CREATE INDEX IF NOT EXISTS idx_media_files_media_type ON media_files(media_type);
CREATE INDEX IF NOT EXISTS idx_media_files_storage_method ON media_files(storage_method);

-- Add PDF preference to users table
-- NULL = no preference (use channel default), 'true' = prefer PDF, 'false' = prefer text
ALTER TABLE users ADD COLUMN pdf_preference TEXT DEFAULT NULL;

-- Add PDF preference to channels table
-- NULL = no default, 'true' = default to PDF, 'false' = default to text
ALTER TABLE channels ADD COLUMN pdf_preference TEXT DEFAULT NULL;

-- Create index on users.pdf_preference for filtering
CREATE INDEX IF NOT EXISTS idx_users_pdf_preference ON users(pdf_preference);

-- Create index on channels.pdf_preference for filtering
CREATE INDEX IF NOT EXISTS idx_channels_pdf_preference ON channels(pdf_preference);

