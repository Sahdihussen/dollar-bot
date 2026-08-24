import json
import logging
import statistics
from datetime import datetime, timezone
from typing import Optional

import database as db

logger = logging.getLogger(__name__)


def calculate_snapshot(city: str, observations: list[dict]) -> Optional[dict]:
    """
    Calculate a market snapshot for a city from its observations.
    Uses median for consensus, not mean.
    Only includes CURRENT observations.
    """
    current_obs = [
        o for o in observations
        if o.get("time_context") == "CURRENT"
        and o.get("rate")
        and (o.get("product") or "usd_iqd") == "usd_iqd"
    ]
    
    if not current_obs:
        return None
    
    rates = [int(o["rate"]) for o in current_obs]
    
    # Overall consensus
    median_rate = int(statistics.median(rates))
    min_rate = min(rates)
    max_rate = max(rates)
    spread = max_rate - min_rate
    
    # Buy/Sell detection
    buy_rates = [int(o["rate"]) for o in current_obs if o.get("rate_role") == "BUY"]
    sell_rates = [int(o["rate"]) for o in current_obs if o.get("rate_role") == "SELL"]
    
    buy_rate = int(statistics.median(buy_rates)) if buy_rates else None
    sell_rate = int(statistics.median(sell_rates)) if sell_rates else None
    
    # Source count (unique sources)
    sources = set(o.get("source", "unknown") for o in current_obs)
    
    # Category breakdown
    category_rates = {}
    for obs in current_obs:
        cat = obs.get("dollar_category_normalized")
        if cat and cat != "UNKNOWN":
            if cat not in category_rates:
                category_rates[cat] = []
            category_rates[cat].append(int(obs["rate"]))
    
    # Take median for each category
    for cat in category_rates:
        category_rates[cat] = int(statistics.median(category_rates[cat]))
    
    # Market layer detection
    market_layer = "local_market"
    for obs in current_obs:
        ml = obs.get("market_layer")
        if ml and ml != "UNKNOWN":
            market_layer = ml
            break
    
    # Freshest observation
    freshest = max(current_obs, key=lambda o: o.get("created_at", ""), default=None)
    freshest_at = freshest.get("created_at") if freshest else datetime.now(timezone.utc).isoformat()
    
    snapshot = {
        "city": city,
        "market_layer": market_layer,
        "consensus_rate": median_rate,
        "median_rate": median_rate,
        "min_rate": min_rate,
        "max_rate": max_rate,
        "spread": spread,
        "buy_rate": buy_rate,
        "sell_rate": sell_rate,
        "observation_count": len(current_obs),
        "source_count": len(sources),
        "freshest_at": freshest_at,
        "category_rates": json.dumps(category_rates),
        "snapshot_at": datetime.now(timezone.utc).isoformat(),
    }
    
    return snapshot


def update_snapshots(observations: list[dict]):
    """
    Recalculate and store snapshots for all cities affected by new observations.
    Also stores rate history entries.
    """
    cities = set(o.get("city") for o in observations if o.get("city"))
    
    for city in cities:
        # Only observations from the last 2 hours feed the consensus, so a
        # quiet city's snapshot can't mix yesterday's rates into today's board.
        city_obs = db.get_recent_observations(city, limit=50, minutes=120)
        snapshot = calculate_snapshot(city, city_obs)
        
        if snapshot:
            db.store_snapshot(snapshot)
            db.store_rate_history(city, snapshot["median_rate"])
            logger.info(f"Updated snapshot for {city}: {snapshot['median_rate']} IQD")


def get_latest_snapshots() -> list[dict]:
    """Get the latest snapshot for each city."""
    return db.get_all_latest_snapshots()


def get_snapshot_for_city(city: str) -> Optional[dict]:
    """Get the latest snapshot for a specific city."""
    return db.get_latest_snapshot(city)
