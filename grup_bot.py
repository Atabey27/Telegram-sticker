from pyrogram import Client, filters
from pyrogram.types import ChatPermissions, Message, ChatMemberUpdated
from collections import defaultdict
from datetime import datetime
import asyncio
import time
import json
import os
from dotenv import load_dotenv

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

@app.on_message(filters.command("giveme") & filters.user(admin_id))
async def add_admin(_, msg: Message):
    if not msg.reply_to_message and len(msg.command) < 2:
        await msg.reply("⚠️ Kullanım: /giveme @kullanici (veya yanıtla)"); return
    uid = msg.reply_to_message.from_user.id if msg.reply_to_message else await app.get_users(msg.command[1].lstrip("@")).id
    yetkili_adminler.add(uid)
    save_json(ADMINS_FILE, list(yetkili_adminler))
    await msg.reply(f"✅ `{uid}` ID'li kullanıcıya komut yetkisi verildi.")

@app.on_message(filters.command("revoke") & filters.user(admin_id))
async def remove_admin(_, msg: Message):
    if not msg.reply_to_message and len(msg.command) < 2:
        await msg.reply("⚠️ Kullanım: /revoke @kullanici (veya yanıtla)"); return
    uid = msg.reply_to_message.from_user.id if msg.reply_to_message else await app.get_users(msg.command[1].lstrip("@")).id
    if uid == admin_id: await msg.reply("❌ Bot sahibinin yetkisi kaldırılamaz."); return
    yetkili_adminler.discard(uid)
    save_json(ADMINS_FILE, list(yetkili_adminler))
    await msg.reply(f"🚫 `{uid}` ID'li kullanıcının yetkisi kaldırıldı.")

@app.on_message(filters.command("help"))
async def help_cmd(_, msg):
    await msg.reply(
        "**📖 Komut Listesi:**\n\n"
        "🔹 `/setlimit [seviye] [mesaj] [süre]`\n"
        "🔹 `/setmaxgrant [adet]`\n"
        "🔹 `/listlimits`\n"
        "🔹 `/status`\n"
        "🔹 `/resetdata`\n"
        "🔹 `/giveme @kullanici`\n"
        "🔹 `/revoke @kullanici`\n"
        "🔹 `/aboutinfo`"
    )

@app.on_message(filters.command("aboutinfo"))
async def about_info(_, msg):
    await msg.reply(
        "🤖 **Bu bot, grup içi kullanıcı aktifliğini takip eder.**\n"
        "Mesaj atan kullanıcılar seviye atlayarak sınırlı süreli sticker/GIF izni kazanır.\n\n"
        "**🛠 Geliştirici:** @Atabey27\n"
        "🔧 Bot açık kaynaklıdır ve sürekli geliştirilir."
    )

@app.on_message(filters.command("setlimit"))
async def set_limit(_, msg):
    if not is_authorized(msg.from_user.id): return
    try:
        _, seviye, mesaj, süre = msg.text.split()
        limits[int(seviye)] = {"msg": int(mesaj), "süre": int(süre)}
        save_json(LIMITS_FILE, limits)
        await msg.reply(f"✅ Seviye {seviye} ayarlandı.")
    except: await msg.reply("⚠️ Kullanım: /setlimit [seviye] [mesaj] [süre]")

@app.on_message(filters.command("setmaxgrant"))
async def set_grant(_, msg):
    if not is_authorized(msg.from_user.id): return
    try:
        global max_grant
        max_grant = int(msg.text.split()[1])
        await msg.reply(f"✅ Günlük hak: {max_grant}")
    except: await msg.reply("⚠️ Kullanım: /setmaxgrant [adet]")

@app.on_message(filters.command("listlimits"))
async def list_limits(_, msg):
    if not is_authorized(msg.from_user.id): return
    if not limits: await msg.reply("⚠️ Hiç limit ayarlanmamış."); return
    text = "📋 **Seviye Limitleri:**\n"
    for seviye in sorted(limits.keys()):
        lim = limits[seviye]
        text += f"🔹 Seviye {seviye}: {lim['msg']} mesaj → {lim['süre']} sn\n"
    await msg.reply(text)

@app.on_message(filters.command("resetdata"))
async def reset_all(_, msg):
    if not is_authorized(msg.from_user.id): return
    user_data.clear(); user_msg_count.clear(); izin_sureleri.clear()
    save_json(USERDATA_FILE, user_data)
    save_json(COUNTS_FILE, user_msg_count)
    save_json(IZIN_FILE, izin_sureleri)
    await msg.reply("✅ Tüm veriler sıfırlandı.")

@app.on_message(filters.command("status"))
async def user_status(_, msg):
    uid, cid = msg.from_user.id, msg.chat.id
    key = f"({cid}, {uid})"
    if key not in user_data: await msg.reply("ℹ️ Kayıtlı verin yok."); return
    veri = user_data[key]
    seviye = veri["seviye"]
    kalan_hak = max_grant - veri["grant_count"]
    if seviye not in limits: await msg.reply("ℹ️ Seviyen tanımlı değil."); return
    gereken = limits[seviye]["msg"]
    atilan = user_msg_count.get(key, 0)
    kalan = max(0, gereken - atilan)
    await msg.reply(
        f"📊 **Durumun:**\n"
        f"🔹 Seviye: {seviye}\n"
        f"📝 Mesaj: {atilan}/{gereken}\n"
        f"⏳ Kalan: {kalan}\n"
        f"🎁 Günlük hak: {veri['grant_count']}/{max_grant}"
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
            await app.send_message(cmu.chat.id,
                "👋 Merhaba! Ben bu grubun aktiflik takip botuyum.\n"
                "Mesaj atan kullanıcılar seviye atlar ve kısa süreli sticker/GIF izni kazanır.\n"
                "ℹ️ Yardım için /help komutunu kullanabilirsin.\n\n"
                "🛠 *Geliştirici:* @Atabey27"
            )

# Botu başlat
print("🚀 Bot başlıyor...")
app.run()
print("❌ Bot durdu.")
