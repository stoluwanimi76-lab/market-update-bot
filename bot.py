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

# Investing.com Forex news RSS
FOREX_RSS = "https://www.investing.com/rss/news_1.rss"

# Correct Cointelegraph RSS
CRYPTO_RSS = "https://cointelegraph.com/rss"

# Official Yogonet Online Gaming RSS
CASINO_RSS = (
    "https://www.yogonet.com/"
    "international/online-gaming/rss.xml"
)


# =========================================================
# SETTINGS
# =========================================================

CHECK_INTERVAL = 120
MAX_MEMORY = 500

USER_AGENT = (
    "Mozilla/5.0 "
    "(Windows NT 10.0; Win64; x64) "
    "AppleWebKit/537.36 "
    "(KHTML, like Gecko) "
    "Chrome/139.0 Safari/537.36"
)


# =========================================================
# MEMORY
# =========================================================

seen_forex = set()
seen_crypto = set()
seen_casino = set()


# =========================================================
# HELPERS
# =========================================================

def clean_text(text):

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

    text = clean_text(text)

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

    return clean_text(
        entry.get(
            "title",
            "Market Update"
        )
    )


def get_summary(entry):

    return (
        entry.get("summary")
        or entry.get("description")
        or ""
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


def get_image_url(entry):

    # media_content
    for media in entry.get(
        "media_content",
        []
    ):

        url = media.get("url")

        if url:
            return url

    # media_thumbnail
    for media in entry.get(
        "media_thumbnail",
        []
    ):

        url = media.get("url")

        if url:
            return url

    # enclosure
    for enclosure in entry.get(
        "enclosures",
        []
    ):

        url = (
            enclosure.get("href")
            or enclosure.get("url")
        )

        if url:
            return url

    # links
    for link in entry.get(
        "links",
        []
    ):

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
                    ".gif"
                ]
            )
        ):

            return href

    return None


def remember(
    seen_set,
    value
):

    seen_set.add(value)

    if len(seen_set) > MAX_MEMORY:

        items = list(seen_set)

        seen_set.clear()

        for item in items[-350:]:
            seen_set.add(item)


def valid_channels(channels):

    return [
        channel.strip()
        for channel in channels
        if channel and channel.strip()
    ]


# =========================================================
# RSS FETCHER
# =========================================================

async def fetch_feed(url):

    try:

        headers = {
            "User-Agent": USER_AGENT,
            "Accept": (
                "application/rss+xml,"
                "application/xml,text/xml,"
                "text/html;q=0.9"
            ),
        }

        async with aiohttp.ClientSession(
            headers=headers
        ) as session:

            async with session.get(
                url,
                timeout=aiohttp.ClientTimeout(
                    total=30
                )
            ) as response:

                print(
                    f"🌐 Feed {url} -> "
                    f"HTTP {response.status}"
                )

                if response.status != 200:

                    return None

                content = await response.read()

        feed = await asyncio.to_thread(
            feedparser.parse,
            content
        )

        if getattr(
            feed,
            "bozo",
            False
        ):

            print(
                f"⚠️ Feed parser warning: {url}"
            )

        return feed

    except Exception as error:

        print(
            f"❌ RSS fetch failed: {url}"
        )

        print(
            f"   {error}"
        )

        return None


# =========================================================
# TELEGRAM POSTING
# =========================================================

async def send_to_channel(
    bot,
    channel,
    text,
    image_url=None
):

    if not channel:

        print(
            "⚠️ Empty Telegram channel."
        )

        return

    channel = channel.strip()

    try:

        # Try article image first
        if image_url:

            try:

                async with aiohttp.ClientSession(
                    headers={
                        "User-Agent": USER_AGENT
                    }
                ) as session:

                    async with session.get(
                        image_url,
                        timeout=20
                    ) as response:

                        if response.status == 200:

                            image_data = (
                                await response.read()
                            )

                            await bot.send_photo(
                                chat_id=channel,
                                photo=image_data,
                                caption=text[:1024]
                            )

                            print(
                                f"✅ Image post sent to "
                                f"{channel}"
                            )

                            return

                        print(
                            f"⚠️ Image HTTP "
                            f"{response.status} for "
                            f"{channel}"
                        )

            except Exception as image_error:

                print(
                    f"⚠️ Image failed for "
                    f"{channel}: {image_error}"
                )

        # Fallback to normal text message
        await bot.send_message(
            chat_id=channel,
            text=text,
            disable_web_page_preview=False
        )

        print(
            f"✅ Text post sent to "
            f"{channel}"
        )

    except Exception as error:

        print(
            f"❌ Telegram posting failed "
            f"for {channel}: {error}"
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

    if not channels:

        print(
            "⚠️ No channels configured."
        )

        return

    for channel in channels:

        await send_to_channel(
            bot,
            channel,
            text,
            image_url
        )

        await asyncio.sleep(1)


# =========================================================
# CRYPTO MARKET DATA
# =========================================================

async def get_crypto_market():

    url = (
        "https://api.coingecko.com/api/v3/simple/price"
        "?ids=bitcoin,ethereum,binancecoin,solana,ripple"
        "&vs_currencies=usd"
        "&include_24hr_change=true"
    )

    try:

        async with aiohttp.ClientSession(
            headers={
                "User-Agent": USER_AGENT
            }
        ) as session:

            async with session.get(
                url,
                timeout=20
            ) as response:

                print(
                    f"🌐 CoinGecko -> "
                    f"HTTP {response.status}"
                )

                if response.status != 200:

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


def format_change(change):

    if change is None:

        return "⚪ N/A"

    if change > 0:

        return f"🟢 +{change:.2f}%"

    if change < 0:

        return f"🔴 {change:.2f}%"

    return "⚪ 0.00%"


async def build_crypto_snapshot():

    data = await get_crypto_market()

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

        lines.append(
            f"{format_change(change)}  "
            f"{symbol}: {format_price(price)}"
        )

    if not lines:
        return ""

    return (
        "📊 CRYPTO MARKET SNAPSHOT\n"
        "━━━━━━━━━━━━━━━━━━\n"
        + "\n".join(lines)
    )


# =========================================================
# PROFESSIONAL POST FORMAT
# =========================================================

def build_forex_post(entry):

    title = get_title(entry)

    summary = shorten(
        get_summary(entry),
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
            "🔗 READ FULL STORY\n"
            f"{link}\n\n"
        )

    text += (
        "📍 SOURCE: Investing.com\n\n"
        "⚠️ Market information only. "
        "Not financial advice."
    )

    return text


async def build_crypto_post(entry):

    title = get_title(entry)

    summary = shorten(
        get_summary(entry),
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
        "⚠️ Market information only. "
        "Not financial advice."
    )

    return text


def build_casino_post(entry):

    title = get_title(entry)

    summary = shorten(
        get_summary(entry),
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
# CHECK FOREX NEWS
# =========================================================

async def check_forex(bot):

    print(
        "🔎 Checking Forex news..."
    )

    feed = await fetch_feed(
        FOREX_RSS
    )

    if not feed or not feed.entries:

        print(
            "ℹ️ No Forex entries."
        )

        return

    for entry in reversed(
        feed.entries[-10:]
    ):

        identifier = get_item_id(
            entry
        )

        if not identifier:
            continue

        if identifier in seen_forex:
            continue

        remember(
            seen_forex,
            identifier
        )

        title = get_title(
            entry
        )

        print(
            f"🆕 NEW FOREX UPDATE: "
            f"{title}"
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
# CHECK CRYPTO NEWS
# =========================================================

async def check_crypto(bot):

    print(
        "🔎 Checking Crypto news..."
    )

    feed = await fetch_feed(
        CRYPTO_RSS
    )

    if not feed or not feed.entries:

        print(
            "ℹ️ No Crypto entries."
        )

        return

    for entry in reversed(
        feed.entries[-10:]
    ):

        identifier = get_item_id(
            entry
        )

        if not identifier:
            continue

        if identifier in seen_crypto:
            continue

        remember(
            seen_crypto,
            identifier
        )

        title = get_title(
            entry
        )

        print(
            f"🆕 NEW CRYPTO UPDATE: "
            f"{title}"
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
# CHECK CASINO NEWS
# =========================================================

async def check_casino(bot):

    print(
        "🔎 Checking Casino news..."
    )

    feed = await fetch_feed(
        CASINO_RSS
    )

    if not feed or not feed.entries:

        print(
            "ℹ️ No Casino entries."
        )

        return

    for entry in reversed(
        feed.entries[-10:]
    ):

        identifier = get_item_id(
            entry
        )

        if not identifier:
            continue

        if identifier in seen_casino:
            continue

        remember(
            seen_casino,
            identifier
        )

        title = get_title(
            entry
        )

        print(
            f"🆕 NEW CASINO UPDATE: "
            f"{title}"
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
# LOAD EXISTING ARTICLES
# =========================================================

async def initialize_memory():

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

            print(
                f"⚠️ No initial "
                f"{category} entries found."
            )

            continue

        for entry in feed.entries[-20:]:

            identifier = get_item_id(
                entry
            )

            if not identifier:
                continue

            if category == "forex":

                seen_forex.add(
                    identifier
                )

            elif category == "crypto":

                seen_crypto.add(
                    identifier
                )

            elif category == "casino":

                seen_casino.add(
                    identifier
                )

    print(
        "📚 Existing articles loaded:"
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
# START COMMAND
# =========================================================

async def start_command(
    update: Update,
    context: ContextTypes.DEFAULT_TYPE
):

    print(
        "🧪 /start received"
    )

    await update.message.reply_text(
        "🤖 MARKET UPDATE BOT\n\n"
        "✅ Forex monitoring: ACTIVE\n"
        "✅ Crypto monitoring: ACTIVE\n"
        "✅ Casino monitoring: ACTIVE\n\n"
        "📰 New updates are automatically "
        "posted to their assigned channels.\n\n"
        "ADMIN TEST COMMANDS:\n"
        "/test_forex\n"
        "/test_crypto\n"
        "/test_casino"
    )


# =========================================================
# TEST FOREX
# =========================================================

async def test_forex(
    update: Update,
    context: ContextTypes.DEFAULT_TYPE
):

    print(
        "🧪 /test_forex received"
    )

    await update.message.reply_text(
        "🔎 Testing Forex..."
    )

    feed = await fetch_feed(
        FOREX_RSS
    )

    if not feed or not feed.entries:

        await update.message.reply_text(
            "❌ Forex feed unavailable."
        )

        return

    entry = feed.entries[0]

    await send_to_channels(
        context.bot,
        FOREX_CHANNELS,
        build_forex_post(entry),
        get_image_url(entry)
    )

    await update.message.reply_text(
        "✅ Forex test completed."
    )


# =========================================================
# TEST CRYPTO
# =========================================================

async def test_crypto(
    update: Update,
    context: ContextTypes.DEFAULT_TYPE
):

    print(
        "🧪 /test_crypto received"
    )

    await update.message.reply_text(
        "🔎 Testing Crypto..."
    )

    feed = await fetch_feed(
        CRYPTO_RSS
    )

    if not feed or not feed.entries:

        await update.message.reply_text(
            "❌ Crypto feed unavailable."
        )

        return

    entry = feed.entries[0]

    await send_to_channels(
        context.bot,
        CRYPTO_CHANNELS,
        await build_crypto_post(entry),
        get_image_url(entry)
    )

    await update.message.reply_text(
        "✅ Crypto test completed."
    )


# =========================================================
# TEST CASINO
# =========================================================

async def test_casino(
    update: Update,
    context: ContextTypes.DEFAULT_TYPE
):

    print(
        "🧪 /test_casino received"
    )

    await update.message.reply_text(
        "🔎 Testing Casino..."
    )

    feed = await fetch_feed(
        CASINO_RSS
    )

    if not feed or not feed.entries:

        await update.message.reply_text(
            "❌ Casino feed unavailable."
        )

        return

    entry = feed.entries[0]

    await send_to_channels(
        context.bot,
        CASINO_CHANNELS,
        build_casino_post(entry),
        get_image_url(entry)
    )

    await update.message.reply_text(
        "✅ Casino test completed."
    )


# =========================================================
# NEWS MONITOR
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

    await initialize_memory()

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
                f"❌ Monitor error: "
                f"{error}"
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

    try:

        bot_info = await application.bot.get_me()

        print(
            f"✅ Connected as "
            f"@{bot_info.username}"
        )

    except Exception as error:

        print(
            f"❌ Telegram connection error: "
            f"{error}"
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
# ERROR HANDLER
# =========================================================

async def error_handler(
    update,
    context
):

    print(
        f"❌ Telegram update error: "
        f"{context.error}"
    )


# =========================================================
# MAIN
# =========================================================

def main():

    if not BOT_TOKEN:

        print(
            "❌ BOT_TOKEN is missing "
            "from Railway Variables."
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

    application.add_error_handler(
        error_handler
    )

    print(
        "🚀 Starting Telegram polling..."
    )

    application.run_polling(
        allowed_updates=Update.ALL_TYPES
    )


if __name__ == "__main__":
    main()
