-- Users who started the bot in a private chat and want live price updates.
CREATE TABLE IF NOT EXISTS subscriber_chats (
  id BIGSERIAL PRIMARY KEY,
  chat_id BIGINT UNIQUE NOT NULL,
  first_name TEXT,
  username TEXT,
  subscribed BOOLEAN DEFAULT true,
  created_at TIMESTAMPTZ DEFAULT now(),
  updated_at TIMESTAMPTZ DEFAULT now()
);
