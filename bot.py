import os
import discord
import aiohttp
from discord import Embed

TOKEN = os.getenv("DISCORD_BOT_TOKEN")
CHANNEL_ID = int(os.getenv("CHANNEL_ID", "0"))
MESSAGE_FILE = "last_message_id.txt"

intents = discord.Intents.default()
client = discord.Client(intents=intents)

# ---------------------- FETCHERS ---------------------- #

async def fetch_epic_free_games():
    """Fetch free games from Epic Games API."""
    url = "https://store-site-backend-static.ak.epicgames.com/freeGamesPromotions"
    async with aiohttp.ClientSession() as session:
        async with session.get(url) as response:
            data = await response.json()
            games = []
            for game in data["data"]["Catalog"]["searchStore"]["elements"]:
                if game["price"]["totalPrice"]["discountPrice"] == 0:
                    title = game["title"]
                    link = f"https://store.epicgames.com/en-US/p/{game['productSlug']}"
                    img = game["keyImages"][0]["url"] if game["keyImages"] else None
                    games.append({
                        "store": "Epic Games",
                        "title": title,
                        "link": link,
                        "img": img
                    })
            return games


async def fetch_steam_free_games():
    """Fetch always-free games from Steam API."""
    url = "https://api.steampowered.com/ISteamApps/GetAppList/v2/"
    # This list is huge; we’ll use Steam’s search page with free filter
    search_url = "https://store.steampowered.com/search/?category1=998&filter=free"
    async with aiohttp.ClientSession() as session:
        async with session.get(search_url) as response:
            html = await response.text()
            from bs4 import BeautifulSoup
            soup = BeautifulSoup(html, "html.parser")
            games = []
            for row in soup.select(".search_result_row"):
                title = row.select_one(".title").get_text(strip=True)
                link = row["href"]
                img = row.select_one("img")["src"] if row.select_one("img") else None
                games.append({
                    "store": "Steam",
                    "title": title,
                    "link": link,
                    "img": img
                })
            return games[:5]


async def fetch_ubisoft_free_games():
    """Fetch Ubisoft free games."""
    url = "https://store.ubisoft.com/us/free-games"
    async with aiohttp.ClientSession() as session:
        async with session.get(url) as response:
            html = await response.text()
            from bs4 import BeautifulSoup
            soup = BeautifulSoup(html, "html.parser")
            games = []
            for item in soup.select(".category-game-card__title"):
                title = item.get_text(strip=True)
                parent = item.find_parent("a")
                link = parent["href"] if parent else None
                if link and not link.startswith("http"):
                    link = "https://store.ubisoft.com" + link
                games.append({
                    "store": "Ubisoft",
                    "title": title,
                    "link": link,
                    "img": None
                })
            return games[:5]

# ---------------------- EMBED BUILDER ---------------------- #

async def build_embed(epic_games, steam_games, ubisoft_games):
    embed = Embed(
        title="🎁 Free Games of the Day",
        description="Grab these **100% free-to-claim** or **temporarily free** games!",
        color=0x00ff99,
    )

    if epic_games:
        embed.add_field(name="🧱 Epic Games Store", value="\u200b", inline=False)
        for g in epic_games[:3]:
            embed.add_field(
                name=f"🎮 {g['title']}",
                value=f"[Claim here]({g['link']})",
                inline=False,
            )

    if steam_games:
        embed.add_field(name="🔥 Steam Free Games", value="\u200b", inline=False)
        for g in steam_games[:3]:
            embed.add_field(
                name=f"🕹️ {g['title']}",
                value=f"[Get on Steam]({g['link']})",
                inline=False,
            )

    if ubisoft_games:
        embed.add_field(name="🧩 Ubisoft Connect", value="\u200b", inline=False)
        for g in ubisoft_games[:3]:
            embed.add_field(
                name=f"🎯 {g['title']}",
                value=f"[Claim now]({g['link']})",
                inline=False,
            )

    # Use first Epic image if available
    if epic_games and epic_games[0].get("img"):
        embed.set_thumbnail(url=epic_games[0]["img"])

    embed.set_footer(text="Auto-updated daily | Epic • Steam • Ubisoft 🎮")
    return embed

# ---------------------- MAIN ---------------------- #

@client.event
async def on_ready():
    print(f"✅ Logged in as {client.user}")
    channel = client.get_channel(CHANNEL_ID)

    epic_games = await fetch_epic_free_games()
    steam_games = await fetch_steam_free_games()
    ubisoft_games = await fetch_ubisoft_free_games()

    embed = await build_embed(epic_games, steam_games, ubisoft_games)

    last_message_id = None
    if os.path.exists(MESSAGE_FILE):
        with open(MESSAGE_FILE, "r") as f:
            last_message_id = f.read().strip()

    try:
        if last_message_id:
            msg = await channel.fetch_message(int(last_message_id))
            await msg.edit(embed=embed)
            print("🔁 Message updated successfully.")
        else:
            msg = await channel.send(embed=embed)
            with open(MESSAGE_FILE, "w") as f:
                f.write(str(msg.id))
            print("✅ First message posted successfully.")
    except Exception as e:
        print(f"⚠️ Error: {e}")


client.run(TOKEN)

