from pyrogram import Client, filters
from pyrogram.types import ChatPermissions, Message, ChatMemberUpdated, InlineKeyboardMarkup, InlineKeyboardButton, CallbackQuery
from datetime import datetime
import asyncio, time, json, os, re, logging
from dotenv import load_dotenv

# Log dosyası
logging.basicConfig(
    filename="bot_log.txt",
    level=logging.INFO,
    format="%(asctime)s - %(levelname)s - %(message)s"
)

# Yardımcı fonksiyonlar
def parse_sure(s: str) -> int:
    matches = re.findall(r"(\d+)\s*(saniye|sn|dakika|dk|saat|sa)", s.lower())
    total = 0
    for v, u in matches:
        v = int(v)
        if u in ["saniye", "sn"]: total += v
        elif u in ["dakika", "dk"]: total += v * 60
        elif u in ["saat", "sa"]: total += v * 3600
    return total

def convert_keys_to_str(d): return {str(k): v for k, v in d.items()}
def load_json(f, d): return json.load(open(f, "r", encoding="utf-8")) if os.path.exists(f) else d
def save_json(f, d): json.dump(d, open(f, "w", encoding="utf-8"), indent=4)

# .env ayarları
load_dotenv()
api_id = int(os.getenv("API_ID"))
api_hash = os.getenv("API_HASH")
bot_token = os.getenv("BOT_TOKEN")
admin_id = int(os.getenv("OWNER_ID"))

# Dosyalar
LIMITS_FILE = "limits.json"
USERDATA_FILE = "users.json"
COUNTS_FILE = "counts.json"
IZIN_FILE = "izinler.json"
ADMINS_FILE = "admins.json"

# Veriler
limits = {int(k): v for k, v in load_json(LIMITS_FILE, {}).items()}
user_data = load_json(USERDATA_FILE, {})
user_msg_count = {eval(k): v for k, v in load_json(COUNTS_FILE, {}).items()}
izin_sureleri = {eval(k): v for k, v in load_json(IZIN_FILE, {}).items()}
yetkili_adminler = set(load_json(ADMINS_FILE, [admin_id]))
max_grant = 2

# Bot
app = Client("bot", api_id=api_id, api_hash=api_hash, bot_token=bot_token)

def is_authorized(uid): return uid in yetkili_adminler

@app.on_message(filters.command("menu"))
async def menu(_, msg: Message):
    kb = InlineKeyboardMarkup([
        [InlineKeyboardButton("📋 Yardım Menüsü", callback_data="help")],
        [InlineKeyboardButton("📊 Seviye Listesi", callback_data="limits")],
        [InlineKeyboardButton("⚙️ Ayarlar", callback_data="settings")]
    ])
    await msg.reply("👋 Merhaba! Ne yapmak istersin?", reply_markup=kb)

@app.on_callback_query()
async def cb_cevapla(_, cb: CallbackQuery):
    d = cb.data
    geri = InlineKeyboardMarkup([[InlineKeyboardButton("◀️ Geri", callback_data="geri")]])
    if d == "help":
        await cb.message.edit_text(
            "**🆘 Yardım Menüsü:**\n\n"
            "🔹 `/seviyeayar` - Seviye mesaj/süre ayarı\n"
            "🔹 `/hakayarla` - Günlük medya hakkı ayarla\n"
            "🔹 `/seviyelistesi` - Tüm seviyeleri göster\n"
            "🔹 `/verisil` - Tüm verileri sıfırla\n"
            "🔹 `/durum` - Seviyeni göster\n"
            "🔹 `/yetkiver` - Komut yetkisi ver\n"
            "🔹 `/yetkial` - Komut yetkisini al\n"
            "🔹 `/hakkinda` - Bot bilgisi\n", reply_markup=geri
        )
    elif d == "limits":
        if not limits:
            await cb.message.edit_text("⚠️ Ayarlanmış seviye yok.", reply_markup=geri)
            return
        metin = "📊 **Seviye Listesi:**\n\n"
        for s in sorted(limits.keys()):
            lim = limits[s]
            metin += f"🔸 Seviye {s}: {lim['msg']} mesaj → {lim['süre']} sn izin\n"
        await cb.message.edit_text(metin, reply_markup=geri)
    elif d == "settings":
        await cb.message.edit_text("⚙️ Ayarlar bölümü yapım aşamasında.", reply_markup=geri)
    elif d == "geri":
        await cb.message.delete()
        await menu(_, cb.message)

@app.on_message(filters.command("seviyeayar"))
async def seviye_ayar(_, msg):
    if not is_authorized(msg.from_user.id): return
    try:
        _, s, m, t = msg.text.split(maxsplit=3)
        limits[int(s)] = {"msg": int(m), "süre": parse_sure(t)}
        save_json(LIMITS_FILE, limits)
        await msg.reply(f"✅ Seviye {s} ayarlandı.")
    except:
        await msg.reply("⚠️ /seviyeayar [seviye] [mesaj] [süre]")

@app.on_message(filters.command("hakayarla"))
async def hak_ayar(_, msg):
    if not is_authorized(msg.from_user.id): return
    try:
        global max_grant
        max_grant = int(msg.text.split()[1])
        await msg.reply(f"✅ Günlük hak: {max_grant}")
    except:
        await msg.reply("⚠️ /hakayarla [adet]")

@app.on_message(filters.command("seviyelistesi"))
async def seviyeler(_, msg):
    if not is_authorized(msg.from_user.id): return
    if not limits:
        await msg.reply("⚠️ Hiç seviye tanımlı değil.")
        return
    metin = "📋 **Seviye Listesi:**\n"
    for s in sorted(limits.keys()):
        l = limits[s]
        metin += f"🔹 Seviye {s}: {l['msg']} mesaj → {l['süre']} sn\n"
    await msg.reply(metin)

@app.on_message(filters.command("verisil"))
async def sifirla(_, msg):
    if not is_authorized(msg.from_user.id): return
    user_data.clear(); user_msg_count.clear(); izin_sureleri.clear()
    save_json(USERDATA_FILE, convert_keys_to_str(user_data))
    save_json(COUNTS_FILE, convert_keys_to_str(user_msg_count))
    save_json(IZIN_FILE, convert_keys_to_str(izin_sureleri))
    await msg.reply("✅ Tüm veriler silindi.")

@app.on_message(filters.command("durum"))
async def durum(_, msg):
    uid, cid = msg.from_user.id, msg.chat.id
    key = f"({cid}, {uid})"
    if key not in user_data:
        await msg.reply("ℹ️ Kayıtlı verin yok.")
        return
    veri = user_data[key]
    seviye = veri["seviye"]
    kalan_hak = max_grant - veri["grant_count"]
    gereken = limits.get(seviye, {}).get("msg", 0)
    atilan = user_msg_count.get(key, 0)
    kalan = max(0, gereken - atilan)
    await msg.reply(
        f"📊 **Durumun:**\n"
        f"🔹 Seviye: {seviye}\n"
        f"📝 Mesaj: {atilan}/{gereken}\n"
        f"⏳ Kalan: {kalan}\n"
        f"🎯 Günlük hak: {veri['grant_count']}/{max_grant}"
    )

@app.on_message(filters.command("yetkiver") & filters.user(admin_id))
async def ver(_, msg):
    if not msg.reply_to_message and len(msg.command) < 2:
        await msg.reply("⚠️ Kullanım: /yetkiver @kullanici")
        return
    uid = msg.reply_to_message.from_user.id if msg.reply_to_message else (await app.get_users(msg.command[1].lstrip("@"))).id
    yetkili_adminler.add(uid)
    save_json(ADMINS_FILE, list(yetkili_adminler))
    await msg.reply(f"✅ `{uid}` yetkilendirildi.")

@app.on_message(filters.command("yetkial") & filters.user(admin_id))
async def al(_, msg):
    if not msg.reply_to_message and len(msg.command) < 2:
        await msg.reply("⚠️ Kullanım: /yetkial @kullanici")
        return
    uid = msg.reply_to_message.from_user.id if msg.reply_to_message else (await app.get_users(msg.command[1].lstrip("@"))).id
    if uid == admin_id:
        await msg.reply("❌ Sahip yetkisi kaldırılamaz.")
        return
    yetkili_adminler.discard(uid)
    save_json(ADMINS_FILE, list(yetkili_adminler))
    await msg.reply(f"🚫 `{uid}` yetkisi alındı.")

@app.on_message(filters.command("hakkinda"))
async def bilgi(_, msg):
    await msg.reply(
        "🤖 **Bu bot, grup aktifliğini takip eder.**\n"
        "📝 Mesaj atan seviye atlar ve sınırlı süreli medya izni kazanır.\n"
        "**Geliştirici:** @Atabey27"
    )

@app.on_message(filters.group & ~filters.service)
async def takip_et(_, msg):
    uid, cid = msg.from_user.id, msg.chat.id
    key = f"({cid}, {uid})"
    now = time.time()
    today = str(datetime.now().date())

    if key not in user_data or user_data[key]["date"] != today:
        user_data[key] = {"seviye": 0, "grant_count": 0, "date": today}
        user_msg_count[key] = 0

    if now < izin_sureleri.get(key, 0): return
    user_msg_count[key] += 1

    for seviye in sorted(limits.keys()):
        lim = limits[seviye]
        if user_msg_count[key] >= lim["msg"] and seviye > user_data[key]["seviye"] and user_data[key]["grant_count"] < max_grant:
            user_data[key]["seviye"] = seviye
            user_data[key]["grant_count"] += 1
            user_msg_count[key] = 0
            izin_sureleri[key] = now + lim["süre"]
            await msg.reply(f"🎉 Seviye {seviye} tamamlandı! {lim['süre']} sn boyunca çıkartma + GIF izni verildi.")
            try:
                izin_ver = ChatPermissions(
                    can_send_messages=True,
                    can_send_stickers=True,
                    can_send_animations=True
                )
                await app.restrict_chat_member(cid, uid, izin_ver)
                await asyncio.sleep(lim["süre"])
                izin_kisitla = ChatPermissions(
                    can_send_messages=True,
                    can_send_stickers=False,
                    can_send_animations=False
                )
                await app.restrict_chat_member(cid, uid, izin_kisitla)
                await msg.reply("⏳ Medya iznin sona erdi.")
            except Exception as e:
                logging.error(f"İzin hatası: {e}")
                await msg.reply("❌ Telegram izin veremedi.")
            save_json(USERDATA_FILE, convert_keys_to_str(user_data))
            save_json(COUNTS_FILE, convert_keys_to_str(user_msg_count))
            save_json(IZIN_FILE, convert_keys_to_str(izin_sureleri))
            break

@app.on_chat_member_updated()
async def bot_eklenince(_, cmu: ChatMemberUpdated):
    if cmu.new_chat_member and cmu.new_chat_member.user.is_bot:
        if cmu.new_chat_member.user.id == (await app.get_me()).id:
            await app.send_message(
                cmu.chat.id,
                "👋 Merhaba! Ben grup aktiflik botuyum.\n"
                "Mesaj atanlar seviye atlar, medya izni kazanır.\n"
                "Komutlar için: /menu"
            )

print("🚀 Bot başlatılıyor...")
app.run()
