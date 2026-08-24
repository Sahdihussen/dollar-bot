import json
from datetime import datetime, timezone, timedelta
from typing import Optional

import database as db

TIMEZONE_OFFSET = 3


def _metals_block() -> str:
    """Build a compact precious-metals line (Dubai lira, silver per kg) if data exists."""
    out: list[str] = []
    for product, label in [("dubai_lira", "💎 دوبەی لیرا"), ("silver_kg", "🪙 زیو (کیلۆ)")]:
        # Only metals observed within the last 24h belong on a market board.
        rows = db.get_recent_by_product(product, 6, minutes=1440)
        if not rows:
            continue
        buy = next((r for r in rows if r.get("rate_role") == "BUY"), None)
        sell = next((r for r in rows if r.get("rate_role") == "SELL"), None)
        vals = []
        if buy:
            vals.append(f"{format_rate(int(buy['rate']))}$ (كڕین)")
        if sell:
            vals.append(f"{format_rate(int(sell['rate']))}$ (فرۆشتن)")
        if not vals:
            vals.append(f"{format_rate(int(rows[0]['rate']))}$")
        out.append(f"{label}: {' · '.join(vals)}")
    return "\n".join(out)


def _source_links(snapshots: list[dict]) -> str:
    """Return the channel that produced the latest (most recent) price."""
    newest_ts = ""
    newest_src = None
    for snap in snapshots:
        city = (snap.get("city") or "").lower()
        if not city:
            continue
        # get_recent_observations returns newest-first CURRENT observations for the city
        rows = db.get_recent_observations(city, limit=1)
        if not rows:
            continue
        ts = str(rows[0].get("created_at") or "")
        if rows[0].get("source") and ts > newest_ts:
            newest_ts = ts
            newest_src = rows[0].get("source")
    if not newest_src:
        return ""
    return f"📍 Source: t.me/{newest_src}"


def now_baghdad() -> datetime:
    """Get current time in Baghdad (GMT+3)."""
    return datetime.now(timezone.utc) + timedelta(hours=TIMEZONE_OFFSET)


def day_rate_stats() -> Optional[dict]:
    """Today's open/close/high/low from stored snapshot medians (Baghdad day).

    rate_history holds one row per snapshot update, newest first. Rows are
    filtered to the current Baghdad calendar day (the day boundary is 21:00 UTC
    because Baghdad is UTC+3). Returns None when nothing has been recorded yet
    today.
    """
    rows = db.get_rate_history_all(minutes=1440)
    if not rows:
        return None
    start_utc = (
        now_baghdad().replace(hour=0, minute=0, second=0, microsecond=0)
        - timedelta(hours=TIMEZONE_OFFSET)
    ).isoformat()
    today = [
        int(r["rate"]) for r in rows
        if r.get("rate") and (r.get("recorded_at") or "")[:19] >= start_utc[:19]
    ]
    if not today:
        return None
    return {
        "open": today[-1],   # oldest recorded today (rows are newest-first)
        "close": today[0],   # newest recorded today
        "high": max(today),
        "low": min(today),
    }


def format_rate(rate: int) -> str:
    """Format rate with comma separator: 152850 → 152,850"""
    return f"{rate:,}"


def format_market_board(snapshots: list[dict], category_data: dict[str, dict] = None) -> str:
    """
    Format the main market board for /price command.
    
    snapshots: list of latest market snapshots per city
    category_data: optional dict of city → {category → rate}
    """
    now = now_baghdad()
    time_str = now.strftime("%I:%M %p")
    date_str = now.strftime("%d/%m/%Y")
    
    lines = [
        f"💵 نرخی دۆلار | USD / IQD",
        f"🕐 {time_str} — {date_str}",
        "",
    ]
    
    # City display order and Kurdish names
    city_info = {
        "sulaymaniyah": ("سلێمانی", "sulaymaniyah"),
        "erbil": ("هەولێر", "erbil"),
        "baghdad": ("بغداد", "baghdad"),
        "mosul": ("مووسڵ", "mosul"),
        "basra": ("بەسرە", "basra"),
        "kirkuk": ("کەرکووک", "kirkuk"),
        "duhok": ("دهۆک", "duhok"),
    }
    
    # Category display
    cat_display = {
        "5000_IQD_CATEGORY": "🔵 پێنجی",
        "25000_IQD_CATEGORY": "🔴 سوور",
        "10000_IQD_CATEGORY": "🟡 دەیی",
        "STANDARD_MIX": "⚪ ستاندارد",
        "MIXED": "⚫ خبط",
        "BLUE_CATEGORY": "🔵 شین",
        "WHITE_CATEGORY": "⚪ سپی",
    }
    
    total_observations = 0
    all_rates = []
    
    for snap in snapshots:
        city = snap.get("city", "").lower()
        if city not in city_info:
            continue
        
        city_kurdish, city_en = city_info[city]
        lines.append(f"{city_kurdish}")
        
        # Category-specific rates
        cat_rates_raw = snap.get("category_rates")
        if cat_rates_raw:
            if isinstance(cat_rates_raw, str):
                try:
                    cat_rates = json.loads(cat_rates_raw)
                except json.JSONDecodeError:
                    cat_rates = {}
            else:
                cat_rates = cat_rates_raw
            
            for cat, rate in cat_rates.items():
                display = cat_display.get(cat, f"📊 {cat}")
                lines.append(f"{display}: {format_rate(rate)}")
        
        # Overall rate if no categories
        if not cat_rates_raw or (isinstance(cat_rates_raw, str) and cat_rates_raw == "{}"):
            consensus = snap.get("consensus_rate")
            if consensus:
                buy = snap.get("buy_rate")
                sell = snap.get("sell_rate")
                if buy and sell:
                    lines.append(f"📊 {format_rate(buy)} — {format_rate(sell)}")
                else:
                    lines.append(f"📊 {format_rate(consensus)}")
        
        obs_count = snap.get("observation_count", 0)
        total_observations += obs_count
        
        if snap.get("median_rate"):
            all_rates.append(snap["median_rate"])
        
        lines.append("")
    
    # Summary
    if all_rates:
        overall_median = sorted(all_rates)[len(all_rates) // 2]
        current_low = min(all_rates)
        current_high = max(all_rates)

        lines.extend([
            f"📊 نرخی بازاڕ: {format_rate(overall_median)} IQD",
            f"↔️ ئێستا: {format_rate(current_low)} — {format_rate(current_high)} IQD",
        ])
        # Today's TRUE extremes from stored rate history (Baghdad day) — not the
        # current across-city spread, which only reflects right-now quotes.
        stats = day_rate_stats()
        if stats:
            lines.extend([
                f"📈 بەرزترین ئەمڕۆ: {format_rate(stats['high'])}",
                f"📉 نزمترین ئەمڕۆ: {format_rate(stats['low'])}",
            ])
        lines.extend([
            "",
            f"Source: {total_observations} market observations",
        ])
        if db.get_setting("show_source_link", "off") == "on":
            src = _source_links(snapshots)
            if src:
                lines.append(src)
    
    # Precious-metals section (silver per kg, Dubai lira) — shown when data exists.
    metals = _metals_block()
    if metals:
        if lines and lines[-1] != "":
            lines.append("")
        lines.append(metals)
    
    return "\n".join(lines)


def format_city_comparison(snapshots: list[dict]) -> str:
    """Format city comparison table."""
    now = now_baghdad()
    time_str = now.strftime("%I:%M %p")
    
    city_names = {
        "sulaymaniyah": "سلێمانی",
        "erbil": "هەولێر",
        "baghdad": "بغداد",
        "mosul": "مووسڵ",
        "basra": "بەسرە",
        "kirkuk": "کەرکووک",
        "duhok": "دهۆک",
    }
    
    lines = [
        f"🌍 جیاوازی نرخی دۆلار",
        f"🕐 {time_str}",
        "",
        f"شار        نرخ",
        "─" * 25,
    ]
    
    rates_by_city = {}
    for snap in snapshots:
        city = snap.get("city", "").lower()
        rate = snap.get("median_rate")
        if city and rate:
            rates_by_city[city] = rate
            name = city_names.get(city, city)
            lines.append(f"{name}    {format_rate(rate)}")
    
    # Compare highest and lowest
    if len(rates_by_city) >= 2:
        max_city = max(rates_by_city, key=rates_by_city.get)
        min_city = min(rates_by_city, key=rates_by_city.get)
        diff = rates_by_city[max_city] - rates_by_city[min_city]
        
        lines.extend([
            "",
            f"{city_names.get(max_city, max_city)} ↔ {city_names.get(min_city, min_city)}: {format_rate(diff)} IQD",
        ])
    
    return "\n".join(lines)


def format_daily_summary(
    snapshots: list[dict],
    open_rate: Optional[int] = None,
    close_rate: Optional[int] = None,
    high_rate: Optional[int] = None,
    low_rate: Optional[int] = None,
) -> str:
    """Format daily closing report."""
    now = now_baghdad()
    date_str = now.strftime("%d/%m/%Y")
    
    city_names = {
        "sulaymaniyah": "سلێمانی",
        "erbil": "هەولێر",
        "baghdad": "بغداد",
    }
    
    lines = [
        f"🌙 کورتەی بازاڕی دۆلار — ئەمڕۆ",
        f"📅 {date_str}",
        "",
    ]
    
    if close_rate:
        lines.append(f"💵 Close: {format_rate(close_rate)}")
    if open_rate and close_rate:
        change = close_rate - open_rate
        sign = "+" if change >= 0 else ""
        lines.append(f"📈 Change: {sign}{format_rate(change)}")
    if high_rate:
        lines.append(f"📊 High: {format_rate(high_rate)}")
    if low_rate:
        lines.append(f"📉 Low: {format_rate(low_rate)}")
    if high_rate and low_rate:
        lines.append(f"↔️ Range: {format_rate(high_rate - low_rate)}")
    
    lines.append("")
    lines.append("By city:")
    lines.append("")
    
    for snap in snapshots:
        city = snap.get("city", "").lower()
        rate = snap.get("median_rate")
        if city and rate:
            name = city_names.get(city, city)
            lines.append(f"{name}: {format_rate(rate)}")
    
    return "\n".join(lines)


def format_sources(channels: list[dict]) -> str:
    """Format channel source information."""
    lines = [
        "📡 Monitored Channels",
        "",
    ]
    
    for ch in channels:
        name = ch.get("name", ch.get("username", "Unknown"))
        username = ch.get("username", "")
        status = "🟢" if ch.get("active") else "🔴"
        categories = ch.get("focused_categories")
        cat_str = ""
        if categories:
            if isinstance(categories, str):
                try:
                    categories = json.loads(categories)
                except json.JSONDecodeError:
                    categories = []
            if categories:
                cat_str = f" [{', '.join(categories)}]"
        
        lines.append(f"{status} {name} (@{username}){cat_str}")
    
    return "\n".join(lines)


def format_history(observations: list[dict]) -> str:
    """Format recent rate history."""
    if not observations:
        return "📊 No recent data available."
    
    lines = [
        "📊 ئەمڕۆنی نرخ",
        "",
    ]
    
    for obs in observations[:5]:
        rate = obs.get("rate", 0)
        city = obs.get("city", "unknown")
        time_str = obs.get("created_at", "")[:16].replace("T", " ")
        evidence = obs.get("evidence_text", "")[:30]
        
        lines.append(f"{time_str} | {city}: {format_rate(rate)}")
        if evidence:
            lines.append(f"  └ {evidence}")
    
    return "\n".join(lines)
