import json
import logging
from datetime import datetime, timedelta, timezone
from typing import Any, Optional

from supabase import create_client, Client
import config

logger = logging.getLogger(__name__)

_client: Optional[Client] = None


def get_client() -> Client:
    global _client
    if _client is None:
        _client = create_client(config.SUPABASE_URL, config.SUPABASE_SERVICE_ROLE_KEY)
    return _client


def store_raw_post(channel_username: str, message_id: int, text: str, published_at: Optional[datetime] = None) -> Optional[dict]:
    db = get_client()
    try:
        result = db.table("raw_posts").upsert({
            "channel_username": channel_username,
            "telegram_message_id": message_id,
            "raw_text": text,
            "post_url": f"https://t.me/{channel_username}/{message_id}",
            "published_at": published_at.isoformat() if published_at else datetime.now(timezone.utc).isoformat(),
            "received_at": datetime.now(timezone.utc).isoformat(),
            "processed": False,
        }, on_conflict="channel_username,telegram_message_id").execute()
        return result.data[0] if result.data else None
    except Exception as e:
        logger.error(f"Failed to store raw post: {e}")
        return None


def mark_post_processed(post_id: int):
    db = get_client()
    try:
        db.table("raw_posts").update({"processed": True}).eq("id", post_id).execute()
    except Exception as e:
        logger.error(f"Failed to mark post {post_id} as processed: {e}")


def get_unprocessed_posts(limit: int = 50) -> list[dict]:
    db = get_client()
    try:
        result = db.table("raw_posts").select("*").eq("processed", False).order("received_at", desc=False).limit(limit).execute()
        return result.data or []
    except Exception as e:
        logger.error(f"Failed to get unprocessed posts: {e}")
        return []


def get_setting(key: str, default: str = "") -> str:
    """Read a boolean-ish string setting (value is a string like 'on'/'off')."""
    db = get_client()
    try:
        rows = db.table("bot_settings").select("value").eq("key", key).limit(1).execute().data or []
        return rows[0].get("value") if rows else default
    except Exception as e:
        logger.error(f"Failed to get setting {key}: {type(e).__name__}")
        return default


def set_setting(key: str, value: str) -> Optional[dict]:
    """Write a setting (key-value)."""
    db = get_client()
    try:
        result = db.table("bot_settings").upsert({
            "key": key,
            "value": value,
        }, on_conflict="key").execute()
        return result.data[0] if result.data else None
    except Exception as e:
        logger.error(f"Failed to set setting {key}: {type(e).__name__}")
        return None


def store_observation(obs: dict) -> Optional[dict]:
    db = get_client()
    try:
        result = db.table("observations").insert(obs).execute()
        return result.data[0] if result.data else None
    except Exception as e:
        logger.error(f"Failed to store observation: {e}")
        return None


def get_recent_observations(city: str, limit: int = 20, minutes: Optional[int] = None) -> list[dict]:
    db = get_client()
    try:
        query = (
            db.table("observations")
            .select("*")
            .eq("city", city)
            .eq("time_context", "CURRENT")
        )
        if minutes:
            cutoff = (datetime.now(timezone.utc) - timedelta(minutes=minutes)).isoformat()
            query = query.gte("created_at", cutoff)
        result = query.order("created_at", desc=True).limit(limit).execute()
        return result.data or []
    except Exception as e:
        logger.error(f"Failed to get recent observations for {city}: {e}")
        return []


def get_recent_by_product(product: str, limit: int = 5, minutes: Optional[int] = None) -> list[dict]:
    """Return the newest CURRENT observations for a product (silver_kg, dubai_lira)."""
    db = get_client()
    try:
        query = (
            db.table("observations")
            .select("*")
            .eq("product", product)
            .eq("time_context", "CURRENT")
        )
        if minutes:
            cutoff = (datetime.now(timezone.utc) - timedelta(minutes=minutes)).isoformat()
            query = query.gte("created_at", cutoff)
        result = query.order("created_at", desc=True).limit(limit).execute()
        return result.data or []
    except Exception as e:
        logger.error(f"Failed to get recent {product} observations: {type(e).__name__}")
        return []


def get_latest_snapshot(city: Optional[str] = None) -> Optional[dict]:
    db = get_client()
    try:
        query = db.table("market_snapshots").select("*").order("snapshot_at", desc=True)
        if city:
            query = query.eq("city", city)
        result = query.limit(1).execute()
        return result.data[0] if result.data else None
    except Exception as e:
        logger.error(f"Failed to get latest snapshot: {e}")
        return None


def get_all_latest_snapshots() -> list[dict]:
    db = get_client()
    try:
        result = db.rpc("get_latest_snapshots_per_city").execute()
        if result.data:
            return result.data
        # Fallback: get latest for each city manually
        cities = ["baghdad", "erbil", "sulaymaniyah", "mosul", "basra", "kirkuk", "duhok"]
        snapshots = []
        for city in cities:
            snap = get_latest_snapshot(city)
            if snap:
                snapshots.append(snap)
        return snapshots
    except Exception as e:
        logger.error(f"Failed to get all latest snapshots: {e}")
        return []


def snapshot_is_fresh(ts: Optional[str], cutoff_iso: str) -> bool:
    """
    Compare a Supabase timestamp against an ISO cutoff at second precision.

    Supabase returns UTC timestamps with variable microsecond widths (e.g.
    `...18.49488+00:00` vs `...18.494880+00:00`), so parse-free second-precision
    string comparison is used; a 120-minute freshness window is unaffected by
    sub-second differences.
    """
    if not ts:
        return False
    return ts[:19] >= cutoff_iso[:19]


def get_fresh_snapshots(max_age_minutes: int = 120) -> list[dict]:
    """
    Latest snapshot per city, filtered to cities refreshed within the window.

    Used by the live board and dashboard-triggered publishes so a city that
    goes quiet never keeps its old price on the board.
    """
    snapshots = get_all_latest_snapshots()
    if not snapshots:
        return []
    cutoff = (datetime.now(timezone.utc) - timedelta(minutes=max_age_minutes)).isoformat()
    fresh = [s for s in snapshots if snapshot_is_fresh(s.get("freshest_at") or s.get("snapshot_at"), cutoff)]
    return fresh


def store_snapshot(snapshot: dict) -> Optional[dict]:
    db = get_client()
    try:
        result = db.table("market_snapshots").insert(snapshot).execute()
        return result.data[0] if result.data else None
    except Exception as e:
        logger.error(f"Failed to store snapshot: {e}")
        return None


def store_rate_history(city: str, rate: int):
    db = get_client()
    try:
        db.table("rate_history").insert({
            "city": city,
            "rate": rate,
            "recorded_at": datetime.now(timezone.utc).isoformat(),
        }).execute()
    except Exception as e:
        logger.error(f"Failed to store rate history: {e}")


def get_rate_history_all(minutes: int = 1440) -> list[dict]:
    """Return recent rate_history rows across all cities, newest first, within the window.

    Used to compute the day's true high/low/open/close from stored snapshot
    medians regardless of which city produced them.
    """
    db = get_client()
    try:
        cutoff = (datetime.now(timezone.utc) - timedelta(minutes=minutes)).isoformat()
        result = (
            db.table("rate_history")
            .select("*")
            .gte("recorded_at", cutoff)
            .order("recorded_at", desc=True)
            .limit(500)
            .execute()
        )
        return result.data or []
    except Exception as e:
        logger.error(f"Failed to get all rate history: {e}")
        return []


def get_rate_history(city: str, minutes: int = 60) -> list[dict]:
    db = get_client()
    try:
        cutoff = (datetime.now(timezone.utc) - timedelta(minutes=minutes)).isoformat()
        result = (
            db.table("rate_history")
            .select("*")
            .eq("city", city)
            .gte("recorded_at", cutoff)
            .order("recorded_at", desc=True)
            .limit(100)
            .execute()
        )
        return result.data or []
    except Exception as e:
        logger.error(f"Failed to get rate history for {city}: {e}")
        return []


def get_active_channels() -> list[dict]:
    """Return active monitored market source channels from the dedicated table."""
    db = get_client()
    try:
        result = db.table("source_channels").select("*").eq("active", True).order("username", desc=False).execute()
        return result.data or []
    except Exception as e:
        logger.error("Failed to get active source channels: %s", type(e).__name__)
        return []


def get_publish_targets() -> list[dict]:
    """Return enabled Telegram destinations for live and scheduled publishing."""
    db = get_client()
    try:
        result = (
            db.table("publish_targets")
            .select("*")
            .eq("enabled", True)
            .order("created_at", desc=False)
            .execute()
        )
        return result.data or []
    except Exception as e:
        logger.error("Failed to get publish targets: %s", type(e).__name__)
        return []


def upsert_publish_target(chat_id: int, title: str, username: Optional[str] = None) -> Optional[dict]:
    """Enable a Telegram chat as a publishing destination."""
    db = get_client()
    try:
        result = db.table("publish_targets").upsert({
            "chat_id": chat_id,
            "title": title,
            "username": username,
            "enabled": True,
            "updated_at": datetime.now(timezone.utc).isoformat(),
        }, on_conflict="chat_id").execute()
        return result.data[0] if result.data else None
    except Exception as e:
        logger.error("Failed to enable publish target: %s", type(e).__name__)
        return None


def add_publish_target_if_missing(chat_id: int, title: str, username: Optional[str] = None) -> Optional[dict]:
    """Register a destination only if it is not already present (preserves user toggles)."""
    db = get_client()
    try:
        result = db.table("publish_targets").upsert({
            "chat_id": chat_id,
            "title": title,
            "username": username,
            "enabled": True,
        }, on_conflict="chat_id", ignore_duplicates=True).execute()
        return result.data[0] if result.data else None
    except Exception as e:
        logger.error("Failed to auto-register publish target: %s", type(e).__name__)
        return None


def disable_publish_target(chat_id: int) -> bool:
    """Disable a Telegram chat as a publishing destination."""
    db = get_client()
    try:
        result = db.table("publish_targets").update({
            "enabled": False,
            "updated_at": datetime.now(timezone.utc).isoformat(),
        }).eq("chat_id", chat_id).execute()
        return bool(result.data)
    except Exception as e:
        logger.error("Failed to disable publish target: %s", type(e).__name__)
        return False


def get_templates() -> list[dict]:
    db = get_client()
    try:
        result = db.table("post_templates").select("*").order("updated_at", desc=True).execute()
        return result.data or []
    except Exception as e:
        logger.error("Failed to get post templates: %s", type(e).__name__)
        return []


def upsert_template(template_id: Optional[int], name: str, body: str, destination: str = "all") -> Optional[dict]:
    db = get_client()
    payload = {
        "name": name.strip(),
        "body": body,
        "destination": destination,
        "updated_at": datetime.now(timezone.utc).isoformat(),
    }
    try:
        if template_id:
            result = db.table("post_templates").update(payload).eq("id", template_id).execute()
        else:
            result = db.table("post_templates").insert(payload).execute()
        return result.data[0] if result.data else None
    except Exception as e:
        logger.error("Failed to save post template: %s", type(e).__name__)
        return None


def delete_template(template_id: int) -> bool:
    db = get_client()
    try:
        result = db.table("post_templates").delete().eq("id", template_id).execute()
        return bool(result.data)
    except Exception as e:
        logger.error("Failed to delete post template: %s", type(e).__name__)
        return False


def add_subscriber(chat_id: int, first_name: Optional[str] = None, username: Optional[str] = None) -> Optional[dict]:
    """Register a user chat as a subscriber (idempotent)."""
    db = get_client()
    try:
        result = db.table("subscriber_chats").upsert({
            "chat_id": chat_id,
            "first_name": first_name,
            "username": username,
            "subscribed": True,
            "updated_at": datetime.now(timezone.utc).isoformat(),
        }, on_conflict="chat_id").execute()
        return result.data[0] if result.data else None
    except Exception as e:
        logger.error("Failed to add subscriber: %s", type(e).__name__)
        return None


def remove_subscriber(chat_id: int) -> bool:
    db = get_client()
    try:
        result = db.table("subscriber_chats").update({
            "subscribed": False,
            "updated_at": datetime.now(timezone.utc).isoformat(),
        }).eq("chat_id", chat_id).execute()
        return bool(result.data)
    except Exception as e:
        logger.error("Failed to remove subscriber: %s", type(e).__name__)
        return False


def get_subscribers(city: Optional[str] = None) -> list[dict]:
    """Return subscribed users, optionally filtered to a tagged city audience."""
    db = get_client()
    try:
        query = db.table("subscriber_chats").select("*").eq("subscribed", True)
        if city:
            query = query.eq("city", city)
        result = query.execute()
        return result.data or []
    except Exception as e:
        logger.error("Failed to get subscribers: %s", type(e).__name__)
        return []


def set_subscriber_city(chat_id: int, city: str) -> Optional[dict]:
    """Tag a subscriber with a city for city-targeted publishing."""
    db = get_client()
    try:
        result = db.table("subscriber_chats").update({
            "city": city,
            "updated_at": datetime.now(timezone.utc).isoformat(),
        }).eq("chat_id", chat_id).execute()
        return result.data[0] if result.data else None
    except Exception as e:
        logger.error("Failed to set subscriber city: %s", type(e).__name__)
        return None


def get_all_subscribers() -> list[dict]:
    """All users who ever started the bot, newest first, including unsubscribed."""
    db = get_client()
    try:
        result = db.table("subscriber_chats").select("*").order("created_at", desc=True).limit(200).execute()
        return result.data or []
    except Exception as e:
        logger.error("Failed to get all subscribers: %s", type(e).__name__)
        return []


def toggle_subscriber(chat_id: int) -> Optional[dict]:
    db = get_client()
    try:
        rows = db.table("subscriber_chats").select("subscribed").eq("chat_id", chat_id).limit(1).execute().data or []
        if not rows:
            return None
        enabled = not bool(rows[0].get("subscribed"))
        result = db.table("subscriber_chats").update({
            "subscribed": enabled,
            "updated_at": datetime.now(timezone.utc).isoformat(),
        }).eq("chat_id", chat_id).execute()
        return result.data[0] if result.data else None
    except Exception as e:
        logger.error("Failed to toggle subscriber: %s", type(e).__name__)
        return None


def get_pending_actions(limit: int = 5) -> list[dict]:
    """Return queued dashboard actions (oldest first) that still need execution."""
    db = get_client()
    try:
        result = db.table("pending_actions").select("*").eq("status", "pending").order("created_at", desc=False).limit(limit).execute()
        return result.data or []
    except Exception as e:
        logger.error("Failed to get pending actions: %s", type(e).__name__)
        return []


def mark_pending_action(action_id: int, status: str = "processed", error: Optional[str] = None) -> None:
    """Mark a queued action as processed or failed."""
    db = get_client()
    try:
        payload: dict = {"status": status, "processed_at": datetime.now(timezone.utc).isoformat()}
        if error is not None:
            payload["error"] = error[:500]
        db.table("pending_actions").update(payload).eq("id", action_id).execute()
    except Exception as e:
        logger.error("Failed to mark pending action %s: %s", action_id, type(e).__name__)


def get_category_breakdown(city: str, hours: int = 2) -> dict:
    db = get_client()
    try:
        result = (
            db.table("observations")
            .select("dollar_category_normalized,rate")
            .eq("city", city)
            .eq("time_context", "CURRENT")
            .order("created_at", desc=True)
            .limit(50)
            .execute()
        )
        breakdown = {}
        for obs in (result.data or []):
            cat = obs.get("dollar_category_normalized", "UNKNOWN")
            rate = obs.get("rate")
            if cat and rate and cat != "UNKNOWN":
                if cat not in breakdown:
                    breakdown[cat] = []
                breakdown[cat].append(rate)
        return breakdown
    except Exception as e:
        logger.error(f"Failed to get category breakdown: {e}")
        return {}
