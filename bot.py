import os
import discord
from discord.ext import commands
import json
from dotenv import load_dotenv

load_dotenv()  # .env dosyasını yükle

DISCORD_TOKEN = os.environ["DISCORD_TOKEN"]
VERIFY_BASE_URL = os.environ["VERIFY_BASE_URL"]

INTENTS = discord.Intents.default()
INTENTS.message_content = True
bot = commands.Bot(command_prefix="!", intents=INTENTS)

DATA_FILE = "data.json"


def load_data():
    """data.json dosyasını her çağrıldığında diskteki SON halinden oku."""
    if not os.path.exists(DATA_FILE):
        return {"users": {}, "codes": []}
    with open(DATA_FILE, "r", encoding="utf-8") as f:
        try:
            return json.load(f)
        except json.JSONDecodeError:
            # dosya bozulursa sıfırla
            return {"users": {}, "codes": []}


def save_data(data):
    with open(DATA_FILE, "w", encoding="utf-8") as f:
        json.dump(data, f, ensure_ascii=False, indent=2)


def is_verified(discord_id: int) -> bool:
    """Kullanıcı verified mı her seferinde dosyadan kontrol et."""
    data = load_data()
    user = data["users"].get(str(discord_id))
    return bool(user and user.get("verified"))


def get_or_assign_code(discord_id: int) -> str | None:
    """Kullanıcıya kod ver (daha önce aldıysa aynı kodu ver)."""
    data = load_data()
    uid = str(discord_id)

    if uid not in data["users"]:
        data["users"][uid] = {}

    # Daha önce kod aldıysa aynı kodu ver
    if "code" in data["users"][uid]:
        return data["users"][uid]["code"]

    # Yeni kod ver
    if not data["codes"]:
        return None  # Kod kalmadı

    code = data["codes"].pop(0)
    data["users"][uid]["code"] = code
    save_data(data)
    return code


@bot.event
async def on_ready():
    print(f"Bot olarak giriş yapıldı: {bot.user}")


@bot.command(name="kod-ekle")
@commands.has_permissions(administrator=True)
async def kod_ekle(ctx, *, kodlar: str):
    data = load_data()
    yeni = kodlar.split()
    data["codes"].extend(yeni)
    save_data(data)
    await ctx.send(f"✅ {len(yeni)} kod eklendi. Toplam kalan kod: {len(data['codes'])}")


@bot.command(name="kod-say")
@commands.has_permissions(administrator=True)
async def kod_say(ctx):
    data = load_data()
    await ctx.send(f"📦 Kalan kod sayısı: {len(data['codes'])}")


@bot.command(name="kod-al")
async def kod_al(ctx):
    user_id = ctx.author.id

    # Her çağrıda dosyanın son haline göre kontrol ediyor
    if not is_verified(user_id):
        verify_link = f"{VERIFY_BASE_URL}?discord_id={user_id}"
        try:
            await ctx.author.send(
                "👋 Kod almak için önce doğrulama yapmalısın.\n"
                f"Doğrulama linkin:\n{verify_link}\n\n"
                "Doğruladıktan sonra tekrar `!kod-al` yaz."
            )
            await ctx.reply("DM'den doğrulama linki gönderdim 📩")
        except:
            await ctx.reply("❌ DM'lerin kapalı. Aç ve tekrar `!kod-al` yaz.")
        return

    code = get_or_assign_code(user_id)
    if code is None:
        await ctx.reply("❌ Kod kalmamış. Admin ekleyene kadar bekle.")
        return

    try:
        await ctx.author.send(f"🎁 Kodun: `{code}`")
        await ctx.reply("Kodunu DM'den gönderdim! 🎉")
    except:
        await ctx.reply(f"🎁 Kodun: `{code}` (DM kapalı olduğu için buraya yazıyorum)")


bot.run(DISCORD_TOKEN)
