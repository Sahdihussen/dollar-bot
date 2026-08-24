import logging
from datetime import datetime, timezone, timedelta

from apscheduler.schedulers.asyncio import AsyncIOScheduler
from apscheduler.triggers.cron import CronTrigger
from apscheduler.triggers.interval import IntervalTrigger

import config
import database as db
from market.calculator import get_latest_snapshots
from market.alerts import check_all_cities_for_alerts, format_alert_message
from output.formatter import format_market_board, format_daily_summary, day_rate_stats
from bot.telegram_bot import broadcast_to_targets, broadcast_text
from templates import render_template
from dashboard_data import dashboard_state

logger = logging.getLogger(__name__)

TIMEZONE_OFFSET = 3


def get_baghdad_now() -> datetime:
    """Get current time in Baghdad (GMT+3)."""
    return datetime.now(timezone.utc) + timedelta(hours=TIMEZONE_OFFSET)


def is_market_hours() -> bool:
    """Check if current time is within market hours (10:00-18:00 GMT+3, Mon-Thu)."""
    now = get_baghdad_now()
    weekday = now.weekday()  # 0=Monday, 6=Sunday
    hour = now.hour
    
    # Market closed on Friday (4) and Sunday (6) in Iraq
    if weekday in (4, 6):
        return False
    
    return 10 <= hour < 18


async def morning_summary_job():
    """Post morning market opening summary at 10:00 AM GMT+3."""
    logger.info("Running morning summary job")
    try:
        snapshots = get_latest_snapshots()
        if snapshots:
            board = format_market_board(snapshots)
            msg = f"☀️ باکری بازاڕ\n\n{board}"
            await broadcast_to_targets(msg)
        else:
            await broadcast_to_targets("☀️ باکری بازاڕ\n\n📊 Data not available yet.")
    except Exception as e:
        logger.error(f"Morning summary job failed: {e}")


async def evening_summary_job():
    """Post evening market closing report at 17:30 GMT+3."""
    logger.info("Running evening summary job")
    try:
        snapshots = get_latest_snapshots()
        if snapshots:
            # True day stats: open = first rate today, close = latest rate today.
            stats = day_rate_stats()
            summary = format_daily_summary(
                snapshots,
                open_rate=stats["open"] if stats else None,
                close_rate=stats["close"] if stats else None,
                high_rate=stats["high"] if stats else None,
                low_rate=stats["low"] if stats else None,
            )
            await broadcast_to_targets(summary)
        else:
            await broadcast_to_targets("🌙 کورتەی بازاڕ\n\n📊 Data not available yet.")
    except Exception as e:
        logger.error(f"Evening summary job failed: {e}")


async def market_radar_job():
    """Check for unusual movement every 10 minutes."""
    try:
        alerts = check_all_cities_for_alerts()
        for alert in alerts:
            alert_msg = format_alert_message(alert)
            await broadcast_to_targets(alert_msg)
    except Exception as e:
        logger.error(f"Market radar job failed: {e}")


async def process_pending_actions_job():
    """Execute dashboard-queued actions (publish board / send template).

    The Cloudflare Worker API inserts actions into `pending_actions`;
    this poll runs every 15 seconds so phone-triggered sends go out quickly.
    """
    try:
        actions = db.get_pending_actions(limit=5)
        for action in actions:
            action_id = action.get("id")
            kind = action.get("action")
            payload = action.get("payload") or {}
            try:
                if kind == "publish_board":
                    snapshots = dashboard_state().get("snapshots", [])
                    if not snapshots:
                        raise RuntimeError("No current market data to publish")
                    board = format_market_board(snapshots)
                    sent = await broadcast_text(board, "all")
                    logger.info("Pending action %s: publish_board sent to %s destinations", action_id, len(sent))
                elif kind == "send_template":
                    body = payload.get("body") or ""
                    destination = payload.get("destination") or "all"
                    rendered = render_template(body, dashboard_state())
                    if rendered["unknown_variables"]:
                        raise RuntimeError("Unknown variables: " + ", ".join(rendered["unknown_variables"]))
                    sent = await broadcast_text(rendered["rendered"], destination)
                    logger.info("Pending action %s: send_template sent to %s recipients", action_id, len(sent))
                else:
                    raise RuntimeError(f"Unknown action: {kind}")
                db.mark_pending_action(action_id, status="processed")
            except Exception as exc:
                logger.error("Pending action %s failed: %s", action_id, exc)
                db.mark_pending_action(action_id, status="failed", error=str(exc))
    except Exception as exc:
        logger.error("Pending actions job failed: %s", exc)


async def daily_summary_job():
    """Post daily summary at 20:00 GMT+3."""
    logger.info("Running daily summary job")
    try:
        snapshots = get_latest_snapshots()
        if snapshots:
            stats = day_rate_stats()
            summary = format_daily_summary(
                snapshots,
                open_rate=stats["open"] if stats else None,
                close_rate=stats["close"] if stats else None,
                high_rate=stats["high"] if stats else None,
                low_rate=stats["low"] if stats else None,
            )
            await broadcast_to_targets(summary)
    except Exception as e:
        logger.error(f"Daily summary job failed: {e}")


def create_scheduler() -> AsyncIOScheduler:
    """Create and configure the APScheduler instance."""
    scheduler = AsyncIOScheduler()
    
    # Morning summary at 10:00 AM GMT+3 (07:00 UTC)
    scheduler.add_job(
        morning_summary_job,
        CronTrigger(hour=7, minute=0, day_of_week="mon,tue,wed,thu"),
        id="morning_summary",
        name="Morning Market Summary",
    )
    
    # Evening summary at 17:30 GMT+3 (14:30 UTC)
    scheduler.add_job(
        evening_summary_job,
        CronTrigger(hour=14, minute=30, day_of_week="mon,tue,wed,thu"),
        id="evening_summary",
        name="Evening Market Summary",
    )
    
    # Market radar every 10 minutes during market hours
    scheduler.add_job(
        market_radar_job,
        IntervalTrigger(minutes=10),
        id="market_radar",
        name="Market Radar",
    )
    
    # Daily summary at 20:00 GMT+3 (17:00 UTC), market days only
    scheduler.add_job(
        daily_summary_job,
        CronTrigger(hour=17, minute=0, day_of_week="mon,tue,wed,thu"),
        id="daily_summary",
        name="Daily Summary",
    )
    
    # Dashboard action queue (Cloudflare Worker inserts, we execute)
    scheduler.add_job(
        process_pending_actions_job,
        IntervalTrigger(seconds=15),
        id="pending_actions",
        name="Pending Actions",
    )
    
    logger.info("Scheduler configured with 5 jobs")
    return scheduler
