"""Inspection only: print the session identity and per-channel read access.

Never prints the session string or any secret.
"""
import asyncio

import config
from telethon import TelegramClient
from telethon.sessions import StringSession


async def main() -> None:
    client = TelegramClient(StringSession(config.TG_SESSION), config.TG_API_ID, config.TG_API_HASH)
    await client.connect()
    me = await client.get_me()
    print("session account:", me.first_name, "@" + (me.username or ""), "(user id", me.id, ")")
    print("----")
    for username in config.MONITORED_CHANNELS:
        try:
            entity = await client.get_entity(username)
            title = getattr(entity, "title", None) or username
            print(f"READABLE: @{username} ({title})")
        except Exception as exc:
            print(f"NO ACCESS: @{username} -> {type(exc).__name__}")
    await client.disconnect()


asyncio.run(main())
