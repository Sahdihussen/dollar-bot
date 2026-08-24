# Dollar Bot · Cloudflare Worker API

Free-tier serverless API for the mobile dashboard. It reads Supabase directly
and queues bot actions (`publish_board`, `send_template`) into `pending_actions`,
which the always-on brain (the Python scheduler) polls and executes.

## Deploy

```bash
cd worker
npm install          # or: bun install
npx wrangler login   # or set CLOUDFLARE_API_TOKEN / CLOUDFLARE_ACCOUNT_ID
npx wrangler secret put SUPABASE_URL
npx wrangler secret put SUPABASE_SERVICE_ROLE_KEY
npx wrangler deploy
```

The deployed URL looks like `https://dollar-bot-api.<your-subdomain>.workers.dev`.

## Point the dashboard at it

Two ways (no code change needed):

1. **Edit the deployed `index.html`** (Freebuff static deploy): set
   `window.__API_BASE__ = "https://dollar-bot-api.<your-subdomain>.workers.dev";`
   in the inline script in `<head>`.
2. **Or rebuild with the build-time env:**
   `VITE_API_BASE=https://dollar-bot-api.<your-subdomain>.workers.dev npm run build`

The dashboard falls back to same-origin (`""`) when unset, which is what the
sandbox preview uses.

## Prerequisites

- Migration `009_pending_actions.sql` must be applied to Supabase
  (run it in the Supabase SQL editor) — otherwise publish/send actions will
  fail with a 503 until the table exists.
