-- W28A-744 (IDAM-B2 §2.1): RBAC resource bindings — the group->resource edge that
-- gives the IDAM cascade a data path. Materialises the central cloud_dog_idam
-- RBACBinding model in the notification-agent DB. The channels (domain) table is
-- NOT modified (IDAM-B2 §2: no per-service domain FK); this is the JOIN table the
-- W28A-741 resolver (cloud_dog_idam.rbac.grants) consumes at authorisation time.
CREATE TABLE IF NOT EXISTS rbac_bindings (
    binding_id    TEXT PRIMARY KEY,
    subject_type  TEXT NOT NULL,
    subject_id    TEXT NOT NULL,
    project       TEXT NOT NULL DEFAULT 'notification-agent',
    resource_type TEXT NOT NULL,
    resource_id   TEXT NOT NULL DEFAULT '*',
    permission    TEXT NOT NULL,
    granted_by    TEXT NOT NULL DEFAULT 'system',
    created_at    TIMESTAMP DEFAULT CURRENT_TIMESTAMP
);
CREATE INDEX IF NOT EXISTS idx_rbac_bindings_subject  ON rbac_bindings (subject_type, subject_id);
CREATE INDEX IF NOT EXISTS idx_rbac_bindings_resource ON rbac_bindings (resource_type, resource_id);
