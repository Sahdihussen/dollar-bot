import { useEffect, useRef, useState } from "react";
import { api } from "../api";
import type { Template, TemplateVariable } from "../types";
import { IconPlus, IconSend, IconTrash } from "../components/Icons";

const DESTINATIONS = [
  { value: "all", label: "All live destinations" },
  { value: "baghdad", label: "Baghdad audience" },
  { value: "erbil", label: "Erbil audience" },
  { value: "sulaymaniyah", label: "Sulaymaniyah audience" },
];

export default function Posts({
  notify,
}: {
  notify: (text: string, kind?: "ok" | "err") => void;
}) {
  const [templates, setTemplates] = useState<Template[]>([]);
  const [variables, setVariables] = useState<TemplateVariable[]>([]);
  const [selectedId, setSelectedId] = useState<number | null>(null);
  const [name, setName] = useState("");
  const [destination, setDestination] = useState("all");
  const [body, setBody] = useState("");
  const [preview, setPreview] = useState("");
  const [status, setStatus] = useState("");
  const bodyRef = useRef<HTMLTextAreaElement>(null);

  useEffect(() => {
    api
      .templates()
      .then((data) => {
        setTemplates(data.templates ?? []);
        setVariables(data.variables ?? []);
        const first = data.templates?.[0];
        if (first) select(first);
      })
      .catch((e) =>
        notify(e instanceof Error ? e.message : "Failed to load templates", "err"),
      );
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, []);

  useEffect(() => {
    if (!body.trim()) {
      setPreview("");
      setStatus("");
      return;
    }
    const id = window.setTimeout(() => {
      api
        .preview(body)
        .then((res) => {
          setPreview(res.rendered ?? "");
          if (res.unknown_variables?.length) {
            setStatus("Unknown: " + res.unknown_variables.join(", "));
          } else {
            setStatus("");
          }
        })
        .catch(() => {
          /* preview is best-effort */
        });
    }, 450);
    return () => window.clearTimeout(id);
  }, [body]);

  function select(t: Template) {
    setSelectedId(t.id ?? null);
    setName(t.name ?? "");
    setDestination(t.destination ?? "all");
    setBody(t.body ?? "");
  }

  function newTemplate() {
    setSelectedId(null);
    setName("");
    setDestination("all");
    setBody("");
    setStatus("");
  }

  function insertVariable(key: string) {
    const area = bodyRef.current;
    if (!area) return;
    const start = area.selectionStart;
    const end = area.selectionEnd;
    const next = area.value.slice(0, start) + `{{${key}}}` + area.value.slice(end);
    setBody(next);
    requestAnimationFrame(() => {
      area.focus();
      area.selectionStart = area.selectionEnd = start + key.length + 4;
    });
  }

  async function save() {
    if (!name.trim() || !body.trim()) {
      setStatus("Name and body are required");
      return;
    }
    try {
      const res = await api.saveTemplate({
        id: selectedId,
        name,
        body,
        destination,
      });
      const saved = res.template;
      if (!saved) throw new Error("Template storage is unavailable");
      notify("Template saved");
      setSelectedId(saved.id ?? null);
      const data = await api.templates();
      setTemplates(data.templates ?? []);
      if (saved.id != null) setSelectedId(saved.id);
    } catch (e) {
      setStatus(e instanceof Error ? e.message : "Save failed");
    }
  }

  async function send() {
    if (!body.trim()) {
      setStatus("Nothing to send — write a post first");
      return;
    }
    setStatus("Sending…");
    try {
      const res = await api.sendTemplate({ name: name || "unsaved", body, destination });
      notify(
        res.queued
          ? "Queued — the bot will send it shortly"
          : `Sent to ${res.sent} recipient${res.sent === 1 ? "" : "s"}`,
      );
      setStatus("");
    } catch (e) {
      const msg = e instanceof Error ? e.message : "Send failed";
      setStatus(msg);
      notify(msg, "err");
    }
  }

  async function remove() {
    if (selectedId == null) return;
    try {
      await api.deleteTemplate(selectedId);
      notify("Template deleted");
      newTemplate();
      const data = await api.templates();
      setTemplates(data.templates ?? []);
      const first = data.templates?.[0];
      if (first) select(first);
    } catch (e) {
      notify(e instanceof Error ? e.message : "Delete failed", "err");
    }
  }

  return (
    <div>
      <div className="title-block" style={{ marginBottom: 14 }}>
        <span className="title-line title-1" style={{ fontSize: 28 }}>
          Post Templates
        </span>
        <div className="title-sub">Write once, render with live variables</div>
      </div>

      <div className="toy white-card card">
        <div className="card-head">
          <span className="card-title">Saved posts</span>
          <button className="btn btn-green" onClick={newTemplate}>
            <IconPlus size={15} /> New
          </button>
        </div>
        {templates.length === 0 && (
          <div className="empty">
            No saved templates yet — create your first post below.
          </div>
        )}
        {templates.map((t) => (
          <button
            key={t.id}
            onClick={() => select(t)}
            style={{
              display: "block",
              width: "100%",
              textAlign: "left",
              border: "none",
              background: "transparent",
              padding: 0,
              cursor: "pointer",
            }}
          >
            <div
              className="row"
              style={{
                borderRadius: 14,
                background: t.id === selectedId ? "#e3f4ff" : "transparent",
                padding: "10px 12px",
              }}
            >
              <div className="row-main">
                <div className="row-title">{t.name ?? "Untitled"}</div>
                <div className="row-sub">
                  {t.body ?? ""} · {t.destination ?? "all"}
                </div>
              </div>
            </div>
          </button>
        ))}
      </div>

      <div className="toy white-card card">
        <div className="card-head">
          <span className="card-title">Editor</span>
          <span className="pill pill-blue">{selectedId ? "saved" : "new"}</span>
        </div>

        <div className="field">
          <label>Template name</label>
          <input
            className="input"
            value={name}
            onChange={(e) => setName(e.target.value)}
            placeholder="Evening market update"
          />
        </div>

        <div className="field">
          <label>Destination</label>
          <select
            className="select"
            value={destination}
            onChange={(e) => setDestination(e.target.value)}
          >
            {DESTINATIONS.map((d) => (
              <option key={d.value} value={d.value}>
                {d.label}
              </option>
            ))}
          </select>
        </div>

        <div className="field">
          <label>Post body · use {"{{variable}}"}</label>
          <textarea
            ref={bodyRef}
            className="textarea"
            value={body}
            onChange={(e) => setBody(e.target.value)}
            placeholder="Hello guys, now price is {{current_price_iqd}}"
          />
        </div>

        <div className="field">
          <label>Insert variable</label>
          <div className="chips">
            {variables.map((v) => (
              <button
                key={v.key}
                className="chip-var"
                title={v.description}
                onClick={() => insertVariable(v.key)}
              >
                {"{{" + v.key + "}}"}
              </button>
            ))}
          </div>
        </div>

        <div className="field">
          <label>Live preview</label>
          <div className="preview-box">
            {preview || "Start writing to preview this post."}
          </div>
        </div>

        <div className="chips" style={{ gap: 10 }}>
          <button className="btn btn-blue" onClick={() => void save()}>
            Save template
          </button>
          <button className="btn btn-green" onClick={() => void send()}>
            <IconSend size={15} /> Send now
          </button>
          {selectedId != null && (
            <button className="btn btn-red" onClick={() => void remove()}>
              <IconTrash size={15} /> Delete
            </button>
          )}
        </div>
        {status && <p className="hint" style={{ marginTop: 10 }}>{status}</p>}
      </div>
    </div>
  );
}
