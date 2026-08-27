import os
import asyncio
from telegram import Bot

BOT_TOKEN = os.getenv("BOT_TOKEN")

FOREX_CHANNELS = [
    os.getenv("FOREX_CHANNEL_1"),
    os.getenv("FOREX_CHANNEL_2"),
]

CRYPTO_CHANNEL = os.getenv("CRYPTO_CHANNEL")

CASINO_CHANNELS = [
    os.getenv("CASINO_CHANNEL_1"),
    os.getenv("CASINO_CHANNEL_2"),
]


async def send_to_channels(bot, channels, message):
    for channel in channels:
        if not channel:
            continue

        try:
            await bot.send_message(
                chat_id=channel,
                text=message
            )
            print(f"✅ Sent to {channel}")

        except Exception as e:
            print(f"❌ Error sending to {channel}: {e}")


async def main():
    print("🤖 Market Update Bot is running...")

    bot = Bot(token=BOT_TOKEN)

    # Startup test
    await send_to_channels(
        bot,
        FOREX_CHANNELS,
        """💱 FOREX UPDATE

🤖 Market Update Bot is now online.

Automated Forex updates will be posted here.

⚠️ Educational information only. Not financial advice."""
    )

    await send_to_channels(
        bot,
        [CRYPTO_CHANNEL],
        """₿ CRYPTO UPDATE

🤖 Market Update Bot is now online.

Automated Crypto updates will be posted here.

⚠️ Educational information only. Not financial advice."""
    )

    await send_to_channels(
        bot,
        CASINO_CHANNELS,
        """🎰 CASINO UPDATE

🤖 Market Update Bot is now online.

Automated Casino updates will be posted here.

18+ | Play responsibly."""
    )

    # Keep the bot running
    while True:
        await asyncio.sleep(3600)


if __name__ == "__main__":
    asyncio.run(main())
