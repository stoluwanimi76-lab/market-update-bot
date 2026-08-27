import os
import asyncio
from telegram import Bot
from telegram.error import TelegramError

# ==========================================
# BOT TOKEN
# ==========================================

BOT_TOKEN = os.getenv("BOT_TOKEN")

# ==========================================
# CHANNELS
# ==========================================

FOREX_CHANNELS = [
    os.getenv("FOREX_CHANNEL_1"),
    os.getenv("FOREX_CHANNEL_2"),
]

CRYPTO_CHANNELS = [
    os.getenv("CRYPTO_CHANNEL"),
]

CASINO_CHANNELS = [
    os.getenv("CASINO_CHANNEL_1"),
    os.getenv("CASINO_CHANNEL_2"),
]


# ==========================================
# SEND MESSAGE FUNCTION
# ==========================================

async def send_message(bot, channel, message, category):

    if not channel:
        print(f"⚠️ {category}: Channel variable is empty")
        return

    try:
        await bot.send_message(
            chat_id=channel,
            text=message
        )

        print(f"✅ {category}: Successfully sent to {channel}")

    except TelegramError as e:
        print(f"❌ {category}: Failed to send to {channel}")
        print(f"   Telegram error: {e}")

    except Exception as e:
        print(f"❌ {category}: Unexpected error with {channel}")
        print(f"   Error: {e}")


# ==========================================
# FOREX TEST POST
# ==========================================

FOREX_MESSAGE = """
💱 FOREX MARKET UPDATE

🤖 Automated Forex Update System

The Forex update service is now online.

📊 Updates will include:
• Major currency pairs
• Market movements
• Important Forex news
• Economic events

⚠️ Educational information only.
Not financial advice.
"""


# ==========================================
# CRYPTO TEST POST
# ==========================================

CRYPTO_MESSAGE = """
₿ CRYPTO MARKET UPDATE

🤖 Automated Crypto Update System

The Crypto update service is now online.

📊 Updates will include:
• Bitcoin
• Ethereum
• Major cryptocurrencies
• Market movements
• Important crypto news

⚠️ Educational information only.
Not financial advice.
"""


# ==========================================
# CASINO TEST POST
# ==========================================

CASINO_MESSAGE = """
🎰 CASINO GAME UPDATE

🤖 Automated Casino Update System

The Casino update service is now online.

🎮 Updates will include:
• New casino games
• Game releases
• Provider updates
• Casino industry news
• Tournament information

🔞 18+ only.
Play responsibly.
"""


# ==========================================
# MAIN PROGRAM
# ==========================================

async def main():

    if not BOT_TOKEN:
        print("❌ BOT_TOKEN is missing from Railway Variables")
        return

    print("====================================")
    print("🤖 MARKET UPDATE BOT")
    print("====================================")
    print("🚀 Bot is starting...")
    print("")

    bot = Bot(token=BOT_TOKEN)

    # ======================================
    # FOREX CHANNELS
    # ======================================

    print("💱 TESTING FOREX CHANNELS")
    print("------------------------------------")

    for channel in FOREX_CHANNELS:

        await send_message(
            bot,
            channel,
            FOREX_MESSAGE,
            "FOREX"
        )

        await asyncio.sleep(2)

    print("")

    # ======================================
    # CRYPTO CHANNEL
    # ======================================

    print("₿ TESTING CRYPTO CHANNEL")
    print("------------------------------------")

    for channel in CRYPTO_CHANNELS:

        await send_message(
            bot,
            channel,
            CRYPTO_MESSAGE,
            "CRYPTO"
        )

        await asyncio.sleep(2)

    print("")

    # ======================================
    # CASINO CHANNELS
    # ======================================

    print("🎰 TESTING CASINO CHANNELS")
    print("------------------------------------")

    for channel in CASINO_CHANNELS:

        await send_message(
            bot,
            channel,
            CASINO_MESSAGE,
            "CASINO"
        )

        await asyncio.sleep(2)

    print("")
    print("====================================")
    print("✅ ALL CHANNEL TESTS COMPLETED")
    print("====================================")

    # Keep Railway service alive
    while True:
        await asyncio.sleep(3600)


# ==========================================
# START BOT
# ==========================================

if __name__ == "__main__":
    asyncio.run(main())
