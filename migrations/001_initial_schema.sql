-- Dollar Bot Database Schema
-- Run this against your Supabase PostgreSQL database

-- Monitored Telegram channels
CREATE TABLE IF NOT EXISTS channels (
  id SERIAL PRIMARY KEY,
  username TEXT UNIQUE NOT NULL,
  name TEXT,
  focused_categories TEXT[],
  active BOOLEAN DEFAULT true,
  created_at TIMESTAMPTZ DEFAULT now()
);

-- Telegram destinations where the bot should publish live/scheduled updates
CREATE TABLE IF NOT EXISTS publish_targets (
  id BIGSERIAL PRIMARY KEY,
  chat_id BIGINT UNIQUE NOT NULL,
  title TEXT NOT NULL,
  username TEXT,
  enabled BOOLEAN DEFAULT true,
  created_at TIMESTAMPTZ DEFAULT now(),
  updated_at TIMESTAMPTZ DEFAULT now()
);

-- Raw Telegram posts
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

-- Individual extracted observations (one post → many observations)
CREATE TABLE IF NOT EXISTS observations (
  id BIGSERIAL PRIMARY KEY,
  raw_post_id BIGINT REFERENCES raw_posts(id),
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
  
  confidence FLOAT DEFAULT 0.5,
  evidence_text TEXT,
  
  created_at TIMESTAMPTZ DEFAULT now()
);

-- Market snapshots (calculated consensus per city/time)
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

-- Rate history for movement detection
CREATE TABLE IF NOT EXISTS rate_history (
  id BIGSERIAL PRIMARY KEY,
  city TEXT NOT NULL,
  rate INTEGER NOT NULL,
  recorded_at TIMESTAMPTZ DEFAULT now()
);

-- Create indexes
CREATE INDEX IF NOT EXISTS idx_raw_posts_received ON raw_posts(received_at DESC);
CREATE INDEX IF NOT EXISTS idx_raw_posts_unprocessed ON raw_posts(processed) WHERE processed = false;
CREATE INDEX IF NOT EXISTS idx_observations_city ON observations(city);
CREATE INDEX IF NOT EXISTS idx_observations_created ON observations(created_at DESC);
CREATE INDEX IF NOT EXISTS idx_rate_history_city_time ON rate_history(city, recorded_at DESC);
CREATE INDEX IF NOT EXISTS idx_snapshots_time ON market_snapshots(snapshot_at DESC);

-- Insert monitored channels
INSERT INTO channels (username, name, focused_categories) VALUES
('pashagoldd', 'Pasha Gold', NULL),
('borsat_alkfah', 'Borsa Al-Kifah', NULL),
('Borsa_Erbil', 'Borsa Erbil', NULL),
('PMCgroup', 'PMC Group', NULL),
('nrxidolar', 'NRXI Dollar', NULL),
('iraqborsa', 'Iraq Borsa', NULL),
('RaprsyWnrx', 'Raprsy WNRX', NULL),
('borsakurdstan', 'Borsa Kurdistan', NULL),
('httpswyTu0W4VrKZkMGZi', 'Market Source', NULL),
('Ranyadollar', 'Ranya Dollar', NULL),
('kurddolar', 'Kurd Dollar', NULL),
('NrxiDraw24', 'NRXI Draw 24', ARRAY['silber_kg', 'dubai_lira']),
('nrxidraw852', 'NRXI Draw 852', ARRAY['silber_kg', 'dubai_lira']),
('YarGold_Co', 'Yar Gold Co', ARRAY['silber_kg', 'dubai_lira'])
ON CONFLICT (username) DO NOTHING;

-- Create a function to get latest snapshots per city
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
) AS $$
BEGIN
  RETURN QUERY
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
  FROM market_snapshots ms
  ORDER BY ms.city, ms.snapshot_at DESC;
END;
$$ LANGUAGE plpgsql;
