import os
import requests
import discord
from discord.ext import commands
from datetime import datetime

TOKEN = os.getenv("DISCORD_BOT_TOKEN")
CHANNEL_ID = int(os.getenv("CHANNEL_ID", "0"))

intents = discord.Intents.default()
bot = commands.Bot(command_prefix="!", intents=intents)

# ----------------------------
# 🧩 Helper functions per store
# ----------------------------

def fetch_epic_games():
    try:
        url = "https://store-site-backend-static.ak.epicgames.com/freeGamesPromotions"
        data = requests.get(url, timeout=10).json()
        games = []
        for game in data["data"]["Catalog"]["searchStore"]["elements"]:
            title = game["title"]
            desc = game.get("description", "Free on Epic Games Store")
            offer = game.get("promotions")
            free_until = "Currently Free"
            if offer and offer.get("promotionalOffers"):
                end_date = offer["promotionalOffers"][0]["promotionalOffers"][0]["endDate"]
                free_until = datetime.fromisoformat(end_date[:-1]).strftime("%b %d, %Y")
            image = game["keyImages"][0]["url"] if game.get("keyImages") else None
            url_game = f"https://store.epicgames.com/en-US/p/{game['productSlug'].split('/')[0]}" if game.get("productSlug") else "https://store.epicgames.com/en-US/"
            games.append({
                "title": title,
                "desc": desc,
                "free_until": free_until,
                "url": url_game,
                "image": image
            })
        return games
    except Exception:
        return []


def fetch_gog_games():
    try:
        resp = requests.get("https://www.gog.com/games/ajax/filtered?mediaType=game&price=free", timeout=10)
        data = resp.json()
        games = []
        for game in data["products"]:
            games.append({
                "title": game["title"],
                "desc": "Free to own on GOG",
                "free_until": "Permanent Free",
                "url": f"https://www.gog.com{game['url']}",
                "image": game["image"]
            })
        return games
    except Exception:
        return []


def fetch_steam_games():
    try:
        resp = requests.get("https://store.steampowered.com/api/featuredcategories", timeout=10)
        data = resp.json()
        games = []
        for g in data["specials"]["items"]:
            if g.get("discounted") and g["final_price"] == 0:
                games.append({
                    "title": g["name"],
                    "desc": "Free for a limited time on Steam",
                    "free_until": "Limited Offer",
                    "url": g["store_url"],
                    "image": g["header_image"]
                })
        return games
    except Exception:
        return []


def fetch_prime_gaming():
    try:
        resp = requests.get("https://gaming.amazon.com/home", timeout=10)
        if resp.status_code != 200:
            return []
        # Simplified: Prime doesn’t have a public API, so we’ll just link the homepage.
        return [{
            "title": "Prime Gaming Free Games",
            "desc": "Check out this month’s free titles with Amazon Prime.",
            "free_until": "Varies",
            "url": "https://gaming.amazon.com/home",
            "image": "https://upload.wikimedia.org/wikipedia/commons/3/37/Prime_Gaming_logo.svg"
        }]
    except Exception:
        return []

# ----------------------------
# 🎨 Build rich embed messages
# ----------------------------

def make_embed(store, color, logo_url, games):
    embed = discord.Embed(
        title=f"🎮 {store} Free Games",
        description=f"Here are the current free games available on {store}!",
        color=color,
        timestamp=datetime.utcnow()
    )
    embed.set_thumbnail(url=logo_url)

    for g in games[:5]:  # limit to 5 per store
        embed.add_field(
            name=f"🕹️ {g['title']}",
            value=f"{g['desc']}\n**Free Until:** {g['free_until']}\n[👉 Get it here]({g['url']})",
            inline=False
        )
    embed.set_footer(text="Posted by FreeGamesBot 🎮")
    return embed

# ----------------------------
# 🤖 Bot command + daily task
# ----------------------------

async def post_free_games(channel):
    stores = [
        ("Epic Games Store", 0x6A5ACD, "https://upload.wikimedia.org/wikipedia/commons/3/31/Epic_Games_logo.svg", fetch_epic_games),
        ("Steam", 0x1B2838, "https://upload.wikimedia.org/wikipedia/commons/8/83/Steam_icon_logo.svg", fetch_steam_games),
        ("GOG", 0x6A0DAD, "https://upload.wikimedia.org/wikipedia/commons/7/78/GOG.com_logo.svg", fetch_gog_games),
        ("Prime Gaming", 0x6441A5, "https://upload.wikimedia.org/wikipedia/commons/3/37/Prime_Gaming_logo.svg", fetch_prime_gaming),
    ]

    for store_name, color, logo, fetch_func in stores:
        games = fetch_func()
        if not games:
            continue
        embed = make_embed(store_name, color, logo, games)
        await channel.send(content="@everyone", embed=embed)

@bot.command(name="freegames")
async def freegames(ctx):
    await ctx.send("Fetching the latest free games... 🎮")
    await post_free_games(ctx.channel)

@bot.event
async def on_ready():
    print(f"✅ Logged in as {bot.user}")
    channel = bot.get_channel(CHANNEL_ID)
    if channel:
        await post_free_games(channel)
    else:
        print("⚠️ Channel not found. Check your CHANNEL_ID.")

# ----------------------------
# 🚀 Run the bot
# ----------------------------
bot.run(TOKEN)
