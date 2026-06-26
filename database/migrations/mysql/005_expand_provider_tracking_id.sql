-- Expand provider_tracking_id to handle large payloads
DROP INDEX idx_deliveries_provider_tracking_id ON deliveries;
ALTER TABLE deliveries MODIFY provider_tracking_id TEXT;
CREATE INDEX idx_deliveries_provider_tracking_id ON deliveries(provider_tracking_id(255));
