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
    url = "https://store.epicgames.com/en-US/free-games"
    async with session.get(url) as response:
        soup = BeautifulSoup(await response.text(), "html.parser")
        games = []

        for item in soup.select("section div div div a[href*='/p/']"):
            title = item.text.strip()
            if title and title not in games:
                games.append(title)

        return list(set(games))[:5]  # limit top 5


async def fetch_steam_games(session):
    url = "https://store.steampowered.com/search/?filter=free&specials=1"
    async with session.get(url) as response:
        soup = BeautifulSoup(await response.text(), "html.parser")
        games = []

        for row in soup.select("a.search_result_row"):
            title = row.select_one(".title")
            discount = row.select_one(".search_discount span")
            if title:
                game_name = title.text.strip()
                if discount and "%" in discount.text:
                    percent = int(discount.text.replace("%", "").replace("-", "").strip())
                    if percent >= 50:
                        games.append(f"{game_name} ({percent}% off)")
                else:
                    games.append(f"{game_name} (Free)")
        return games[:5]


async def fetch_ubisoft_games(session):
    url = "https://store.ubisoft.com/in/deals"
    async with session.get(url) as response:
        soup = BeautifulSoup(await response.text(), "html.parser")
        games = []
        for product in soup.select("div.product-tile__title"):
            title = product.text.strip()
            if title:
                games.append(title)
        return games[:5]

# ---------- MAIN POST FUNCTION ---------- #

async def post_free_games():
    async with aiohttp.ClientSession() as session:
        epic = await fetch_epic_games(session)
        steam = await fetch_steam_games(session)
        ubi = await fetch_ubisoft_games(session)

        # Debug info
        print(f"Epic Games: {epic}")
        print(f"Steam Games: {steam}")
        print(f"Ubisoft Games: {ubi}")

        message_lines = [f"🎁 **Free & Discounted Games of the Day ({datetime.now().strftime('%Y-%m-%d')})**",
                         "Grab these Free and ≥50% Off games before they expire!\n"]

        if epic:
            message_lines.append("🔥 **Epic Games**")
            for g in epic:
                message_lines.append(f"🕹️ {g}")
            message_lines.append("")

        if steam:
            message_lines.append("🔥 **Steam**")
            for g in steam:
                message_lines.append(f"🕹️ {g}")
            message_lines.append("")

        if ubi:
            message_lines.append("🔥 **Ubisoft**")
            for g in ubi:
                message_lines.append(f"🕹️ {g}")
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
