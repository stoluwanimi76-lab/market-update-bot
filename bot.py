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
# RSS SOURCES
# =========================================================

FOREX_RSS = "https://www.investing.com/rss/news_1.rss"

# Cointelegraph RSS endpoint
CRYPTO_RSS = "https://cointelegraph.com/?format=rss"

# Yogonet Online Gaming RSS
CASINO_RSS = (
    "https://www.yogonet.com/"
    "international/online-gaming/rss.xml"
)


# =========================================================
# SETTINGS
# =========================================================

# Check every 2 minutes
CHECK_INTERVAL = 120

# Amount of article IDs remembered in memory
MAX_MEMORY = 500


# =========================================================
# MEMORY
# =========================================================

seen_forex = set()
seen_crypto = set()
seen_casino = set()


# =========================================================
# BASIC HELPERS
# =========================================================

def clean_html(text):
    if not text:
        return ""

    text = html.unescape(text)

    text = re.sub(
        r"<[^>]+>",
        " ",
        text
    )

    text = re.sub(
        r"\s+",
        " ",
        text
    )

    return text.strip()


def shorten(text, limit=350):

    text = clean_html(text)

    if len(text) <= limit:
        return text

    return text[:limit - 3] + "..."


def get_item_id(entry):

    return (
        entry.get("id")
        or entry.get("guid")
        or entry.get("link")
        or entry.get("title")
    )


def get_title(entry):

    return clean_html(
        entry.get(
            "title",
            "Market Update"
        )
    )


def get_link(entry):

    return (
        entry.get("link")
        or ""
    ).strip()


def get_published(entry):

    return (
        entry.get("published")
        or entry.get("updated")
        or ""
    ).strip()


def valid_channels(channels):

    return [
        c.strip()
        for c in channels
        if c and c.strip()
    ]


def remember(seen_set, item_id):

    seen_set.add(item_id)

    if len(seen_set) > MAX_MEMORY:

        items = list(seen_set)

        seen_set.clear()

        for item in items[-350:]:
            seen_set.add(item)


# =========================================================
# IMAGE EXTRACTION
# =========================================================

def get_image_url(entry):

    # media_content
    media_content = entry.get(
        "media_content",
        []
    )

    for media in media_content:

        url = media.get("url")

        if url:
            return url


    # media_thumbnail
    thumbnails = entry.get(
        "media_thumbnail",
        []
    )

    for media in thumbnails:

        url = media.get("url")

        if url:
            return url


    # enclosure
    enclosures = entry.get(
        "enclosures",
        []
    )

    for enclosure in enclosures:

        url = (
            enclosure.get("href")
            or enclosure.get("url")
        )

        if url:

            content_type = (
                enclosure.get("type")
                or ""
            )

            if (
                content_type.startswith("image/")
                or content_type == ""
            ):
                return url


    # links containing image
    links = entry.get(
        "links",
        []
    )

    for link in links:

        href = link.get(
            "href",
            ""
        )

        link_type = link.get(
            "type",
            ""
        )

        if (
            link_type.startswith("image/")
            or any(
                href.lower().endswith(ext)
                for ext in [
                    ".jpg",
                    ".jpeg",
                    ".png",
                    ".webp",
                ]
            )
        ):
            return href


    return None


# =========================================================
# FEED FETCHER
# =========================================================

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
                        f"❌ RSS HTTP {response.status}: "
                        f"{url}"
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
            f"❌ Feed error: {url}"
        )
        print(error)

        return None


# =========================================================
# TELEGRAM POSTER
# =========================================================

async def send_to_channel(
    bot,
    channel,
    text,
    image_url=None
):

    try:

        if image_url:

            try:

                async with aiohttp.ClientSession() as session:

                    async with session.get(
                        image_url,
                        timeout=20
                    ) as response:

                        if response.status == 200:

                            image_data = (
                                await response.read()
                            )

                            # Telegram captions max out
                            # much earlier than messages,
                            # so keep them compact.
                            await bot.send_photo(
                                chat_id=channel,
                                photo=image_data,
                                caption=text[:1024]
                            )

                            print(
                                f"✅ Image post sent to {channel}"
                            )

                            return

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
            f"✅ Text post sent to {channel}"
        )


    except Exception as error:

        print(
            f"❌ Telegram post failed for "
            f"{channel}: {error}"
        )


async def send_to_channels(
    bot,
    channels,
    text,
    image_url=None
):

    channels = valid_channels(
        channels
    )

    for channel in channels:

        await send_to_channel(
            bot,
            channel,
            text,
            image_url
        )

        await asyncio.sleep(1)


# =========================================================
# CRYPTO MARKET SNAPSHOT
# =========================================================

async def get_crypto_snapshot():

    url = (
        "https://api.coingecko.com/api/v3/simple/price"
        "?ids=bitcoin,ethereum,binancecoin,solana,ripple"
        "&vs_currencies=usd"
        "&include_24hr_change=true"
    )

    try:

        async with aiohttp.ClientSession() as session:

            async with session.get(
                url,
                timeout=20
            ) as response:

                if response.status != 200:

                    print(
                        f"❌ CoinGecko HTTP "
                        f"{response.status}"
                    )

                    return None

                return await response.json()

    except Exception as error:

        print(
            f"❌ CoinGecko error: {error}"
        )

        return None


def format_price(price):

    if price >= 1000:
        return f"${price:,.2f}"

    if price >= 1:
        return f"${price:,.4f}"

    return f"${price:,.6f}"


def direction(change):

    if change is None:
        return "⚪"

    if change > 0:
        return "🟢"

    if change < 0:
        return "🔴"

    return "⚪"


async def build_crypto_snapshot():

    data = await get_crypto_snapshot()

    if not data:
        return ""

    coins = [
        ("bitcoin", "BTC"),
        ("ethereum", "ETH"),
        ("binancecoin", "BNB"),
        ("solana", "SOL"),
        ("ripple", "XRP"),
    ]

    lines = []

    for coin_id, symbol in coins:

        coin = data.get(
            coin_id
        )

        if not coin:
            continue

        price = coin.get(
            "usd"
        )

        change = coin.get(
            "usd_24h_change"
        )

        if price is None:
            continue

        if change is None:

            change_text = "N/A"
            arrow = "⚪"

        else:

            arrow = direction(
                change
            )

            sign = (
                "+"
                if change >= 0
                else ""
            )

            change_text = (
                f"{sign}{change:.2f}%"
            )

        lines.append(
            f"{arrow} {symbol} "
            f"{format_price(price)} "
            f"({change_text} 24H)"
        )

    if not lines:
        return ""

    return (
        "📊 MARKET SNAPSHOT\n"
        "━━━━━━━━━━━━━━━━━━\n"
        + "\n".join(lines)
    )


# =========================================================
# FOREX POST
# =========================================================

def build_forex_post(entry):

    title = get_title(entry)

    summary = shorten(
        entry.get(
            "summary",
            ""
        ),
        300
    )

    link = get_link(entry)

    published = get_published(
        entry
    )

    now = datetime.now(
        timezone.utc
    )

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

    text += (
        f"🕒 {published or now.strftime('%Y-%m-%d %H:%M UTC')}\n\n"
    )

    if link:

        text += (
            f"🔗 READ FULL STORY\n"
            f"{link}\n\n"
        )

    text += (
        "📍 SOURCE: Investing.com\n\n"
        "⚠️ Market news & information only.\n"
        "Not financial advice."
    )

    return text


# =========================================================
# CRYPTO POST
# =========================================================

async def build_crypto_post(entry):

    title = get_title(entry)

    summary = shorten(
        entry.get(
            "summary",
            ""
        ),
        300
    )

    link = get_link(entry)

    published = get_published(
        entry
    )

    snapshot = (
        await build_crypto_snapshot()
    )

    now = datetime.now(
        timezone.utc
    )

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

    if snapshot:

        text += (
            snapshot
            + "\n\n"
        )

    text += (
        f"🕒 {published or now.strftime('%Y-%m-%d %H:%M UTC')}\n\n"
    )

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


# =========================================================
# CASINO POST
# =========================================================

def build_casino_post(entry):

    title = get_title(entry)

    summary = shorten(
        entry.get(
            "summary",
            ""
        ),
        320
    )

    link = get_link(entry)

    published = get_published(
        entry
    )

    now = datetime.now(
        timezone.utc
    )

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

    text += (
        f"🕒 {published or now.strftime('%Y-%m-%d %H:%M UTC')}\n\n"
    )

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


# =========================================================
# CHECK FOREX
# =========================================================

async def check_forex(bot):

    print("🔎 Checking Forex news...")

    feed = await fetch_feed(
        FOREX_RSS
    )

    if not feed or not feed.entries:

        print(
            "ℹ️ Forex feed contains no entries."
        )

        return

    # Newest article first
    for entry in reversed(
        feed.entries[-10:]
    ):

        item_id = get_item_id(
            entry
        )

        if not item_id:
            continue

        if item_id in seen_forex:
            continue

        remember(
            seen_forex,
            item_id
        )

        title = get_title(
            entry
        )

        print(
            f"🆕 NEW FOREX UPDATE: {title}"
        )

        text = build_forex_post(
            entry
        )

        image = get_image_url(
            entry
        )

        await send_to_channels(
            bot,
            FOREX_CHANNELS,
            text,
            image
        )


# =========================================================
# CHECK CRYPTO
# =========================================================

async def check_crypto(bot):

    print("🔎 Checking Crypto news...")

    feed = await fetch_feed(
        CRYPTO_RSS
    )

    if not feed or not feed.entries:

        print(
            "ℹ️ Crypto feed contains no entries."
        )

        return

    for entry in reversed(
        feed.entries[-10:]
    ):

        item_id = get_item_id(
            entry
        )

        if not item_id:
            continue

        if item_id in seen_crypto:
            continue

        remember(
            seen_crypto,
            item_id
        )

        title = get_title(
            entry
        )

        print(
            f"🆕 NEW CRYPTO UPDATE: {title}"
        )

        text = await build_crypto_post(
            entry
        )

        image = get_image_url(
            entry
        )

        await send_to_channels(
            bot,
            CRYPTO_CHANNELS,
            text,
            image
        )


# =========================================================
# CHECK CASINO
# =========================================================

async def check_casino(bot):

    print("🔎 Checking Casino news...")

    feed = await fetch_feed(
        CASINO_RSS
    )

    if not feed or not feed.entries:

        print(
            "ℹ️ Casino feed contains no entries."
        )

        return

    for entry in reversed(
        feed.entries[-10:]
    ):

        item_id = get_item_id(
            entry
        )

        if not item_id:
            continue

        if item_id in seen_casino:
            continue

        remember(
            seen_casino,
            item_id
        )

        title = get_title(
            entry
        )

        print(
            f"🆕 NEW CASINO UPDATE: {title}"
        )

        text = build_casino_post(
            entry
        )

        image = get_image_url(
            entry
        )

        await send_to_channels(
            bot,
            CASINO_CHANNELS,
            text,
            image
        )


# =========================================================
# INITIAL MEMORY
# =========================================================

async def load_existing_articles():

    global seen_forex
    global seen_crypto
    global seen_casino

    sources = [
        (
            "forex",
            FOREX_RSS
        ),
        (
            "crypto",
            CRYPTO_RSS
        ),
        (
            "casino",
            CASINO_RSS
        ),
    ]

    for category, url in sources:

        feed = await fetch_feed(
            url
        )

        if not feed or not feed.entries:
            continue

        for entry in feed.entries[-20:]:

            item_id = get_item_id(
                entry
            )

            if not item_id:
                continue

            if category == "forex":

                seen_forex.add(
                    item_id
                )

            elif category == "crypto":

                seen_crypto.add(
                    item_id
                )

            elif category == "casino":

                seen_casino.add(
                    item_id
                )

    print(
        "📚 Existing articles remembered:"
    )

    print(
        f"   Forex: {len(seen_forex)}"
    )

    print(
        f"   Crypto: {len(seen_crypto)}"
    )

    print(
        f"   Casino: {len(seen_casino)}"
    )


# =========================================================
# ADMIN TEST COMMANDS
# =========================================================

async def test_forex(
    update: Update,
    context: ContextTypes.DEFAULT_TYPE
):

    message = await update.message.reply_text(
        "🔎 Testing Forex feed..."
    )

    feed = await fetch_feed(
        FOREX_RSS
    )

    if not feed or not feed.entries:

        await message.edit_text(
            "❌ Forex feed unavailable."
        )

        return

    entry = feed.entries[0]

    text = build_forex_post(
        entry
    )

    image = get_image_url(
        entry
    )

    await send_to_channels(
        context.bot,
        FOREX_CHANNELS,
        text,
        image
    )

    await message.edit_text(
        "✅ Forex test post sent."
    )


async def test_crypto(
    update: Update,
    context: ContextTypes.DEFAULT_TYPE
):

    message = await update.message.reply_text(
        "🔎 Testing Crypto feed..."
    )

    feed = await fetch_feed(
        CRYPTO_RSS
    )

    if not feed or not feed.entries:

        await message.edit_text(
            "❌ Crypto feed unavailable."
        )

        return

    entry = feed.entries[0]

    text = await build_crypto_post(
        entry
    )

    image = get_image_url(
        entry
    )

    await send_to_channels(
        context.bot,
        CRYPTO_CHANNELS,
        text,
        image
    )

    await message.edit_text(
        "✅ Crypto test post sent."
    )


async def test_casino(
    update: Update,
    context: ContextTypes.DEFAULT_TYPE
):

    message = await update.message.reply_text(
        "🔎 Testing Casino feed..."
    )

    feed = await fetch_feed(
        CASINO_RSS
    )

    if not feed or not feed.entries:

        await message.edit_text(
            "❌ Casino feed unavailable."
        )

        return

    entry = feed.entries[0]

    text = build_casino_post(
        entry
    )

    image = get_image_url(
        entry
    )

    await send_to_channels(
        context.bot,
        CASINO_CHANNELS,
        text,
        image
    )

    await message.edit_text(
        "✅ Casino test post sent."
    )


# =========================================================
# START
# =========================================================

async def start_command(
    update: Update,
    context: ContextTypes.DEFAULT_TYPE
):

    await update.message.reply_text(
        "🤖 MARKET UPDATE BOT\n\n"
        "✅ Forex monitoring: ACTIVE\n"
        "✅ Crypto monitoring: ACTIVE\n"
        "✅ Casino monitoring: ACTIVE\n\n"
        "📰 New updates are automatically "
        "posted to their assigned channels.\n\n"
        "Admin tests:\n"
        "/test_forex\n"
        "/test_crypto\n"
        "/test_casino"
    )


# =========================================================
# MONITOR
# =========================================================

async def monitor(application):

    print(
        "========================================"
    )

    print(
        "📰 NEWS MONITOR STARTED"
    )

    print(
        "========================================"
    )

    await load_existing_articles()

    print(
        f"⏱ Checking every "
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
# STARTUP
# =========================================================

async def post_init(
    application
):

    print(
        "========================================"
    )

    print(
        "🤖 MARKET UPDATE BOT"
    )

    print(
        "========================================"
    )

    print(
        "✅ Telegram connected"
    )

    print(
        "✅ News monitor launching"
    )

    application.bot_data[
        "monitor_task"
    ] = asyncio.create_task(
        monitor(application)
    )


async def post_shutdown(
    application
):

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

    application.add_handler(
        CommandHandler(
            "test_forex",
            test_forex
        )
    )

    application.add_handler(
        CommandHandler(
            "test_crypto",
            test_crypto
        )
    )

    application.add_handler(
        CommandHandler(
            "test_casino",
            test_casino
        )
    )

    print(
        "🚀 Starting Telegram bot..."
    )

    application.run_polling()


if __name__ == "__main__":
    main()
