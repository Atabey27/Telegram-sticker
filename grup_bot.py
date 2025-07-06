from pyrogram import Client, filters
from pyrogram.types import ChatPermissions, Message, ChatMemberUpdated, InlineKeyboardMarkup, InlineKeyboardButton, CallbackQuery
from datetime import datetime
import asyncio, time, json, os, re
from dotenv import load_dotenv

# Süreyi saniyeye çevir
def parse_sure(s: str) -> int:
    matches = re.findall(r"(\d+)\s*(saniye|sn|dakika|dk|saat|sa)", s.lower())
    total_seconds = 0
    for value, unit in matches:
        value = int(value)
        if unit in ["saniye", "sn"]:
            total_seconds += value
        elif unit in ["dakika", "dk"]:
            total_seconds += value * 60
        elif unit in ["saat", "sa"]:
            total_seconds += value * 3600
    return total_seconds

def convert_keys_to_str(d: dict) -> dict:
    return {str(k): v for k, v in d.items()}

def load_json(filename, default):
    return json.load(open(filename, "r", encoding="utf-8")) if os.path.exists(filename) else default

def save_json(filename, data):
    json.dump(data, open(filename, "w", encoding="utf-8"), indent=4)

load_dotenv()
api_id = int(os.getenv("API_ID"))
api_hash = os.getenv("API_HASH")
bot_token = os.getenv("BOT_TOKEN")
admin_id = int(os.getenv("OWNER_ID"))

LIMITS_FILE = "limits.json"
USERDATA_FILE = "users.json"
COUNTS_FILE = "counts.json"
IZIN_FILE = "izinler.json"
ADMINS_FILE = "admins.json"

limits = {int(k): v for k, v in load_json(LIMITS_FILE, {}).items()}
user_data = load_json(USERDATA_FILE, {})
user_msg_count = {eval(k): v for k, v in load_json(COUNTS_FILE, {}).items()}
izin_sureleri = {eval(k): v for k, v in load_json(IZIN_FILE, {}).items()}
yetkili_adminler = set(load_json(ADMINS_FILE, [admin_id]))
max_grant = 2

app = Client("bot", api_id=api_id, api_hash=api_hash, bot_token=bot_token)

def is_authorized(user_id: int): return user_id in yetkili_adminler

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
            await msg.reply(f"🎉 Seviye {seviye} tamamlandı! {lim['süre']} sn izin verildi.")
            try:
                await app.restrict_chat_member(cid, uid, ChatPermissions(True, True, True, True))
                await asyncio.sleep(lim["süre"])
                await app.restrict_chat_member(cid, uid, ChatPermissions(True, True, False, True))
                await msg.reply("⌛️ Sticker/GIF iznin sona erdi.")
            except Exception as e:
                print("HATA:", e)
                await msg.reply("❌ Telegram izin veremedi (admin olabilir).")

    save_json(USERDATA_FILE, user_data)
    save_json(COUNTS_FILE, user_msg_count)
    save_json(IZIN_FILE, izin_sureleri)

@app.on_chat_member_updated()
async def yeni_katilim(_, cmu: ChatMemberUpdated):
    if cmu.new_chat_member and cmu.new_chat_member.user.is_bot:
        if cmu.new_chat_member.user.id == (await app.get_me()).id:
            await app.send_message(
                cmu.chat.id,
                "👋 Selam! Ben aktiflik takip botuyum.\n"
                "Mesaj atan kullanıcılar seviye atlar, çıkartma ve GIF izni kazanır.\n"
                "Komutlar için /menu"
            )

@app.on_message(filters.command("menu"))
async def menu(_, msg: Message):
    butonlar = InlineKeyboardMarkup([
        [InlineKeyboardButton("📋 Yardım Menüsü", callback_data="help")],
        [InlineKeyboardButton("📊 Seviye Listesi", callback_data="limits")],
        [InlineKeyboardButton("⚙️ Ayarlar", callback_data="settings")]
    ])
    await msg.reply("👋 Merhaba! Ne yapmak istersin?", reply_markup=butonlar)

@app.on_callback_query()
async def buton_yanitla(_, cb: CallbackQuery):
    data = cb.data
    if data == "help":
        butonlar = InlineKeyboardMarkup([[InlineKeyboardButton("◀️ Geri", callback_data="geri")]])
        await cb.message.edit_text(
            "**🆘 Yardım Menüsü:**\n\n"
            "🔹 `/seviyeayar` - Seviye ayarı yapar.\n"
            "🔹 `/hakayarla` - Günlük medya hakkı belirler.\n"
            "🔹 `/verisil` - Verileri sıfırlar.\n"
            "🔹 `/durum` - Kendi seviyeni gösterir.\n"
            "🔹 `/yetkiver`, `/yetkial` - Yetki yönetimi.\n",
            reply_markup=butonlar
        )
    elif data == "limits":
        if not limits:
            await cb.message.edit_text("⚠️ Ayarlanmış bir seviye yok.", reply_markup=InlineKeyboardMarkup([[InlineKeyboardButton("◀️ Geri", callback_data="geri")]]))
            return
        metin = "📊 **Seviye Listesi:**\n"
        for seviye in sorted(limits.keys()):
            lim = limits[seviye]
            metin += f"🔸 Seviye {seviye}: {lim['msg']} mesaj → {lim['süre']} sn\n"
        await cb.message.edit_text(metin, reply_markup=InlineKeyboardMarkup([[InlineKeyboardButton("◀️ Geri", callback_data="geri")]]))
    elif data == "settings":
        await cb.message.edit_text("⚙️ Ayarlar menüsü geliştiriliyor.", reply_markup=InlineKeyboardMarkup([[InlineKeyboardButton("◀️ Geri", callback_data="geri")]]))
    elif data == "geri":
        await cb.message.delete()
        await menu(_, cb.message)

print("✅ Bot başlatılıyor...")
app.run()
