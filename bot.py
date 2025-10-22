import discord
import requests
from bs4 import BeautifulSoup
import os
from datetime import datetime

TOKEN = os.getenv("DISCORD_BOT_TOKEN")
CHANNEL_ID = int(os.getenv("CHANNEL_ID", "0"))

intents = discord.Intents.default()
client = discord.Client(intents=intents)


# ---------- EPIC GAMES (API-BASED) ----------
def fetch_epic_games():
    url = "https://store-site-backend-static.ak.epicgames.com/freeGamesPromotions?locale=en-US"
    res = requests.get(url)
    data = res.json()

    free_games, discount_games = [], []

    for game in data["data"]["Catalog"]["searchStore"]["elements"]:
        title = game["title"]
        url_slug = game["productSlug"] or game["catalogNs"]["mappings"][0]["pageSlug"]
        link = f"https://store.epicgames.com/en-US/p/{url_slug}"

        price_info = game.get("price", {}).get("totalPrice", {})
        discount_percentage = price_info.get("discountPercentage", 0)

        # Free game
        if price_info.get("originalPrice", 0) != 0 and price_info.get("discountPrice", 0) == 0:
            free_games.append((title, link))
        # Discount >= 50%
        elif discount_percentage >= 50:
            final_price = price_info.get("fmtPrice", {}).get("discountPrice", "")
            discount_games.append((title, link, f"{discount_percentage}% Off (Now {final_price})"))

    return free_games, discount_games


# ---------- STEAM (HTML SCRAPE) ----------
def fetch_steam_games():
    url = "https://store.steampowered.com/search/?specials=1&cc=in"
    headers = {"User-Agent": "Mozilla/5.0"}
    res = requests.get(url, headers=headers)
    soup = BeautifulSoup(res.text, "html.parser")

    free_games, discount_games = [], []

    for row in soup.select(".search_result_row"):
        title = row.select_one(".title").get_text(strip=True)
        link = row.get("href")
        discount_el = row.select_one(".search_discount span")
        price_el = row.select_one(".discount_final_price")

        if not discount_el:
            continue
        discount_text = discount_el.get_text(strip=True).replace("-", "")
        if discount_text == "100%":
            free_games.append((title, link))
        elif discount_text.endswith("%") and int(discount_text[:-1]) >= 50:
            price = price_el.get_text(strip=True) if price_el else ""
            discount_games.append((title, link, f"{discount_text} Off (Now {price})"))

    return free_games, discount_games


# ---------- UBISOFT (API-BASED) ----------
def fetch_ubisoft_games():
    url = "https://store.ubisoft.com/api/v1/products?categories=ON_SALE&locale=en_IN&limit=50"
    res = requests.get(url)
    data = res.json()

    free_games, discount_games = [], []

    for product in data.get("products", []):
        title = product.get("name")
        link = f"https://store.ubisoft.com/in/{product.get('url').lstrip('/')}"
        discount = product.get("discount", 0)
        price = product.get("price", {}).get("final", "")
        currency = product.get("price", {}).get("currency", "")

        if discount == 100:
            free_games.append((title, link))
        elif discount >= 50:
            discount_games.append((title, link, f"{discount}% Off (Now {currency} {price})"))

    return free_games, discount_games


# ---------- MESSAGE BUILDER ----------
def build_message(epic, steam, ubi):
    today = datetime.now().strftime("%Y-%m-%d")

    msg = f"🎁 **Free & Discounted Games of the Day** ({today})\nGrab these **Free** and **≥50% Off** games before they expire!\n\n"

    def section(name, free, deals):
        part = f"🔥 **{name}**\n"
        if free:
            part += "🆓 **Free Games**\n"
            for t, l in free[:5]:
                part += f"• [{t}]({l})\n"
        if deals:
            part += "\n💸 **Big Discounts (≥50%)**\n"
            for t, l, d in deals[:5]:
                part += f"• [{t}]({l}) — **{d}**\n"
        return part + "\n\n"

    msg += section("Epic Games", *epic)
    msg += section("Steam", *steam)
    msg += section("Ubisoft", *ubi)
    msg += "🕓 Auto-updated daily | Epic • Steam • Ubisoft 🎮"
    return msg


@client.event
async def on_ready():
    print(f"✅ Logged in as {client.user}")
    channel = client.get_channel(CHANNEL_ID)
    if not channel:
        print("❌ Invalid channel ID.")
        await client.close()
        return

    print("Fetching Epic Games...")
    epic = fetch_epic_games()
    print("Fetching Steam Games...")
    steam = fetch_steam_games()
    print("Fetching Ubisoft Games...")
    ubi = fetch_ubisoft_games()

    msg = build_message(epic, steam, ubi)

    embed = discord.Embed(
        title="🎮 Free & Discounted Games",
        description=msg,
        color=discord.Color.gold(),
        timestamp=datetime.now()
    )
    embed.set_footer(text="Auto-updated daily | Epic • Steam • Ubisoft 🎮")

    await channel.send(embed=embed)
    await client.close()


if __name__ == "__main__":
    if not TOKEN or CHANNEL_ID == 0:
        print("❌ Missing TOKEN or CHANNEL_ID environment variables.")
    else:
        client.run(TOKEN)
