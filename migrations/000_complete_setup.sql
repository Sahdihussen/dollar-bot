-- Dollar Bot complete Supabase setup
-- Paste the CONTENTS of this file into Supabase SQL Editor and click Run.
-- Do not paste the filename or the word migrations.

BEGIN;

CREATE TABLE IF NOT EXISTS channels (
  id BIGSERIAL PRIMARY KEY,
  username TEXT UNIQUE NOT NULL,
  name TEXT,
  focused_categories TEXT[],
  active BOOLEAN DEFAULT true,
  created_at TIMESTAMPTZ DEFAULT now()
);

ALTER TABLE channels ADD COLUMN IF NOT EXISTS username TEXT;
ALTER TABLE channels ADD COLUMN IF NOT EXISTS name TEXT;
ALTER TABLE channels ADD COLUMN IF NOT EXISTS focused_categories TEXT[];
ALTER TABLE channels ADD COLUMN IF NOT EXISTS active BOOLEAN DEFAULT true;
ALTER TABLE channels ADD COLUMN IF NOT EXISTS created_at TIMESTAMPTZ DEFAULT now();

CREATE TABLE IF NOT EXISTS publish_targets (
  id BIGSERIAL PRIMARY KEY,
  chat_id BIGINT UNIQUE NOT NULL,
  title TEXT NOT NULL,
  username TEXT,
  enabled BOOLEAN DEFAULT true,
  created_at TIMESTAMPTZ DEFAULT now(),
  updated_at TIMESTAMPTZ DEFAULT now()
);

CREATE TABLE IF NOT EXISTS raw_posts (
  id BIGSERIAL PRIMARY KEY,
  channel_username TEXT NOT NULL,
  telegram_message_id BIGINT NOT NULL,
  post_url TEXT,
  raw_text TEXT NOT NULL,
  published_at TIMESTAMPTZ,
  received_at TIMESTAMPTZ DEFAULT now(),
  processed BOOLEAN DEFAULT false,
  UNIQUE(channel_username, telegram_message_id)
);

CREATE TABLE IF NOT EXISTS observations (
  id BIGSERIAL PRIMARY KEY,
  raw_post_id BIGINT,
  source TEXT,
  city TEXT,
  city_raw TEXT,
  market TEXT,
  market_layer TEXT,
  currency TEXT DEFAULT 'USD',
  quote_currency TEXT DEFAULT 'IQD',
  denomination INTEGER DEFAULT 100,
  rate INTEGER,
  rate_role TEXT DEFAULT 'UNKNOWN',
  quote_label_raw TEXT,
  quote_label_normalized TEXT,
  dollar_category_raw TEXT,
  dollar_category_normalized TEXT,
  time_context TEXT DEFAULT 'UNKNOWN',
  confidence DOUBLE PRECISION DEFAULT 0.5,
  evidence_text TEXT,
  created_at TIMESTAMPTZ DEFAULT now()
);

ALTER TABLE observations ADD COLUMN IF NOT EXISTS raw_post_id BIGINT;
ALTER TABLE observations ADD COLUMN IF NOT EXISTS source TEXT;
ALTER TABLE observations ADD COLUMN IF NOT EXISTS city TEXT;
ALTER TABLE observations ADD COLUMN IF NOT EXISTS city_raw TEXT;
ALTER TABLE observations ADD COLUMN IF NOT EXISTS market TEXT;
ALTER TABLE observations ADD COLUMN IF NOT EXISTS market_layer TEXT;
ALTER TABLE observations ADD COLUMN IF NOT EXISTS currency TEXT DEFAULT 'USD';
ALTER TABLE observations ADD COLUMN IF NOT EXISTS quote_currency TEXT DEFAULT 'IQD';
ALTER TABLE observations ADD COLUMN IF NOT EXISTS denomination INTEGER DEFAULT 100;
ALTER TABLE observations ADD COLUMN IF NOT EXISTS rate INTEGER;
ALTER TABLE observations ADD COLUMN IF NOT EXISTS rate_role TEXT DEFAULT 'UNKNOWN';
ALTER TABLE observations ADD COLUMN IF NOT EXISTS quote_label_raw TEXT;
ALTER TABLE observations ADD COLUMN IF NOT EXISTS quote_label_normalized TEXT;
ALTER TABLE observations ADD COLUMN IF NOT EXISTS dollar_category_raw TEXT;
ALTER TABLE observations ADD COLUMN IF NOT EXISTS dollar_category_normalized TEXT;
ALTER TABLE observations ADD COLUMN IF NOT EXISTS time_context TEXT DEFAULT 'UNKNOWN';
ALTER TABLE observations ADD COLUMN IF NOT EXISTS confidence DOUBLE PRECISION DEFAULT 0.5;
ALTER TABLE observations ADD COLUMN IF NOT EXISTS evidence_text TEXT;
ALTER TABLE observations ADD COLUMN IF NOT EXISTS created_at TIMESTAMPTZ DEFAULT now();

CREATE TABLE IF NOT EXISTS market_snapshots (
  id BIGSERIAL PRIMARY KEY,
  city TEXT NOT NULL,
  market_layer TEXT,
  consensus_rate INTEGER,
  median_rate INTEGER,
  min_rate INTEGER,
  max_rate INTEGER,
  spread INTEGER,
  buy_rate INTEGER,
  sell_rate INTEGER,
  observation_count INTEGER,
  source_count INTEGER,
  freshest_at TIMESTAMPTZ,
  category_rates JSONB,
  snapshot_at TIMESTAMPTZ DEFAULT now()
);

CREATE TABLE IF NOT EXISTS rate_history (
  id BIGSERIAL PRIMARY KEY,
  city TEXT NOT NULL,
  rate INTEGER NOT NULL,
  recorded_at TIMESTAMPTZ DEFAULT now()
);

CREATE TABLE IF NOT EXISTS post_templates (
  id BIGSERIAL PRIMARY KEY,
  name TEXT NOT NULL,
  body TEXT NOT NULL,
  destination TEXT DEFAULT 'all',
  created_at TIMESTAMPTZ DEFAULT now(),
  updated_at TIMESTAMPTZ DEFAULT now()
);

CREATE INDEX IF NOT EXISTS idx_channels_active ON channels(active);
CREATE INDEX IF NOT EXISTS idx_raw_posts_received ON raw_posts(received_at DESC);
CREATE INDEX IF NOT EXISTS idx_raw_posts_unprocessed ON raw_posts(processed) WHERE processed = false;
CREATE INDEX IF NOT EXISTS idx_observations_city ON observations(city);
CREATE INDEX IF NOT EXISTS idx_observations_created ON observations(created_at DESC);
CREATE INDEX IF NOT EXISTS idx_rate_history_city_time ON rate_history(city, recorded_at DESC);
CREATE INDEX IF NOT EXISTS idx_snapshots_time ON market_snapshots(snapshot_at DESC);
CREATE INDEX IF NOT EXISTS idx_publish_targets_enabled ON publish_targets(enabled);
CREATE INDEX IF NOT EXISTS idx_post_templates_updated ON post_templates(updated_at DESC);

-- Source channels are read from the existing channels table and the app config;
-- no seed is needed here because the table predates this project.

INSERT INTO post_templates (name, body, destination)
SELECT
  'Live market board',
  '💵 USD/IQD

Current price: {{current_price_iqd}}
Baghdad: {{baghdad_price}}
Erbil: {{erbil_price}}
Sulaymaniyah: {{sulaymaniyah_price}}

Updated: {{time}} - {{date}}',
  'all'
WHERE NOT EXISTS (SELECT 1 FROM post_templates);

DROP FUNCTION IF EXISTS get_latest_snapshots_per_city();

CREATE OR REPLACE FUNCTION get_latest_snapshots_per_city()
RETURNS TABLE (
  city TEXT,
  market_layer TEXT,
  consensus_rate INTEGER,
  median_rate INTEGER,
  min_rate INTEGER,
  max_rate INTEGER,
  spread INTEGER,
  buy_rate INTEGER,
  sell_rate INTEGER,
  observation_count INTEGER,
  source_count INTEGER,
  freshest_at TIMESTAMPTZ,
  category_rates JSONB,
  snapshot_at TIMESTAMPTZ
)
LANGUAGE SQL
STABLE
AS $$
  SELECT DISTINCT ON (ms.city)
    ms.city,
    ms.market_layer,
    ms.consensus_rate,
    ms.median_rate,
    ms.min_rate,
    ms.max_rate,
    ms.spread,
    ms.buy_rate,
    ms.sell_rate,
    ms.observation_count,
    ms.source_count,
    ms.freshest_at,
    ms.category_rates,
    ms.snapshot_at
  FROM market_snapshots AS ms
  ORDER BY ms.city, ms.snapshot_at DESC;
$$;

COMMIT;

-- Verification query: run after the setup succeeds.
-- SELECT table_name FROM information_schema.tables
-- WHERE table_schema = 'public'
-- AND table_name IN ('channels','publish_targets','raw_posts','observations','market_snapshots','rate_history','post_templates')
-- ORDER BY table_name;
