-- Initial Schema for Notification Agent MCP Server (Postgres)
-- Version: 0.1.0
-- Created: 2025-11-10

-- Messages table - notification requests
CREATE TABLE IF NOT EXISTS messages (
    id SERIAL PRIMARY KEY,
    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
    updated_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
    created_by VARCHAR(255),
    audience_type VARCHAR(50) NOT NULL DEFAULT 'personalised',
    content_json TEXT NOT NULL,
    template_ref VARCHAR(255),
    variables_json TEXT,
    llm_profile VARCHAR(100),
    ttl_at TIMESTAMP,
    idempotency_key VARCHAR(255) UNIQUE,
    status VARCHAR(50) DEFAULT 'queued',
    metadata_json TEXT
);

CREATE INDEX IF NOT EXISTS idx_messages_status ON messages(status);
CREATE INDEX IF NOT EXISTS idx_messages_created_at ON messages(created_at);
CREATE INDEX IF NOT EXISTS idx_messages_ttl_at ON messages(ttl_at);
CREATE INDEX IF NOT EXISTS idx_messages_idempotency_key ON messages(idempotency_key);

-- Channels table - channel configurations
CREATE TABLE IF NOT EXISTS channels (
    id SERIAL PRIMARY KEY,
    name VARCHAR(100) UNIQUE NOT NULL,
    type VARCHAR(50) NOT NULL,
    enabled BOOLEAN DEFAULT TRUE,
    config_json TEXT,
    limits_json TEXT,
    error_count INTEGER DEFAULT 0,
    last_error_at TIMESTAMP,
    circuit_state VARCHAR(50) DEFAULT 'closed',
    circuit_opened_at TIMESTAMP,
    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
    updated_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
);

CREATE INDEX IF NOT EXISTS idx_channels_type ON channels(type);
CREATE INDEX IF NOT EXISTS idx_channels_enabled ON channels(enabled);
CREATE INDEX IF NOT EXISTS idx_channels_circuit_state ON channels(circuit_state);

-- Users table - admin users
CREATE TABLE IF NOT EXISTS users (
    id SERIAL PRIMARY KEY,
    username VARCHAR(100) UNIQUE NOT NULL,
    email VARCHAR(255),
    password_hash VARCHAR(255) NOT NULL,
    role VARCHAR(50) DEFAULT 'viewer',
    preferences_json TEXT,
    enabled BOOLEAN DEFAULT TRUE,
    last_login_at TIMESTAMP,
    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
    updated_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
);

CREATE INDEX IF NOT EXISTS idx_users_username ON users(username);
CREATE INDEX IF NOT EXISTS idx_users_email ON users(email);
CREATE INDEX IF NOT EXISTS idx_users_role ON users(role);

-- Templates table - content templates
CREATE TABLE IF NOT EXISTS templates (
    id SERIAL PRIMARY KEY,
    name VARCHAR(100) UNIQUE NOT NULL,
    version INTEGER DEFAULT 1,
    format VARCHAR(50),
    body TEXT NOT NULL,
    validators_json TEXT,
    enabled BOOLEAN DEFAULT TRUE,
    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
    updated_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
);

CREATE INDEX IF NOT EXISTS idx_templates_name ON templates(name);
CREATE INDEX IF NOT EXISTS idx_templates_enabled ON templates(enabled);

-- Audit Events table - security audit log
CREATE TABLE IF NOT EXISTS audit_events (
    id SERIAL PRIMARY KEY,
    kind VARCHAR(100) NOT NULL,
    ref_type VARCHAR(50),
    ref_id INTEGER,
    actor VARCHAR(255),
    data_json TEXT,
    ip_address VARCHAR(50),
    user_agent TEXT,
    signature TEXT,
    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
);

CREATE INDEX IF NOT EXISTS idx_audit_events_kind ON audit_events(kind);
CREATE INDEX IF NOT EXISTS idx_audit_events_ref_type_id ON audit_events(ref_type, ref_id);
CREATE INDEX IF NOT EXISTS idx_audit_events_actor ON audit_events(actor);
CREATE INDEX IF NOT EXISTS idx_audit_events_created_at ON audit_events(created_at);

-- Insert default email channel
INSERT INTO channels (name, type, enabled, config_json, limits_json)
SELECT 'email_default', 'smtp', FALSE,
       '{"host":null,"port":null,"username":null,"password":null,"from_address":null,"use_tls":null,"use_starttls":null}',
       '{"rate_per_minute":600,"rate_per_hour":10000}'
WHERE NOT EXISTS (SELECT 1 FROM channels WHERE name = 'email_default');

-- Insert default SMS channel (mock)
INSERT INTO channels (name, type, enabled, config_json, limits_json)
SELECT 'sms_default', 'sms', FALSE,
       '{"provider":null,"sender":null}',
       '{"rate_per_minute":100,"rate_per_hour":1000}'
WHERE NOT EXISTS (SELECT 1 FROM channels WHERE name = 'sms_default');

-- Insert default loopback channel used by local tests
INSERT INTO channels (name, type, enabled, config_json, limits_json)
SELECT 'loopback_test', 'loopback', TRUE,
       '{"mode":"memory"}',
       '{"rate_per_minute":1000,"rate_per_hour":100000}'
WHERE NOT EXISTS (SELECT 1 FROM channels WHERE name = 'loopback_test');

-- Deliveries table - per-channel delivery tracking
CREATE TABLE IF NOT EXISTS deliveries (
    id SERIAL PRIMARY KEY,
    message_id INTEGER NOT NULL,
    channel_id INTEGER NOT NULL,
    destination VARCHAR(500) NOT NULL,
    personalised_payload TEXT,
    attempt_no INTEGER DEFAULT 0,
    state VARCHAR(50) DEFAULT 'queued',
    last_error TEXT,
    next_action_at TIMESTAMP,
    provider_tracking_id TEXT,
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
    id SERIAL PRIMARY KEY,
    delivery_id INTEGER NOT NULL,
    provider_event VARCHAR(100),
    status VARCHAR(50),
    raw_data TEXT,
    received_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
    signature_ok BOOLEAN DEFAULT FALSE,
    processed BOOLEAN DEFAULT FALSE,
    FOREIGN KEY (delivery_id) REFERENCES deliveries(id) ON DELETE CASCADE
);

CREATE INDEX IF NOT EXISTS idx_receipts_delivery_id ON receipts(delivery_id);
CREATE INDEX IF NOT EXISTS idx_receipts_received_at ON receipts(received_at);
CREATE INDEX IF NOT EXISTS idx_receipts_processed ON receipts(processed);
