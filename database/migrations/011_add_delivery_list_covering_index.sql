-- W28E-1882: keep WebUI delivery summaries off the multi-gigabyte payload table pages.
-- SQLite can satisfy the ordered summary query from this covering index, avoiding
-- repeated reads of personalised_payload/metadata_json during initial page load.
CREATE INDEX IF NOT EXISTS idx_deliveries_list_cover
ON deliveries(
    created_at DESC,
    id,
    message_id,
    channel_id,
    destination,
    attempt_no,
    state,
    last_error,
    next_action_at,
    provider_tracking_id,
    updated_at,
    sent_at,
    accepted_at,
    delivered_at,
    read_at
);
