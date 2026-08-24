import logging
from telegram.ext import (
    ApplicationBuilder,
    CommandHandler,
)
import config
import database as db
from bot.commands import (
    price_command,
    source_command,
    history_command,
    help_command,
    start_command,
    subscribe_command,
    unsubscribe_command,
    private_message_handler,
    live_on_command,
    live_off_command,
    live_status_command,
    auto_register_destination,
    setcity_command,
)

logger = logging.getLogger(__name__)

_bot_app = None


def create_bot_app():
    """Create and configure the Telegram bot application."""
    global _bot_app
    
    if _bot_app is not None:
        return _bot_app
    
    app = ApplicationBuilder().token(config.TELEGRAM_BOT_TOKEN).build()
    
    app.add_handler(CommandHandler("start", start_command))
    app.add_handler(CommandHandler("subscribe", subscribe_command))
    app.add_handler(CommandHandler("unsubscribe", unsubscribe_command))
    app.add_handler(CommandHandler("price", price_command))
    app.add_handler(CommandHandler("source", source_command))
    app.add_handler(CommandHandler("history", history_command))
    app.add_handler(CommandHandler("help", help_command))
    app.add_handler(CommandHandler("live_on", live_on_command))
    app.add_handler(CommandHandler("live_off", live_off_command))
    app.add_handler(CommandHandler("live_status", live_status_command))
    app.add_handler(CommandHandler("setcity", setcity_command))
    from telegram.ext import MessageHandler, ChatMemberHandler, filters
    app.add_handler(MessageHandler(filters.UpdateType.CHANNEL_POST, auto_register_destination))
    app.add_handler(ChatMemberHandler(auto_register_destination, chat_member_types=ChatMemberHandler.MY_CHAT_MEMBER))
    # Last: any plain private message gets the current price board.
    app.add_handler(MessageHandler(filters.ChatType.PRIVATE & ~filters.COMMAND, private_message_handler))
    
    _bot_app = app
    logger.info("Telegram bot application created")
    return app


async def send_message(chat_id: int, text: str):
    """Send a message via the bot."""
    if _bot_app is None:
        logger.error("Bot app not initialized")
        return False
    
    try:
        await _bot_app.bot.send_message(chat_id=chat_id, text=text)
        return True
    except Exception as e:
        logger.error("Failed to send bot message: %s", type(e).__name__)
        return False


async def send_to_channel(channel: str | int, text: str):
    """Send a message to one Telegram channel or chat."""
    return await send_message(channel, text)


async def broadcast_to_targets(text: str, exclude_chat_id: int | None = None):
    """Publish a message to every enabled channel destination and every subscribed user."""
    targets = db.get_publish_targets()
    
    # Keep the legacy configured destination working until it is replaced by /live_on.
    destinations = {target.get("chat_id") for target in targets if target.get("chat_id") is not None}
    if config.MARKET_CHANNEL and not targets:
        destinations.add(config.MARKET_CHANNEL)
    
    # Subscribed users who started the bot.
    subscribers = db.get_subscribers()
    for subscriber in subscribers:
        chat_id = subscriber.get("chat_id")
        if chat_id is not None:
            destinations.add(chat_id)
    
    sent = 0
    for destination in destinations:
        if exclude_chat_id is not None and str(destination) == str(exclude_chat_id):
            continue
        if await send_message(destination, text):
            sent += 1
    return sent


async def broadcast_text(text: str, destination: str = "all") -> list[int]:
    """Send rendered text to a destination audience via the bot.

    destination "all" sends to every enabled channel target and every
    subscribed user; a city name sends only to subscribers tagged with
    that city. Returns the list of chat_ids that received the message.
    """
    if _bot_app is None:
        logger.error("Bot app not initialized")
        return []

    chat_ids: list[int] = []
    if destination == "all":
        targets = db.get_publish_targets()
        chat_ids.extend(t.get("chat_id") for t in targets if t.get("chat_id") is not None)
        subscribers = db.get_subscribers()
        chat_ids.extend(s.get("chat_id") for s in subscribers if s.get("chat_id") is not None)
    else:
        subscribers = db.get_subscribers(city=destination)
        chat_ids.extend(s.get("chat_id") for s in subscribers if s.get("chat_id") is not None)

    sent: list[int] = []
    for chat_id in dict.fromkeys(chat_ids):  # de-dupe, preserve order
        try:
            await _bot_app.bot.send_message(chat_id=chat_id, text=text)
            sent.append(chat_id)
        except Exception as e:
            logger.error("Failed to send to %s: %s", chat_id, type(e).__name__)
    logger.info("Stage publish: template sent to %d recipient(s)", len(sent))
    return sent


def reset_bot_app():
    """Drop the cached bot application so the next start builds a fresh one.

    Used by the supervisor loop in main.py after a bot failure: python-telegram-bot
    applications are single-use, so a crashed instance must not be reused.
    """
    global _bot_app
    _bot_app = None


def get_bot():
    """Get the bot instance."""
    if _bot_app is None:
        return None
    return _bot_app.bot
