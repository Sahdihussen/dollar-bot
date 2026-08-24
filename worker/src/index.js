/**
 * Dollar Bot · Cloudflare Worker API
 *
 * Serves the dashboard API on the free Workers tier:
 *  - reads market data, sources, targets, subscribers, templates, settings
 *    directly from Supabase (PostgREST)
 *  - dashboard-triggered bot actions (publish board / send template) are
 *    queued into `pending_actions`; the always-on brain polls and executes
 *    them with the real formatter + Telegram bot.
 *
 * Secrets (set via `wrangler secret put`):
 *   SUPABASE_URL, SUPABASE_SERVICE_ROLE_KEY
 */

const CORS_HEADERS = {
  "Access-Control-Allow-Origin": "*",
  "Access-Control-Allow-Methods": "GET, POST, DELETE, OPTIONS",
  "Access-Control-Allow-Headers": "Content-Type",
};

const CITIES = ["baghdad", "erbil", "sulaymaniyah", "mosul", "basra", "kirkuk", "duhok"];

// ── helpers ────────────────────────────────────────────────────
function json(data, status = 200) {
  return new Response(JSON.stringify(data), {
    status,
    headers: { "Content-Type": "application/json", ...CORS_HEADERS },
  });
}

function err(detail, status) {
  return json({ detail }, status);
}

function sbHeaders(env) {
  return {
    apikey: env.SUPABASE_SERVICE_ROLE_KEY,
    Authorization: `Bearer ${env.SUPABASE_SERVICE_ROLE_KEY}`,
    "Content-Type": "application/json",
  };
}

async function sbFetch(env, url, init = {}) {
  const res = await fetch(url, { ...init, headers: { ...sbHeaders(env), ...(init.headers || {}) } });
  if (!res.ok) {
    throw new Error(`supabase ${res.status}`);
  }
  const text = await res.text();
  return text ? JSON.parse(text) : [];
}

const sbGet = (env, table, query = "") =>
  sbFetch(env, `${env.SUPABASE_URL}/rest/v1/${table}${query}`);

const sbPost = (env, path, body) =>
  sbFetch(env, `${env.SUPABASE_URL}/rest/v1/${path}`, {
    method: "POST",
    headers: { Prefer: "return=representation" },
    body: JSON.stringify(body),
  });

const sbPatch = (env, table, query, body) =>
  sbFetch(env, `${env.SUPABASE_URL}/rest/v1/${table}${query}`, {
    method: "PATCH",
    headers: { Prefer: "return=representation" },
    body: JSON.stringify(body),
  });

const sbDelete = (env, table, query) =>
  sbFetch(env, `${env.SUPABASE_URL}/rest/v1/${table}${query}`, {
    method: "DELETE",
    headers: { Prefer: "return=representation" },
  });

const eq = (v) => encodeURIComponent(String(v));

// ── dashboard aggregation (mirrors dashboard_data.py) ───────────
function normalizeSnapshot(s) {
  let cat = s.category_rates;
  if (typeof cat === "string") {
    try {
      cat = JSON.parse(cat);
    } catch {
      cat = {};
    }
  }
  return {
    city: s.city,
    market_layer: s.market_layer || "unknown",
    rate: s.median_rate || s.consensus_rate || null,
    min_rate: s.min_rate,
    max_rate: s.max_rate,
    spread: s.spread,
    observation_count: s.observation_count || 0,
    source_count: s.source_count || 0,
    freshest_at: s.freshest_at || s.snapshot_at,
    category_rates: cat || {},
  };
}

const MAX_SNAPSHOT_AGE_MS = 2 * 60 * 60 * 1000; // 2h, matches the Python backend

function isFreshSnapshot(s) {
  const ts = s.freshest_at || s.snapshot_at;
  if (!ts) return false;
  const t = new Date(ts).getTime();
  return Number.isFinite(t) && Date.now() - t < MAX_SNAPSHOT_AGE_MS;
}

async function loadSnapshots(env) {
  // Prefer the SQL function used by the Python backend.
  try {
    const res = await fetch(`${env.SUPABASE_URL}/rest/v1/rpc/get_latest_snapshots_per_city`, {
      method: "POST",
      headers: sbHeaders(env),
    });
    if (res.ok) {
      const rows = await res.json();
      if (Array.isArray(rows) && rows.length) return rows.filter(isFreshSnapshot);
    }
  } catch {
    /* fall through to per-city query */
  }
  const snapshots = [];
  for (const city of CITIES) {
    try {
      const rows = await sbGet(env, "market_snapshots", `?select=*&city=eq.${eq(city)}&order=snapshot_at.desc&limit=1`);
      if (rows[0] && isFreshSnapshot(rows[0])) snapshots.push(rows[0]);
    } catch {
      /* skip city */
    }
  }
  return snapshots;
}

async function dashboard(env) {
  let snapshots = [];
  try {
    snapshots = await loadSnapshots(env);
  } catch {
    snapshots = [];
  }
  const normalized = snapshots.map(normalizeSnapshot);
  const observation_count = normalized.reduce((a, s) => a + (s.observation_count || 0), 0);

  let sources = [];
  let targets = [];
  let subscribers = [];
  let sourceLink = "off";

  try {
    sources = await sbGet(env, "source_channels", "?select=*&active=eq.true&order=username.asc");
  } catch { /* keep [] */ }
  try {
    targets = await sbGet(env, "publish_targets", "?select=*&enabled=eq.true&order=created_at.asc");
  } catch { /* keep [] */ }
  try {
    subscribers = await sbGet(env, "subscriber_chats", "?select=*&order=created_at.desc&limit=200");
  } catch { /* keep [] */ }
  try {
    const rows = await sbGet(env, "bot_settings", `?select=value&key=eq.show_source_link&limit=1`);
    if (rows[0] && rows[0].value) sourceLink = rows[0].value;
  } catch { /* keep off */ }

  const subscribedCount = subscribers.filter((s) => s.subscribed !== false).length;

  return {
    service: "dollar-bot",
    version: "1.0.0",
    listener: "connected",
    source_count: sources.length,
    target_count: targets.length,
    subscriber_count: subscribedCount,
    subscribers,
    observation_count,
    snapshots: normalized,
    sources,
    targets,
    demo_data: false,
    db_connected: true,
    waiting_for_data: normalized.length === 0,
    checked_at: new Date().toISOString(),
  };
}

// ── template variables + rendering (mirrors templates.py) ──────
const VARIABLES = [
  { key: "current_price", label: "Current market price", example: "152,850", description: "Overall median USD/100 IQD rate" },
  { key: "current_price_iqd", label: "Current price with IQD", example: "152,850 IQD", description: "Overall median with currency" },
  { key: "baghdad_price", label: "Baghdad price", example: "152,750", description: "Latest Baghdad median" },
  { key: "erbil_price", label: "Erbil price", example: "152,900", description: "Latest Erbil median" },
  { key: "sulaymaniyah_price", label: "Sulaymaniyah price", example: "152,850", description: "Latest Sulaymaniyah median" },
  { key: "buy_rate", label: "Buy rate", example: "152,800", description: "Validated buy-side rate when available" },
  { key: "sell_rate", label: "Sell rate", example: "152,950", description: "Validated sell-side rate when available" },
  { key: "market_high", label: "Market high", example: "152,950", description: "Highest current city snapshot" },
  { key: "market_low", label: "Market low", example: "152,700", description: "Lowest current city snapshot" },
  { key: "market_spread", label: "Market spread", example: "250 IQD", description: "High minus low" },
  { key: "observation_count", label: "Observation count", example: "53", description: "Current validated observations" },
  { key: "source_count", label: "Source count", example: "14", description: "Active source channels" },
  { key: "time", label: "Baghdad time", example: "08:45 PM", description: "Current Iraq/Kurdistan time" },
  { key: "date", label: "Baghdad date", example: "24/08/2026", description: "Current Iraq/Kurdistan date" },
  { key: "movement", label: "Movement", example: "+150 IQD", description: "Reserved for latest movement calculation" },
];

function variableValues(snapshots, observationCount, sourceCount) {
  const rates = snapshots.map((s) => Number(s.rate)).filter((r) => Number.isFinite(r));
  const sorted = [...rates].sort((a, b) => a - b);
  const current = sorted.length ? sorted[Math.floor(sorted.length / 2)] : null;
  const buy = snapshots.map((s) => s.buy_rate).filter((v) => v != null).sort((a, b) => a - b);
  const sell = snapshots.map((s) => s.sell_rate).filter((v) => v != null).sort((a, b) => a - b);
  const byCity = {};
  for (const s of snapshots) if (s.city) byCity[s.city] = s;

  const n = (v) => (v == null ? "N/A" : Number(v).toLocaleString("en-US"));
  const cityRate = (c) => (byCity[c] && byCity[c].rate != null ? n(byCity[c].rate) : "N/A");
  const high = sorted.length ? n(sorted[sorted.length - 1]) : "N/A";
  const low = sorted.length ? n(sorted[0]) : "N/A";

  const now = new Date(Date.now() + 3 * 3600 * 1000);
  return {
    current_price: n(current),
    current_price_iqd: current == null ? "N/A" : `${n(current)} IQD`,
    baghdad_price: cityRate("baghdad"),
    erbil_price: cityRate("erbil"),
    sulaymaniyah_price: cityRate("sulaymaniyah"),
    buy_rate: buy.length ? n(buy[Math.floor(buy.length / 2)]) : "N/A",
    sell_rate: sell.length ? n(sell[Math.floor(sell.length / 2)]) : "N/A",
    market_high: high,
    market_low: low,
    market_spread: sorted.length ? `${n(sorted[sorted.length - 1] - sorted[0])} IQD` : "N/A",
    observation_count: n(observationCount),
    source_count: n(sourceCount),
    time: now.toLocaleTimeString("en-US", { hour: "numeric", minute: "2-digit", hour12: true }),
    date: `${String(now.getDate()).padStart(2, "0")}/${String(now.getMonth() + 1).padStart(2, "0")}/${now.getFullYear()}`,
    movement: "N/A",
  };
}

function renderTemplate(template, snapshots, observationCount, sourceCount) {
  const values = variableValues(snapshots, observationCount, sourceCount);
  const unknown = new Set();
  const rendered = template.replace(/\{\{\s*([a-zA-Z0-9_]+)\s*\}\}/g, (match, key) => {
    if (!(key in values)) {
      unknown.add(key);
      return match;
    }
    return values[key];
  });
  return { rendered, unknown_variables: [...unknown].sort() };
}

// ── route handlers ─────────────────────────────────────────────
async function handleGet(env, url) {
  const path = url.pathname;

  if (path === "/api/dashboard") {
    return json(await dashboard(env));
  }

  if (path === "/api/metals") {
    const fetchProduct = async (product) => {
      try {
        return await sbGet(env, "observations", `?select=*&product=eq.${eq(product)}&time_context=eq.CURRENT&order=created_at.desc&limit=4`);
      } catch {
        return [];
      }
    };
    return json({ silver_kg: await fetchProduct("silver_kg"), dubai_lira: await fetchProduct("dubai_lira") });
  }

  if (path === "/api/templates") {
    try {
      const rows = await sbGet(env, "post_templates", "?select=*&order=updated_at.desc");
      return json({ templates: rows, variables: VARIABLES, demo_data: false });
    } catch (e) {
      return err("Template storage is unavailable", 503);
    }
  }

  if (path === "/api/settings/source_link") {
    let enabled = false;
    try {
      const rows = await sbGet(env, "bot_settings", "?select=value&key=eq.show_source_link&limit=1");
      enabled = rows[0] && rows[0].value === "on";
    } catch { /* default off */ }
    return json({ enabled });
  }

  return err("Not found", 404);
}

async function handlePost(env, url, request) {
  const path = url.pathname;
  const body = await request.json().catch(() => ({}));

  if (path === "/api/templates/preview") {
    const text = (body.body || "").toString();
    const state = await dashboard(env);
    const result = renderTemplate(text, state.snapshots || [], state.observation_count || 0, state.source_count || 0);
    return json(result);
  }

  if (path === "/api/templates/send") {
    const text = (body.body || "").toString();
    if (!text.trim()) return err("Template body is empty", 400);
    const state = await dashboard(env);
    const result = renderTemplate(text, state.snapshots || [], state.observation_count || 0, state.source_count || 0);
    if (result.unknown_variables.length) {
      return err("Cannot send: unknown variables " + result.unknown_variables.join(", "), 400);
    }
    await sbPost(env, "pending_actions", {
      action: "send_template",
      payload: { name: (body.name || "unsaved").toString(), body: text, destination: (body.destination || "all").toString() },
    });
    return json({ sent: 0, queued: true, recipients: [] });
  }

  if (path === "/api/publish/board") {
    const state = await dashboard(env);
    if (!(state.snapshots || []).length) {
      return err("No current market data to publish yet", 400);
    }
    await sbPost(env, "pending_actions", { action: "publish_board", payload: {} });
    return json({ sent: 0, queued: true, recipients: [] });
  }

  if (path === "/api/templates") {
    const name = (body.name || "").toString().trim();
    const text = (body.body || "").toString();
    if (!name || !text.trim()) return err("Template name and body are required", 400);
    const destination = (body.destination || "all").toString();
    try {
      let row;
      if (body.id) {
        const rows = await sbPatch(env, "post_templates", `?id=eq.${eq(body.id)}`, { name, body: text, destination, updated_at: new Date().toISOString() });
        row = rows[0];
      } else {
        const rows = await sbPost(env, "post_templates", { name, body: text, destination, updated_at: new Date().toISOString() });
        row = rows[0];
      }
      return json({ template: row || null });
    } catch (e) {
      return err("Template storage is unavailable. Run migration 003.", 503);
    }
  }

  if (path === "/api/settings/source_link") {
    const enabled = Boolean(body.enabled);
    const value = enabled ? "on" : "off";
    try {
      const rows = await sbPatch(env, "bot_settings", "?key=eq.show_source_link", { value });
      if (!rows.length) {
        await sbPost(env, "bot_settings", { key: "show_source_link", value });
      }
      return json({ enabled });
    } catch (e) {
      return err("Setting failed", 503);
    }
  }

  const sourceMatch = path.match(/^\/api\/sources\/([^/]+)$/);
  if (sourceMatch) {
    try {
      const rows = await sbPatch(env, "source_channels", `?username=eq.${eq(decodeURIComponent(sourceMatch[1]))}`, { active: Boolean(body.active) });
      if (!rows.length) return err("Source not found", 404);
      return json({ ok: true, source: rows[0] });
    } catch (e) {
      return err("Supabase is unavailable or the channels table is missing", 503);
    }
  }

  const targetMatch = path.match(/^\/api\/targets\/(\d+)\/toggle$/);
  if (targetMatch) {
    const chatId = Number(targetMatch[1]);
    try {
      const rows = await sbGet(env, "publish_targets", `?select=enabled&chat_id=eq.${chatId}&limit=1`);
      if (!rows.length) return err("Publishing target not found", 404);
      const enabled = !rows[0].enabled;
      const updated = await sbPatch(env, "publish_targets", `?chat_id=eq.${chatId}`, { enabled });
      return json({ ok: true, enabled, target: updated[0] || null });
    } catch (e) {
      return err("Supabase is unavailable or the publish_targets table is missing", 503);
    }
  }

  const subscriberMatch = path.match(/^\/api\/subscribers\/(\d+)\/toggle$/);
  if (subscriberMatch) {
    const chatId = Number(subscriberMatch[1]);
    try {
      const rows = await sbGet(env, "subscriber_chats", `?select=subscribed&chat_id=eq.${chatId}&limit=1`);
      if (!rows.length) return err("Subscriber not found", 404);
      const subscribed = !rows[0].subscribed;
      const updated = await sbPatch(env, "subscriber_chats", `?chat_id=eq.${chatId}`, { subscribed, updated_at: new Date().toISOString() });
      return json({ ok: true, subscribed, subscriber: updated[0] || null });
    } catch (e) {
      return err("Supabase is unavailable or the subscribers table is missing", 503);
    }
  }

  return err("Not found", 404);
}

async function handleDelete(env, url) {
  const path = url.pathname;
  const match = path.match(/^\/api\/templates\/(\d+)$/);
  if (!match) return err("Not found", 404);
  try {
    await sbDelete(env, "post_templates", `?id=eq.${eq(match[1])}`);
    return json({ ok: true });
  } catch (e) {
    return err("Template could not be deleted", 503);
  }
}

// ── entry ──────────────────────────────────────────────────────
export default {
  async fetch(request, env) {
    const url = new URL(request.url);

    if (request.method === "OPTIONS") {
      return new Response(null, { status: 204, headers: CORS_HEADERS });
    }

    try {
      if (!env.SUPABASE_URL || !env.SUPABASE_SERVICE_ROLE_KEY) {
        return err("Worker secrets are not configured", 500);
      }
      if (request.method === "GET") return await handleGet(env, url);
      if (request.method === "POST") return await handlePost(env, url, request);
      if (request.method === "DELETE") return await handleDelete(env, url);
      return err("Method not allowed", 405);
    } catch (e) {
      return err(`Server error: ${e && e.message ? e.message : e}`, 500);
    }
  },
};
