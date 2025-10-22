import os
import discord
import aiohttp
from bs4 import BeautifulSoup
from datetime import datetime

TOKEN = os.getenv("DISCORD_BOT_TOKEN")
CHANNEL_ID = int(os.getenv("CHANNEL_ID", "0"))

intents = discord.Intents.default()
client = discord.Client(intents=intents)

# ---------- FETCH FUNCTIONS ---------- #

async def fetch_epic_games(session):
    """Fetch currently free games from Epic Games Store."""
    url = "https://store.epicgames.com/en-US/free-games"
    async with session.get(url) as response:
        html = await response.text()
        soup = BeautifulSoup(html, "html.parser")
        games = []

        # Epic dynamically loads games; we look for known free game elements
        for item in soup.select("a[href*='/p/']"):
            title_tag = item.select_one("span")
            if title_tag:
                title = title_tag.text.strip()
                link = "https://store.epicgames.com" + item["href"]
                if title and title not in [g["title"] for g in games]:
                    games.append({"title": title, "url": link})

        return games[:5]


async def fetch_steam_games(session):
    """Fetch Steam games that are free or have ≥50% discount."""
    url = "https://store.steampowered.com/search/?filter=free&specials=1"
    async with session.get(url) as response:
        html = await response.text()
        soup = BeautifulSoup(html, "html.parser")
        games = []

        for row in soup.select("a.search_result_row"):
            title_el = row.select_one(".title")
            discount_el = row.select_one(".search_discount span")
            link = row.get("href", "").split("?")[0]

            if title_el:
                title = title_el.text.strip()
                if discount_el and "%" in discount_el.text:
                    percent = int(discount_el.text.replace("%", "").replace("-", "").strip())
                    if percent >= 50:
                        games.append({"title": f"{title} ({percent}% off)", "url": link})
                else:
                    games.append({"title": f"{title} (Free)", "url": link})
        return games[:5]


async def fetch_ubisoft_games(session):
    """Fetch Ubisoft games with ≥50% discount."""
    url = "https://store.ubisoft.com/in/deals"
    async with session.get(url) as response:
        html = await response.text()
        soup = BeautifulSoup(html, "html.parser")
        games = []

        for card in soup.select("div.product-tile__title"):
            title = card.text.strip()
            link_tag = card.find_parent("a")
            link = "https://store.ubisoft.com" + link_tag["href"] if link_tag else "https://store.ubisoft.com/in/deals"
            if title:
                games.append({"title": title, "url": link})
        return games[:5]

# ---------- MAIN POST FUNCTION ---------- #

async def post_free_games():
    async with aiohttp.ClientSession() as session:
        epic = await fetch_epic_games(session)
        steam = await fetch_steam_games(session)
        ubi = await fetch_ubisoft_games(session)

        print(f"Epic Games fetched: {epic}")
        print(f"Steam Games fetched: {steam}")
        print(f"Ubisoft Games fetched: {ubi}")

        message_lines = [
            f"🎁 **Free & Discounted Games of the Day ({datetime.now().strftime('%Y-%m-%d')})**",
            "Grab these Free and ≥50% Off games before they expire!\n"
        ]

        if epic:
            message_lines.append("🔥 **Epic Games**")
            for g in epic:
                message_lines.append(f"🕹️ [{g['title']}]({g['url']})")
            message_lines.append("")

        if steam:
            message_lines.append("🔥 **Steam**")
            for g in steam:
                message_lines.append(f"🕹️ [{g['title']}]({g['url']})")
            message_lines.append("")

        if ubi:
            message_lines.append("🔥 **Ubisoft**")
            for g in ubi:
                message_lines.append(f"🕹️ [{g['title']}]({g['url']})")
            message_lines.append("")

        message_lines.append("🕓 Auto-updated daily | Epic • Steam • Ubisoft 🎮")

        if not (epic or steam or ubi):
            message_lines.insert(1, "_No currently free or ≥50% discounted games found._")

        channel = client.get_channel(CHANNEL_ID)
        if channel:
            await channel.send("\n".join(message_lines))
        else:
            print("❌ Channel not found! Check CHANNEL_ID.")


@client.event
async def on_ready():
    print(f"✅ Logged in as {client.user}")
    await post_free_games()
    await client.close()


if __name__ == "__main__":
    client.run(TOKEN)
