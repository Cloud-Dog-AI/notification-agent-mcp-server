-- Index the deliveries created_at column, which the deliveries LIST query orders
-- by (ORDER BY d.created_at DESC). Without it SQLite builds a temp B-tree over
-- the whole table for every list call; combined with the (separately fixed)
-- SELECT d.* blob materialisation this made a single list() take 20+ seconds and
-- stall the single-worker async servers' event loops under concurrent load.
-- Additive + idempotent (CREATE INDEX IF NOT EXISTS): a re-apply is a no-op.
CREATE INDEX IF NOT EXISTS idx_deliveries_created_at ON deliveries(created_at);
