import logging
from datetime import datetime, timezone, timedelta
from typing import Optional

import database as db
from extraction.outlier import check_movement_threshold

logger = logging.getLogger(__name__)


def check_all_cities_for_alerts() -> list[dict]:
    """
    Check all cities for significant rate movements.
    Returns list of alert dicts for cities that exceeded threshold.
    """
    alerts = []
    
    snapshots = db.get_all_latest_snapshots()
    cities_with_data = {s["city"]: s for s in snapshots if s.get("city") and s.get("median_rate")}
    
    for city, current_snap in cities_with_data.items():
        history = db.get_rate_history(city, minutes=30)
        
        if len(history) < 2:
            continue
        
        # Compare current rate with the rate from ~15-30 minutes ago
        old_entry = None
        current_time = datetime.now(timezone.utc)
        
        for entry in history:
            recorded = entry.get("recorded_at", "")
            try:
                recorded_dt = datetime.fromisoformat(recorded.replace("Z", "+00:00"))
                diff = current_time - recorded_dt
                if timedelta(minutes=10) <= diff <= timedelta(minutes=30):
                    old_entry = entry
                    break
            except (ValueError, TypeError):
                continue
        
        if not old_entry:
            continue
        
        old_rate = old_entry.get("rate")
        new_rate = current_snap["median_rate"]
        
        alert_info = check_movement_threshold(city, old_rate, new_rate)
        if alert_info:
            alert_info["current_snapshot"] = current_snap
            alerts.append(alert_info)
            logger.warning(f"Market alert: {city} moved {alert_info['change']} IQD")
    
    return alerts


def format_alert_message(alert: dict) -> str:
    """Format an alert into a Telegram-ready message."""
    city = alert["city"].upper()
    old_rate = alert["old_rate"]
    new_rate = alert["new_rate"]
    change = alert["change"]
    direction = alert["direction"]
    
    arrow = "🔺" if direction == "UP" else "📉"
    
    # City names in Kurdish
    city_names = {
        "baghdad": "بغداد",
        "erbil": "هەولێر",
        "sulaymaniyah": "سلێمانی",
        "mosul": "مووسڵ",
        "basra": "بەسرە",
        "kirkuk": "کەرکووک",
        "duhok": "دهۆک",
    }
    city_kurdish = city_names.get(alert["city"].lower(), city)
    
    return (
        f"🚨 دۆلار جوڵا\n\n"
        f"USD/100: {old_rate:,} → {new_rate:,}\n"
        f"{arrow} {'+' if change > 0 else ''}{change:,} IQD\n\n"
        f"📍 {city_kurdish}\n"
        f"⏱ Within last 30 minutes"
    )
