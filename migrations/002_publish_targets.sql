-- Run this migration if 001_initial_schema.sql was already applied.
-- It lets administrators opt a channel or group into live price publishing.

CREATE TABLE IF NOT EXISTS publish_targets (
  id BIGSERIAL PRIMARY KEY,
  chat_id BIGINT UNIQUE NOT NULL,
  title TEXT NOT NULL,
  username TEXT,
  enabled BOOLEAN DEFAULT true,
  created_at TIMESTAMPTZ DEFAULT now(),
  updated_at TIMESTAMPTZ DEFAULT now()
);
