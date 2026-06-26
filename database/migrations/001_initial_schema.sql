-- Initial Schema for Notification Agent MCP Server
-- Version: 0.1.0
-- Created: 2025-11-10

-- Messages table - notification requests
CREATE TABLE IF NOT EXISTS messages (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
    updated_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
    created_by VARCHAR(255),
    audience_type VARCHAR(50) NOT NULL DEFAULT 'personalised',  -- 'broadcast' or 'personalised'
    content_json TEXT NOT NULL,  -- JSON array of content blocks
    template_ref VARCHAR(255),
    variables_json TEXT,  -- JSON object of template variables
    llm_profile VARCHAR(100),
    ttl_at TIMESTAMP,
    idempotency_key VARCHAR(255) UNIQUE,
    status VARCHAR(50) DEFAULT 'queued',  -- queued, processing, completed, failed, ttl_expired
    metadata_json TEXT  -- Additional metadata
);

CREATE INDEX IF NOT EXISTS idx_messages_status ON messages(status);
CREATE INDEX IF NOT EXISTS idx_messages_created_at ON messages(created_at);
CREATE INDEX IF NOT EXISTS idx_messages_ttl_at ON messages(ttl_at);
CREATE INDEX IF NOT EXISTS idx_messages_idempotency_key ON messages(idempotency_key);

-- Deliveries table - per-channel delivery tracking
CREATE TABLE IF NOT EXISTS deliveries (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    message_id INTEGER NOT NULL,
    channel_id INTEGER NOT NULL,
    destination VARCHAR(500) NOT NULL,  -- email/phone/webhook URL
    personalised_payload TEXT,  -- formatted content for this delivery
    attempt_no INTEGER DEFAULT 0,
    state VARCHAR(50) DEFAULT 'queued',  -- queued, formatting, sending, sent, accepted, delivered, read, soft_failed, hard_failed, ttl_expired, cancelled
    last_error TEXT,
    next_action_at TIMESTAMP,
    provider_tracking_id TEXT,  -- External tracking ID from provider
    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
    updated_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
    sent_at TIMESTAMP,
    accepted_at TIMESTAMP,
    delivered_at TIMESTAMP,
    read_at TIMESTAMP,
    FOREIGN KEY (message_id) REFERENCES messages(id) ON DELETE CASCADE,
    FOREIGN KEY (channel_id) REFERENCES channels(id)
);

CREATE INDEX IF NOT EXISTS idx_deliveries_message_id ON deliveries(message_id);
CREATE INDEX IF NOT EXISTS idx_deliveries_channel_id ON deliveries(channel_id);
CREATE INDEX IF NOT EXISTS idx_deliveries_state ON deliveries(state);
CREATE INDEX IF NOT EXISTS idx_deliveries_next_action_at ON deliveries(next_action_at);
CREATE INDEX IF NOT EXISTS idx_deliveries_provider_tracking_id ON deliveries(provider_tracking_id);

-- Receipts table - provider confirmations
CREATE TABLE IF NOT EXISTS receipts (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    delivery_id INTEGER NOT NULL,
    provider_event VARCHAR(100),  -- Event type from provider
    status VARCHAR(50),  -- Provider's status
    raw_data TEXT,  -- Raw provider payload
    received_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
    signature_ok BOOLEAN DEFAULT 0,  -- Whether signature verification passed
    processed BOOLEAN DEFAULT 0,
    FOREIGN KEY (delivery_id) REFERENCES deliveries(id) ON DELETE CASCADE
);

CREATE INDEX IF NOT EXISTS idx_receipts_delivery_id ON receipts(delivery_id);
CREATE INDEX IF NOT EXISTS idx_receipts_received_at ON receipts(received_at);
CREATE INDEX IF NOT EXISTS idx_receipts_processed ON receipts(processed);

-- Channels table - channel configurations
CREATE TABLE IF NOT EXISTS channels (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    name VARCHAR(100) UNIQUE NOT NULL,
    type VARCHAR(50) NOT NULL,  -- smtp, sms, whatsapp, chat_rest
    enabled BOOLEAN DEFAULT 1,
    config_json TEXT,  -- channel-specific configuration (encrypted)
    limits_json TEXT,  -- rate limits, quotas
    error_count INTEGER DEFAULT 0,
    last_error_at TIMESTAMP,
    circuit_state VARCHAR(50) DEFAULT 'closed',  -- closed, open, half_open
    circuit_opened_at TIMESTAMP,
    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
    updated_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
);

CREATE INDEX IF NOT EXISTS idx_channels_type ON channels(type);
CREATE INDEX IF NOT EXISTS idx_channels_enabled ON channels(enabled);
CREATE INDEX IF NOT EXISTS idx_channels_circuit_state ON channels(circuit_state);

-- Users table - admin users
CREATE TABLE IF NOT EXISTS users (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    username VARCHAR(100) UNIQUE NOT NULL,
    email VARCHAR(255),
    password_hash VARCHAR(255) NOT NULL,
    role VARCHAR(50) DEFAULT 'viewer',  -- admin, sender, viewer
    preferences_json TEXT,
    enabled BOOLEAN DEFAULT 1,
    last_login_at TIMESTAMP,
    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
    updated_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
);

CREATE INDEX IF NOT EXISTS idx_users_username ON users(username);
CREATE INDEX IF NOT EXISTS idx_users_email ON users(email);
CREATE INDEX IF NOT EXISTS idx_users_role ON users(role);

-- Templates table - content templates
CREATE TABLE IF NOT EXISTS templates (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    name VARCHAR(100) UNIQUE NOT NULL,
    version INTEGER DEFAULT 1,
    format VARCHAR(50),  -- text, markdown, html
    body TEXT NOT NULL,
    validators_json TEXT,  -- Validation rules
    enabled BOOLEAN DEFAULT 1,
    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
    updated_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
);

CREATE INDEX IF NOT EXISTS idx_templates_name ON templates(name);
CREATE INDEX IF NOT EXISTS idx_templates_enabled ON templates(enabled);

-- Audit Events table - security audit log
CREATE TABLE IF NOT EXISTS audit_events (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    kind VARCHAR(100) NOT NULL,  -- message_submit, delivery_attempt, config_change, etc.
    ref_type VARCHAR(50),  -- message, delivery, channel, user
    ref_id INTEGER,
    actor VARCHAR(255),  -- Username or API key identifier
    data_json TEXT,  -- Event-specific data
    ip_address VARCHAR(50),
    user_agent TEXT,
    signature TEXT,  -- Cryptographic signature for non-repudiation
    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
);

CREATE INDEX IF NOT EXISTS idx_audit_events_kind ON audit_events(kind);
CREATE INDEX IF NOT EXISTS idx_audit_events_ref_type_id ON audit_events(ref_type, ref_id);
CREATE INDEX IF NOT EXISTS idx_audit_events_actor ON audit_events(actor);
CREATE INDEX IF NOT EXISTS idx_audit_events_created_at ON audit_events(created_at);

-- Admin user must be configured via env/config (no hardcoded credentials)

-- Insert default email channel (configured via env-build)
-- Note: Configuration should be loaded from CLOUD_DOG__NOTIFY__CHANNELS__SMTP__DEFAULT__* env vars
-- Default values here are placeholders - actual config comes from env-build
INSERT OR IGNORE INTO channels (name, type, enabled, config_json, limits_json)
VALUES (
    'email_default',
    'smtp',
    0,
    '{"host":null,"port":null,"username":null,"password":null,"from_address":null,"use_tls":null,"use_starttls":null}',
    '{"rate_per_minute":600,"rate_per_hour":10000}'
);

-- Insert default SMS channel (mock)
INSERT OR IGNORE INTO channels (name, type, enabled, config_json, limits_json)
VALUES (
    'sms_default',
    'sms',
    0,
    '{"provider":null,"sender":null}',
    '{"rate_per_minute":100,"rate_per_hour":1000}'
);

-- Insert default loopback channel used by local tests
INSERT OR IGNORE INTO channels (name, type, enabled, config_json, limits_json)
VALUES (
    'loopback_test',
    'loopback',
    1,
    '{"mode":"memory"}',
    '{"rate_per_minute":1000,"rate_per_hour":100000}'
);
