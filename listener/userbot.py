import asyncio
import logging
import time
from datetime import datetime, timezone

from telethon import TelegramClient, events
from telethon.sessions import StringSession
import config
import database as db
from extraction.preprocessor import preprocess, build_fallback_observations
from extraction.ai_parser import parse_with_ai
from extraction.validator import validate_all
from extraction.dedup import deduplicate
from extraction.outlier import detect_outliers
from market.calculator import update_snapshots
from market.alerts import check_all_cities_for_alerts, format_alert_message
from bot.telegram_bot import broadcast_to_targets

logger = logging.getLogger(__name__)

_client: TelegramClient = None
_last_live_publish_at = 0.0
_live_publish_lock = asyncio.Lock()
LIVE_PUBLISH_COOLDOWN_SECONDS = 120


def get_client() -> TelegramClient:
    """Get or create the Telethon client."""
    global _client
    if _client is None:
        _client = TelegramClient(
            StringSession(config.TG_SESSION),
            config.TG_API_ID,
            config.TG_API_HASH,
        )
    return _client


async def process_message(message, channel_username: str):
    """Process a single Telegram message through the extraction pipeline."""
    try:
        text = message.message
        if not text or len(text.strip()) < 5:
            return
        
        logger.info(f"Stage collect: message {message.id} from @{channel_username} ({len(text)} chars)")
        
        # 1. Store raw post
        raw_post = db.store_raw_post(
            channel_username=channel_username,
            message_id=message.id,
            text=text,
            published_at=message.date,
        )
        
        if not raw_post:
            logger.warning(f"Stage collect FAILED: could not store raw post from {channel_username}")
            return
        
        post_id = raw_post.get("id")
        logger.info(f"Stage raw_post: stored id={post_id}")
        
        # 2. Preprocessing (deterministic regex layer)
        preprocessed = preprocess(text)
        logger.info(
            f"Stage normalize: city={preprocessed.get('city')} label={preprocessed.get('label')} "
            f"category={preprocessed.get('category')} candidates={len(preprocessed.get('candidate_rates', []))}"
        )
        
        # 3. AI semantic parsing (OrcaRouter -> Mistral -> Groq -> OpenRouter)
        ai_observations, ai_all_failed = await parse_with_ai(text, preprocessed)
        logger.info(f"Stage ai_parse: {len(ai_observations)} observations from @{channel_username}")
        
        # 3b. Deterministic fallback: use the regex candidates ONLY when every AI
        # provider errored out (network/API outage), never when a provider
        # answered but found nothing — a working AI's verdict is authoritative.
        if ai_all_failed:
            ai_observations = build_fallback_observations(preprocessed, post_id, channel_username)
            if ai_observations:
                logger.info(
                    f"Stage ai_parse: AI unavailable, deterministic fallback produced "
                    f"{len(ai_observations)} observations from @{channel_username}"
                )
        
        if not ai_observations:
            logger.info(f"Stage ai_parse: no extractable rates, marking post {post_id} processed")
            db.mark_post_processed(post_id)
            return
        
        # 4. Add metadata to observations
        for obs in ai_observations:
            obs["raw_post_id"] = post_id
            obs["source"] = channel_username
            # A message the listener just received is by definition current unless
            # it is explicitly historical/forecast (أمس, غداً, etc.). Treat the AI's
            # UNKNOWN default as CURRENT so snapshots can be computed.
            if not obs.get("time_context") or obs.get("time_context") == "UNKNOWN":
                obs["time_context"] = "CURRENT"
        
        # 5. Deterministic validation
        valid, rejected = validate_all(ai_observations)
        logger.info(f"Stage validate: {len(valid)} valid / {len(rejected)} rejected from @{channel_username}")
        for bad in rejected[:5]:
            logger.warning(f"Stage validate rejected: {bad.get('_rejection_reason')} | {str(bad.get('evidence_text'))[:60]}")
        
        if not valid:
            db.mark_post_processed(post_id)
            return
        
        # 6. Deduplication
        unique = deduplicate(valid)
        logger.info(f"Stage dedup: {len(unique)} unique observations")
        
        # 7. Outlier detection
        clean, quarantined = detect_outliers(unique)
        if quarantined:
            logger.warning(f"Stage outlier: {len(quarantined)} quarantined from @{channel_username}")
        
        # 8. Store observations
        for obs in clean:
            store_obs = {
                "raw_post_id": obs.get("raw_post_id"),
                "source": obs.get("source"),
                "city": obs.get("city"),
                "city_raw": obs.get("city_raw"),
                "market": obs.get("market"),
                "market_layer": obs.get("market_layer", "local_market"),
                "currency": "USD",
                "quote_currency": "IQD",
                "denomination": obs.get("denomination", 100),
                "rate": int(obs.get("rate", 0)),
                "rate_role": obs.get("rate_role", "UNKNOWN"),
                "quote_label_raw": obs.get("quote_label_raw"),
                "quote_label_normalized": obs.get("quote_label_normalized"),
                "dollar_category_raw": obs.get("dollar_category_raw"),
                "dollar_category_normalized": obs.get("dollar_category_normalized", "UNKNOWN"),
                "time_context": obs.get("time_context", "CURRENT"),
                "product": obs.get("product", "usd_iqd"),
                "confidence": obs.get("confidence", 0.5),
                "evidence_text": obs.get("evidence_text", ""),
            }
            db.store_observation(store_obs)
        
        # 9. Update market snapshots
        if clean:
            update_snapshots(clean)
            cities = sorted({o.get('city') for o in clean if o.get('city')})
            logger.info(f"Stage snapshot: updated for {', '.join(cities) or 'none'}")
        
        # 10. Publish a fresh live board at most once every two minutes.
        # The lock makes the cooldown check-and-set atomic across concurrent
        # message handlers so two boards can't be sent back-to-back.
        global _last_live_publish_at
        if clean:
            async with _live_publish_lock:
                now = time.monotonic()
                if now - _last_live_publish_at >= LIVE_PUBLISH_COOLDOWN_SECONDS:
                    snapshots = db.get_fresh_snapshots()
                    if snapshots:
                        from output.formatter import format_market_board
                        await broadcast_to_targets(format_market_board(snapshots))
                        _last_live_publish_at = now
                        logger.info("Stage publish: live market board sent to targets")
        
        # 11. Check for market alerts
        alerts = check_all_cities_for_alerts()
        for alert in alerts:
            alert_msg = format_alert_message(alert)
            await broadcast_to_targets(alert_msg)
            logger.warning(f"Stage alert: {alert.get('city')} moved {alert.get('change')} IQD")
        
        db.mark_post_processed(post_id)
        logger.info(f"Pipeline complete: message {message.id} from @{channel_username} -> {len(clean)} observations stored")
        
    except Exception as e:
        logger.error(f"Error processing message from {channel_username}: {e}", exc_info=True)


def setup_event_handlers(client: TelegramClient):
    """Set up event handlers for monitored channels."""
    
    # Build a set of channel usernames to monitor
    monitored = set(config.MONITORED_CHANNELS)
    
    @client.on(events.NewMessage(chats=monitored))
    async def handler(event):
        """Handle new messages from monitored channels."""
        try:
            # Get channel username
            channel = await event.get_chat()
            username = getattr(channel, "username", None)
            if not username:
                username = getattr(channel, "title", "unknown")
            
            await process_message(event.message, username)
        except Exception as e:
            logger.error(f"Event handler error: {e}", exc_info=True)
    
    logger.info(f"Set up event handlers for {len(monitored)} channels")


async def auto_register_admin_chats(client: TelegramClient):
    """Discover every channel/group where the account is admin and register it as a publish destination."""
    registered = 0
    skipped = 0
    try:
        me = await client.get_me()
        dialogs = await client.get_dialogs(limit=300)
        for dialog in dialogs:
            chat = dialog.entity
            chat_id = getattr(chat, "id", None)
            if chat_id is None or chat_id == me.id:
                continue
            if not (getattr(chat, "is_channel", False) or getattr(chat, "is_group", False)):
                continue
            try:
                permissions = await client.get_permissions(chat, me)
            except Exception:
                continue
            if not getattr(permissions, "is_admin", False):
                continue
            title = getattr(chat, "title", None) or str(chat_id)
            username = getattr(chat, "username", None)
            db.add_publish_target_if_missing(chat_id, title, username)
            registered += 1
            logger.info(f"Stage targets: registered admin chat '{title}' (@{username}) as publish destination")
    except Exception as exc:
        logger.error(f"Stage targets: auto-registration scan failed: {exc}")
    logger.info(f"Stage targets: scan complete, {registered} admin chats registered")


async def start_userbot():
    """Start the Telethon userbot, restarting automatically if it disconnects.

    A transient network hiccup (or a Telegram-side disconnect) must never kill
    the whole app: the listener is the heart of the pipeline, so this loop
    reconnects with a backoff instead of letting the task complete.
    """
    while True:
        client = get_client()
        try:
            # Start the client with the session string
            await client.start()

            # Set up event handlers
            setup_event_handlers(client)

            me = await client.get_me()
            logger.info(f"Userbot started as: {me.first_name} (@{me.username})")

            # Auto-register channels/groups where the account is admin.
            await auto_register_admin_chats(client)

            # Run until disconnected
            await client.run_until_disconnected()
        except Exception as e:
            logger.error(f"Userbot failed: {e}", exc_info=True)
        try:
            await client.disconnect()
        except Exception:
            pass
        logger.warning("Userbot stopped; reconnecting in 30 seconds")
        await asyncio.sleep(30)
