import { useState, type ReactElement } from "react";
import { api } from "../api";
import type { DashboardState, Snapshot } from "../types";
import type { Tab } from "../components/NavBar";
import {
  IconCitadel,
  IconCoin,
  IconGear,
  IconMosque,
  IconRadar,
  IconSend,
  IconSun,
  IconUsers,
} from "../components/Icons";

const CITIES = [
  "baghdad",
  "erbil",
  "sulaymaniyah",
  "mosul",
  "basra",
  "kirkuk",
  "duhok",
];

export const fmt = (v: number | null | undefined) =>
  v == null ? "—" : Number(v).toLocaleString("en-US");

export const cityLabel = (city: string) =>
  city.charAt(0).toUpperCase() + city.slice(1);

function median(rates: number[]): number | null {
  if (!rates.length) return null;
  const sorted = [...rates].sort((a, b) => a - b);
  return sorted[Math.floor(sorted.length / 2)];
}

function Tile({
  color,
  label,
  tag,
  value,
  sub,
  delta,
  icon,
}: {
  color: string;
  label: string;
  tag?: string;
  value: string;
  sub: string;
  delta?: string;
  icon: ReactElement;
}) {
  return (
    <div className={`toy tile tile-${color}`}>
      <div className="tile-head">
        <div>
          <div className="tile-label">{label}</div>
          {tag && <span className="tile-tag">{tag}</span>}
        </div>
        <div className="icobg">{icon}</div>
      </div>
      <div>
        <div className="tile-value">{value}</div>
        <div className="tile-foot">
          <span className="tile-sub">{sub}</span>
          {delta && <span className="tile-delta">{delta}</span>}
        </div>
      </div>
    </div>
  );
}

interface Props {
  state: DashboardState | null;
  notify: (text: string, kind?: "ok" | "err") => void;
  onChanged: () => void;
  onNavigate: (tab: Tab) => void;
}

export default function Home({ state, notify, onChanged, onNavigate }: Props) {
  const [armed, setArmed] = useState(false);
  const [sending, setSending] = useState(false);

  const snapshots = (state?.snapshots ?? []).filter((s) => s.rate != null);
  const byCity: Record<string, Snapshot | undefined> = {};
  for (const s of snapshots) if (s.city) byCity[s.city] = s;
  const overall = median(snapshots.map((s) => Number(s.rate)));
  const coverage = Math.min(
    100,
    Math.round((snapshots.length / CITIES.length) * 100),
  );

  async function publish() {
    if (!armed) {
      setArmed(true);
      window.setTimeout(() => setArmed(false), 4000);
      return;
    }
    setSending(true);
    try {
      const res = await api.publishBoard();
      notify(
        res.queued
          ? "Board queued — the bot will publish it shortly"
          : res.sent > 0
            ? `Board sent to ${res.sent} destination${res.sent === 1 ? "" : "s"}`
            : "Board published — no live destinations yet",
      );
      setArmed(false);
      onChanged();
    } catch (e) {
      notify(e instanceof Error ? e.message : "Publish failed", "err");
    } finally {
      setSending(false);
    }
  }

  return (
    <div>
      <div className="topbar">
        <div className="avatar">
          <IconCoin size={30} />
        </div>
        <div className="counters">
          <div className="counter">
            <span className="chip chip-blue">
              <IconUsers size={14} />
            </span>
            {fmt(state?.subscriber_count)}
          </div>
          <div className="counter">
            <span className="chip chip-green">
              <IconRadar size={14} />
            </span>
            {fmt(state?.source_count)}
          </div>
        </div>
        <button
          className="iconbtn"
          aria-label="Open settings"
          onClick={() => onNavigate("settings")}
        >
          <IconGear size={22} />
        </button>
      </div>

      <div className="title-block">
        <span className="title-line title-1">Dollar</span>
        <span className="title-line title-2">Live Board</span>
        <div className="title-sub">Iraq · Kurdistan · USD / IQD</div>
      </div>

      <div className="tiles">
        <Tile
          color="blue"
          label="Live rate"
          tag="USD / IQD"
          value={fmt(overall)}
          sub="All cities median"
          delta={`${fmt(state?.observation_count)} obs`}
          icon={<IconCoin size={24} />}
        />
        <Tile
          color="orange"
          label="Baghdad"
          tag={byCity.baghdad?.market_layer ?? "market"}
          value={fmt(byCity.baghdad?.rate)}
          sub={`high ${fmt(byCity.baghdad?.max_rate)} · low ${fmt(byCity.baghdad?.min_rate)}`}
          icon={<IconMosque size={24} />}
        />
        <Tile
          color="green"
          label="Erbil"
          tag={byCity.erbil?.market_layer ?? "market"}
          value={fmt(byCity.erbil?.rate)}
          sub={`high ${fmt(byCity.erbil?.max_rate)} · low ${fmt(byCity.erbil?.min_rate)}`}
          icon={<IconCitadel size={24} />}
        />
        <Tile
          color="purple"
          label="Sulaymaniyah"
          tag={byCity.sulaymaniyah?.market_layer ?? "market"}
          value={fmt(byCity.sulaymaniyah?.rate)}
          sub={`high ${fmt(byCity.sulaymaniyah?.max_rate)} · low ${fmt(byCity.sulaymaniyah?.min_rate)}`}
          icon={<IconSun size={24} />}
        />
      </div>

      <div className="toy progress">
        <div className="progress-head">
          <span className="progress-title">Market coverage</span>
          <span className="progress-pct">{coverage}%</span>
        </div>
        <div className="progress-track">
          <div className="progress-fill" style={{ width: `${coverage}%` }} />
        </div>
        <div className="progress-sub">
          {snapshots.length} of {CITIES.length} cities reporting live ·{" "}
          {fmt(state?.observation_count)} observations · {fmt(state?.source_count)}{" "}
          sources
        </div>
      </div>

      <button
        className={`publish-btn ${armed ? "armed" : ""}`}
        onClick={() => void publish()}
        disabled={sending}
      >
        <IconSend size={20} />
        {sending ? "Sending…" : armed ? "Tap again to confirm" : "Publish now"}
      </button>
    </div>
  );
}
