import os
import asyncio
import feedparser
import aiohttp

from datetime import datetime, timezone

from telegram import Update
from telegram.ext import (
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

CRYPTO_CHANNELS = [
    os.getenv("CRYPTO_CHANNEL"),
]

CASINO_CHANNELS = [
    os.getenv("CASINO_CHANNEL_1"),
    os.getenv("CASINO_CHANNEL_2"),
]


# =========================================================
# NEWS RSS SOURCES
# =========================================================

FOREX_RSS = "https://www.investing.com/rss/news_1.rss"
CRYPTO_RSS = "https://cointelegraph.com/rss"
CASINO_RSS = "https://www.yogonet.com/international/online-gaming/rss.xml"


# =========================================================
# SETTINGS
# =========================================================

# Check for new articles every 2 minutes.
CHECK_INTERVAL = 120

# Number of previous articles remembered during this run.
MAX_MEMORY = 300


# =========================================================
# MEMORY
# =========================================================

seen_forex = set()
seen_crypto = set()
seen_casino = set()


# =========================================================
# START COMMAND
# =========================================================

async def start_command(
    update: Update,
    context: ContextTypes.DEFAULT_TYPE
):
    await update.message.reply_text(
        "🤖 Market Update Bot is online.\n\n"
        "💱 Forex monitoring: ACTIVE\n"
        "₿ Crypto monitoring: ACTIVE\n"
        "🎰 Casino monitoring: ACTIVE\n\n"
        "New updates are automatically sent to their assigned channels."
    )


# =========================================================
# GENERAL HELPERS
# =========================================================

def clean_text(text):
    if not text:
        return ""

    return " ".join(text.split())


def get_entry_id(entry):
    return (
        entry.get("id")
        or entry.get("guid")
        or entry.get("link")
        or entry.get("title")
    )


def get_image(entry):
    # Standard RSS media
    media_content = entry.get("media_content")

    if media_content:
        for media in media_content:
            url = media.get("url")
            if url:
                return url

    # media_thumbnail
    media_thumbnail = entry.get("media_thumbnail")

    if media_thumbnail:
        for media in media_thumbnail:
            url = media.get("url")
            if url:
                return url

    # enclosure
    enclosures = entry.get("enclosures")

    if enclosures:
        for enclosure in enclosures:
            url = enclosure.get("href") or enclosure.get("url")

            if url:
                content_type = enclosure.get("type", "")

                if (
                    content_type.startswith("image/")
                    or content_type == ""
                ):
                    return url

    # image in parsed links
    links = entry.get("links", [])

    for link in links:

        href = link.get("href", "")
        link_type = link.get("type", "")

        if (
            link_type.startswith("image/")
            or any(
                href.lower().endswith(ext)
                for ext in [
                    ".jpg",
                    ".jpeg",
                    ".png",
                    ".webp"
                ]
            )
        ):
            return href

    return None


def get_summary(entry):
    summary = (
        entry.get("summary")
        or entry.get("description")
        or ""
    )

    summary = clean_text(summary)

    # Keep Telegram posts compact.
    if len(summary) > 500:
        summary = summary[:497] + "..."

    return summary


def get_published(entry):
    return (
        entry.get("published")
        or entry.get("updated")
        or ""
    )


def remember(seen_set, item_id):
    seen_set.add(item_id)

    if len(seen_set) > MAX_MEMORY:

        # Keep approximately the newest memory items.
        items = list(seen_set)

        seen_set.clear()

        for item in items[-200:]:
            seen_set.add(item)


# =========================================================
# TELEGRAM SENDER
# =========================================================

async def send_post(
    bot,
    channels,
    text,
    image_url=None
):

    channels = [
        c.strip()
        for c in channels
        if c and c.strip()
    ]

    for channel in channels:

        try:

            if image_url:

                try:

                    async with aiohttp.ClientSession() as session:

                        async with session.get(
                            image_url,
                            timeout=15
                        ) as response:

                            if response.status == 200:

                                image_bytes = await response.read()

                                await bot.send_photo(
                                    chat_id=channel,
                                    photo=image_bytes,
                                    caption=text
                                )

                            else:

                                await bot.send_message(
                                    chat_id=channel,
                                    text=text,
                                    disable_web_page_preview=False
                                )

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

            else:

                await bot.send_message(
                    chat_id=channel,
                    text=text,
                    disable_web_page_preview=False
                )

            print(
                f"✅ Posted successfully to {channel}"
            )

        except Exception as error:

            print(
                f"❌ Could not post to {channel}: {error}"
            )

        await asyncio.sleep(1)


# =========================================================
# FORMAT FOREX
# =========================================================

def format_forex(entry):

    title = clean_text(
        entry.get("title", "Forex Market Update")
    )

    summary = get_summary(entry)
    link = entry.get("link", "")
    published = get_published(entry)

    text = (
        "💱 FOREX MARKET ALERT\n"
        "━━━━━━━━━━━━━━━━━━\n\n"
        f"📰 {title}\n\n"
    )

    if summary:
        text += (
            "📊 MARKET FOCUS\n"
            f"{summary}\n\n"
        )

    if published:
        text += f"🕒 {published}\n\n"

    if link:
        text += f"🔗 Read full story\n{link}\n\n"

    text += (
        "📌 SOURCE: Investing.com\n\n"
        "⚠️ Market news & information only.\n"
        "Not financial advice."
    )

    return text


# =========================================================
# FORMAT CRYPTO
# =========================================================

def format_crypto(entry):

    title = clean_text(
        entry.get("title", "Crypto Market Update")
    )

    summary = get_summary(entry)
    link = entry.get("link", "")
    published = get_published(entry)

    text = (
        "₿ CRYPTO MARKET ALERT\n"
        "━━━━━━━━━━━━━━━━━━\n\n"
        f"📰 {title}\n\n"
    )

    if summary:
        text += (
            "📈 MARKET FOCUS\n"
            f"{summary}\n\n"
        )

    if published:
        text += f"🕒 {published}\n\n"

    if link:
        text += f"🔗 Read full story\n{link}\n\n"

    text += (
        "📌 SOURCE: Cointelegraph\n\n"
        "⚠️ Market news & information only.\n"
        "Not financial advice."
    )

    return text


# =========================================================
# FORMAT CASINO
# =========================================================

def format_casino(entry):

    title = clean_text(
        entry.get("title", "Casino Industry Update")
    )

    summary = get_summary(entry)
    link = entry.get("link", "")
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
        text += f"🔗 Read full story\n{link}\n\n"

    text += (
        "📌 SOURCE: Yogonet\n\n"
        "🔞 18+ only.\n"
        "Play responsibly."
    )

    return text


# =========================================================
# CHECK RSS FEED
# =========================================================

async def fetch_feed(url):

    try:

        async with aiohttp.ClientSession(
            headers={
                "User-Agent": (
                    "Mozilla/5.0 "
                    "(compatible; MarketUpdateBot/1.0)"
                )
            }
        ) as session:

            async with session.get(
                url,
                timeout=30
            ) as response:

                if response.status != 200:

                    print(
                        f"❌ Feed returned HTTP "
                        f"{response.status}: {url}"
                    )

                    return None

                content = await response.read()

                feed = await asyncio.to_thread(
                    feedparser.parse,
                    content
                )

                return feed

    except Exception as error:

        print(
            f"❌ Feed error: {url} -> {error}"
        )

        return None


# =========================================================
# PROCESS FOREX
# =========================================================

async def check_forex(bot):

    print("🔎 Checking Forex news...")

    feed = await fetch_feed(
        FOREX_RSS
    )

    if not feed or not feed.entries:

        print("ℹ️ No Forex feed entries.")
        return

    # Feed is normally newest first.
    newest_entries = list(
        reversed(
            feed.entries[-10:]
        )
    )

    for entry in newest_entries:

        item_id = get_entry_id(entry)

        if not item_id:
            continue

        if item_id in seen_forex:
            continue

        remember(
            seen_forex,
            item_id
        )

        title = clean_text(
            entry.get("title", "")
        )

        print(
            f"🆕 NEW FOREX UPDATE: {title}"
        )

        text = format_forex(entry)
        image = get_image(entry)

        await send_post(
            bot,
            FOREX_CHANNELS,
            text,
            image
        )


# =========================================================
# PROCESS CRYPTO
# =========================================================

async def check_crypto(bot):

    print("🔎 Checking Crypto news...")

    feed = await fetch_feed(
        CRYPTO_RSS
    )

    if not feed or not feed.entries:

        print("ℹ️ No Crypto feed entries.")
        return

    newest_entries = list(
        reversed(
            feed.entries[-10:]
        )
    )

    for entry in newest_entries:

        item_id = get_entry_id(entry)

        if not item_id:
            continue

        if item_id in seen_crypto:
            continue

        remember(
            seen_crypto,
            item_id
        )

        title = clean_text(
            entry.get("title", "")
        )

        print(
            f"🆕 NEW CRYPTO UPDATE: {title}"
        )

        text = format_crypto(entry)
        image = get_image(entry)

        await send_post(
            bot,
            CRYPTO_CHANNELS,
            text,
            image
        )


# =========================================================
# PROCESS CASINO
# =========================================================

async def check_casino(bot):

    print("🔎 Checking Casino news...")

    feed = await fetch_feed(
        CASINO_RSS
    )

    if not feed or not feed.entries:

        print("ℹ️ No Casino feed entries.")
        return

    newest_entries = list(
        reversed(
            feed.entries[-10:]
        )
    )

    for entry in newest_entries:

        item_id = get_entry_id(entry)

        if not item_id:
            continue

        if item_id in seen_casino:
            continue

        remember(
            seen_casino,
            item_id
        )

        title = clean_text(
            entry.get("title", "")
        )

        print(
            f"🆕 NEW CASINO UPDATE: {title}"
        )

        text = format_casino(entry)
        image = get_image(entry)

        await send_post(
            bot,
            CASINO_CHANNELS,
            text,
            image
        )


# =========================================================
# NEWS MONITOR
# =========================================================

async def news_monitor(application):

    print("========================================")
    print("📰 NEWS MONITOR STARTED")
    print("========================================")

    # -----------------------------------------------------
    # FIRST SCAN
    # -----------------------------------------------------
    #
    # We DON'T immediately publish every article already
    # sitting in the RSS feed when the bot starts.
    #
    # We mark current articles as seen first.
    # New articles appearing afterward will be posted.
    #

    await initialize_seen_items()

    print("✅ Existing articles marked as seen.")
    print(
        f"⏱ Checking feeds every "
        f"{CHECK_INTERVAL} seconds."
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


# =========================================================
# INITIALIZE MEMORY
# =========================================================

async def initialize_seen_items():

    global seen_forex
    global seen_crypto
    global seen_casino

    feeds = [
        ("forex", FOREX_RSS),
        ("crypto", CRYPTO_RSS),
        ("casino", CASINO_RSS),
    ]

    for category, url in feeds:

        feed = await fetch_feed(
            url
        )

        if not feed or not feed.entries:
            continue

        recent = feed.entries[-20:]

        for entry in recent:

            item_id = get_entry_id(entry)

            if not item_id:
                continue

            if category == "forex":
                seen_forex.add(item_id)

            elif category == "crypto":
                seen_crypto.add(item_id)

            elif category == "casino":
                seen_casino.add(item_id)

    print(
        f"📚 Memory loaded: "
        f"Forex={len(seen_forex)}, "
        f"Crypto={len(seen_crypto)}, "
        f"Casino={len(seen_casino)}"
    )


# =========================================================
# APPLICATION
# =========================================================

async def post_init(application):

    print("========================================")
    print("🤖 MARKET UPDATE BOT")
    print("========================================")

    print("✅ Telegram connected")
    print("✅ News monitor launching")

    application.bot_data[
        "monitor_task"
    ] = asyncio.create_task(
        news_monitor(application)
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


# =========================================================
# MAIN
# =========================================================

def main():

    if not BOT_TOKEN:

        print(
            "❌ BOT_TOKEN is missing."
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

    print(
        "🚀 Starting Telegram bot..."
    )

    app.run_polling()


if __name__ == "__main__":
    main()
