import os
import discord
from discord.ext import tasks, commands
import requests
from datetime import datetime
import json

TOKEN = os.getenv("DISCORD_BOT_TOKEN")
CHANNEL_ID = 1429999637284126910  # 🔹 Replace with your Discord channel ID
POSTED_FILE = "posted_games.json"

intents = discord.Intents.default()
bot = commands.Bot(command_prefix="!", intents=intents)

# ---------------------- Utility functions ----------------------

def load_posted():
    if os.path.exists(POSTED_FILE):
        with open(POSTED_FILE, "r") as f:
            return json.load(f)
    return []

def save_posted(posted):
    with open(POSTED_FILE, "w") as f:
        json.dump(posted, f, indent=2)

# ---------------------- Fetch from APIs ----------------------

def get_epic_games():
    """Fetch free games from Epic Games Store"""
    url = "https://store-site-backend-static.ak.epicgames.com/freeGamesPromotions"
    data = requests.get(url).json()
    games = []

    for game in data["data"]["Catalog"]["searchStore"]["elements"]:
        title = game["title"]
        offers = game.get("promotions")
        if not offers or not offers.get("promotionalOffers"):
            continue
        offer = offers["promotionalOffers"][0]["promotionalOffers"][0]
        start = offer["startDate"][:10]
        end = offer["endDate"][:10]
        image = game["keyImages"][0]["url"]
        url_slug = game.get("productSlug") or game["catalogNs"]["mappings"][0]["pageSlug"]
        store_url = f"https://store.epicgames.com/en-US/p/{url_slug}"

        games.append({
            "title": title,
            "store": "Epic Games Store",
            "url": store_url,
            "start": start,
            "end": end,
            "image": image
        })
    return games

def get_steam_free_weekends():
    """Fetch temporary free games from Steam"""
    url = "https://store.steampowered.com/search/?filter=freeweekend&ndl=1"
    html = requests.get(url).text
    import re
    pattern = r'data-ds-appid="(\d+)"'
    appids = re.findall(pattern, html)
    games = []
    for appid in set(appids):
        games.append({
            "title": f"Steam Game (AppID: {appid})",
            "store": "Steam",
            "url": f"https://store.steampowered.com/app/{appid}/",
            "image": f"https://cdn.akamai.steamstatic.com/steam/apps/{appid}/header.jpg"
        })
    return games

def get_ubisoft_free_games():
    """Fetch Ubisoft limited-time free games (scrape site)"""
    url = "https://store.ubisoft.com/us/free-games"
    html = requests.get(url).text
    import re
    pattern = r'"productName":"(.*?)","imageUrl":"(.*?)","url":"(.*?)"'
    matches = re.findall(pattern, html)
    games = []
    for title, image, link in matches:
        games.append({
            "title": title,
            "store": "Ubisoft Store",
            "url": "https://store.ubisoft.com" + link,
            "image": image
        })
    return games

# ---------------------- Post to Discord ----------------------

async def post_free_games():
    channel = bot.get_channel(CHANNEL_ID)
    if not channel:
        print("⚠️ Channel not found!")
        return

    posted = load_posted()
    all_games = get_epic_games() + get_steam_free_weekends() + get_ubisoft_free_games()

    new_games = [g for g in all_games if g["title"] not in posted]

    for game in new_games:
        embed = discord.Embed(
            title=f"{game['title']}",
            description=f"🎮 **Store:** {game['store']}\n🕓 **Free until:** {game.get('end', 'N/A')}",
            url=game["url"],
            color=discord.Color.green()
        )
        embed.set_thumbnail(url=game["image"])
        embed.set_footer(text=f"Added on {datetime.now().strftime('%Y-%m-%d')}")
        await channel.send(embed=embed)
        await channel.send("✅ React if you claimed this game!")
        posted.append(game["title"])

    save_posted(posted)

# ---------------------- Bot Events ----------------------

@bot.event
async def on_ready():
    print(f"✅ Logged in as {bot.user}")
    await post_free_games()

bot.run(TOKEN)
