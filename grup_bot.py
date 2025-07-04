from pyrogram import Client, filters
from pyrogram.types import ChatPermissions, Message
from datetime import datetime
import asyncio
import time
import json
import os

# Telegram API bilgilerin
api_id = 24562058
api_hash = "a5562428e856f01ac943de0d29036cde"
bot_token = "7276297040:AAGNgZF2REjksCwgagXMPCwwjCubyT5BzaM"

# Kalıcı kayıt dosyalarının adları
LIMITS_FILE = "limits.json"
USERDATA_FILE = "users.json"
COUNTS_FILE = "counts.json"
IZIN_FILE = "izinler.json"
ADMINS_FILE = "admins.json"

# Sabit admin ID (bot sahibi)
admin_id = 244062665

# Anahtarları güvenli string formatında oluştur
def get_key(cid, uid):
    return f"{cid}_{uid}"

# JSON'dan veri yükleme fonksiyonu
def load_json(filename, default):
    if os.path.exists(filename):
        with open(filename, "r", encoding="utf-8") as f:
            return json.load(f)
    return default

# JSON'a veri kaydetme fonksiyonu
def save_json(filename, data):
    with open(filename, "w", encoding="utf-8") as f:
        json.dump(data, f, indent=4)

# JSON dosyalarını oku
limits = {int(k): v for k, v in load_json(LIMITS_FILE, {}).items()}
user_data = load_json(USERDATA_FILE, {})
user_msg_count = load_json(COUNTS_FILE, {})
izin_sureleri = load_json(IZIN_FILE, {})
yetkili_adminler = set(load_json(ADMINS_FILE, [admin_id]))

# Günlük kaç hak verileceği
max_grant = 2

# Botu başlat
app = Client("bot", api_id=api_id, api_hash=api_hash, bot_token=bot_token)

# Yetkili kontrolü
def is_authorized(user_id: int) -> bool:
    return user_id in yetkili_adminler

# /giveme komutu: kullanıcıya yetki ver
@app.on_message(filters.command("giveme") & filters.user(admin_id))
async def add_admin(_, msg: Message):
    if not msg.reply_to_message and len(msg.command) < 2:
        await msg.reply("⚠️ Kullanım: /giveme @kullanici (veya yanıtla)")
        return
    if msg.reply_to_message:
        uid = msg.reply_to_message.from_user.id
    else:
        username = msg.command[1].lstrip("@")
        try:
            user = await app.get_users(username)
            uid = user.id
        except:
            await msg.reply("❌ Kullanıcı bulunamadı.")
            return
    yetkili_adminler.add(uid)
    save_json(ADMINS_FILE, list(yetkili_adminler))
    await msg.reply(f"✅ `{uid}` ID'li kullanıcıya komut yetkisi verildi.")

# /revoke komutu: kullanıcıdan yetki al
@app.on_message(filters.command("revoke") & filters.user(admin_id))
async def remove_admin(_, msg: Message):
    if not msg.reply_to_message and len(msg.command) < 2:
        await msg.reply("⚠️ Kullanım: /revoke @kullanici (veya yanıtla)")
        return
    if msg.reply_to_message:
        uid = msg.reply_to_message.from_user.id
    else:
        username = msg.command[1].lstrip("@")
        try:
            user = await app.get_users(username)
            uid = user.id
        except:
            await msg.reply("❌ Kullanıcı bulunamadı.")
            return
    if uid == admin_id:
        await msg.reply("❌ Bot sahibinin yetkisi kaldırılamaz.")
        return
    yetkili_adminler.discard(uid)
    save_json(ADMINS_FILE, list(yetkili_adminler))
    await msg.reply(f"🚫 `{uid}` ID'li kullanıcının yetkisi kaldırıldı.")

from pyrogram.types import ChatMemberUpdated
       #Botu gruba ekleyenlere yetki verir
@app.on_chat_member_updated()
async def on_bot_added(client, update: ChatMemberUpdated):
    # Bot eklendi mi kontrol et
    if update.new_chat_member and update.new_chat_member.user.is_bot:
        bot_id = (await app.get_me()).id
        if update.new_chat_member.user.id == bot_id:
            ekleyen = update.from_user
            if ekleyen and not ekleyen.is_bot:
                yetkili_adminler.add(ekleyen.id)
                save_json(ADMINS_FILE, list(yetkili_adminler))
                try:
                    await app.send_message(
                        update.chat.id,
                        f"✅ <b>{ekleyen.first_name}</b> botu gruba ekledi ve artık yetkilidir.",
                        parse_mode="html"
                    )
                except:
                    pass

# /help komutu: komut listesini göster
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
        "🔹 `/help`\n\n"
        "Komutlar sadece yetkili kişiler tarafından kullanılabilir."
    )

# /setlimit komutu: seviye limitini belirle
@app.on_message(filters.command("setlimit"))
async def set_limit(_, msg):
    if not is_authorized(msg.from_user.id): return
    try:
        _, seviye, mesaj, süre = msg.text.split()
        limits[int(seviye)] = {"msg": int(mesaj), "süre": int(süre)}
        save_json(LIMITS_FILE, limits)
        await msg.reply(f"✅ Seviye {seviye} ayarlandı: {mesaj} mesaj → {süre} saniye")
    except:
        await msg.reply("⚠️ Kullanım: /setlimit [seviye] [mesaj] [süre]")

# /setmaxgrant komutu: günlük izin sayısını belirle
@app.on_message(filters.command("setmaxgrant"))
async def set_grant(_, msg):
    if not is_authorized(msg.from_user.id): return
    try:
        global max_grant
        max_grant = int(msg.text.split()[1])
        await msg.reply(f"✅ Günlük hak sayısı: {max_grant}")
    except:
        await msg.reply("⚠️ Kullanım: /setmaxgrant [adet]")

# /listlimits komutu: tüm seviye limitlerini listele
@app.on_message(filters.command("listlimits"))
async def list_limits(_, msg):
    if not is_authorized(msg.from_user.id): return
    if not limits:
        await msg.reply("⚠️ Hiç seviye limiti ayarlanmamış.")
        return
    text = "📋 **Tüm Seviye Limitleri:**\n"
    for seviye in sorted(limits.keys()):
        lim = limits[seviye]
        text += f"🔹 Seviye {seviye}: {lim['msg']} mesaj → {lim['süre']} saniye\n"
    await msg.reply(text)

# /resetdata komutu: kullanıcı verilerini sıfırlar
@app.on_message(filters.command("resetdata"))
async def reset_all(_, msg):
    if not is_authorized(msg.from_user.id): return
    user_data.clear()
    user_msg_count.clear()
    izin_sureleri.clear()
    save_json(USERDATA_FILE, user_data)
    save_json(COUNTS_FILE, user_msg_count)
    save_json(IZIN_FILE, izin_sureleri)
    await msg.reply("✅ Tüm kullanıcı verileri sıfırlandı.")

# /status komutu: kullanıcı kendi durumunu sorgular
@app.on_message(filters.command("status"))
async def user_status(_, msg):
    uid = msg.from_user.id
    cid = msg.chat.id
    key = get_key(cid, uid)

    if key not in user_data:
        await msg.reply("ℹ️ Henüz kayıtlı bir verin yok.")
        return

    veri = user_data[key]
    mevcut_seviye = veri["seviye"]
    kalan_hak = max_grant - veri["grant_count"]

    if mevcut_seviye not in limits:
        await msg.reply("ℹ️ Seviyen tanımlı değil.")
        return

    gereken = limits[mevcut_seviye]["msg"]
    atilan = user_msg_count.get(key, 0)
    kalan = max(0, gereken - atilan)

    await msg.reply(
        f"📊 **Durumun:**\n"
        f"🔹 Seviye: {mevcut_seviye}\n"
        f"📝 Attığın mesaj: {atilan}/{gereken}\n"
        f"⏳ Kalan: {kalan} mesaj\n"
        f"🎁 Günlük hak: {veri['grant_count']}/{max_grant}"
    )

# 🔁 Tüm grup mesajlarını takip eden sistem
@app.on_message(filters.group & ~filters.service)
async def takip_et(_, msg):
    uid = msg.from_user.id
    cid = msg.chat.id
    key = get_key(cid, uid)
    now = time.time()

    # Her gün sıfırla
    today = str(datetime.now().date())
    if key not in user_data or user_data[key]["date"] != today:
        user_data[key] = {"seviye": 0, "grant_count": 0, "date": today}
        user_msg_count[key] = 0

    # Kullanıcı hala izin süresindeyse mesaj sayılmasın
    if now < izin_sureleri.get(key, 0):
        return

    user_msg_count[key] += 1

    for seviye in sorted(limits.keys()):
        lim = limits[seviye]
        if (
            user_msg_count[key] >= lim["msg"]
            and seviye > user_data[key]["seviye"]
            and user_data[key]["grant_count"] < max_grant
        ):
            user_data[key]["seviye"] = seviye
            user_data[key]["grant_count"] += 1
            user_msg_count[key] = 0
            izin_sureleri[key] = now + lim["süre"]

            await msg.reply(f"🎉 Seviye {seviye} tamamlandı! {lim['süre']} sn izin verildi.")

            try:
                await app.restrict_chat_member(
                    cid, uid,
                    permissions=ChatPermissions(
                        can_send_messages=True,
                        can_send_media_messages=True,
                        can_send_other_messages=True,
                        can_add_web_page_previews=True
                    )
                )
                await asyncio.sleep(lim["süre"])
                await app.restrict_chat_member(
                    cid, uid,
                    permissions=ChatPermissions(
                        can_send_messages=True,
                        can_send_media_messages=True,
                        can_send_other_messages=False,
                        can_add_web_page_previews=True
                    )
                )
                await msg.reply("⌛️ Sticker/GIF iznin sona erdi.")
            except Exception as e:
                print(f"HATA: {e}")
                await msg.reply("❌ Telegram izin veremedi (belki kullanıcı admindir).")

    # JSON dosyalarına verileri kaydet
    save_json(USERDATA_FILE, user_data)
    save_json(COUNTS_FILE, user_msg_count)
    save_json(IZIN_FILE, izin_sureleri)

# Botu başlat
print("🚀 Bot başlıyor...")
app.run()
print("❌ Bot durdu.")
