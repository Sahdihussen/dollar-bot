-- Saved Telegram post templates used by the management dashboard.
CREATE TABLE IF NOT EXISTS post_templates (
  id BIGSERIAL PRIMARY KEY,
  name TEXT NOT NULL,
  body TEXT NOT NULL,
  destination TEXT DEFAULT 'all',
  created_at TIMESTAMPTZ DEFAULT now(),
  updated_at TIMESTAMPTZ DEFAULT now()
);

INSERT INTO post_templates (name, body, destination)
SELECT 'Live market board', '💵 USD/IQD\n\nCurrent price: {{current_price_iqd}}\nBaghdad: {{baghdad_price}}\nErbil: {{erbil_price}}\nSulaymaniyah: {{sulaymaniyah_price}}\n\nUpdated: {{time}} · {{date}}', 'all'
WHERE NOT EXISTS (SELECT 1 FROM post_templates);
