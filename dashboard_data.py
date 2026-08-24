import json
import logging
from datetime import datetime, timezone
from typing import Any

import config
import database as db

logger = logging.getLogger(__name__)

DEMO_SNAPSHOTS = [
    {
        "city": "sulaymaniyah",
        "market_layer": "local_market",
        "median_rate": 152850,
        "consensus_rate": 152850,
        "min_rate": 152800,
        "max_rate": 152950,
        "spread": 150,
        "observation_count": 18,
        "source_count": 5,
        "freshest_at": datetime.now(timezone.utc).isoformat(),
        "category_rates": json.dumps({"5000_IQD_CATEGORY": 152850, "25000_IQD_CATEGORY": 152950}),
        "snapshot_at": datetime.now(timezone.utc).isoformat(),
    },
    {
        "city": "erbil",
        "market_layer": "bourse",
        "median_rate": 152900,
        "consensus_rate": 152900,
        "min_rate": 152850,
        "max_rate": 152950,
        "spread": 100,
        "observation_count": 14,
        "source_count": 4,
        "freshest_at": datetime.now(timezone.utc).isoformat(),
        "category_rates": json.dumps({"5000_IQD_CATEGORY": 152900}),
        "snapshot_at": datetime.now(timezone.utc).isoformat(),
    },
    {
        "city": "baghdad",
        "market_layer": "AL_KIFAH_BOURSE",
        "median_rate": 152750,
        "consensus_rate": 152750,
        "min_rate": 152700,
        "max_rate": 152850,
        "spread": 150,
        "observation_count": 21,
        "source_count": 6,
        "freshest_at": datetime.now(timezone.utc).isoformat(),
        "category_rates": json.dumps({"STANDARD_MIX": 152750}),
        "snapshot_at": datetime.now(timezone.utc).isoformat(),
    },
]

DEMO_SOURCES = [
    {"username": "pashagoldd", "name": "Pasha Gold", "active": True},
    {"username": "borsat_alkfah", "name": "Borsa Al-Kifah", "active": True},
    {"username": "Borsa_Erbil", "name": "Borsa Erbil", "active": True},
    {"username": "PMCgroup", "name": "PMC Group", "active": True},
    {"username": "NrxiDraw24", "name": "NRXI Draw 24", "active": True, "focused_categories": ["silber_kg", "dubai_lira"]},
    {"username": "nrxidraw852", "name": "NRXI Draw 852", "active": True, "focused_categories": ["silber_kg", "dubai_lira"]},
    {"username": "YarGold_Co", "name": "Yar Gold Co", "active": True, "focused_categories": ["silber_kg", "dubai_lira"]},
]


def safe_snapshots() -> tuple[list[dict], bool]:
    """Return (snapshots, db_unreachable). Demo data only when the DB is unreachable.

    Only cities refreshed within the last 2 hours are included, so boards,
    template renders, and the dashboard never show stale prices.
    """
    try:
        return db.get_fresh_snapshots(), False
    except Exception:
        return DEMO_SNAPSHOTS, True


def safe_sources() -> tuple[list[dict], bool]:
    try:
        return db.get_active_channels(), False
    except Exception:
        return DEMO_SOURCES, True


def safe_targets() -> tuple[list[dict], bool]:
    try:
        return db.get_publish_targets(), False
    except Exception:
        return [], True


def safe_subscriber_count() -> int:
    try:
        return len(db.get_subscribers())
    except Exception:
        return 0


def safe_subscribers() -> list[dict]:
    try:
        return db.get_all_subscribers()
    except Exception:
        return []


def normalize_snapshot(snapshot: dict) -> dict:
    category_rates = snapshot.get("category_rates") or {}
    if isinstance(category_rates, str):
        try:
            category_rates = json.loads(category_rates)
        except json.JSONDecodeError:
            category_rates = {}
    return {
        "city": snapshot.get("city"),
        "market_layer": snapshot.get("market_layer") or "unknown",
        "rate": snapshot.get("median_rate") or snapshot.get("consensus_rate"),
        "min_rate": snapshot.get("min_rate"),
        "max_rate": snapshot.get("max_rate"),
        "spread": snapshot.get("spread"),
        "observation_count": snapshot.get("observation_count", 0),
        "source_count": snapshot.get("source_count", 0),
        "freshest_at": snapshot.get("freshest_at") or snapshot.get("snapshot_at"),
        "category_rates": category_rates,
    }


def dashboard_state() -> dict[str, Any]:
    snapshots, snapshots_demo = safe_snapshots()
    sources, sources_demo = safe_sources()
    targets, targets_demo = safe_targets()
    subscriber_count = safe_subscriber_count()
    subscribers = safe_subscribers()
    normalized = [normalize_snapshot(row) for row in snapshots]
    observation_count = sum(int(row.get("observation_count") or 0) for row in normalized)
    db_ok = not (snapshots_demo or sources_demo or targets_demo)
    return {
        "service": "dollar-bot",
        "version": "1.0.0",
        "runtime": "Python 3.11",
        "listener": "connected",
        "source_count": len(sources),
        "target_count": len(targets),
        "subscriber_count": subscriber_count,
        "subscribers": subscribers,
        "observation_count": observation_count,
        "snapshots": normalized,
        "sources": sources,
        "targets": targets,
        "demo_data": snapshots_demo or sources_demo or targets_demo,
        "db_connected": db_ok,
        "waiting_for_data": db_ok and not normalized,
        "checked_at": datetime.now(timezone.utc).isoformat(),
        "config": {
            "sanity_min_rate": config.SANITY_MIN_RATE,
            "sanity_max_rate": config.SANITY_MAX_RATE,
            "outlier_threshold_iqd": config.OUTLIER_THRESHOLD_IQD,
            "live_publish_cooldown_seconds": 120,
        },
    }
