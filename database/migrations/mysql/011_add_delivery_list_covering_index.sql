CREATE INDEX idx_deliveries_list_cover
ON deliveries(
    created_at DESC,
    id,
    message_id,
    channel_id
);
