import re
from datetime import datetime, timezone, timedelta
from typing import Any

from dashboard_data import dashboard_state

TIMEZONE_OFFSET = 3

VARIABLES = [
    {"key": "current_price", "label": "Current market price", "example": "152,850", "description": "Overall median USD/100 IQD rate"},
    {"key": "current_price_iqd", "label": "Current price with IQD", "example": "152,850 IQD", "description": "Overall median with currency"},
    {"key": "baghdad_price", "label": "Baghdad price", "example": "152,750", "description": "Latest Baghdad median"},
    {"key": "erbil_price", "label": "Erbil price", "example": "152,900", "description": "Latest Erbil median"},
    {"key": "sulaymaniyah_price", "label": "Sulaymaniyah price", "example": "152,850", "description": "Latest Sulaymaniyah median"},
    {"key": "buy_rate", "label": "Buy rate", "example": "152,800", "description": "Validated buy-side rate when available"},
    {"key": "sell_rate", "label": "Sell rate", "example": "152,950", "description": "Validated sell-side rate when available"},
    {"key": "market_high", "label": "Market high", "example": "152,950", "description": "Highest current city snapshot"},
    {"key": "market_low", "label": "Market low", "example": "152,700", "description": "Lowest current city snapshot"},
    {"key": "market_spread", "label": "Market spread", "example": "250 IQD", "description": "High minus low"},
    {"key": "observation_count", "label": "Observation count", "example": "53", "description": "Current validated observations"},
    {"key": "source_count", "label": "Source count", "example": "14", "description": "Active source channels"},
    {"key": "time", "label": "Baghdad time", "example": "08:45 PM", "description": "Current Iraq/Kurdistan time"},
    {"key": "date", "label": "Baghdad date", "example": "24/08/2026", "description": "Current Iraq/Kurdistan date"},
    {"key": "movement", "label": "Movement", "example": "+150 IQD", "description": "Reserved for latest movement calculation"},
]


def _rate_map(state: dict) -> dict[str, dict]:
    return {snapshot.get("city"): snapshot for snapshot in state.get("snapshots", [])}


def variable_values(state: dict | None = None) -> dict[str, str]:
    state = state or dashboard_state()
    snapshots = state.get("snapshots", [])
    rates = [int(item["rate"]) for item in snapshots if item.get("rate") is not None]
    city_rates = _rate_map(state)
    current = int(sorted(rates)[len(rates) // 2]) if rates else None
    buy = [item.get("buy_rate") for item in snapshots if item.get("buy_rate")]
    sell = [item.get("sell_rate") for item in snapshots if item.get("sell_rate")]
    now = datetime.now(timezone.utc) + timedelta(hours=TIMEZONE_OFFSET)
    values = {
        "current_price": f"{current:,}" if current else "N/A",
        "current_price_iqd": f"{current:,} IQD" if current else "N/A",
        "baghdad_price": f"{city_rates.get('baghdad', {}).get('rate'):,}" if city_rates.get("baghdad", {}).get("rate") else "N/A",
        "erbil_price": f"{city_rates.get('erbil', {}).get('rate'):,}" if city_rates.get("erbil", {}).get("rate") else "N/A",
        "sulaymaniyah_price": f"{city_rates.get('sulaymaniyah', {}).get('rate'):,}" if city_rates.get("sulaymaniyah", {}).get("rate") else "N/A",
        "buy_rate": f"{int(sorted(buy)[len(buy) // 2]):,}" if buy else "N/A",
        "sell_rate": f"{int(sorted(sell)[len(sell) // 2]):,}" if sell else "N/A",
        "market_high": f"{max(rates):,}" if rates else "N/A",
        "market_low": f"{min(rates):,}" if rates else "N/A",
        "market_spread": f"{max(rates) - min(rates):,} IQD" if rates else "N/A",
        "observation_count": f"{state.get('observation_count', 0):,}",
        "source_count": f"{state.get('source_count', 0):,}",
        "time": now.strftime("%I:%M %p"),
        "date": now.strftime("%d/%m/%Y"),
        "movement": "N/A",
    }
    return values


def render_template(template: str, state: dict | None = None) -> dict[str, Any]:
    values = variable_values(state)
    unknown: list[str] = []

    def replace(match: re.Match) -> str:
        key = match.group(1).strip()
        if key not in values:
            unknown.append(key)
            return f"{{{{{key}}}}}"
        return values[key]

    rendered = re.sub(r"\{\{\s*([a-zA-Z0-9_]+)\s*\}\}", replace, template)
    return {"rendered": rendered, "unknown_variables": sorted(set(unknown)), "values": values}
