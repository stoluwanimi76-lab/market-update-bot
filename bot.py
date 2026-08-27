import os
import asyncio
from telegram import Bot

BOT_TOKEN = os.getenv("BOT_TOKEN")

# =========================
# CHANNEL CONFIGURATION
# =========================

FOREX_CHANNELS = [
    os.getenv("FOREX_CHANNEL_1"),
    os.getenv("FOREX_CHANNEL_2"),
]

CRYPTO_CHANNEL = os.getenv("CRYPTO_CHANNEL")

CASINO_CHANNELS = [
    os.getenv("CASINO_CHANNEL_1"),
    os.getenv("CASINO_CHANNEL_2"),
]


async def send_message(channel, message):
    if not channel:
        return

    bot = Bot(token=BOT_TOKEN)
    await bot.send_message(
        chat_id=channel,
        text=message
    )


async def main():
    print("🤖 Market Update Bot is running...")

    # Test message
    await send_message(
        FOREX_CHANNELS[0],
        "💱 FOREX UPDATE\n\n"
        "The automated Forex update system is now online."
    )


if __name__ == "__main__":
    asyncio.run(main())
