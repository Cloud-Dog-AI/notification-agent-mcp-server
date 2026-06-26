-- Migration: Ukraine Digest Group Seed
-- Version: 0.7.0
-- Created: 2026-05-25
-- Description: Seed durable Ukraine digest groups for client, admin, and legacy routing.
--   Ensures groups survive restart, migration, or rebuild.
--   Uses INSERT OR IGNORE so existing groups are not duplicated.

-- Client distribution group: final client-ready Ukraine digest reports only
INSERT OR IGNORE INTO groups (name, description, language, preferred_channel, content_style, enabled)
VALUES (
    'Ukraine Digest Clients Group',
    'Final client-ready Ukraine digest reports only',
    'en',
    'email',
    'rich',
    1
);

-- Admin/process notification group: source search, ingest, process, and validation notices
INSERT OR IGNORE INTO groups (name, description, language, preferred_channel, content_style, enabled)
VALUES (
    'Ukraine Digest Admin Group',
    'Source search, ingest, process, and validation notices for Ukraine digest',
    'en',
    'email',
    'detailed',
    1
);

-- Legacy historical group: do not target for new final client sends
INSERT OR IGNORE INTO groups (name, description, language, preferred_channel, content_style, enabled)
VALUES (
    'Ukraine Digest Demo Group',
    'Legacy historical group - do not target for new final client sends',
    'en',
    'email',
    'detailed',
    1
);
