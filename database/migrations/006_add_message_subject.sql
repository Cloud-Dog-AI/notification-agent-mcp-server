-- W28D-440A: Add subject column to messages table for DEMO-027 title persistence
ALTER TABLE messages ADD COLUMN subject VARCHAR(500);

-- Backfill subject from variables_json where available
UPDATE messages SET subject = json_extract(variables_json, '$.subject') WHERE subject IS NULL AND variables_json IS NOT NULL AND json_extract(variables_json, '$.subject') IS NOT NULL;
