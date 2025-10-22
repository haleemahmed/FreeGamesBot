import discord
import requests
from bs4 import BeautifulSoup
import os
from datetime import datetime

TOKEN = os.getenv("DISCORD_BOT_TOKEN")
CHANNEL_ID = int(os.getenv("CHANNEL_ID", "0"))

intents = discord.Intents.default()
client = discord.Client(intents=intents)


# ---------- EPIC GAMES ----------
def fetch_epic_games():
    url = "https://store.epicgames.com/en-US/free-games"
    headers = {"User-Agent": "Mozilla/5.0"}
    res = requests.get(url, headers=headers)
    soup = BeautifulSoup(res.text, "html.parser")

    free_games, discount_games = [], []

    for card in soup.select("a.css-1jx3eyg"):
        title = card.select_one(".css-2ucwu")
        if not title:
            continue
        title = title.get_text(strip=True)
        link = f"https://store.epicgames.com{card['href']}"

        price_el = card.select_one(".css-rgqwpc, .css-1x9zltl")
        price_text = price_el.get_text(strip=True) if price_el else ""

        if "Free" in price_text:
            free_games.append((title, link))
        elif "%" in price_text:
            discount = price_text.replace("-", "")
            if discount.endswith("%") and int(discount[:-1]) >= 50:
                discount_games.append((title, link, f"{discount} Off"))

    return free_games, discount_games


# ---------- STEAM ----------
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


# ---------- UBISOFT ----------
def fetch_ubisoft_games():
    url = "https://store.ubisoft.com/in/deals"
    headers = {"User-Agent": "Mozilla/5.0"}
    res = requests.get(url, headers=headers)
    soup = BeautifulSoup(res.text, "html.parser")

    free_games, discount_games = [], []

    for card in soup.select(".product-card"):
        title_el = card.select_one(".product-card-title")
        discount_el = card.select_one(".discount-percentage")
        price_el = card.select_one(".price-item")
        link_el = card.find("a", href=True)

        if not title_el or not discount_el or not link_el:
            continue

        title = title_el.get_text(strip=True)
        link = f"https://store.ubisoft.com{link_el['href']}"
        discount_text = discount_el.get_text(strip=True).replace("-", "")

        if discount_text == "100%":
            free_games.append((title, link))
        elif discount_text.endswith("%") and int(discount_text[:-1]) >= 50:
            price = price_el.get_text(strip=True) if price_el else ""
            discount_games.append((title, link, f"{discount_text} Off (Now {price})"))

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
