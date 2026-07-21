CREATE INDEX idx_deliveries_channel_stats_cover
ON deliveries(channel_id, message_id, created_at);
