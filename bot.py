#!/usr/bin/env python3
"""
FreeGames Discord Bot - Full rebuild

Supports two modes:
- action (default): login, post new free games, logout (for GitHub Actions)
- daemon: run as persistent bot (for VPS/docker) and accept !freegames command

Configure via env:
- DISCORD_BOT_TOKEN       (required)
- CHANNEL_ID              (required, numeric)
- RUN_MODE                "action" or "daemon" (default "action")
- MENTION_ON_NEW          "true" or "false" (default "false")
"""

import os
import asyncio
import json
from datetime import datetime
from typing import List, Dict, Optional
import aiohttp
from bs4 import BeautifulSoup
import re
import traceback

import discord
from discord import Embed, File, Colour
from discord.ext import commands

# -------------------------
# Config
# -------------------------
TOKEN = os.getenv("DISCORD_BOT_TOKEN")
CHANNEL_ID = int(os.getenv("CHANNEL_ID", "0"))
RUN_MODE = os.getenv("RUN_MODE", "action").lower()   # "action" or "daemon"
MENTION_ON_NEW = os.getenv("MENTION_ON_NEW", "false").lower() == "true"
POSTED_FILE = "posted_games.json"

if not TOKEN:
    raise SystemExit("DISCORD_BOT_TOKEN is required in env")

if CHANNEL_ID == 0:
    raise SystemExit("CHANNEL_ID is required in env (set channel id where bot should post)")

# Logos and colors per store
STORE_META = {
    "Epic": {
        "name": "Epic Games Store",
        "color": Colour.blue(),
        "logo": "https://upload.wikimedia.org/wikipedia/commons/1/12/Epic_Games_logo.svg"
    },
    "Steam": {
        "name": "Steam",
        "color": Colour.dark_grey(),
        "logo": "https://upload.wikimedia.org/wikipedia/commons/8/83/Steam_icon_logo.svg"
    },
    "GOG": {
        "name": "GOG",
        "color": Colour.dark_purple(),
        "logo": "https://upload.wikimedia.org/wikipedia/commons/7/73/GOG.com_logo.svg"
    },
    "Ubisoft": {
        "name": "Ubisoft Store",
        "color": Colour.gold(),
        "logo": "https://upload.wikimedia.org/wikipedia/commons/3/3e/Ubisoft_2017_logo.svg"
    },
    "EA": {
        "name": "Electronic Arts",
        "color": Colour.red(),
        "logo": "https://upload.wikimedia.org/wikipedia/commons/6/6b/Electronic_Arts_Logo.svg"
    },
    # add more stores if desired
}

# -------------------------
# Storage helpers
# -------------------------
def load_posted() -> List[str]:
    if os.path.exists(POSTED_FILE):
        try:
            with open(POSTED_FILE, "r", encoding="utf-8") as f:
                return json.load(f)
        except Exception:
            return []
    return []

def save_posted(posted: List[str]):
    with open(POSTED_FILE, "w", encoding="utf-8") as f:
        json.dump(posted, f, indent=2, ensure_ascii=False)

# -------------------------
# Fetchers
# Each fetcher returns List[dict] with keys:
#  - id (unique string)
#  - title
#  - store (one of keys in STORE_META)
#  - url
#  - image (thumbnail url)
#  - note (str) - optional
#  - free_until (str ISO date or human)
#  - price (optional)
# -------------------------
HEADERS = {"User-Agent": "Mozilla/5.0 (X11; Linux x86_64) FreeGamesBot/1.0"}

async def fetch_epic(session: aiohttp.ClientSession) -> List[Dict]:
    url = "https://store-site-backend-static.ak.epicgames.com/freeGamesPromotions?locale=en-US&country=US&allowCountries=US"
    items = []
    try:
        async with session.get(url, headers=HEADERS, timeout=30) as r:
            if r.status != 200:
                return items
            j = await r.json()
    except Exception:
        return items

    elements = j.get("data", {}).get("Catalog", {}).get("searchStore", {}).get("elements", [])
    for el in elements:
        promotions = el.get("promotions", {})
        found_free = False
        free_until = None
        # check both promotionalOffers and upcomingPromotionalOffers
        for block in ("promotionalOffers", "upcomingPromotionalOffers"):
            for entry in promotions.get(block, []):
                for offer in entry.get("promotionalOffers", []):
                    ds = offer.get("discountSetting", {})
                    if ds.get("discountType") == "FREE":
                        found_free = True
                        free_until = offer.get("endDate")
                        # keep latest end if multiple
        if not found_free:
            continue
        title = el.get("title") or el.get("localizedTitle") or el.get("productSlug", "Unknown")
        product_slug = el.get("productSlug")
        url_game = f"https://www.epicgames.com/store/en-US/p/{product_slug}" if product_slug else el.get("url", "")
        image = None
        # find a key image (safely)
        for img in el.get("keyImages", []):
            if img.get("type") == "Thumbnail" or img.get("type") == "OfferImageTall":
                image = img.get("url")
                break
        image = image or (el.get("keyImages") and el["keyImages"][0].get("url")) or ""
        item_id = f"epic:{el.get('id') or product_slug or title}"
        items.append({
            "id": item_id,
            "title": title,
            "store": "Epic",
            "url": url_game,
            "image": image,
            "note": el.get("description", "") or el.get("shortDescription", ""),
            "free_until": free_until or "",
            "price": el.get("price", {}).get("totalPrice", {}).get("fmt", "")
        })
    return items

async def fetch_steam(session: aiohttp.ClientSession) -> List[Dict]:
    # We'll use Steam search filters for free or free weekends and parse HTML
    base = "https://store.steampowered.com/search/results/"
    params = {"query": "", "start": 0, "count": 50, "filter": "free", "infinite": 1, "cc": "us", "l": "en"}
    items = []
    try:
        async with session.get(base, params=params, headers=HEADERS, timeout=30) as r:
            if r.status != 200:
                return items
            data = await r.json()
            results_html = data.get("results_html", "")
    except Exception:
        return items

    soup = BeautifulSoup(results_html, "html.parser")
    rows = soup.select(".search_result_row")
    for row in rows:
        appid = row.get("data-ds-appid") or row.get("data-ds-packageid") or ""
        title_tag = row.select_one(".title")
        title = title_tag.text.strip() if title_tag else f"Steam {appid}"
        url = row.get("href") or f"https://store.steampowered.com/app/{appid}/"
        # try to get thumbnail by appid
        image = f"https://cdn.akamai.steamstatic.com/steam/apps/{appid}/header.jpg" if appid else ""
        # price / free until not always available via this endpoint
        items.append({
            "id": f"steam:{appid or title}",
            "title": title,
            "store": "Steam",
            "url": url,
            "image": image,
            "note": "",
            "free_until": ""
        })
    return items

async def fetch_gog(session: aiohttp.ClientSession) -> List[Dict]:
    # GOG sometimes exposes freebies in a specials feed. We'll attempt to parse the deals page.
    url = "https://www.gog.com/games?price=free"
    items = []
    try:
        async with session.get(url, headers=HEADERS, timeout=30) as r:
            if r.status != 200:
                return items
            text = await r.text()
    except Exception:
        return items

    soup = BeautifulSoup(text, "html.parser")
    # GOG uses JSON in window.__INITIAL_STATE__ sometimes; fallback to parse cards
    cards = soup.select("a.product-tile")
    for c in cards:
        title = c.select_one(".product-title")
        title_text = title.text.strip() if title else "GOG Game"
        href = c.get("href")
        url_full = f"https://www.gog.com{href}" if href and href.startswith("/") else href or ""
        img_tag = c.select_one("img")
        img = img_tag.get("src") if img_tag and img_tag.get("src") else ""
        item_id = f"gog:{href or title_text}"
        items.append({
            "id": item_id,
            "title": title_text,
            "store": "GOG",
            "url": url_full,
            "image": img,
            "note": "",
            "free_until": ""
        })
    return items

async def fetch_ubisoft(session: aiohttp.ClientSession) -> List[Dict]:
    # Ubisoft page structure changes often; attempt best-effort
    url = "https://store.ubisoft.com/us/free-games"
    items = []
    try:
        async with session.get(url, headers=HEADERS, timeout=30) as r:
            if r.status != 200:
                return items
            text = await r.text()
    except Exception:
        return items

    # Search for product blocks with JSON snippets
    # naive regex to get productName / image / url pairs
    pattern = re.compile(r'"productName"\s*:\s*"([^"]+)"|"(image|imageUrl)"\s*:\s*"([^"]+)"|"(fullPath)"\s*:\s*"([^"]+)"')
    # fallback parsing: find <a> blocks with product tiles
    soup = BeautifulSoup(text, "html.parser")
    tiles = soup.select(".ProductTile, .product-tile, .product-card")
    for t in tiles[:20]:
        name = t.get("data-product-name") or (t.select_one(".product-title") and t.select_one(".product-title").text.strip())
        link = t.get("href") or (t.select_one("a") and t.select_one("a").get("href"))
        img = ""
        img_tag = t.select_one("img")
        img = img_tag.get("src") if img_tag and img_tag.get("src") else ""
        if not name:
            continue
        item_id = f"ubisoft:{name}"
        url_full = link if link and link.startswith("http") else ("https://store.ubisoft.com" + link if link else "")
        items.append({
            "id": item_id,
            "title": name,
            "store": "Ubisoft",
            "url": url_full,
            "image": img,
            "note": "",
            "free_until": ""
        })
    return items

# You can add more fetchers (EA / Prime) using the same pattern.

# -------------------------
# Utilities
# -------------------------
def build_embed(game: Dict) -> Embed:
    store_key = game.get("store")
    meta = STORE_META.get(store_key, {})
    title = game.get("title")
    url = game.get("url") or ""
    note = game.get("note") or ""
    free_until = game.get("free_until") or ""
    price = game.get("price") or ""

    color = meta.get("color", Colour.blurple())
    logo = meta.get("logo", "")

    # Humanize free_until
    free_str = ""
    if free_until:
        # Try to shorten ISO format
        try:
            dt = datetime.fromisoformat(free_until.replace("Z", "+00:00"))
            free_str = dt.strftime("%b %d, %Y %I:%M %p UTC")
        except Exception:
            free_str = free_until

    description_lines = []
    if note:
        description_lines.append(note)
    if price:
        description_lines.append(f"Price: {price}")
    if free_str:
        description_lines.append(f"Free until: **{free_str}**")
    description = "\n".join(description_lines) if description_lines else None

    embed = Embed(title=title, url=url, description=description or None, color=color)
    # add a field for store
    embed.add_field(name="Store", value=meta.get("name", store_key), inline=True)
    if free_str:
        embed.add_field(name="Free until", value=free_str, inline=True)
    if price:
        embed.add_field(name="Price", value=str(price), inline=True)
    # set thumbnail to game image and set author to store logo
    image = game.get("image") or ""
    if image:
        embed.set_image(url=image)
    if logo:
        embed.set_author(name=meta.get("name", store_key), url=url, icon_url=logo)

    embed.set_footer(text=f"Added {datetime.utcnow().strftime('%Y-%m-%d')}")
    return embed

async def gather_all(session: aiohttp.ClientSession) -> List[Dict]:
    results = []
    try:
        epic = await fetch_epic(session)
        results.extend(epic)
    except Exception:
        pass
    try:
        steam = await fetch_steam(session)
        results.extend(steam)
    except Exception:
        pass
    try:
        gog = await fetch_gog(session)
        results.extend(gog)
    except Exception:
        pass
    try:
        ub = await fetch_ubisoft(session)
        results.extend(ub)
    except Exception:
        pass
    # normalize titles (strip)
    for r in results:
        r["title"] = (r.get("title") or "").strip()
    return results

# -------------------------
# Post logic
# -------------------------
async def post_new_games_and_exit():
    posted = load_posted()
    async with aiohttp.ClientSession() as session:
        all_games = await gather_all(session)

    # dedupe by id
    new_games = [g for g in all_games if g["id"] not in posted]
    if not new_games:
        print("No new games to post.")
        return 0

    # connect a lightweight client to post then logout
    intents = discord.Intents.default()
    client = discord.Client(intents=intents)

    @client.event
    async def on_ready():
        try:
            ch = client.get_channel(CHANNEL_ID)
            if ch is None:
                # Try fetch channel
                ch = await client.fetch_channel(CHANNEL_ID)
            mention = "@everyone " if MENTION_ON_NEW else ""
            for g in new_games:
                try:
                    embed = build_embed(g)
                    # Send mention + embed
                    await ch.send(content=mention, embed=embed)
                    # Add reaction to the embed message
                    # We need the message object to react; send returns a Message
                    # Some servers disallow embeds from bots; fallback to simple text if needed
                    msg = await ch.send("✅ React if you claimed this game!")
                    await msg.add_reaction("✅")
                except Exception as e:
                    print("Failed sending one embed:", e)
            # update posted list
            for g in new_games:
                posted.append(g["id"])
            save_posted(posted)
        except Exception:
            traceback.print_exc()
        finally:
            await client.close()

    await client.start(TOKEN)
    return len(new_games)

# -------------------------
# Daemon mode (long-running)
# -------------------------
def build_bot_daemon():
    intents = discord.Intents.default()
    bot = commands.Bot(command_prefix="!", intents=intents)

    @bot.event
    async def on_ready():
        print(f"Daemon bot logged in as {bot.user} (id: {bot.user.id})")

    @bot.command(name="freegames", help="Fetch and post latest free games now")
    @commands.is_owner()  # only server owner or bot owner can run if using owner check. Remove if undesired.
    async def freegames_cmd(ctx):
        await ctx.send("Fetching latest free games...")
        posted = load_posted()
        async with aiohttp.ClientSession() as session:
            all_games = await gather_all(session)
        new_games = [g for g in all_games if g["id"] not in posted]
        if not new_games:
            await ctx.send("No new free games found right now.")
            return
        mention = "@everyone " if MENTION_ON_NEW else ""
        for g in new_games:
            embed = build_embed(g)
            await ctx.send(content=mention, embed=embed)
            msg = await ctx.send("✅ React if you claimed this game!")
            await msg.add_reaction("✅")
            posted.append(g["id"])
        save_posted(posted)
        await ctx.send("Done! Posted {} new games.".format(len(new_games)))

    return bot

# -------------------------
# Entrypoint
# -------------------------
def main():
    if RUN_MODE == "daemon":
        print("Starting in daemon mode (persistent). Use !freegames to manually fetch.")
        bot = build_bot_daemon()
        bot.run(TOKEN)
    else:
        print("Running in action mode (login, post new games, exit).")
        # for action mode, run the async posting flow and exit
        loop = asyncio.get_event_loop()
        res = loop.run_until_complete(post_new_games_and_exit())
        print(f"Posted {res} new games (if >0).")

if __name__ == "__main__":
    main()
