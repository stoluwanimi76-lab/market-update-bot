import os
import asyncio
from telegram import Bot
from telegram.error import TelegramError


BOT_TOKEN = os.getenv("BOT_TOKEN")

CHANNELS = [
    ("FOREX 1", os.getenv("FOREX_CHANNEL_1")),
    ("FOREX 2", os.getenv("FOREX_CHANNEL_2")),
    ("CRYPTO", os.getenv("CRYPTO_CHANNEL")),
    ("CASINO 1", os.getenv("CASINO_CHANNEL_1")),
    ("CASINO 2", os.getenv("CASINO_CHANNEL_2")),
]


TEST_MESSAGES = {
    "FOREX": """💱 FOREX UPDATE

✅ Forex channel connection test successful.

Your automated Forex update bot is online.

⚠️ Educational information only. Not financial advice.
""",

    "CRYPTO": """₿ CRYPTO UPDATE

✅ Crypto channel connection test successful.

Your automated Crypto update bot is online.

⚠️ Educational information only. Not financial advice.
""",

    "CASINO": """🎰 CASINO GAME UPDATE

✅ Casino channel connection test successful.

Your automated Casino update bot is online.

🔞 18+ only. Play responsibly.
"""
}


def get_message(category):
    if category == "FOREX":
        return TEST_MESSAGES["FOREX"]

    if category == "CRYPTO":
        return TEST_MESSAGES["CRYPTO"]

    return TEST_MESSAGES["CASINO"]


def get_category(name):
    if "FOREX" in name:
        return "FOREX"

    if "CRYPTO" in name:
        return "CRYPTO"

    return "CASINO"


async def test_channel(bot, name, channel):

    print(f"\n🔎 Testing {name}")

    if not channel:
        print(f"❌ {name}: Railway variable is EMPTY")
        return

    channel = channel.strip()

    print(f"📌 Target: {channel}")

    try:
        chat = await bot.get_chat(channel)

        print(f"✅ Channel found: {chat.title}")
        print(f"🆔 Channel ID: {chat.id}")

        await bot.send_message(
            chat_id=chat.id,
            text=get_message(get_category(name))
        )

        print(f"✅ {name}: MESSAGE SENT SUCCESSFULLY")

    except TelegramError as error:
        print(f"❌ {name}: TELEGRAM ERROR")
        print(f"   {error}")

    except Exception as error:
        print(f"❌ {name}: UNKNOWN ERROR")
        print(f"   {error}")


async def main():

    print("========================================")
    print("🤖 MARKET UPDATE BOT - CHANNEL TEST")
    print("========================================")

    if not BOT_TOKEN:
        print("❌ BOT_TOKEN is missing from Railway")
        return

    bot = Bot(token=BOT_TOKEN)

    for name, channel in CHANNELS:
        await test_channel(bot, name, channel)
        await asyncio.sleep(2)

    print("\n========================================")
    print("✅ ALL 5 CHANNEL TESTS FINISHED")
    print("========================================")

    # Keep Railway service alive
    while True:
        await asyncio.sleep(3600)


if __name__ == "__main__":
    asyncio.run(main())
