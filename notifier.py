"""
notifier.py – Send Telegram messages via python-telegram-bot.
asyncio.run() is used to drive the async bot call from synchronous code.
"""

import asyncio
from telegram import Bot
from config import TELEGRAM_TOKEN, TELEGRAM_CHAT_ID


async def _send_async(text: str) -> None:
    async with Bot(token=TELEGRAM_TOKEN) as bot:
        await bot.send_message(
            chat_id=TELEGRAM_CHAT_ID,
            text=text,
            # parse_mode left as default (plain text) so AI output renders safely
        )


def send(text: str) -> None:
    """
    Prepend the 📅 calendar emoji to the overall message and send it.
    Per-item emojis (🔺 cancelled, 🟢 changed, 🟡 exam) are included
    by the AI in its output, so no further prefix logic is needed here.
    """
    full_text = f"📅 {text}"
    try:
        loop = asyncio.get_event_loop()
        if loop.is_running():
            loop.create_task(_send_async(full_text))
        else:
            asyncio.run(_send_async(full_text))
    except RuntimeError:
        asyncio.run(_send_async(full_text))
