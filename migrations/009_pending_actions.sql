-- Dashboard action queue: the Cloudflare Worker (or any API caller) inserts
-- bot actions here; the always-on brain polls and executes them.
CREATE TABLE IF NOT EXISTS pending_actions (
  id BIGINT GENERATED ALWAYS AS IDENTITY PRIMARY KEY,
  action TEXT NOT NULL,
  payload JSONB NOT NULL DEFAULT '{}'::jsonb,
  status TEXT NOT NULL DEFAULT 'pending',
  created_at TIMESTAMPTZ NOT NULL DEFAULT now(),
  processed_at TIMESTAMPTZ,
  error TEXT
);

CREATE INDEX IF NOT EXISTS pending_actions_pending_idx
  ON pending_actions (status, created_at);

ALTER TABLE pending_actions ENABLE ROW LEVEL SECURITY;
