import hashlib
import logging
from typing import Optional

logger = logging.getLogger(__name__)


def make_dedup_key(obs: dict) -> str:
    """
    Create a composite deduplication key from an observation.
    Based on: source + city + market + rate + label + category + post_id
    """
    parts = [
        str(obs.get("source", "")),
        str(obs.get("city", "")),
        str(obs.get("market_layer", "")),
        str(obs.get("rate", "")),
        str(obs.get("quote_label_normalized", "")),
        str(obs.get("dollar_category_normalized", "")),
        str(obs.get("product", "usd_iqd")),
        str(obs.get("raw_post_id", "")),
    ]
    raw = "|".join(parts)
    return hashlib.md5(raw.encode()).hexdigest()


def deduplicate(observations: list[dict]) -> list[dict]:
    """
    Remove duplicate observations based on composite key.
    """
    seen = set()
    unique = []
    
    for obs in observations:
        key = make_dedup_key(obs)
        if key not in seen:
            seen.add(key)
            unique.append(obs)
        else:
            logger.debug(f"Duplicate removed: {obs.get('evidence_text', '')[:50]}")
    
    removed = len(observations) - len(unique)
    if removed > 0:
        logger.info(f"Dedup removed {removed} duplicates")
    
    return unique
