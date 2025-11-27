import os
import discord
from discord.ext import commands
import json
from dotenv import load_dotenv

load_dotenv()

DISCORD_TOKEN = os.environ["DISCORD_TOKEN"]
VERIFY_BASE_URL = os.environ["VERIFY_BASE_URL"]
LOG_CHANNEL_ID = int(os.environ.get("LOG_CHANNEL_ID", "0"))

INTENTS = discord.Intents.default()
INTENTS.message_content = True
bot = commands.Bot(command_prefix="!", intents=INTENTS)

DATA_FILE = "data.json"

# Admin yetkisi olan Discord ID'ler
ALLOWED_ADMIN_IDS = {
    294866990110343168,
    324895490237923340,
}


def is_super_admin():
    async def predicate(ctx):
        if ctx.author.id in ALLOWED_ADMIN_IDS:
            return True
        await ctx.send("❌ Bu komutu kullanma yetkin yok.")
        return False
    return commands.check(predicate)


# VERİ YÖNETİMİ ----------------------------------------------------------

def load_data():
    if not os.path.exists(DATA_FILE):
        return {"users": {}, "codes": [], "banned": {}}
    try:
        with open(DATA_FILE, "r", encoding="utf-8") as f:
            return json.load(f)
    except:
        return {"users": {}, "codes": [], "banned": {}}


def save_data(data):
    with open(DATA_FILE, "w", encoding="utf-8") as f:
        json.dump(data, f, ensure_ascii=False, indent=2)


# LOG SİSTEMİ ------------------------------------------------------------

async def log_action(message: str):
    if LOG_CHANNEL_ID == 0:
        return
    channel = bot.get_channel(LOG_CHANNEL_ID)
    if channel:
        try:
            await channel.send(message)
        except:
            pass


# BOT HAZIR ---------------------------------------------------------------

@bot.event
async def on_ready():
    print(f"Bot olarak giriş yapıldı: {bot.user}")


# ADMIN KOMUTLARI ---------------------------------------------------------

@bot.command(name="kod-ekle")
@is_super_admin()
async def kod_ekle(ctx, *, kodlar: str):
    data = load_data()
    yeni = kodlar.split()
    data["codes"].extend(yeni)
    save_data(data)
    await ctx.send(f"✅ {len(yeni)} kod eklendi.")
    await log_action(f"🟢 {ctx.author.mention} {len(yeni)} kod ekledi.")


@bot.command(name="kod-say")
@is_super_admin()
async def kod_say(ctx):
    data = load_data()
    await ctx.send(f"📦 Kalan kod: {len(data['codes'])}")


@bot.command(name="kod-liste")
@is_super_admin()
async def kod_liste(ctx):
    data = load_data()
    codes = data["codes"]
    if not codes:
        await ctx.send("📭 Kod yok.")
        return

    # Limit aşmaması için parça parça gönder
    chunk = ""
    for code in codes:
        line = f"- {code}\n"
        if len(chunk) + len(line) > 1900:
            await ctx.send(chunk)
            chunk = ""
        chunk += line

    if chunk:
        await ctx.send(chunk)


@bot.command(name="kod-sil")
@is_super_admin()
async def kod_sil(ctx, *, kod: str):
    data = load_data()
    if kod not in data["codes"]:
        await ctx.send("❌ Kod bulunamadı.")
        return

    data["codes"] = [c for c in data["codes"] if c != kod]
    save_data(data)
    await ctx.send(f"🗑️ `{kod}` silindi.")


@bot.command(name="kod-temizle")
@is_super_admin()
async def kod_temizle(ctx):
    data = load_data()
    adet = len(data["codes"])
    data["codes"] = []
    save_data(data)
    await ctx.send(f"🧹 Tüm kodlar silindi ({adet}).")


# ------------------------- 💀 BAN SİSTEMİ ------------------------------------

@bot.command(name="ban")
@is_super_admin()
async def ban_user(ctx, member: discord.Member = None):
    if member is None:
        await ctx.send("❌ Kullanıcı etiketle: `!ban @kullanıcı`")
        return

    guild = ctx.guild
    data = load_data()

    # 1) Kullanıcının eski rollerini kaydet
    old_roles = [role.id for role in member.roles if role != guild.default_role]
    data["banned"][str(member.id)] = old_roles
    save_data(data)

    # 2) Tüm rollerini kaldır
    roles_to_remove = [r for r in member.roles if r != guild.default_role]
    try:
        await member.remove_roles(*roles_to_remove, reason="Ban sistemi: roller alındı")
    except Exception as e:
        await ctx.send(f"❌ Roller alınamadı: {e}")
        return

    # 3) Banned rolü oluştur veya al
    ban_role = discord.utils.get(guild.roles, name="Banned")
    if ban_role is None:
        ban_role = await guild.create_role(
            name="Banned",
            color=discord.Color.dark_gray(),
            reason="Ban rolü oluşturuldu"
        )

    # 4) Ban rolünü tüm sunucuya uygula
    for channel in guild.channels:
        try:
            await channel.set_permissions(
                ban_role,
                view_channel=False,
                send_messages=False,
                read_message_history=False
            )
        except:
            pass

    # 5) Kullanıcının özel izinlerini sıfırla
    for channel in guild.channels:
        try:
            await channel.set_permissions(member, overwrite=None)
        except:
            pass

    # 6) Kullanıcıya banned rolü ver
    await member.add_roles(ban_role)

    await ctx.send(f"🚫 {member.mention} tamamen banlandı.\n"
                   f"- Tüm roller alındı\n"
                   f"- Tüm kanallar gizlendi\n"
                   f"- Mesaj yazamaz\n"
                   f"- Özel izinleri silindi\n")

    await log_action(f"🚫 {ctx.author.mention}, {member.mention} kullanıcısını banladı.")


# ------------------------- 🔓 UNBAN SİSTEMİ ------------------------------------

@bot.command(name="unban")
@is_super_admin()
async def unban_user(ctx, member: discord.Member = None):
    if member is None:
        await ctx.send("❌ Kullanıcı etiketle: `!unban @kullanıcı`")
        return

    guild = ctx.guild
    data = load_data()
    ban_role = discord.utils.get(guild.roles, name="Banned")

    # 1) Banned rolünü kaldır
    if ban_role in member.roles:
        await member.remove_roles(ban_role)

    # 2) Özel izinlerini sıfırla
    for channel in guild.channels:
        try:
            await channel.set_permissions(member, overwrite=None)
        except:
            pass

    # 3) Eski rollerini geri yükle
    old_roles_ids = data["banned"].get(str(member.id), [])
    roles_to_give = []
    for role_id in old_roles_ids:
        role = guild.get_role(role_id)
        if role:
            roles_to_give.append(role)

    if roles_to_give:
        await member.add_roles(*roles_to_give)

    # 4) Kaydı sil
    if str(member.id) in data["banned"]:
        del data["banned"][str(member.id)]
        save_data(data)

    await ctx.send(f"✅ {member.mention} banı kaldırıldı ve eski roller geri verildi.")
    await log_action(f"✅ {ctx.author.mention}, {member.mention} kullanıcısının banını kaldırdı.")


# ------------------------- NORMAL KOMUTLAR ------------------------------------

@bot.command(name="kod-al")
async def kod_al(ctx):
    user_id = ctx.author.id

    if not is_verified(user_id):
        verify_link = f"{VERIFY_BASE_URL}?discord_id={user_id}"
        try:
            await ctx.author.send(
                "👋 Kod almak için önce abone olup https://www.youtube.com/@t3az doğrulama yapmalısın.\n"
                f"Doğrulama linkin:\n{verify_link}"
            )
            await ctx.reply("DM'den doğrulama linki gönderdim 📩")
        except:
            await ctx.reply("❌ DM'lerin kapalı, aç ve tekrar yaz.")
        return

    code = get_or_assign_code(user_id)
    if code is None:
        await ctx.reply("❌ Kod kalmamış.")
        return

    try:
        await ctx.author.send(f"🎁 Kodun: `{code}`")
    except:
        await ctx.reply(f"🎁 Kodun: `{code}` (DM kapalı)")

    await ctx.reply("Kod gönderildi 🎉")
    await log_action(f"🎁 {ctx.author.mention} kod aldı: `{code}`")


@bot.command(name="kod-durum")
async def kod_durum(ctx):
    user_id = ctx.author.id
    data = load_data()
    user = data["users"].get(str(user_id))

    verified = "✅ Doğrulanmış" if is_verified(user_id) else "❌ Doğrulanmamış"

    msg = f"👤 {ctx.author.mention}\n• Doğrulama: {verified}\n"

    if user and "code" in user:
        msg += f"• Kodun: `{user['code']}`"
    else:
        msg += "• Kodun yok."

    await ctx.send(msg)


@bot.command(name="yardim")
async def yardim(ctx):
    text = (
        "📚 **Komutlar:**\n"
        "\n"
        "__Kullanıcı Komutları:__\n"
        "`!kod-al` → Kod alırsın\n"
        "`!kod-durum` → Kod durumunu gösterir\n"
        "\n"
        "__Admin Komutları:__\n"
        "`!kod-ekle <kodlar>`\n"
        "`!kod-say`\n"
        "`!kod-liste`\n"
        "`!kod-sil <kod>`\n"
        "`!kod-temizle`\n"
        "`!ban @kullanıcı` → Tüm roller alınır, gizli ban\n"
        "`!unban @kullanıcı` → Roller geri verilir\n"
    )
    await ctx.send(text)


bot.run(DISCORD_TOKEN)
