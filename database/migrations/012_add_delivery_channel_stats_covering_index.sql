-- W28E-1882: serve channel list counts without reading multi-gigabyte delivery payload pages.
CREATE INDEX IF NOT EXISTS idx_deliveries_channel_stats_cover
ON deliveries(channel_id, message_id, created_at);
