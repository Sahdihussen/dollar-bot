import logging
from typing import Optional
import statistics

import config
import database as db

logger = logging.getLogger(__name__)


def detect_outliers(observations: list[dict]) -> tuple[list[dict], list[dict]]:
    """
    Detect and quarantine outlier observations.
    Returns (clean_observations, quarantined_observations).
    
    Compares each observation's rate against recent rate history for its city.
    If the rate deviates more than OUTLIER_THRESHOLD_IQD from the median of recent rates,
    it's quarantined.
    """
    clean = []
    quarantined = []
    
    # Group observations by city
    by_city: dict[str, list[dict]] = {}
    for obs in observations:
        city = obs.get("city", "unknown")
        if city not in by_city:
            by_city[city] = []
        by_city[city].append(obs)
    
    for city, city_obs in by_city.items():
        if city == "unknown":
            # Can't check outliers without a city
            clean.extend(city_obs)
            continue
        
        # Get recent rate history for this city
        history = db.get_rate_history(city, minutes=60)
        recent_rates = [h["rate"] for h in history if h.get("rate")]
        
        if len(recent_rates) < 3:
            # Not enough history to detect outliers
            clean.extend(city_obs)
            continue
        
        try:
            median_rate = statistics.median(recent_rates)
        except statistics.StatisticsError:
            clean.extend(city_obs)
            continue
        
        for obs in city_obs:
            rate = obs.get("rate")
            if not rate:
                clean.append(obs)
                continue
            
            deviation = abs(rate - median_rate)
            if deviation > config.OUTLIER_THRESHOLD_IQD:
                obs["_outlier_info"] = {
                    "deviation": deviation,
                    "median": median_rate,
                    "threshold": config.OUTLIER_THRESHOLD_IQD,
                }
                quarantined.append(obs)
                logger.warning(
                    f"Outlier quarantined: {rate} (deviation {deviation} from median {median_rate}) "
                    f"in {city}: {obs.get('evidence_text', '')[:50]}"
                )
            else:
                clean.append(obs)
    
    if quarantined:
        logger.info(f"Quarantined {len(quarantined)} outlier observations")
    
    return clean, quarantined


def check_movement_threshold(city: str, old_rate: int, new_rate: int) -> Optional[dict]:
    """
    Check if rate movement exceeds threshold for market alert.
    Returns alert info dict if threshold exceeded, None otherwise.
    """
    if not old_rate or not new_rate:
        return None
    
    change = new_rate - old_rate
    abs_change = abs(change)
    
    if abs_change >= config.OUTLIER_THRESHOLD_IQD:
        direction = "UP" if change > 0 else "DOWN"
        return {
            "city": city,
            "old_rate": old_rate,
            "new_rate": new_rate,
            "change": change,
            "abs_change": abs_change,
            "direction": direction,
        }
    
    return None
