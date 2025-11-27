import os
import discord
from discord.ext import commands
import json
from dotenv import load_dotenv

load_dotenv()  # .env dosyasını yükle

DISCORD_TOKEN = os.environ["DISCORD_TOKEN"]
VERIFY_BASE_URL = os.environ["VERIFY_BASE_URL"]
LOG_CHANNEL_ID = int(os.environ.get("LOG_CHANNEL_ID", "0"))

INTENTS = discord.Intents.default()
INTENTS.message_content = True
bot = commands.Bot(command_prefix="!", intents=INTENTS)

DATA_FILE = "data.json"

# Sadece bu kullanıcılar "admin" komutlarını kullanabilsin
ALLOWED_ADMIN_IDS = {
    294866990110343168,
    324895490237923340,
}


def is_super_admin():
    """Belirli ID'lere özel check."""
    async def predicate(ctx):
        if ctx.author.id in ALLOWED_ADMIN_IDS:
            return True
        await ctx.send("❌ Bu komutu kullanma yetkin yok.")
        return False

    return commands.check(predicate)


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


async def log_action(message: str):
    """İşlemleri log kanalına yazar."""
    if LOG_CHANNEL_ID == 0:
        return
    channel = bot.get_channel(LOG_CHANNEL_ID)
    if channel is None:
        return
    try:
        await channel.send(message)
    except:
        pass


@bot.event
async def on_ready():
    print(f"Bot olarak giriş yapıldı: {bot.user}")


# --- ADMIN KOMUTLARI (Sadece ALLOWED_ADMIN_IDS kullanabilir) ---

@bot.command(name="kod-ekle")
@is_super_admin()
async def kod_ekle(ctx, *, kodlar: str):
    """
    Örnek:
    !kod-ekle KOD1 KOD2 KOD3
    """
    data = load_data()
    yeni = kodlar.split()
    data["codes"].extend(yeni)
    save_data(data)
    await ctx.send(f"✅ {len(yeni)} kod eklendi. Toplam kalan kod: {len(data['codes'])}")
    await log_action(f"🟢 {ctx.author.mention} {len(yeni)} adet kod ekledi. Toplam: {len(data['codes'])}")


@bot.command(name="kod-say")
@is_super_admin()
async def kod_say(ctx):
    data = load_data()
    await ctx.send(f"📦 Kalan kod sayısı: {len(data['codes'])}")
    await log_action(f"ℹ️ {ctx.author.mention} kalan kod sayısını sorguladı: {len(data['codes'])}")


@bot.command(name="kod-liste")
@is_super_admin()
async def kod_liste(ctx):
    """
    Tüm mevcut kodları listeler.
    """
    data = load_data()
    codes = data["codes"]

    if not codes:
        await ctx.send("📭 Kayıtlı kod yok.")
        return

    # Mesaj limiti için parçalı gönder (2000 karakter sınırı)
    chunk = ""
    header = "📃 Mevcut kodlar:\n"
    for code in codes:
        line = f"- {code}\n"
        if len(chunk) + len(line) > 1900:  # güvenli sınır
            await ctx.send(header + chunk)
            chunk = ""
        chunk += line

    if chunk:
        await ctx.send(header + chunk)

    await log_action(f"📃 {ctx.author.mention} mevcut kod listesini görüntüledi. Toplam: {len(codes)}")


@bot.command(name="kod-sil")
@is_super_admin()
async def kod_sil(ctx, *, kod: str):
    """
    Belirtilen tek bir kodu siler.
    Örnek:
    !kod-sil KOD123
    """
    data = load_data()
    if kod not in data["codes"]:
        await ctx.send("❌ Bu kod listede bulunamadı.")
        return

    # Sadece bu kodun geçtiği tüm yerleri sil (aynı kod birden fazla olabilir)
    eski_sayi = len(data["codes"])
    data["codes"] = [c for c in data["codes"] if c != kod]
    yeni_sayi = len(data["codes"])
    silinen = eski_sayi - yeni_sayi

    save_data(data)
    await ctx.send(f"🗑️ `{kod}` kodu listeden silindi (silinen adet: {silinen}).")
    await log_action(f"🗑️ {ctx.author.mention} `{kod}` kodunu sildi. Silinen adet: {silinen}.")


@bot.command(name="kod-temizle")
@is_super_admin()
async def kod_temizle(ctx):
    """
    Tüm kodları siler.
    """
    data = load_data()
    adet = len(data["codes"])
    data["codes"] = []
    save_data(data)
    await ctx.send(f"🧹 Tüm kodlar silindi. (Silinen kod sayısı: {adet})")
    await log_action(f"🧹 {ctx.author.mention} tüm kodları temizledi. Silinen: {adet}.")


@bot.command(name="ban")
@is_super_admin()
async def ban_user(ctx, member: discord.Member = None):
    """
    Kullanıcıyı sunucudan atmadan tüm kanalları göremeyecek hale getirir.
    Kullanım: !ban @kullanıcı
    """
    if member is None:
        await ctx.send("❌ Lütfen bir kullanıcı etiketle: `!ban @kullanıcı`")
        return

    guild = ctx.guild
    ban_role_name = "Banned"

    # Rol var mı kontrol et
    ban_role = discord.utils.get(guild.roles, name=ban_role_name)

    # Rol yoksa oluştur
    if ban_role is None:
        ban_role = await guild.create_role(
            name=ban_role_name,
            color=discord.Color.dark_gray(),
            reason="Ban rolü otomatik oluşturuldu"
        )

        # Tüm kanallar için görüntüleme iznini kapat
        for channel in guild.channels:
            await channel.set_permissions(ban_role, view_channel=False)

    # Kullanıcıya rol ver
    await member.add_roles(ban_role)
    await ctx.send(f"🚫 {member.mention} artık tüm kanalları göremeyecek şekilde banlandı.")
    await log_action(f"🚫 {ctx.author.mention}, {member.mention} kullanıcısını görünmez banladı.")


@bot.command(name="unban")
@is_super_admin()
async def unban_user(ctx, member: discord.Member = None):
    """
    Kullanıcıdan Banned rolünü kaldırır.
    Kullanım: !unban @kullanıcı
    """
    if member is None:
        await ctx.send("❌ Lütfen bir kullanıcı etiketle: `!unban @kullanıcı`")
        return

    guild = ctx.guild
    ban_role_name = "Banned"
    ban_role = discord.utils.get(guild.roles, name=ban_role_name)

    if ban_role is None:
        await ctx.send("❌ 'Banned' isimli bir rol bulunamadı.")
        return

    if ban_role not in member.roles:
        await ctx.send("ℹ️ Bu kullanıcıda zaten 'Banned' rolü bulunmuyor.")
        return

    await member.remove_roles(ban_role)
    await ctx.send(f"✅ {member.mention} için ban kaldırıldı, kanalları tekrar görebilecek.")
    await log_action(f"✅ {ctx.author.mention}, {member.mention} kullanıcısının banını kaldırdı.")


# --- NORMAL KULLANICI KOMUTLARI ---

@bot.command(name="kod-al")
async def kod_al(ctx):
    user_id = ctx.author.id

    # Her çağrıda dosyanın son haline göre kontrol ediyor
    if not is_verified(user_id):
        verify_link = f"{VERIFY_BASE_URL}?discord_id={user_id}"
        try:
            await ctx.author.send(
                "👋 Kod almak için önce abone olup https://www.youtube.com/@t3az doğrulama yapmalısın.\n"
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

    await log_action(f"🎁 {ctx.author.mention} bir kod aldı: `{code}`")


@bot.command(name="kod-durum")
async def kod_durum(ctx):
    """Kullanıcının doğrulama ve kod durumunu gösterir."""
    user_id = ctx.author.id
    data = load_data()
    uid = str(user_id)
    user = data["users"].get(uid)

    verified_emoji = "✅" if is_verified(user_id) else "❌"
    msg = f"👤 {ctx.author.mention}\n"
    msg += f"• Doğrulama durumu: {verified_emoji}\n"

    if user and "code" in user:
        msg += f"• Kod durumun: ✅ Kodun: `{user['code']}`\n"
    else:
        msg += "• Kod durumun: ❌ Henüz kod almamışsın. `!kod-al` yazabilirsin.\n"

    await ctx.send(msg)


@bot.command(name="yardim")
async def yardim(ctx):
    """Komut listesini gösterir."""
    text = (
        "📚 **Komutlar:**\n"
        "\n"
        "__Kullanıcı Komutları:__\n"
        "`!kod-al` → Doğrulama yaptıysan sana bir kod gönderir.\n"
        "`!kod-durum` → Doğrulama ve kod durumunu gösterir.\n"
        "`!yardim` → Bu mesajı gösterir.\n"
        "\n"
        "__Admin Komutları (sadece yetkili ID'ler):__\n"
        "`!kod-ekle <kod1 kod2 ...>` → Yeni kodlar ekler.\n"
        "`!kod-say` → Kalan kod sayısını gösterir.\n"
        "`!kod-liste` → Kalan tüm kodları listeler.\n"
        "`!kod-sil <kod>` → Belirtilen kodu listeden siler.\n"
        "`!kod-temizle` → Tüm kodları sıfırlar.\n"
        "`!ban @kullanıcı` → Kullanıcıyı tüm kanalları göremeyecek hale getirir.\n"
        "`!unban @kullanıcı` → Kullanıcıdan 'Banned' rolünü kaldırır.\n"
    )
    await ctx.send(text)


bot.run(DISCORD_TOKEN)
