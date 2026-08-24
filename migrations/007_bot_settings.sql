-- Key-value settings table for bot publish policy
CREATE TABLE IF NOT EXISTS bot_settings (
  key TEXT PRIMARY KEY,
  value TEXT
);

INSERT INTO bot_settings (key, value) VALUES ('show_source_link', 'off')
ON CONFLICT (key) DO NOTHING;
