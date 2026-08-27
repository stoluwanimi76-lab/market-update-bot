import os
import asyncio
import feedparser
import aiohttp

from datetime import datetime, timezone

from telegram import Update
from telegram.ext import (
    Application,
    ApplicationBuilder,
    CommandHandler,
    ContextTypes,
)


# =========================================================
# RAILWAY VARIABLES
# =========================================================

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


# =========================================================
# SETTINGS
# =========================================================

# How often the scheduler checks whether it is time to post.
CHECK_EVERY_SECONDS = 60

# Posting times are UTC.
# You can change these later.
FOREX_TIMES = ["08:00", "14:00", "19:00"]
CRYPTO_TIMES = ["09:00", "15:00", "21:00"]
CASINO_TIMES = ["10:00", "16:00", "20:00"]

# Casino RSS source
CASINO_RSS_URL = "https://www.yogonet.com/international/online-gaming/rss.xml"


# =========================================================
# MEMORY
# =========================================================

last_forex_post = None
last_crypto_post = None
last_casino_title = None

sent_casino_items = set()


# =========================================================
# START COMMAND
# =========================================================

async def start_command(
    update: Update,
    context: ContextTypes.DEFAULT_TYPE
):
    await update.message.reply_text(
        "🤖 Market Update Bot is online.\n\n"
        "✅ Forex updates\n"
        "✅ Crypto updates\n"
        "✅ Casino game updates\n\n"
        "Automatic channel posting is active."
    )


# =========================================================
# HELPERS
# =========================================================

def valid_channels(channels):
    return [c.strip() for c in channels if c and c.strip()]


async def send_to_channel(
    bot,
    channel,
    text
):
    try:
        await bot.send_message(
            chat_id=channel,
            text=text,
            disable_web_page_preview=True
        )

        print(f"✅ Posted to {channel}")

    except Exception as e:
        print(f"❌ Failed to post to {channel}: {e}")


async def send_to_channels(
    bot,
    channels,
    text
):
    channels = valid_channels(channels)

    for channel in channels:
        await send_to_channel(
            bot,
            channel,
            text
        )

        await asyncio.sleep(1)


def utc_now():
    return datetime.now(timezone.utc)


# =========================================================
# FOREX DATA
# =========================================================

async def get_forex_rate(
    session,
    pair
):
    url = f"https://api.frankfurter.dev/v2/rate/{pair}"

    try:
        async with session.get(
            url,
            timeout=20
        ) as response:

            if response.status != 200:
                print(
                    f"❌ Forex API error for {pair}: "
                    f"{response.status}"
                )
                return None

            data = await response.json()
            return data

    except Exception as e:
        print(f"❌ Forex request failed for {pair}: {e}")
        return None


async def create_forex_update():

    pairs = [
        ("EUR", "USD"),
        ("GBP", "USD"),
        ("USD", "JPY"),
        ("USD", "CAD"),
        ("EUR", "GBP"),
    ]

    results = []

    async with aiohttp.ClientSession() as session:

        for base, quote in pairs:

            data = await get_forex_rate(
                session,
                f"{base}/{quote}"
            )

            if data:
                rate = data.get("rate")
                date = data.get("date")

                if rate is not None:

                    results.append(
                        f"• {base}/{quote}: {rate:.4f}"
                    )

    if not results:
        return None

    now = utc_now()

    text = (
        "💱 FOREX MARKET UPDATE\n\n"
        f"🕒 {now.strftime('%Y-%m-%d %H:%M UTC')}\n\n"
        + "\n".join(results)
        + "\n\n"
        "📌 Rates supplied by Frankfurter.\n"
        "⚠️ Educational information only. Not financial advice."
    )

    return text


# =========================================================
# CRYPTO DATA
# =========================================================

async def get_crypto_data():

    url = (
        "https://api.coingecko.com/api/v3/simple/price"
        "?ids=bitcoin,ethereum,binancecoin,solana,ripple"
        "&vs_currencies=usd"
        "&include_24hr_change=true"
        "&include_24hr_vol=true"
    )

    try:

        async with aiohttp.ClientSession() as session:

            async with session.get(
                url,
                timeout=20
            ) as response:

                if response.status != 200:

                    print(
                        f"❌ CoinGecko API error: "
                        f"{response.status}"
                    )

                    return None

                return await response.json()

    except Exception as e:

        print(
            f"❌ Crypto request failed: {e}"
        )

        return None


def format_price(price):

    if price >= 1000:
        return f"${price:,.2f}"

    if price >= 1:
        return f"${price:,.4f}"

    return f"${price:,.6f}"


async def create_crypto_update():

    data = await get_crypto_data()

    if not data:
        return None

    coins = [
        ("bitcoin", "₿ Bitcoin"),
        ("ethereum", "🔷 Ethereum"),
        ("binancecoin", "🟡 BNB"),
        ("solana", "🟣 Solana"),
        ("ripple", "✕ XRP"),
    ]

    lines = []

    for coin_id, name in coins:

        coin = data.get(coin_id)

        if not coin:
            continue

        price = coin.get("usd")
        change = coin.get("usd_24h_change")

        if price is None:
            continue

        if change is None:
            change_text = "N/A"
        else:
            sign = "+" if change >= 0 else ""
            change_text = f"{sign}{change:.2f}%"

        lines.append(
            f"• {name}: {format_price(price)} "
            f"({change_text} 24h)"
        )

    if not lines:
        return None

    now = utc_now()

    text = (
        "₿ CRYPTO MARKET UPDATE\n\n"
        f"🕒 {now.strftime('%Y-%m-%d %H:%M UTC')}\n\n"
        + "\n".join(lines)
        + "\n\n"
        "📊 24h price changes included.\n"
        "⚠️ Educational information only. Not financial advice."
    )

    return text


# =========================================================
# CASINO NEWS
# =========================================================

async def get_casino_news():

    global last_casino_title

    try:

        feed = await asyncio.to_thread(
            feedparser.parse,
            CASINO_RSS_URL
        )

        if not feed.entries:
            print("❌ No casino RSS entries found.")
            return None

        for item in feed.entries:

            title = item.get(
                "title",
                "Casino update"
            ).strip()

            link = item.get(
                "link",
                ""
            ).strip()

            published = item.get(
                "published",
                ""
            ).strip()

            # Don't repeat the same title
            if title in sent_casino_items:
                continue

            sent_casino_items.add(title)
            last_casino_title = title

            text = (
                "🎰 CASINO GAME UPDATE\n\n"
                f"📰 {title}\n\n"
            )

            if published:
                text += f"📅 {published}\n\n"

            if link:
                text += f"🔗 Read more: {link}\n\n"

            text += (
                "🔞 18+ only.\n"
                "Play responsibly."
            )

            # Keep memory from growing forever
            if len(sent_casino_items) > 100:
                oldest = next(iter(sent_casino_items))
                sent_casino_items.remove(oldest)

            return text

        print("ℹ️ No new casino article found.")
        return None

    except Exception as e:

        print(
            f"❌ Casino RSS error: {e}"
        )

        return None


# =========================================================
# POST FUNCTIONS
# =========================================================

async def post_forex(bot):

    global last_forex_post

    print("💱 Creating Forex update...")

    message = await create_forex_update()

    if not message:
        print("❌ Forex update could not be created.")
        return

    await send_to_channels(
        bot,
        FOREX_CHANNELS,
        message
    )

    last_forex_post = utc_now()


async def post_crypto(bot):

    global last_crypto_post

    print("₿ Creating Crypto update...")

    message = await create_crypto_update()

    if not message:
        print("❌ Crypto update could not be created.")
        return

    await send_to_channels(
        bot,
        [CRYPTO_CHANNEL],
        message
    )

    last_crypto_post = utc_now()


async def post_casino(bot):

    print("🎰 Looking for casino news...")

    message = await get_casino_news()

    if not message:
        print("ℹ️ No new casino update.")
        return

    await send_to_channels(
        bot,
        CASINO_CHANNELS,
        message
    )


# =========================================================
# SCHEDULER
# =========================================================

async def scheduler_loop(application):

    print("⏰ Scheduler started.")

    last_run = {
        "forex": set(),
        "crypto": set(),
        "casino": set(),
    }

    while True:

        try:

            now = utc_now()

            current_time = now.strftime("%H:%M")
            date_key = now.strftime("%Y-%m-%d")

            # ---------------------------------------------
            # FOREX
            # ---------------------------------------------

            if current_time in FOREX_TIMES:

                key = f"{date_key}-{current_time}"

                if key not in last_run["forex"]:

                    print(
                        f"💱 Forex schedule triggered "
                        f"at {current_time} UTC"
                    )

                    await post_forex(
                        application.bot
                    )

                    last_run["forex"].add(key)

            # ---------------------------------------------
            # CRYPTO
            # ---------------------------------------------

            if current_time in CRYPTO_TIMES:

                key = f"{date_key}-{current_time}"

                if key not in last_run["crypto"]:

                    print(
                        f"₿ Crypto schedule triggered "
                        f"at {current_time} UTC"
                    )

                    await post_crypto(
                        application.bot
                    )

                    last_run["crypto"].add(key)

            # ---------------------------------------------
            # CASINO
            # ---------------------------------------------

            if current_time in CASINO_TIMES:

                key = f"{date_key}-{current_time}"

                if key not in last_run["casino"]:

                    print(
                        f"🎰 Casino schedule triggered "
                        f"at {current_time} UTC"
                    )

                    await post_casino(
                        application.bot
                    )

                    last_run["casino"].add(key)

            # Keep memory small
            for category in last_run:

                if len(last_run[category]) > 100:

                    last_run[category] = set(
                        list(last_run[category])[-50:]
                    )

        except Exception as e:

            print(
                f"❌ Scheduler error: {e}"
            )

        await asyncio.sleep(
            CHECK_EVERY_SECONDS
        )


# =========================================================
# APPLICATION START
# =========================================================

async def post_init(application):

    print("========================================")
    print("🤖 MARKET UPDATE BOT")
    print("========================================")

    print("✅ Telegram connected")
    print("✅ Scheduler launching")

    application.bot_data["scheduler_task"] = (
        asyncio.create_task(
            scheduler_loop(application)
        )
    )


async def post_shutdown(application):

    task = application.bot_data.get(
        "scheduler_task"
    )

    if task:

        task.cancel()

        try:
            await task

        except asyncio.CancelledError:
            pass


# =========================================================
# MAIN
# =========================================================

def main():

    if not BOT_TOKEN:

        print(
            "❌ BOT_TOKEN is missing from Railway Variables."
        )

        return

    application = (
        ApplicationBuilder()
        .token(BOT_TOKEN)
        .post_init(post_init)
        .post_shutdown(post_shutdown)
        .build()
    )

    application.add_handler(
        CommandHandler(
            "start",
            start_command
        )
    )

    print(
        "🚀 Starting Telegram polling..."
    )

    application.run_polling(
        allowed_updates=Update.ALL_TYPES
    )


if __name__ == "__main__":
    main()
