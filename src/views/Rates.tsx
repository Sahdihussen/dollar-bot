import { useCallback, useEffect, useState } from "react";
import { api } from "../api";
import type {
  DashboardState,
  MetalObservation,
  Metals,
  Snapshot,
} from "../types";
import { cityLabel, fmt } from "./Home";

function byRole(obs: MetalObservation[], role: string) {
  return obs.find((o) => (o.rate_role ?? "").toUpperCase() === role);
}

function CityCard({ s }: { s: Snapshot }) {
  const cats = Object.entries(s.category_rates ?? {});
  return (
    <div className="toy white-card card">
      <div className="card-head">
        <span className="card-title">{cityLabel(s.city ?? "unknown")}</span>
        <span className="pill pill-blue">{s.market_layer ?? "market"}</span>
      </div>
      <div className="big-rate">
        {fmt(s.rate)} <small>IQD / 100$</small>
      </div>
      <div className="row">
        <span className="row-title">Range</span>
        <span className="row-sub">
          {fmt(s.min_rate)} – {fmt(s.max_rate)}
        </span>
      </div>
      <div className="row">
        <span className="row-title">Spread</span>
        <span className="row-sub">{fmt(s.spread)} IQD</span>
      </div>
      <div className="row">
        <span className="row-title">Observations</span>
        <span className="row-sub">
          {fmt(s.observation_count)} from {fmt(s.source_count)} sources
        </span>
      </div>
      {cats.length > 0 && (
        <div className="chips" style={{ marginTop: 10 }}>
          {cats.map(([k, v]) => (
            <span key={k} className="pill pill-off">
              {k.replace(/_/g, " ")} {fmt(v)}
            </span>
          ))}
        </div>
      )}
    </div>
  );
}

function MetalCard({ title, obs }: { title: string; obs: MetalObservation[] }) {
  if (!obs.length) return null;
  const sell = byRole(obs, "SELL");
  const buy = byRole(obs, "BUY");
  const market = byRole(obs, "MARKET");
  const latest = sell ?? market ?? buy;
  return (
    <div className="toy white-card card">
      <div className="card-head">
        <span className="card-title">{title}</span>
        <span className="pill pill-green">{obs.length} obs</span>
      </div>
      <div className="big-rate">
        ${fmt(latest?.rate)} <small>USD</small>
      </div>
      {(buy || sell) && (
        <div className="chips" style={{ marginTop: 10 }}>
          {buy && <span className="pill pill-blue">Buy ${fmt(buy.rate)}</span>}
          {sell && <span className="pill pill-on">Sell ${fmt(sell.rate)}</span>}
        </div>
      )}
      <div className="row" style={{ marginTop: 8 }}>
        <span className="row-title">Source</span>
        <span className="row-sub">
          {latest?.source ? `@${latest.source}` : "—"}
        </span>
      </div>
      <div className="row">
        <span className="row-title">City</span>
        <span className="row-sub">
          {latest?.city ? cityLabel(latest.city) : "—"}
        </span>
      </div>
    </div>
  );
}

export default function Rates({
  state,
  notify,
}: {
  state: DashboardState | null;
  notify: (text: string, kind?: "ok" | "err") => void;
}) {
  const [metals, setMetals] = useState<Metals | null>(null);

  const loadMetals = useCallback(async () => {
    try {
      setMetals(await api.metals());
    } catch (e) {
      notify(e instanceof Error ? e.message : "Metals unavailable", "err");
    }
  }, [notify]);

  useEffect(() => {
    void loadMetals();
  }, [loadMetals]);

  const snapshots = (state?.snapshots ?? []).filter((s) => s.rate != null);

  return (
    <div>
      <div className="title-block" style={{ marginBottom: 14 }}>
        <span className="title-line title-1" style={{ fontSize: 28 }}>
          Live Rates
        </span>
        <div className="title-sub">Updated every 30 seconds</div>
      </div>

      {snapshots.length === 0 && (
        <div className="toy white-card card">
          <div className="empty">
            No current snapshots yet — waiting for the next price post from the
            monitored channels.
          </div>
        </div>
      )}
      {snapshots.map((s) => (
        <CityCard key={s.city ?? "unknown"} s={s} />
      ))}

      {(metals?.silver_kg?.length ?? 0) > 0 && (
        <MetalCard title="Silver · per kg" obs={metals?.silver_kg ?? []} />
      )}
      {(metals?.dubai_lira?.length ?? 0) > 0 && (
        <MetalCard title="Dubai Lira · 7.2g 22k" obs={metals?.dubai_lira ?? []} />
      )}

      <button
        className="btn btn-blue"
        style={{ width: "100%" }}
        onClick={() => void loadMetals()}
      >
        Refresh metals
      </button>
    </div>
  );
}
