-- Dedicated table for the 14 monitored market Telegram channels.
-- The pre-existing "channels" table belongs to the user's other work and is left alone.
CREATE TABLE IF NOT EXISTS source_channels (
  id BIGSERIAL PRIMARY KEY,
  username TEXT UNIQUE NOT NULL,
  name TEXT,
  focused_categories TEXT[],
  active BOOLEAN DEFAULT true,
  created_at TIMESTAMPTZ DEFAULT now()
);

INSERT INTO source_channels (username, name, focused_categories)
SELECT v.username, v.name, v.focused_categories
FROM (VALUES
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
) AS v(username, name, focused_categories)
WHERE NOT EXISTS (
  SELECT 1 FROM source_channels c WHERE c.username = v.username
);
