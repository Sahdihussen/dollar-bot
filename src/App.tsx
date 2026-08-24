import { useCallback, useEffect, useRef, useState } from "react";
import { api } from "./api";
import type { DashboardState } from "./types";
import Background from "./components/Background";
import NavBar, { type Tab } from "./components/NavBar";
import { IconBolt, IconCheck } from "./components/Icons";
import Home from "./views/Home";
import Rates from "./views/Rates";
import Posts from "./views/Posts";
import Settings from "./views/Settings";

export default function App() {
  const [tab, setTab] = useState<Tab>("home");
  const [state, setState] = useState<DashboardState | null>(null);
  const [toast, setToast] = useState<{ text: string; kind: "ok" | "err" } | null>(
    null,
  );
  const toastTimer = useRef<number | undefined>(undefined);

  const refresh = useCallback(async () => {
    try {
      setState(await api.dashboard());
    } catch {
      // Keep the last known state; tiles fall back to placeholders.
    }
  }, []);

  useEffect(() => {
    void refresh();
    const id = window.setInterval(() => void refresh(), 30000);
    return () => window.clearInterval(id);
  }, [refresh]);

  const notify = useCallback((text: string, kind: "ok" | "err" = "ok") => {
    setToast({ text, kind });
    window.clearTimeout(toastTimer.current);
    toastTimer.current = window.setTimeout(() => setToast(null), 3400);
  }, []);

  return (
    <>
      <Background />
      <div className="phone">
        {toast && (
          <div className={`toast ${toast.kind}`}>
            {toast.kind === "ok" ? (
              <IconCheck size={16} />
            ) : (
              <IconBolt size={16} />
            )}
            <span>{toast.text}</span>
          </div>
        )}
        <div className="screen">
          {tab === "home" && (
            <Home state={state} notify={notify} onChanged={refresh} onNavigate={setTab} />
          )}
          {tab === "rates" && <Rates state={state} notify={notify} />}
          {tab === "posts" && <Posts notify={notify} />}
          {tab === "settings" && (
            <Settings state={state} notify={notify} onChanged={refresh} />
          )}
        </div>
        <NavBar tab={tab} onChange={setTab} />
      </div>
    </>
  );
}
