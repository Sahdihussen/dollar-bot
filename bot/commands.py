import logging
from telegram import Update
from telegram.constants import ChatMemberStatus
from telegram.ext import ContextTypes

import database as db
from market.calculator import get_latest_snapshots, get_snapshot_for_city
from output.formatter import format_market_board, format_sources, format_history

logger = logging.getLogger(__name__)


async def price_command(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Handle /price command — return latest market snapshot."""
    if update.message is None:
        return
    
    await update.message.reply_text("📊 Loading market data...")
    
    try:
        snapshots = get_latest_snapshots()
        
        if not snapshots:
            await update.message.reply_text(
                "📊 No market data available yet.\n"
                "The bot is monitoring channels and will have data soon."
            )
            return
        
        board = format_market_board(snapshots)
        await update.message.reply_text(board)
    except Exception as e:
        logger.error("Error in /price command: %s", type(e).__name__)
        await update.message.reply_text("❌ Error loading market data. Please try again.")


async def source_command(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Handle /source command — show monitored source channels."""
    if update.message is None:
        return
    
    try:
        channels = db.get_active_channels()
        
        if not channels:
            await update.message.reply_text("📡 No source channels configured.")
            return
        
        text = format_sources(channels)
        await update.message.reply_text(text)
    except Exception as e:
        logger.error("Error in /source command: %s", type(e).__name__)
        await update.message.reply_text("❌ Error loading channel data.")


async def history_command(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Handle /history command — show recent rate history."""
    if update.message is None:
        return
    
    try:
        city = context.args[0].lower() if context.args else None
        cities = [city] if city else ["sulaymaniyah", "erbil", "baghdad"]
        all_history = []
        for selected_city in cities:
            all_history.extend(db.get_recent_observations(selected_city, limit=5))
        
        if not all_history:
            await update.message.reply_text("📊 No recent data available.")
            return
        
        await update.message.reply_text(format_history(all_history))
    except Exception as e:
        logger.error("Error in /history command: %s", type(e).__name__)
        await update.message.reply_text("❌ Error loading history.")


async def _is_chat_admin(update: Update, context: ContextTypes.DEFAULT_TYPE) -> bool:
    """Require admin access for groups; channel posts imply channel access was granted."""
    chat = update.effective_chat
    if chat is None:
        return False
    
    if chat.type == "private":
        await context.bot.send_message(chat_id=chat.id, text="Use this command inside the channel or group you want to publish to.")
        return False
    
    # Channel posts do not expose a user, but Telegram only delivers them to a bot
    # with channel access. The channel itself is the publishing principal.
    if chat.type == "channel":
        return True
    
    if update.effective_user is None:
        return False
    
    try:
        member = await context.bot.get_chat_member(
            update.effective_chat.id,
            update.effective_user.id,
        )
        if member.status not in (ChatMemberStatus.ADMINISTRATOR, ChatMemberStatus.OWNER):
            await update.message.reply_text("Only a channel/group administrator can change live publishing.")
            return False
        return True
    except Exception as e:
        logger.error("Admin check failed: %s", type(e).__name__)
        await update.message.reply_text("I could not verify administrator permissions.")
        return False


async def live_on_command(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Enable automatic live/scheduled price publishing in this chat."""
    if update.effective_chat is None or not await _is_chat_admin(update, context):
        return
    
    chat = update.effective_chat
    title = chat.title or chat.username or str(chat.id)
    target = db.upsert_publish_target(chat.id, title, getattr(chat, "username", None))
    
    if not target:
        await context.bot.send_message(
            chat_id=chat.id,
            text="⚠️ I could not save this destination. Run the publish_targets migration first.",
        )
        return
    
    await context.bot.send_message(
        chat_id=chat.id,
        text="✅ Live publishing enabled here.\nI will send validated market boards, scheduled summaries, and movement alerts to this channel.",
    )


async def live_off_command(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Disable automatic live/scheduled price publishing in this chat."""
    if update.effective_chat is None or not await _is_chat_admin(update, context):
        return
    
    chat_id = update.effective_chat.id
    if db.disable_publish_target(chat_id):
        await context.bot.send_message(chat_id=chat_id, text="✅ Live publishing disabled here.")
    else:
        await context.bot.send_message(chat_id=chat_id, text="This channel was not enabled for live publishing.")


async def auto_register_destination(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Auto-register a channel/group that interacts with the bot as a publish destination.

    Fires on channel posts (the bot is inside the channel) and on my_chat_member
    updates (the bot was added or promoted to admin). Idempotent: existing
    destinations and explicitly disabled ones are left untouched.
    """
    chat = update.effective_chat
    if chat is None or chat.type == "private":
        return

    title = chat.title or chat.username or str(chat.id)
    username = getattr(chat, "username", None)
    registered = db.add_publish_target_if_missing(chat.id, title, username)

    if registered:
        logger.info("Stage targets: auto-registered '%s' (@%s) as publish destination", title, username)
        try:
            await context.bot.send_message(
                chat_id=chat.id,
                text="✅ Live publishing enabled here. I will send validated market boards and alerts to this channel.",
            )
        except Exception:
            pass
    else:
        logger.info("Stage targets: '%s' already registered or disabled, skipped", title)


async def live_status_command(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Show enabled publication destinations."""
    if update.message is None:
        return
    
    targets = db.get_publish_targets()
    if not targets:
        await update.message.reply_text(
            "📡 No explicit live destinations are enabled.\n"
            "An administrator can enable this channel with /live_on."
        )
        return
    
    lines = ["📡 Live publishing destinations", ""]
    for target in targets:
        username = f" @{target['username']}" if target.get("username") else ""
        lines.append(f"🟢 {target.get('title', target.get('chat_id'))}{username}")
    await update.message.reply_text("\n".join(lines))


async def start_command(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Handle /start — welcome the user and subscribe them to live prices."""
    if update.message is None or update.effective_chat is None:
        return

    if update.effective_chat.type == "private" and update.effective_user is not None:
        db.add_subscriber(
            update.effective_chat.id,
            update.effective_user.first_name,
            update.effective_user.username,
        )

    welcome = (
        "💵 USD/IQD Market Bot\n\n"
        "You are subscribed to live price updates.\n"
        "Send any message to get the current price.\n\n"
        "Commands:\n"
        "/price — Latest market rates\n"
        "/subscribe — Receive live updates\n"
        "/unsubscribe — Stop updates\n"
        "/history — Recent history\n"
        "/setcity — Tag your city (e.g. /setcity erbil)\n"
        "/help — Full help"
    )
    await update.message.reply_text(welcome)
    await price_command(update, context)


async def subscribe_command(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Handle /subscribe — receive live price updates in this chat."""
    if update.message is None or update.effective_chat is None:
        return
    first_name = update.effective_user.first_name if update.effective_user else None
    username = update.effective_user.username if update.effective_user else None
    if db.add_subscriber(update.effective_chat.id, first_name, username):
        await update.message.reply_text("✅ You are now subscribed to live price updates.")
    else:
        await update.message.reply_text("❌ Could not subscribe. Try again later.")


async def unsubscribe_command(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Handle /unsubscribe — stop live price updates."""
    if update.message is None or update.effective_chat is None:
        return
    if db.remove_subscriber(update.effective_chat.id):
        await update.message.reply_text("👋 Unsubscribed. You can resubscribe anytime with /subscribe.")
    else:
        await update.message.reply_text("You were not subscribed.")


async def private_message_handler(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Any plain message from a user in private chat gets the current price board."""
    if update.message is None or update.effective_chat is None:
        return
    if update.effective_chat.type != "private":
        return
    await price_command(update, context)


CITIES = {"baghdad", "erbil", "sulaymaniyah", "mosul", "basra", "kirkuk", "duhok"}


async def setcity_command(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Handle /setcity — tag this user with a city for city-targeted posts."""
    if update.message is None or update.effective_chat is None:
        return
    if update.effective_chat.type != "private":
        await update.message.reply_text("Use /setcity in a private chat with the bot.")
        return

    city = (context.args[0] if context.args else "").strip().lower()
    if city not in CITIES:
        await update.message.reply_text(
            "Usage: /setcity <city>\n"
            "Cities: baghdad, erbil, sulaymaniyah, mosul, basra, kirkuk, duhok"
        )
        return

    if db.set_subscriber_city(update.effective_chat.id, city):
        await update.message.reply_text(f"✅ City set to {city}. City-targeted price updates will reach you here.")
    else:
        await update.message.reply_text("❌ Could not set city. Send /start first, then try again.")


async def help_command(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Handle /help command."""
    if update.message is None:
        return
    
    text = (
        "💵 Iraqi/Kurdistan USD/IQD Market Bot\n\n"
        "Commands:\n"
        "/price — Latest market rates for all cities\n"
        "/source — Monitored Telegram source channels\n"
        "/history — Recent rate history\n"
        "/subscribe — Receive live updates in this chat\n"
        "/unsubscribe — Stop live updates\n"
        "/live_on — Enable live publishing in this channel (admin only)\n"
        "/live_off — Disable live publishing here (admin only)\n"
        "/live_status — Show publishing destinations\n"
        "/setcity — Tag your city for city-targeted posts (e.g. /setcity erbil)\n"
        "/help — This message"
    )
    await update.message.reply_text(text)
