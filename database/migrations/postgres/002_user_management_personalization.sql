-- Migration: User Management & Personalization (Postgres)
-- Version: 0.2.0
-- Created: 2025-11-11
-- Description: Adds user management, groups, preferences, destinations, LLM prompts, and LDAP sync

-- Update users table with new fields
ALTER TABLE users ADD COLUMN display_name VARCHAR(255);
ALTER TABLE users ADD COLUMN user_type VARCHAR(50) DEFAULT 'real';
ALTER TABLE users ADD COLUMN language VARCHAR(10);
ALTER TABLE users ADD COLUMN preferred_channel VARCHAR(50);
ALTER TABLE users ADD COLUMN content_style VARCHAR(50);
ALTER TABLE users ADD COLUMN timezone VARCHAR(100);
ALTER TABLE users ADD COLUMN ldap_sync_id VARCHAR(255);
ALTER TABLE users ADD COLUMN ldap_source VARCHAR(50);

-- User destinations table
CREATE TABLE IF NOT EXISTS user_destinations (
    id SERIAL PRIMARY KEY,
    user_id INTEGER NOT NULL,
    channel_type VARCHAR(50) NOT NULL,
    destination VARCHAR(500) NOT NULL,
    verified BOOLEAN DEFAULT FALSE,
    is_primary BOOLEAN DEFAULT FALSE,
    metadata_json TEXT,
    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
    updated_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
    FOREIGN KEY (user_id) REFERENCES users(id) ON DELETE CASCADE
);

CREATE INDEX IF NOT EXISTS idx_user_destinations_user_id ON user_destinations(user_id);
CREATE INDEX IF NOT EXISTS idx_user_destinations_channel_type ON user_destinations(channel_type);
CREATE INDEX IF NOT EXISTS idx_user_destinations_destination ON user_destinations(destination);
CREATE INDEX IF NOT EXISTS idx_user_destinations_primary ON user_destinations(user_id, channel_type, is_primary);

-- User keywords table
CREATE TABLE IF NOT EXISTS user_keywords (
    id SERIAL PRIMARY KEY,
    user_id INTEGER NOT NULL,
    keyword VARCHAR(100) NOT NULL,
    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
    FOREIGN KEY (user_id) REFERENCES users(id) ON DELETE CASCADE,
    UNIQUE(user_id, keyword)
);

CREATE INDEX IF NOT EXISTS idx_user_keywords_user_id ON user_keywords(user_id);
CREATE INDEX IF NOT EXISTS idx_user_keywords_keyword ON user_keywords(keyword);

-- Groups table
CREATE TABLE IF NOT EXISTS groups (
    id SERIAL PRIMARY KEY,
    name VARCHAR(100) UNIQUE NOT NULL,
    description TEXT,
    language VARCHAR(10),
    preferred_channel VARCHAR(50),
    content_style VARCHAR(50),
    enabled BOOLEAN DEFAULT TRUE,
    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
    updated_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
);

CREATE INDEX IF NOT EXISTS idx_groups_name ON groups(name);
CREATE INDEX IF NOT EXISTS idx_groups_enabled ON groups(enabled);

-- Group members table
CREATE TABLE IF NOT EXISTS group_members (
    id SERIAL PRIMARY KEY,
    group_id INTEGER NOT NULL,
    user_id INTEGER NOT NULL,
    role VARCHAR(50) DEFAULT 'member',
    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
    FOREIGN KEY (group_id) REFERENCES groups(id) ON DELETE CASCADE,
    FOREIGN KEY (user_id) REFERENCES users(id) ON DELETE CASCADE,
    UNIQUE(group_id, user_id)
);

CREATE INDEX IF NOT EXISTS idx_group_members_group_id ON group_members(group_id);
CREATE INDEX IF NOT EXISTS idx_group_members_user_id ON group_members(user_id);

-- Group keywords table
CREATE TABLE IF NOT EXISTS group_keywords (
    id SERIAL PRIMARY KEY,
    group_id INTEGER NOT NULL,
    keyword VARCHAR(100) NOT NULL,
    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
    FOREIGN KEY (group_id) REFERENCES groups(id) ON DELETE CASCADE,
    UNIQUE(group_id, keyword)
);

CREATE INDEX IF NOT EXISTS idx_group_keywords_group_id ON group_keywords(group_id);
CREATE INDEX IF NOT EXISTS idx_group_keywords_keyword ON group_keywords(keyword);

-- LLM Prompts table
CREATE TABLE IF NOT EXISTS llm_prompts (
    id SERIAL PRIMARY KEY,
    name VARCHAR(255) NOT NULL,
    channel_type VARCHAR(50),
    group_id INTEGER,
    language VARCHAR(10),
    keyword VARCHAR(100),
    prompt_text TEXT NOT NULL,
    variables_json TEXT,
    priority INTEGER DEFAULT 0,
    enabled BOOLEAN DEFAULT TRUE,
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
ALTER TABLE channels ADD COLUMN preferences_json TEXT;
ALTER TABLE channels ADD COLUMN restrictions_json TEXT;

-- LDAP Sync table
CREATE TABLE IF NOT EXISTS ldap_syncs (
    id SERIAL PRIMARY KEY,
    source_type VARCHAR(50) NOT NULL,
    name VARCHAR(100) NOT NULL,
    config_json TEXT NOT NULL,
    enabled BOOLEAN DEFAULT TRUE,
    sync_schedule VARCHAR(100),
    last_sync_at TIMESTAMP,
    sync_status VARCHAR(50) DEFAULT 'pending',
    last_error TEXT,
    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
    updated_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
);

CREATE INDEX IF NOT EXISTS idx_ldap_syncs_source_type ON ldap_syncs(source_type);
CREATE INDEX IF NOT EXISTS idx_ldap_syncs_enabled ON ldap_syncs(enabled);
CREATE INDEX IF NOT EXISTS idx_ldap_syncs_last_sync_at ON ldap_syncs(last_sync_at);

-- Insert default groups
INSERT INTO groups (name, description, enabled)
SELECT 'Admin Users', 'Administrative users', TRUE
WHERE NOT EXISTS (SELECT 1 FROM groups WHERE name = 'Admin Users');

INSERT INTO groups (name, description, enabled)
SELECT 'System Users', 'Service accounts and system users', TRUE
WHERE NOT EXISTS (SELECT 1 FROM groups WHERE name = 'System Users');

-- Insert default LLM prompts for each channel type
INSERT INTO llm_prompts (name, channel_type, prompt_text, priority, enabled)
SELECT 'Email Default', 'email', 'Format the following content as a professional email. 

IMPORTANT INSTRUCTIONS:
1. Generate an appropriate email subject line based on the content if no subject is provided.
2. Add a brief introductory paragraph at the beginning if the content doesn''t start with a greeting or introduction.
3. Format the content clearly with proper structure.
4. If the content contains markdown syntax, convert it to the appropriate format based on user preferences (HTML or plain text).

Content to format:
{content}

Format as: {content_style}
Channel: {channel_type}', 0, TRUE
WHERE NOT EXISTS (SELECT 1 FROM llm_prompts WHERE name = 'Email Default' AND channel_type = 'email');

INSERT INTO llm_prompts (name, channel_type, prompt_text, priority, enabled)
SELECT 'SMS Default', 'sms', 'Format the following content as a concise SMS message. Maximum 140 characters. Be direct and clear.', 0, TRUE
WHERE NOT EXISTS (SELECT 1 FROM llm_prompts WHERE name = 'SMS Default' AND channel_type = 'sms');

INSERT INTO llm_prompts (name, channel_type, prompt_text, priority, enabled)
SELECT 'WhatsApp Default', 'whatsapp', 'Format the following content as a WhatsApp message. Use emojis sparingly. Be conversational but professional.', 0, TRUE
WHERE NOT EXISTS (SELECT 1 FROM llm_prompts WHERE name = 'WhatsApp Default' AND channel_type = 'whatsapp');

INSERT INTO llm_prompts (name, channel_type, prompt_text, priority, enabled)
SELECT 'Slack Default', 'slack', 'Format the following content as a Slack message. Use Slack markdown formatting. Be concise and actionable.', 0, TRUE
WHERE NOT EXISTS (SELECT 1 FROM llm_prompts WHERE name = 'Slack Default' AND channel_type = 'slack');

INSERT INTO llm_prompts (name, channel_type, prompt_text, priority, enabled)
SELECT 'Teams Default', 'teams', 'Format the following content as a Microsoft Teams message. Use Teams markdown. Be professional and clear.', 0, TRUE
WHERE NOT EXISTS (SELECT 1 FROM llm_prompts WHERE name = 'Teams Default' AND channel_type = 'teams');
