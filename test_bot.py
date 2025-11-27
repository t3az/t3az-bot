import discord
from discord.ext import commands

DISCORD_TOKEN = """  # Aynı token

intents = discord.Intents.default()
intents.message_content = True

bot = commands.Bot(command_prefix="!", intents=intents)

@bot.event
async def on_ready():
    print(f"Bot olarak giriş yapıldı: {bot.user}")

try:
    bot.run(DISCORD_TOKEN)
except Exception as e:
    print("HATA OLDU:", e)
