-- Add optional city tag to bot subscribers for city-targeted publishing
-- (used by /setcity and the dashboard template destination selector)
ALTER TABLE subscriber_chats ADD COLUMN IF NOT EXISTS city TEXT;
