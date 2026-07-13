-- Index deliveries.created_at (LIST view orders by it). Idempotent no-op re-apply.
CREATE INDEX IF NOT EXISTS idx_deliveries_created_at ON deliveries(created_at);
