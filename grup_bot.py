from pyrogram import Client, filters
from pyrogram.types import ChatPermissions, Message, ChatMemberUpdated, InlineKeyboardMarkup, InlineKeyboardButton, CallbackQuery
from datetime import datetime
import asyncio
import time
import json
import os
from dotenv import load_dotenv

def convert_keys_to_str(d): return {str(k): v for k, v in d.items()}
def parse_time(val, unit): return int(val) * {"saniye": 1, "dakika": 60, "saat": 3600}.get(unit, 1)

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

def load_json(f, d): return json.load(open(f, "r", encoding="utf-8")) if os.path.exists(f) else d
def save_json(f, d): json.dump(d, open(f, "w", encoding="utf-8"), indent=4)

limits = {}  # Artık tüm grup için değil, grup özelinde çalışacağız
user_data = load_json(USERDATA_FILE, {})
user_msg_count = {eval(k): v for k, v in load_json(COUNTS_FILE, {}).items()}
izin_sureleri = {eval(k): v for k, v in load_json(IZIN_FILE, {}).items()}
yetkili_adminler = set(load_json(ADMINS_FILE, [admin_id]))
max_grant = 2

app = Client("bot", api_id=api_id, api_hash=api_hash, bot_token=bot_token, in_memory=True)
def is_authorized(uid): return uid in yetkili_adminler

@app.on_message(filters.command("menu"))
async def menu(_, msg: Message):
    btn = InlineKeyboardMarkup([
        [InlineKeyboardButton("📋 Yardım Menüsü", callback_data="help")],
        [InlineKeyboardButton("📊 Seviye Listesi", callback_data="limits")],
        [InlineKeyboardButton("⚙️ Ayarlar", callback_data="settings")],
        [InlineKeyboardButton("👥 Admin Listesi", callback_data="adminlistesi")],
        [InlineKeyboardButton("❌ Kapat", callback_data="kapat")]
    ])
    await msg.reply("👋 Merhaba! Aşağıdan bir seçenek seç:", reply_markup=btn)

@app.on_callback_query()
async def buton(_, cb: CallbackQuery):
    data = cb.data
    cid = cb.message.chat.id
    if data == "kapat":
        await cb.message.delete()
        return
    elif data == "help":
        await cb.message.edit_text(
            "**🆘 Yardım Menüsü:**\n\n"
            "🧱 `/seviyeayar [seviye] [mesaj] [süre] [birim]`\n"
            " ➡️ Örnek: `/seviyeayar 2 10 5 dakika`\n"
            " Seviye 2 için 10 mesaj atınca 5 dakika sticker/GIF izni verilir.\n\n"
            "🎯 `/hakayarla [adet]`\n"
            " ➡️ Her gün en fazla kaç seviye atlanabilir ayarlar.\n\n"
            "📊 `/seviyelistesi`\n"
            " ➡️ Şu anki seviye ayarlarını listeler.\n\n"
            "📌 `/durumum`\n"
            " ➡️ Kendi seviyeni, kalan mesaj sayını ve günlük hakkını gösterir.\n\n"
            "🧹 `/verisil`\n"
            " ➡️ Tüm kullanıcı verilerini siler (admin komutu).\n\n"
            "🛡️ `/yetkiver @kullanici`\n"
            "🚫 `/yetkial @kullanici`\n"
            " ➡️ Komut yetkisi verir/alır.\n\n"
            "ℹ️ `/hakkinda`\n"
            " ➡️ Bot hakkında bilgi verir.",
            reply_markup=InlineKeyboardMarkup([[InlineKeyboardButton("◀️ Geri", callback_data="geri")]])
        )
    elif data == "limits":
        if cid not in limits or not limits[cid]:
            await cb.message.edit_text("⚠️ Bu grup için seviye ayarı yok.", reply_markup=InlineKeyboardMarkup([[InlineKeyboardButton("◀️ Geri", callback_data="geri")]]))
            return
        text = "📊 **Seviye Listesi:**\n\n"
        for s in sorted(limits[cid].keys()):
            l = limits[cid][s]
            text += f"🔹 Seviye {s}: {l['msg']} mesaj → {l['süre']} sn izin\n"
        await cb.message.edit_text(text, reply_markup=InlineKeyboardMarkup([[InlineKeyboardButton("◀️ Geri", callback_data="geri")]]))
    elif data == "settings":
        await cb.message.edit_text("⚙️ Ayarlar menüsü geliştiriliyor.", reply_markup=InlineKeyboardMarkup([[InlineKeyboardButton("◀️ Geri", callback_data="geri")]]))
    elif data == "adminlistesi":
        metin = "👥 **Yetkili Adminler:**\n"
        for uid in yetkili_adminler:
            try:
                u = await app.get_users(uid)
                metin += f"• @{u.username}\n" if u.username else f"• {u.first_name}\n"
            except: continue
        await cb.message.edit_text(metin, reply_markup=InlineKeyboardMarkup([[InlineKeyboardButton("◀️ Geri", callback_data="geri")]]))
    elif data == "geri":
        await cb.message.delete()
        await menu(_, cb.message)

@app.on_message(filters.command("seviyeayar"))
async def set_limit(_, msg):
    if not is_authorized(msg.from_user.id): return
    try:
        _, seviye, mesaj, sure, birim = msg.text.split()
        cid = msg.chat.id
        if cid not in limits:
            limits[cid] = {}
        limits[cid][int(seviye)] = {"msg": int(mesaj), "süre": parse_time(int(sure), birim)}
        await msg.reply(f"✅ Grup için seviye {seviye} ayarlandı.")
    except:
        await msg.reply("⚠️ Kullanım: /seviyeayar [seviye] [mesaj] [süre] [saniye|dakika|saat]")

@app.on_message(filters.command("hakayarla"))
async def set_grant(_, msg):
    if not is_authorized(msg.from_user.id): return
    try:
        global max_grant
        max_grant = int(msg.text.split()[1])
        await msg.reply(f"✅ Günlük hak: {max_grant}")
    except:
        await msg.reply("⚠️ Kullanım: /hakayarla [adet]")

@app.on_message(filters.command("verisil"))
async def reset_all(_, msg):
    if not is_authorized(msg.from_user.id): return
    cid = msg.chat.id
    user_data_keys = [k for k in user_data if eval(k)[0] == cid]
    for k in user_data_keys:
        user_data.pop(k, None)
        user_msg_count.pop(eval(k), None)
        izin_sureleri.pop(eval(k), None)
    await msg.reply("✅ Bu grubun verileri sıfırlandı.")

@app.on_message(filters.command("seviyelistesi"))
async def list_limits(_, msg):
    cid = msg.chat.id
    if cid not in limits or not limits[cid]:
        await msg.reply("⚠️ Seviye ayarı yapılmamış.")
        return
    text = "📋 **Seviye Listesi:**\n"
    for s in sorted(limits[cid].keys()):
        l = limits[cid][s]
        text += f"🔹 Seviye {s}: {l['msg']} mesaj → {l['süre']} sn\n"
    await msg.reply(text)

@app.on_message(filters.command("durumum"))
async def user_status(_, msg):
    uid, cid = msg.from_user.id, msg.chat.id
    key = f"({cid}, {uid})"
    if key not in user_data: return await msg.reply("ℹ️ Kayıtlı verin yok.")
    veri = user_data[key]
    sev = veri["seviye"]
    gerek = limits.get(cid, {}).get(sev, {}).get("msg", 0)
    atilan = user_msg_count.get((cid, uid), 0)
    kalan = max(0, gerek - atilan)
    await msg.reply(f"👤 **Durum Bilgin:**\n🔹 Seviye: {sev}\n📨 Mesaj: {atilan}/{gerek}\n⏳ Kalan: {kalan}\n🎁 Hak: {veri['grant_count']}/{max_grant}")

@app.on_message(filters.group & ~filters.service)
async def takip_et(_, msg):
    uid, cid = msg.from_user.id, msg.chat.id
    me = await app.get_chat_member(cid, uid)
    if me.status in ("administrator", "creator"): return
    key = f"({cid}, {uid})"
    now = time.time()
    today = str(datetime.now().date())
    if key not in user_data or user_data[key]["date"] != today:
        user_data[key] = {"seviye": 0, "grant_count": 0, "date": today}
        user_msg_count[(cid, uid)] = 0
    if now < izin_sureleri.get((cid, uid), 0): return
    user_msg_count[(cid, uid)] += 1
    grup_limits = limits.get(cid, {})
    for seviye in sorted(grup_limits.keys()):
        lim = grup_limits[seviye]
        if user_msg_count[(cid, uid)] >= lim["msg"] and seviye > user_data[key]["seviye"] and user_data[key]["grant_count"] < max_grant:
            user_data[key]["seviye"] = seviye
            user_data[key]["grant_count"] += 1
            user_msg_count[(cid, uid)] = 0
            izin_sureleri[(cid, uid)] = now + lim["süre"]
            await msg.reply(f"🎉 Seviye {seviye} tamamlandı! {lim['süre']} sn izin verildi.")
            try:
                await app.restrict_chat_member(cid, uid, ChatPermissions(can_send_media_messages=True, can_send_other_messages=True))
                await asyncio.sleep(lim["süre"])
                await app.restrict_chat_member(cid, uid, ChatPermissions(can_send_media_messages=False, can_send_other_messages=False))
                await msg.reply("⌛️ Sticker/GIF iznin sona erdi.")
            except Exception as e:
                await msg.reply(f"❌ Hata: {e}")

@app.on_chat_member_updated()
async def yeni_katilim(_, cmu: ChatMemberUpdated):
    if cmu.new_chat_member and cmu.new_chat_member.user.id == (await app.get_me()).id:
        await app.send_message(cmu.chat.id,
            "👋 Merhaba! Ben aktiflik takip botuyum.\nMesaj atarak seviye atla, sticker/GIF izni kazan!\n/menu yazarak başla.")

print("🚀 Bot başlatılıyor...")
app.run()
