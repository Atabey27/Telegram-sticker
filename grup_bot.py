from pyrogram import Client, filters
from pyrogram.types import InlineKeyboardMarkup, InlineKeyboardButton, ChatPermissions, Message, ChatMemberUpdated
from datetime import datetime
import asyncio
import time
import json
import os
import re
from dotenv import load_dotenv

def convert_keys_to_str(d: dict) -> dict:
    return {str(k): v for k, v in d.items()}

def parse_duration(text):
    saniye = 0
    text = text.lower()
    saniye += int(match := re.search(r"(\d+)\s*saniye", text)) and int(match.group(1)) if "saniye" in text else 0
    saniye += int(match := re.search(r"(\d+)\s*dakika", text)) and int(match.group(1)) * 60 if "dakika" in text else 0
    saniye += int(match := re.search(r"(\d+)\s*saat", text)) and int(match.group(1)) * 3600 if "saat" in text else 0
    return saniye if saniye > 0 else None

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

def load_json(filename, default): return json.load(open(filename, "r", encoding="utf-8")) if os.path.exists(filename) else default
def save_json(filename, data): json.dump(data, open(filename, "w", encoding="utf-8"), indent=4)

limits = {int(k): v for k, v in load_json(LIMITS_FILE, {}).items()}
user_data = load_json(USERDATA_FILE, {})
user_msg_count = {eval(k): v for k, v in load_json(COUNTS_FILE, {}).items()}
izin_sureleri = {eval(k): v for k, v in load_json(IZIN_FILE, {}).items()}
yetkili_adminler = set(load_json(ADMINS_FILE, [admin_id]))
max_grant = 2

app = Client("bot", api_id=api_id, api_hash=api_hash, bot_token=bot_token, in_memory=True)
def is_authorized(user_id: int): return user_id in yetkili_adminler

# Yardım / Menü
@app.on_message(filters.command("yardim"))
async def help_cmd(_, msg):
    keyboard = InlineKeyboardMarkup([
        [InlineKeyboardButton("📊 Durumum", callback_data="status")],
        [InlineKeyboardButton("📋 Seviye Listesi", callback_data="listlimits")],
        [InlineKeyboardButton("🗑️ Verileri Sil", callback_data="resetdata")],
        [InlineKeyboardButton("ℹ️ Hakkında", callback_data="aboutinfo")],
    ])
    await msg.reply("📖 *Komut Menüsü*:\n\n👇 Aşağıdaki butonlardan birini seç:", reply_markup=keyboard)

def geri_tusu():
    return InlineKeyboardMarkup([[InlineKeyboardButton("◀️ Geri", callback_data="geri")]])

@app.on_callback_query()
async def handle_buttons(_, query):
    cid = query.message.chat.id
    uid = query.from_user.id
    key = f"({cid}, {uid})"
    data = query.data

    if data == "status":
        if key not in user_data:
            await query.message.edit("ℹ️ Kayıtlı verin yok.", reply_markup=geri_tusu()); return
        veri = user_data[key]
        seviye = veri["seviye"]
        kalan_hak = max_grant - veri["grant_count"]
        if seviye not in limits:
            await query.message.edit("ℹ️ Seviyen tanımlı değil.", reply_markup=geri_tusu()); return
        gereken = limits[seviye]["msg"]
        atilan = user_msg_count.get(key, 0)
        kalan = max(0, gereken - atilan)
        await query.message.edit(
            f"📊 *Durumun:*\n"
            f"🔹 Seviye: {seviye}\n"
            f"✉️ Mesaj: {atilan}/{gereken}\n"
            f"⏳ Kalan Mesaj: {kalan}\n"
            f"🎁 Kalan Hak: {veri['grant_count']}/{max_grant}",
            reply_markup=geri_tusu()
        )

    elif data == "listlimits":
        if not limits:
            await query.message.edit("⚠️ Hiç seviye ayarı yapılmamış.", reply_markup=geri_tusu()); return
        text = "📋 *Seviye Listesi:*\n"
        for seviye in sorted(limits.keys()):
            lim = limits[seviye]
            text += f"🔹 Seviye {seviye}: {lim['msg']} mesaj → {lim['süre']} sn\n"
        await query.message.edit(text, reply_markup=geri_tusu())

    elif data == "resetdata":
        if not is_authorized(uid):
            await query.answer("❌ Yetkin yok!", show_alert=True); return
        user_data.clear(); user_msg_count.clear(); izin_sureleri.clear()
        save_json(USERDATA_FILE, convert_keys_to_str(user_data))
        save_json(COUNTS_FILE, convert_keys_to_str(user_msg_count))
        save_json(IZIN_FILE, convert_keys_to_str(izin_sureleri))
        await query.message.edit("✅ *Tüm veriler silindi.*", reply_markup=geri_tusu())

    elif data == "aboutinfo":
        await query.message.edit(
            "🤖 *Hakkında:*\n"
            "Bu bot, aktif kullanıcıları ödüllendirir.\n"
            "Mesaj atanlar seviye atlayıp çıkartma/gif izni kazanır. 🎉",
            reply_markup=geri_tusu()
        )

    elif data == "geri":
        await help_cmd(_, query.message)

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
            try:
                await app.restrict_chat_member(cid, uid, ChatPermissions(can_send_other_messages=True))
                await asyncio.sleep(lim["süre"])
                await app.restrict_chat_member(cid, uid, ChatPermissions(can_send_other_messages=False))
                await msg.reply("⌛️ Sticker/GIF iznin sona erdi.")
            except Exception as e:
                print("HATA:", e)
            save_json(USERDATA_FILE, convert_keys_to_str(user_data))
            save_json(COUNTS_FILE, convert_keys_to_str(user_msg_count))
            save_json(IZIN_FILE, convert_keys_to_str(izin_sureleri))

@app.on_message(filters.command("seviyeara"))
async def set_limit(_, msg):
    if not is_authorized(msg.from_user.id): return
    try:
        _, seviye, mesaj, *süre = msg.text.split()
        süre = parse_duration(" ".join(süre))
        limits[int(seviye)] = {"msg": int(mesaj), "süre": süre}
        save_json(LIMITS_FILE, limits)
        await msg.reply(f"✅ Seviye {seviye} ayarlandı.")
    except:
        await msg.reply("⚠️ Kullanım: /seviyeara [seviye] [mesaj] [süre]\n🧪 Örnek: `/seviyeara 2 50 2 dakika`")

@app.on_chat_member_updated()
async def yeni_katilim(_, cmu: ChatMemberUpdated):
    if cmu.new_chat_member and cmu.new_chat_member.user.is_bot:
        if cmu.new_chat_member.user.id == (await app.get_me()).id:
            await app.send_message(cmu.chat.id,
                "👋 Selam! Ben grup aktiflik botuyum.\n"
                "Mesaj attıkça seviye atlayıp ödül kazanırsın!\n"
                "Yardım: /yardim"
            )

print("🚀 Bot başlatıldı.")
app.run()
