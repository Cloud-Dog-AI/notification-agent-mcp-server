-- Expand provider_tracking_id to handle large payloads
ALTER TABLE deliveries ALTER COLUMN provider_tracking_id TYPE TEXT;
