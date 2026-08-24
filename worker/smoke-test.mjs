/**
 * Local smoke test: runs the Worker fetch handler against real Supabase.
 * Secrets come from the environment, never from this file.
 *
 *   SUPABASE_URL=... SUPABASE_SERVICE_ROLE_KEY=... node smoke-test.mjs
 */
import worker from "./src/index.js";

const env = {
  SUPABASE_URL: process.env.SUPABASE_URL,
  SUPABASE_SERVICE_ROLE_KEY: process.env.SUPABASE_SERVICE_ROLE_KEY,
};

async function hit(path, init) {
  const res = await worker.fetch(new Request("https://test.local" + path, init), env);
  const body = await res.text();
  console.log(`${init?.method || "GET"} ${path} -> ${res.status} ${body.slice(0, 160)}`);
  return { res, body };
}

for (const path of ["/api/dashboard", "/api/metals", "/api/templates", "/api/settings/source_link"]) {
  await hit(path);
}

// Preview a template (exercise the JS renderer)
await hit("/api/templates/preview", {
  method: "POST",
  body: JSON.stringify({ name: "preview", body: "Hello, price is {{current_price_iqd}} and {{bogus_var}}", destination: "all" }),
  headers: { "Content-Type": "application/json" },
});
