import type { ReactElement } from "react";
import { IconChart, IconDoc, IconGear, IconHome } from "./Icons";

export type Tab = "home" | "rates" | "posts" | "settings";

interface Item {
  tab: Tab;
  label: string;
  Icon: (props: { size?: number }) => ReactElement;
}

const ITEMS: Item[] = [
  { tab: "home", label: "Home", Icon: IconHome },
  { tab: "rates", label: "Rates", Icon: IconChart },
  { tab: "posts", label: "Posts", Icon: IconDoc },
  { tab: "settings", label: "Settings", Icon: IconGear },
];

export default function NavBar({
  tab,
  onChange,
}: {
  tab: Tab;
  onChange: (tab: Tab) => void;
}) {
  return (
    <nav className="navbar">
      {ITEMS.map(({ tab: t, label, Icon }) => (
        <button
          key={t}
          className={`nav-item ${tab === t ? "active" : ""}`}
          onClick={() => onChange(t)}
        >
          <span className="nav-glow">
            <Icon size={22} />
          </span>
          {label}
          <span className="nav-dot" style={{ opacity: tab === t ? 1 : 0 }} />
        </button>
      ))}
    </nav>
  );
}
