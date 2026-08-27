import os
import asyncio
import html
import re
import feedparser
import aiohttp

from datetime import datetime, timezone

from telegram import Update
from telegram.ext import (
    ApplicationBuilder,
    CommandHandler,
    ContextTypes,
)


BOT_TOKEN = os.getenv("BOT_TOKEN")

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


FOREX_RSS = "https://www.investing.com/rss/news_1.rss"
CRYPTO_RSS = "https://cointelegraph.com/?format=rss"
CASINO_RSS = "https://www.yogonet.com/international/online-gaming/rss.xml"

CHECK_INTERVAL = 120

seen_forex = set()
seen_crypto = set()
seen_casino = set()

MAX_MEMORY = 500


def clean_text(text):
    if not text:
        return ""

    text = html.unescape(text)
    text = re.sub(r"<[^>]+>", " ", text)
    text = re.sub(r"\s+", " ", text)

    return text.strip()


def shorten(text, limit=350):
    text = clean_text(text)

    if len(text) <= limit:
        return text

    return text[:limit - 3] + "..."


def item_id(entry):
    return (
        entry.get("id")
        or entry.get("guid")
        or entry.get("link")
        or entry.get("title")
    )


def get_title(entry):
    return clean_text(
        entry.get("title", "Market Update")
    )


def get_link(entry):
    return (
        entry.get("link") or ""
    ).strip()


def get_published(entry):
    return (
        entry.get("published")
        or entry.get("updated")
        or ""
    ).strip()


def get_image(entry):

    for media in entry.get("media_content", []):
        if media.get("url"):
            return media["url"]

    for media in entry.get("media_thumbnail", []):
        if media.get("url"):
            return media["url"]

    for enclosure in entry.get("enclosures", []):
        url = (
            enclosure.get("href")
            or enclosure.get("url")
        )

        if url:
            return url

    return None


def remember(seen, value):

    seen.add(value)

    if len(seen) > MAX_MEMORY:

        values = list(seen)

        seen.clear()

        for value in values[-350:]:
            seen.add(value)


async def fetch_feed(url):

    try:

        headers = {
            "User-Agent": (
                "Mozilla/5.0 "
                "(compatible; MarketUpdateBot/1.0)"
            )
        }

        async with aiohttp.ClientSession(
            headers=headers
        ) as session:

            async with session.get(
                url,
                timeout=30
            ) as response:

                if response.status != 200:

                    print(
                        f"❌ RSS HTTP {response.status}: {url}"
                    )

                    return None

                content = await response.read()

        return await asyncio.to_thread(
            feedparser.parse,
            content
        )

    except Exception as error:

        print(
            f"❌ RSS error: {url}"
        )
        print(error)

        return None


async def send_post(
    bot,
    channels,
    text,
    image_url=None
):

    for channel in channels:

        if not channel:
            print("⚠️ Empty channel variable.")
            continue

        channel = channel.strip()

        try:

            if image_url:

                try:

                    async with aiohttp.ClientSession() as session:

                        async with session.get(
                            image_url,
                            timeout=20
                        ) as response:

                            if response.status == 200:

                                image = await response.read()

                                await bot.send_photo(
                                    chat_id=channel,
                                    photo=image,
                                    caption=text[:1024]
                                )

                                print(
                                    f"✅ Image posted to {channel}"
                                )

                                await asyncio.sleep(1)
                                continue

                except Exception as image_error:

                    print(
                        f"⚠️ Image failed for {channel}: "
                        f"{image_error}"
                    )

            await bot.send_message(
                chat_id=channel,
                text=text,
                disable_web_page_preview=False
            )

            print(
                f"✅ Message posted to {channel}"
            )

        except Exception as error:

            print(
                f"❌ Telegram posting error "
                f"for {channel}: {error}"
            )

        await asyncio.sleep(1)


def forex_post(entry):

    title = get_title(entry)

    summary = shorten(
        entry.get("summary", ""),
        300
    )

    link = get_link(entry)

    published = get_published(entry)

    text = (
        "💱 FOREX MARKET ALERT\n"
        "━━━━━━━━━━━━━━━━━━\n\n"
        f"📰 {title}\n\n"
    )

    if summary:
        text += (
            "📌 MARKET FOCUS\n"
            f"{summary}\n\n"
        )

    if published:
        text += f"🕒 {published}\n\n"

    if link:
        text += (
            "🔗 READ FULL STORY\n"
            f"{link}\n\n"
        )

    text += (
        "📍 SOURCE: Investing.com\n\n"
        "⚠️ Market news & information only.\n"
        "Not financial advice."
    )

    return text


def crypto_post(entry):

    title = get_title(entry)

    summary = shorten(
        entry.get("summary", ""),
        300
    )

    link = get_link(entry)

    published = get_published(entry)

    text = (
        "₿ CRYPTO MARKET ALERT\n"
        "━━━━━━━━━━━━━━━━━━\n\n"
        f"📰 {title}\n\n"
    )

    if summary:
        text += (
            "📌 MARKET FOCUS\n"
            f"{summary}\n\n"
        )

    if published:
        text += f"🕒 {published}\n\n"

    if link:
        text += (
            "🔗 READ FULL STORY\n"
            f"{link}\n\n"
        )

    text += (
        "📍 SOURCE: Cointelegraph\n\n"
        "⚠️ Market news & information only.\n"
        "Not financial advice."
    )

    return text


def casino_post(entry):

    title = get_title(entry)

    summary = shorten(
        entry.get("summary", ""),
        320
    )

    link = get_link(entry)

    published = get_published(entry)

    text = (
        "🎰 CASINO & IGAMING ALERT\n"
        "━━━━━━━━━━━━━━━━━━\n\n"
        f"📰 {title}\n\n"
    )

    if summary:
        text += (
            "📌 INDUSTRY UPDATE\n"
            f"{summary}\n\n"
        )

    if published:
        text += f"🕒 {published}\n\n"

    if link:
        text += (
            "🔗 READ FULL STORY\n"
            f"{link}\n\n"
        )

    text += (
        "📍 SOURCE: Yogonet\n\n"
        "🔞 18+ only.\n"
        "Play responsibly."
    )

    return text


async def test_forex(update, context):

    print("🧪 /test_forex received")

    await update.message.reply_text(
        "🔎 Testing Forex..."
    )

    feed = await fetch_feed(FOREX_RSS)

    if not feed or not feed.entries:

        await update.message.reply_text(
            "❌ Forex feed unavailable."
        )

        return

    entry = feed.entries[0]

    await send_post(
        context.bot,
        FOREX_CHANNELS,
        forex_post(entry),
        get_image(entry)
    )

    await update.message.reply_text(
        "✅ Forex test completed."
    )


async def test_crypto(update, context):

    print("🧪 /test_crypto received")

    await update.message.reply_text(
        "🔎 Testing Crypto..."
    )

    feed = await fetch_feed(CRYPTO_RSS)

    if not feed or not feed.entries:

        await update.message.reply_text(
            "❌ Crypto feed unavailable."
        )

        return

    entry = feed.entries[0]

    await send_post(
        context.bot,
        CRYPTO_CHANNELS,
        crypto_post(entry),
        get_image(entry)
    )

    await update.message.reply_text(
        "✅ Crypto test completed."
    )


async def test_casino(update, context):

    print("🧪 /test_casino received")

    await update.message.reply_text(
        "🔎 Testing Casino..."
    )

    feed = await fetch_feed(CASINO_RSS)

    if not feed or not feed.entries:

        await update.message.reply_text(
            "❌ Casino feed unavailable."
        )

        return

    entry = feed.entries[0]

    await send_post(
        context.bot,
        CASINO_CHANNELS,
        casino_post(entry),
        get_image(entry)
    )

    await update.message.reply_text(
        "✅ Casino test completed."
    )


async def start_command(update, context):

    print("🧪 /start received")

    await update.message.reply_text(
        "🤖 MARKET UPDATE BOT\n\n"
        "✅ Forex monitoring\n"
        "✅ Crypto monitoring\n"
        "✅ Casino monitoring\n\n"
        "📰 Automatic new-update posting is active.\n\n"
        "/test_forex\n"
        "/test_crypto\n"
        "/test_casino"
    )


async def check_forex(bot):

    print("🔎 Checking Forex news...")

    feed = await fetch_feed(FOREX_RSS)

    if not feed or not feed.entries:
        return

    for entry in reversed(
        feed.entries[-10:]
    ):

        identifier = item_id(entry)

        if not identifier:
            continue

        if identifier in seen_forex:
            continue

        remember(
            seen_forex,
            identifier
        )

        print(
            f"🆕 NEW FOREX UPDATE: "
            f"{get_title(entry)}"
        )

        await send_post(
            bot,
            FOREX_CHANNELS,
            forex_post(entry),
            get_image(entry)
        )


async def check_crypto(bot):

    print("🔎 Checking Crypto news...")

    feed = await fetch_feed(CRYPTO_RSS)

    if not feed or not feed.entries:
        return

    for entry in reversed(
        feed.entries[-10:]
    ):

        identifier = item_id(entry)

        if not identifier:
            continue

        if identifier in seen_crypto:
            continue

        remember(
            seen_crypto,
            identifier
        )

        print(
            f"🆕 NEW CRYPTO UPDATE: "
            f"{get_title(entry)}"
        )

        await send_post(
            bot,
            CRYPTO_CHANNELS,
            crypto_post(entry),
            get_image(entry)
        )


async def check_casino(bot):

    print("🔎 Checking Casino news...")

    feed = await fetch_feed(CASINO_RSS)

    if not feed or not feed.entries:
        return

    for entry in reversed(
        feed.entries[-10:]
    ):

        identifier = item_id(entry)

        if not identifier:
            continue

        if identifier in seen_casino:
            continue

        remember(
            seen_casino,
            identifier
        )

        print(
            f"🆕 NEW CASINO UPDATE: "
            f"{get_title(entry)}"
        )

        await send_post(
            bot,
            CASINO_CHANNELS,
            casino_post(entry),
            get_image(entry)
        )


async def initialize_memory():

    feeds = [
        ("forex", FOREX_RSS),
        ("crypto", CRYPTO_RSS),
        ("casino", CASINO_RSS),
    ]

    for category, url in feeds:

        feed = await fetch_feed(url)

        if not feed or not feed.entries:
            continue

        for entry in feed.entries[-20:]:

            identifier = item_id(entry)

            if not identifier:
                continue

            if category == "forex":
                seen_forex.add(identifier)

            elif category == "crypto":
                seen_crypto.add(identifier)

            else:
                seen_casino.add(identifier)


async def monitor(application):

    print(
        "📰 NEWS MONITOR STARTED"
    )

    await initialize_memory()

    print(
        f"📚 Memory: "
        f"Forex={len(seen_forex)} | "
        f"Crypto={len(seen_crypto)} | "
        f"Casino={len(seen_casino)}"
    )

    while True:

        try:

            await check_forex(
                application.bot
            )

            await check_crypto(
                application.bot
            )

            await check_casino(
                application.bot
            )

        except Exception as error:

            print(
                f"❌ Monitor error: {error}"
            )

        await asyncio.sleep(
            CHECK_INTERVAL
        )


async def post_init(application):

    print("========================================")
    print("🤖 MARKET UPDATE BOT")
    print("========================================")

    try:

        me = await application.bot.get_me()

        print(
            f"✅ Connected as "
            f"@{me.username}"
        )

    except Exception as error:

        print(
            f"❌ Telegram connection error: {error}"
        )

    print(
        "✅ News monitor launching"
    )

    application.bot_data[
        "monitor_task"
    ] = asyncio.create_task(
        monitor(application)
    )


async def post_shutdown(application):

    task = application.bot_data.get(
        "monitor_task"
    )

    if task:

        task.cancel()

        try:
            await task

        except asyncio.CancelledError:
            pass


async def error_handler(update, context):

    print(
        f"❌ UPDATE HANDLER ERROR: "
        f"{context.error}"
    )


def main():

    if not BOT_TOKEN:

        print(
            "❌ BOT_TOKEN missing from Railway."
        )

        return

    app = (
        ApplicationBuilder()
        .token(BOT_TOKEN)
        .post_init(post_init)
        .post_shutdown(post_shutdown)
        .build()
    )

    app.add_handler(
        CommandHandler(
            "start",
            start_command
        )
    )

    app.add_handler(
        CommandHandler(
            "test_forex",
            test_forex
        )
    )

    app.add_handler(
        CommandHandler(
            "test_crypto",
            test_crypto
        )
    )

    app.add_handler(
        CommandHandler(
            "test_casino",
            test_casino
        )
    )

    app.add_error_handler(
        error_handler
    )

    print(
        "🚀 Starting Telegram polling..."
    )

    app.run_polling(
        allowed_updates=Update.ALL_TYPES
    )


if __name__ == "__main__":
    main()
