import logging
from typing import Optional

import config
from extraction.preprocessor import CITY_MAP

logger = logging.getLogger(__name__)

VALID_CITIES = set(CITY_MAP.values())
VALID_RATE_ROLES = {"MARKET", "BUY", "SELL", "OFFICIAL", "UNKNOWN"}
VALID_TIME_CONTEXTS = {"CURRENT", "PREVIOUS", "FORECAST", "HISTORICAL", "UNKNOWN"}
VALID_PRODUCTS = {"usd_iqd", "silver_kg", "dubai_lira"}
# Precious-metal/fiat-coin quotes are quoted in USD per unit, not IQD per 100 USD.
METAL_MAX_RATE = 100000
VALID_CATEGORIES = {
    "5000_IQD_CATEGORY", "10000_IQD_CATEGORY", "25000_IQD_CATEGORY",
    "STANDARD_MIX", "MIXED", "BLUE_CATEGORY", "WHITE_CATEGORY", "UNKNOWN",
}


def validate_observation(obs: dict) -> tuple[bool, Optional[str]]:
    """
    Validate an extracted observation.
    Returns (is_valid, error_reason).
    """
    # Must have a rate
    rate = obs.get("rate")
    if not rate or not isinstance(rate, (int, float)):
        return False, "missing_or_invalid_rate"
    
    rate = int(rate)
    
    # Product-aware sanity range. USD/IQD rates are IQD per 100 USD (140-165k);
    # silver_kg / dubai_lira are USD per unit (e.g. 2180, 958) and must never be
    # tested against the IQD band.
    product = (obs.get("product") or "usd_iqd").lower()
    if product not in VALID_PRODUCTS:
        obs["product"] = product = "usd_iqd"
    if product == "usd_iqd":
        if rate < config.SANITY_MIN_RATE or rate > config.SANITY_MAX_RATE:
            return False, f"rate_out_of_range_{rate}"
    else:
        if rate <= 0 or rate > METAL_MAX_RATE:
            return False, f"rate_out_of_range_{rate}"
    
    # City validation (optional — some observations may not have a city)
    city = obs.get("city")
    if city and city.lower() not in VALID_CITIES:
        return False, f"unknown_city_{city}"
    
    # Rate role validation
    rate_role = obs.get("rate_role", "UNKNOWN")
    if rate_role not in VALID_RATE_ROLES:
        obs["rate_role"] = "UNKNOWN"
    
    # Time context validation
    time_ctx = obs.get("time_context", "UNKNOWN")
    if time_ctx not in VALID_TIME_CONTEXTS:
        obs["time_context"] = "UNKNOWN"
    
    # Category validation
    cat = obs.get("dollar_category_normalized")
    if cat and cat not in VALID_CATEGORIES:
        obs["dollar_category_normalized"] = "UNKNOWN"
    
    # Denomination check
    denom = obs.get("denomination", 100)
    if denom not in (50, 100):
        obs["denomination"] = 100
    
    # Confidence check
    conf = obs.get("confidence", 0.5)
    if not isinstance(conf, (int, float)) or conf < 0 or conf > 1:
        obs["confidence"] = 0.5
    
    return True, None


def validate_all(observations: list[dict]) -> tuple[list[dict], list[dict]]:
    """
    Validate a list of observations.
    Returns (valid_observations, rejected_observations).
    """
    valid = []
    rejected = []
    
    for obs in observations:
        is_valid, reason = validate_observation(obs)
        if is_valid:
            valid.append(obs)
        else:
            obs["_rejection_reason"] = reason
            rejected.append(obs)
            logger.debug(f"Rejected observation: {reason} | {obs.get('evidence_text', '')[:50]}")
    
    return valid, rejected
