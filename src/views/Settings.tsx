import { useEffect, useState } from "react";
import { api } from "../api";
import type { DashboardState } from "../types";
import { cityLabel } from "./Home";

export default function Settings({
  state,
  notify,
  onChanged,
}: {
  state: DashboardState | null;
  notify: (text: string, kind?: "ok" | "err") => void;
  onChanged: () => void;
}) {
  const [sourceLink, setSourceLink] = useState(false);

  useEffect(() => {
    api
      .sourceLink()
      .then((d) => setSourceLink(d.enabled))
      .catch(() => {
        /* keep default */
      });
  }, []);

  async function toggleSourceLink(v: boolean) {
    setSourceLink(v);
    try {
      await api.setSourceLink(v);
      notify(`Source link ${v ? "on" : "off"}`);
    } catch (e) {
      setSourceLink(!v);
      notify(e instanceof Error ? e.message : "Setting failed", "err");
    }
  }

  const sources = state?.sources ?? [];
  const targets = state?.targets ?? [];
  const subscribers = state?.subscribers ?? [];

  return (
    <div>
      <div className="title-block" style={{ marginBottom: 14 }}>
        <span className="title-line title-1" style={{ fontSize: 28 }}>
          Settings
        </span>
        <div className="title-sub">Bot, sources and publishing control</div>
      </div>

      <div className="toy white-card card">
        <div className="card-head">
          <span className="card-title">Post settings</span>
        </div>
        <div className="row">
          <div className="row-main">
            <div className="row-title">Show source channel link</div>
            <div className="row-sub">
              Adds 📍 with the latest price's channel at the bottom of each post
            </div>
          </div>
          <button
            className={`switch ${sourceLink ? "on" : ""}`}
            aria-label="Toggle source link"
            onClick={() => void toggleSourceLink(!sourceLink)}
          />
        </div>
      </div>

      <div className="toy white-card card">
        <div className="card-head">
          <span className="card-title">Source channels</span>
          <span className="pill pill-blue">{sources.length}</span>
        </div>
        {sources.length === 0 && (
          <div className="empty">No source channels configured.</div>
        )}
        {sources.map((s) => (
          <div className="row" key={s.username ?? s.name ?? "s"}>
            <div className="row-main">
              <div className="row-title">{s.name || s.username}</div>
              <div className="row-sub">
                @{s.username}
                {s.focused_categories?.length
                  ? ` · ${s.focused_categories.join(", ")}`
                  : ""}
              </div>
            </div>
            <span className={`pill ${s.active ? "pill-on" : "pill-off"}`}>
              {s.active ? "Collecting" : "Paused"}
            </span>
            <button
              className="btn btn-blue"
              style={{ padding: "6px 12px", fontSize: 12 }}
              onClick={() => {
                if (!s.username) return;
                void api
                  .toggleSource(s.username, !s.active)
                  .then(() => {
                    notify(`${s.username} ${s.active ? "paused" : "enabled"}`);
                    onChanged();
                  })
                  .catch((e) =>
                    notify(e instanceof Error ? e.message : "Failed", "err"),
                  );
              }}
            >
              {s.active ? "Pause" : "Enable"}
            </button>
          </div>
        ))}
      </div>

      <div className="toy white-card card">
        <div className="card-head">
          <span className="card-title">Publish targets</span>
          <span className="pill pill-blue">{targets.length}</span>
        </div>
        {targets.length === 0 && (
          <div className="empty">
            No destinations yet. Add the bot as admin and send /live_on in a
            channel.
          </div>
        )}
        {targets.map((t) => (
          <div className="row" key={t.chat_id ?? "t"}>
            <div className="row-main">
              <div className="row-title">{t.title}</div>
              <div className="row-sub">{t.username || t.chat_id}</div>
            </div>
            <span className={`pill ${t.enabled ? "pill-on" : "pill-off"}`}>
              {t.enabled ? "Publishing" : "Paused"}
            </span>
            <button
              className="btn btn-orange"
              style={{ padding: "6px 12px", fontSize: 12 }}
              onClick={() => {
                if (t.chat_id == null) return;
                void api
                  .toggleTarget(t.chat_id)
                  .then(() => {
                    notify("Target updated");
                    onChanged();
                  })
                  .catch((e) =>
                    notify(e instanceof Error ? e.message : "Failed", "err"),
                  );
              }}
            >
              {t.enabled ? "Pause" : "Enable"}
            </button>
          </div>
        ))}
      </div>

      <div className="toy white-card card">
        <div className="card-head">
          <span className="card-title">Bot subscribers</span>
          <span className="pill pill-blue">{subscribers.length}</span>
        </div>
        {subscribers.length === 0 && (
          <div className="empty">
            No users have started the bot yet. Share the bot link to grow your
            audience.
          </div>
        )}
        {subscribers.map((s) => (
          <div className="row" key={s.chat_id ?? "u"}>
            <div className="row-main">
              <div className="row-title">{s.first_name || "—"}</div>
              <div className="row-sub">
                {s.username ? `@${s.username}` : s.chat_id}
                {s.city ? ` · ${cityLabel(s.city)}` : ""}
              </div>
            </div>
            <span className={`pill ${s.subscribed ? "pill-on" : "pill-off"}`}>
              {s.subscribed ? "Subscribed" : "Paused"}
            </span>
            <button
              className="btn btn-blue"
              style={{ padding: "6px 12px", fontSize: 12 }}
              onClick={() => {
                if (s.chat_id == null) return;
                void api
                  .toggleSubscriber(s.chat_id)
                  .then(() => {
                    notify("Subscriber updated");
                    onChanged();
                  })
                  .catch((e) =>
                    notify(e instanceof Error ? e.message : "Failed", "err"),
                  );
              }}
            >
              {s.subscribed ? "Pause" : "Resume"}
            </button>
          </div>
        ))}
      </div>
    </div>
  );
}
