from pyrogram import Client, filters
from pyrogram.types import (
    ChatPermissions, Message, ChatMemberUpdated,
    InlineKeyboardMarkup, InlineKeyboardButton, CallbackQuery
)
from datetime import datetime
import asyncio
import time
import json
import os
from dotenv import load_dotenv

def convert_keys_to_str(d: dict) -> dict:
    return {str(k): v for k, v in d.items()}

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
        await cb.message.edit_text(
            "**🆘 Yardım Menüsü:**\n\n"
            "🔹 `/seviyeayar` - 🧱 Seviye mesaj/süre ayarı yapar.\n"
            "🔹 `/hakayarla` - 🎯 Günlük medya izni adedini belirler.\n"
            "🔹 `/seviyelistesi` - 📊 Tüm seviyeleri listeler.\n"
            "🔹 `/verisil` - 🧹 Tüm kullanıcı verilerini sıfırlar.\n"
            "🔹 `/durumum` - 📌 Mevcut seviyeni ve kalan hakkını gösterir.\n"
            "🔹 `/yetkiver` - 🛡️ Kullanıcıya komut yetkisi verir.\n"
            "🔹 `/yetkial` - 🚫 Kullanıcının yetkisini kaldırır.\n"
            "🔹 `/hakkinda` - ℹ️ Botun tanıtımı.\n",
            reply_markup=InlineKeyboardMarkup([[InlineKeyboardButton("◀️ Geri", callback_data="geri")]])
        )

    elif data == "limits":
        if not limits:
            await cb.message.edit_text(
                "⚠️ Ayarlanmış bir seviye bulunamadı.",
                reply_markup=InlineKeyboardMarkup([[InlineKeyboardButton("◀️ Geri", callback_data="geri")]])
            )
            return
        metin = "📊 **Seviye Listesi:**\n\n"
        for seviye in sorted(limits.keys()):
            lim = limits[seviye]
            metin += f"🔸 Seviye {seviye}: {lim['msg']} mesaj → {lim['süre']} sn medya izni\n"
        await cb.message.edit_text(
            metin,
            reply_markup=InlineKeyboardMarkup([[InlineKeyboardButton("◀️ Geri", callback_data="geri")]])
        )

    elif data == "settings":
        await cb.message.edit_text(
            "⚙️ Ayarlar menüsü şu an geliştiriliyor.",
            reply_markup=InlineKeyboardMarkup([[InlineKeyboardButton("◀️ Geri", callback_data="geri")]])
        )

    elif data == "geri":
        await cb.message.delete()
        await menu(_, cb.message)

@app.on_message(filters.command("seviyeayar"))
async def set_limit(_, msg):
    if not is_authorized(msg.from_user.id): return
    try:
        _, seviye, mesaj, süre = msg.text.split()
        limits[int(seviye)] = {"msg": int(mesaj), "süre": int(süre)}
        save_json(LIMITS_FILE, limits)
        await msg.reply(f"✅ Seviye {seviye} ayarlandı.")
    except:
        await msg.reply("⚠️ Kullanım: /seviyeayar [seviye] [mesaj] [süre]")

@app.on_message(filters.command("hakayarla"))
async def set_grant(_, msg):
    if not is_authorized(msg.from_user.id): return
    try:
        global max_grant
        max_grant = int(msg.text.split()[1])
        await msg.reply(f"✅ Günlük hak: {max_grant}")
    except:
        await msg.reply("⚠️ Kullanım: /hakayarla [adet]")

@app.on_message(filters.command("seviyelistesi"))
async def list_limits(_, msg):
    if not is_authorized(msg.from_user.id): return
    if not limits:
        await msg.reply("⚠️ Henüz hiç seviye ayarı yapılmamış.")
        return
    text = "📋 **Seviye Listesi:**\n"
    for seviye in sorted(limits.keys()):
        lim = limits[seviye]
        text += f"🔹 Seviye {seviye}: {lim['msg']} mesaj → {lim['süre']} sn izin\n"
    await msg.reply(text)

@app.on_message(filters.command("verisil"))
async def reset_all(_, msg):
    if not is_authorized(msg.from_user.id): return
    user_data.clear(); user_msg_count.clear(); izin_sureleri.clear()
    save_json(USERDATA_FILE, convert_keys_to_str(user_data))
    save_json(COUNTS_FILE, convert_keys_to_str(user_msg_count))
    save_json(IZIN_FILE, convert_keys_to_str(izin_sureleri))
    await msg.reply("✅ Tüm kullanıcı verileri silindi.")

@app.on_message(filters.command("durumum"))
async def user_status(_, msg):
    uid, cid = msg.from_user.id, msg.chat.id
    key = f"({cid}, {uid})"
    if key not in user_data:
        await msg.reply("ℹ️ Henüz kayıtlı verin bulunamadı.")
        return
    veri = user_data[key]
    seviye = veri["seviye"]
    if seviye not in limits:
        await msg.reply("ℹ️ Seviyen ayarlanmamış.")
        return
    gereken = limits[seviye]["msg"]
    atilan = user_msg_count.get(key, 0)
    kalan = max(0, gereken - atilan)
    await msg.reply(
        f"👤 **Durum Bilgin:**\n"
        f"🔹 Seviye: {seviye}\n"
        f"📨 Mesaj Sayısı: {atilan}/{gereken}\n"
        f"⏳ Kalan: {kalan} mesaj\n"
        f"🎁 Kalan Günlük Hak: {veri['grant_count']}/{max_grant}"
    )

@app.on_message(filters.command("yetkiver") & filters.user(admin_id))
async def add_admin(_, msg: Message):
    if not msg.reply_to_message and len(msg.command) < 2:
        await msg.reply("⚠️ Kullanım: /yetkiver @kullanici (veya yanıtla)")
        return
    uid = msg.reply_to_message.from_user.id if msg.reply_to_message else (await app.get_users(msg.command[1].lstrip("@"))).id
    yetkili_adminler.add(uid)
    save_json(ADMINS_FILE, list(yetkili_adminler))
    await msg.reply(f"✅ `{uid}` ID'li kullanıcıya komut yetkisi verildi.")

@app.on_message(filters.command("yetkial") & filters.user(admin_id))
async def remove_admin(_, msg: Message):
    if not msg.reply_to_message and len(msg.command) < 2:
        await msg.reply("⚠️ Kullanım: /yetkial @kullanici (veya yanıtla)")
        return
    uid = msg.reply_to_message.from_user.id if msg.reply_to_message else (await app.get_users(msg.command[1].lstrip("@"))).id
    if uid == admin_id:
        await msg.reply("❌ Bot sahibinin yetkisi kaldırılamaz.")
        return
    yetkili_adminler.discard(uid)
    save_json(ADMINS_FILE, list(yetkili_adminler))
    await msg.reply(f"🚫 `{uid}` ID'li kullanıcının yetkisi kaldırıldı.")

@app.on_message(filters.command("hakkinda"))
async def about_info(_, msg):
    await msg.reply(
        "🤖 **Aktiflik Takip Botu**\n"
        "Kullanıcıların mesaj sayılarına göre seviye atlamasını sağlar ve onlara kısa süreli sticker/GIF izni tanır.\n\n"
        "🛠 Geliştirici: @Atabey27"
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
            await msg.reply(f"🎉 Tebrikler! Seviye {seviye} tamamlandı. {lim['süre']} sn sticker/GIF izni verildi.")

            izin_ver = ChatPermissions(
                can_send_messages=True,
                can_send_media_messages=True,
                can_send_polls=False,
                can_send_other_messages=True,
                can_add_web_page_previews=False,
                can_change_info=False,
                can_invite_users=False,
                can_pin_messages=False
            )
            izin_kisitla = ChatPermissions(
                can_send_messages=True,
                can_send_media_messages=False,
                can_send_polls=False,
                can_send_other_messages=False,
                can_add_web_page_previews=False,
                can_change_info=False,
                can_invite_users=False,
                can_pin_messages=False
            )

            try:
                await app.restrict_chat_member(cid, uid, izin_ver)
                await asyncio.sleep(lim["süre"])
                await app.restrict_chat_member(cid, uid, izin_kisitla)
                await msg.reply("⌛️ Sticker/GIF iznin sona erdi.")
            except Exception as e:
                print("HATA:", e)
                await msg.reply(f"❌ Telegram izinleri uygulanamadı:\n{e}")
            save_json(USERDATA_FILE, convert_keys_to_str(user_data))
            save_json(COUNTS_FILE, convert_keys_to_str(user_msg_count))
            save_json(IZIN_FILE, convert_keys_to_str(izin_sureleri))

@app.on_chat_member_updated()
async def yeni_katilim(_, cmu: ChatMemberUpdated):
    if cmu.new_chat_member and cmu.new_chat_member.user.is_bot:
        if cmu.new_chat_member.user.id == (await app.get_me()).id:
            await app.send_message(cmu.chat.id,
                "👋 Merhaba! Ben bu grubun aktiflik takip botuyum.\n"
                "Mesaj atan kullanıcılar seviye atlar ve kısa süreli sticker/GIF izni kazanır.\n"
                "ℹ️ Menü için /menu yazabilirsin."
            )

print("🚀 Bot başlatılıyor...")
app.run()
print("❌ Bot durduruldu.")
