-- Migration: User Management & Personalization
-- Version: 0.2.0
-- Created: 2025-11-11
-- Description: Adds user management, groups, preferences, destinations, LLM prompts, and LDAP sync

-- Update users table with new fields
ALTER TABLE users ADD COLUMN display_name VARCHAR(255);
ALTER TABLE users ADD COLUMN user_type VARCHAR(50) DEFAULT 'real';  -- 'real' or 'system'
ALTER TABLE users ADD COLUMN language VARCHAR(10);  -- ISO 639-1 code (en, fr, de, etc.)
ALTER TABLE users ADD COLUMN preferred_channel VARCHAR(50);  -- email, sms, whatsapp, slack, teams
ALTER TABLE users ADD COLUMN content_style VARCHAR(50);  -- short, detailed, summary_link, rich
ALTER TABLE users ADD COLUMN timezone VARCHAR(100);  -- IANA timezone (Europe/London, etc.)
ALTER TABLE users ADD COLUMN ldap_sync_id VARCHAR(255);  -- External ID from LDAP/Keycloak
ALTER TABLE users ADD COLUMN ldap_source VARCHAR(50);  -- 'local', 'ldap', 'keycloak'

-- User destinations table - stores email, SMS, WhatsApp, Slack, Teams addresses
CREATE TABLE IF NOT EXISTS user_destinations (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    user_id INTEGER NOT NULL,
    channel_type VARCHAR(50) NOT NULL,  -- email, sms, whatsapp, slack, teams
    destination VARCHAR(500) NOT NULL,  -- email address, phone number (E.164), user ID
    verified BOOLEAN DEFAULT 0,
    is_primary BOOLEAN DEFAULT 0,  -- Primary destination for this channel type
    metadata_json TEXT,  -- Additional metadata (Slack workspace, Teams tenant, etc.)
    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
    updated_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
    FOREIGN KEY (user_id) REFERENCES users(id) ON DELETE CASCADE
);

CREATE INDEX IF NOT EXISTS idx_user_destinations_user_id ON user_destinations(user_id);
CREATE INDEX IF NOT EXISTS idx_user_destinations_channel_type ON user_destinations(channel_type);
CREATE INDEX IF NOT EXISTS idx_user_destinations_destination ON user_destinations(destination);
CREATE INDEX IF NOT EXISTS idx_user_destinations_primary ON user_destinations(user_id, channel_type, is_primary);

-- User keywords table - personalization keywords for users
CREATE TABLE IF NOT EXISTS user_keywords (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    user_id INTEGER NOT NULL,
    keyword VARCHAR(100) NOT NULL,  -- e.g., 'security', 'devops', 'executive', 'technical'
    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
    FOREIGN KEY (user_id) REFERENCES users(id) ON DELETE CASCADE,
    UNIQUE(user_id, keyword)
);

CREATE INDEX IF NOT EXISTS idx_user_keywords_user_id ON user_keywords(user_id);
CREATE INDEX IF NOT EXISTS idx_user_keywords_keyword ON user_keywords(keyword);

-- Groups table
CREATE TABLE IF NOT EXISTS groups (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    name VARCHAR(100) UNIQUE NOT NULL,
    description TEXT,
    language VARCHAR(10),  -- Default language for group
    preferred_channel VARCHAR(50),  -- Default preferred channel
    content_style VARCHAR(50),  -- Default content style
    enabled BOOLEAN DEFAULT 1,
    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
    updated_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
);

CREATE INDEX IF NOT EXISTS idx_groups_name ON groups(name);
CREATE INDEX IF NOT EXISTS idx_groups_enabled ON groups(enabled);

-- Group members table - many-to-many relationship
CREATE TABLE IF NOT EXISTS group_members (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    group_id INTEGER NOT NULL,
    user_id INTEGER NOT NULL,
    role VARCHAR(50) DEFAULT 'member',  -- member, admin, etc.
    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
    FOREIGN KEY (group_id) REFERENCES groups(id) ON DELETE CASCADE,
    FOREIGN KEY (user_id) REFERENCES users(id) ON DELETE CASCADE,
    UNIQUE(group_id, user_id)
);

CREATE INDEX IF NOT EXISTS idx_group_members_group_id ON group_members(group_id);
CREATE INDEX IF NOT EXISTS idx_group_members_user_id ON group_members(user_id);

-- Group keywords table - personalization keywords for groups
CREATE TABLE IF NOT EXISTS group_keywords (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    group_id INTEGER NOT NULL,
    keyword VARCHAR(100) NOT NULL,
    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
    FOREIGN KEY (group_id) REFERENCES groups(id) ON DELETE CASCADE,
    UNIQUE(group_id, keyword)
);

CREATE INDEX IF NOT EXISTS idx_group_keywords_group_id ON group_keywords(group_id);
CREATE INDEX IF NOT EXISTS idx_group_keywords_keyword ON group_keywords(keyword);

-- LLM Prompts table - stores prompts for channels, groups, languages, keywords
CREATE TABLE IF NOT EXISTS llm_prompts (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    name VARCHAR(255) NOT NULL,
    channel_type VARCHAR(50),  -- email, sms, whatsapp, slack, teams, NULL for all
    group_id INTEGER,  -- NULL for all groups
    language VARCHAR(10),  -- NULL for all languages
    keyword VARCHAR(100),  -- NULL for all keywords
    prompt_text TEXT NOT NULL,  -- The actual prompt template
    variables_json TEXT,  -- JSON schema for prompt variables
    priority INTEGER DEFAULT 0,  -- Higher priority = selected first (for same specificity)
    enabled BOOLEAN DEFAULT 1,
    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
    updated_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
    FOREIGN KEY (group_id) REFERENCES groups(id) ON DELETE SET NULL
);

CREATE INDEX IF NOT EXISTS idx_llm_prompts_channel_type ON llm_prompts(channel_type);
CREATE INDEX IF NOT EXISTS idx_llm_prompts_group_id ON llm_prompts(group_id);
CREATE INDEX IF NOT EXISTS idx_llm_prompts_language ON llm_prompts(language);
CREATE INDEX IF NOT EXISTS idx_llm_prompts_keyword ON llm_prompts(keyword);
CREATE INDEX IF NOT EXISTS idx_llm_prompts_priority ON llm_prompts(priority DESC);
CREATE INDEX IF NOT EXISTS idx_llm_prompts_enabled ON llm_prompts(enabled);

-- Channel preferences and restrictions - extend channels table
ALTER TABLE channels ADD COLUMN preferences_json TEXT;  -- Language defaults, content style hints
ALTER TABLE channels ADD COLUMN restrictions_json TEXT;  -- Max length, allowed formats, media restrictions, link strategy

-- LDAP Sync table - tracks external user source syncs
CREATE TABLE IF NOT EXISTS ldap_syncs (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    source_type VARCHAR(50) NOT NULL,  -- 'ldap', 'keycloak', 'database'
    name VARCHAR(100) NOT NULL,
    config_json TEXT NOT NULL,  -- Connection config (encrypted)
    enabled BOOLEAN DEFAULT 1,
    sync_schedule VARCHAR(100),  -- cron expression or 'manual', 'realtime'
    last_sync_at TIMESTAMP,
    sync_status VARCHAR(50) DEFAULT 'pending',  -- pending, running, success, error
    last_error TEXT,
    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
    updated_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
);

CREATE INDEX IF NOT EXISTS idx_ldap_syncs_source_type ON ldap_syncs(source_type);
CREATE INDEX IF NOT EXISTS idx_ldap_syncs_enabled ON ldap_syncs(enabled);
CREATE INDEX IF NOT EXISTS idx_ldap_syncs_last_sync_at ON ldap_syncs(last_sync_at);

-- Insert default groups
INSERT OR IGNORE INTO groups (name, description, enabled)
VALUES 
    ('Admin Users', 'Administrative users', 1),
    ('System Users', 'Service accounts and system users', 1);

-- Insert default LLM prompts for each channel type
INSERT OR IGNORE INTO llm_prompts (name, channel_type, prompt_text, priority, enabled)
VALUES 
    ('Email Default', 'email', 'Format the following content as a professional email. 

IMPORTANT INSTRUCTIONS:
1. Generate an appropriate email subject line based on the content if no subject is provided.
2. Add a brief introductory paragraph at the beginning if the content doesn''t start with a greeting or introduction.
3. Format the content clearly with proper structure.
4. If the content contains markdown syntax, convert it to the appropriate format based on user preferences (HTML or plain text).

Content to format:
{content}

Format as: {content_style}
Channel: {channel_type}', 0, 1),
    ('SMS Default', 'sms', 'Format the following content as a concise SMS message. Maximum 140 characters. Be direct and clear.', 0, 1),
    ('WhatsApp Default', 'whatsapp', 'Format the following content as a WhatsApp message. Use emojis sparingly. Be conversational but professional.', 0, 1),
    ('Slack Default', 'slack', 'Format the following content as a Slack message. Use Slack markdown formatting. Be concise and actionable.', 0, 1),
    ('Teams Default', 'teams', 'Format the following content as a Microsoft Teams message. Use Teams markdown. Be professional and clear.', 0, 1);

