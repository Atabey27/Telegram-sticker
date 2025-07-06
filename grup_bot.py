from pyrogram import Client, filters
from pyrogram.types import ChatPermissions, Message, ChatMemberUpdated, InlineKeyboardMarkup, InlineKeyboardButton, CallbackQuery
from datetime import datetime
import asyncio, time, json, os
from dotenv import load_dotenv

def convert_keys_to_str(d: dict): return {str(k): v for k, v in d.items()}
def parse_time_value(val, birim): return int(val) * {"saniye": 1, "dakika": 60, "saat": 3600}.get(birim, 1)

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
        [InlineKeyboardButton("⚙️ Ayarlar", callback_data="settings")],
        [InlineKeyboardButton("👥 Admin Listesi", callback_data="adminlistesi")]
    ])
    await msg.reply("👋 Merhaba! Aşağıdan bir seçenek seç:", reply_markup=butonlar)

@app.on_callback_query()
async def butonlar(_, cb: CallbackQuery):
    data = cb.data
    if data == "help":
        await cb.message.edit_text(
            "**🆘 Yardım Menüsü**\n\n"
            "🔹 `/seviyeayar [seviye] [mesaj] [süre] [birim]`\n"
            "→ Bir seviyeye mesaj sayısı ve süre atar. Birim: saniye/dakika/saat\n\n"
            "🔹 `/hakayarla [adet]`\n"
            "→ Günlük kullanıcıya verilecek toplam izin hakkı.\n\n"
            "🔹 `/seviyelistesi`\n"
            "→ Tüm seviye ayarlarını listeler.\n\n"
            "🔹 `/verisil`\n"
            "→ Tüm kullanıcı verilerini sıfırlar.\n\n"
            "🔹 `/durumum`\n"
            "→ Kendi seviyeni, mesaj durumunu ve haklarını gösterir.\n\n"
            "🔹 `/yetkiver @kullanici` (veya yanıtlama)\n"
            "→ Kullanıcıya komut yetkisi verir.\n\n"
            "🔹 `/yetkial @kullanici` (veya yanıtlama)\n"
            "→ Kullanıcının komut yetkisini kaldırır.\n\n"
            "🔹 `/hakkinda`\n"
            "→ Bot hakkında bilgi verir.",
            reply_markup=InlineKeyboardMarkup([[InlineKeyboardButton("◀️ Geri", callback_data="geri")]])
        )
    elif data == "limits":
        if not limits:
            await cb.message.edit_text("⚠️ Ayarlanmış bir seviye yok.", reply_markup=geri_btn())
            return
        metin = "📊 **Seviye Listesi:**\n\n"
        for seviye in sorted(limits.keys()):
            lim = limits[seviye]
            metin += f"🔸 Seviye {seviye}: {lim['msg']} mesaj → {lim['süre']} sn medya izni\n"
        await cb.message.edit_text(metin, reply_markup=geri_btn())
    elif data == "settings":
        await cb.message.edit_text("⚙️ Ayarlar menüsü geliştiriliyor.", reply_markup=geri_btn())
    elif data == "adminlistesi":
        metin = "👥 **Yetkili Adminler:**\n"
        for uid in yetkili_adminler:
            try:
                user = await app.get_users(uid)
                isim = user.username and f"@{user.username}" or user.first_name
                metin += f"• {isim} (`{uid}`)\n"
            except:
                metin += f"• Bilinmeyen kullanıcı (`{uid}`)\n"
        await cb.message.edit_text(metin, reply_markup=geri_btn())
    elif data == "geri":
        await cb.message.delete()
        await menu(_, cb.message)

def geri_btn(): return InlineKeyboardMarkup([[InlineKeyboardButton("◀️ Geri", callback_data="geri")]])

@app.on_message(filters.command("seviyeayar"))
async def seviye_ayarla(_, msg: Message):
    if not is_authorized(msg.from_user.id): return
    try:
        _, seviye, mesaj, süre, birim = msg.text.split()
        limits[int(seviye)] = {"msg": int(mesaj), "süre": parse_time_value(süre, birim)}
        save_json(LIMITS_FILE, limits)
        await msg.reply(f"✅ Seviye {seviye} ayarlandı.")
    except:
        await msg.reply("⚠️ Kullanım: /seviyeayar [seviye] [mesaj] [süre] [saniye/dakika/saat]")

@app.on_message(filters.command("hakayarla"))
async def hak_ayarla(_, msg: Message):
    if not is_authorized(msg.from_user.id): return
    try:
        global max_grant
        max_grant = int(msg.text.split()[1])
        await msg.reply(f"✅ Günlük hak: {max_grant}")
    except:
        await msg.reply("⚠️ Kullanım: /hakayarla [adet]")

@app.on_message(filters.command("seviyelistesi"))
async def seviye_listesi(_, msg: Message):
    if not is_authorized(msg.from_user.id): return
    if not limits: return await msg.reply("⚠️ Seviye ayarı yok.")
    metin = "📋 **Seviye Listesi:**\n"
    for seviye in sorted(limits.keys()):
        lim = limits[seviye]
        metin += f"🔹 Seviye {seviye}: {lim['msg']} mesaj → {lim['süre']} sn\n"
    await msg.reply(metin)

@app.on_message(filters.command("verisil"))
async def verileri_sil(_, msg: Message):
    if not is_authorized(msg.from_user.id): return
    user_data.clear(); user_msg_count.clear(); izin_sureleri.clear()
    save_json(USERDATA_FILE, convert_keys_to_str(user_data))
    save_json(COUNTS_FILE, convert_keys_to_str(user_msg_count))
    save_json(IZIN_FILE, convert_keys_to_str(izin_sureleri))
    await msg.reply("✅ Tüm kullanıcı verileri silindi.")

@app.on_message(filters.command("durumum"))
async def durum(_, msg: Message):
    uid, cid = msg.from_user.id, msg.chat.id
    key = f"({cid}, {uid})"
    if key not in user_data: return await msg.reply("ℹ️ Verin yok.")
    veri = user_data[key]
    seviye = veri["seviye"]
    if seviye not in limits: return await msg.reply("ℹ️ Seviyen tanımlı değil.")
    gereken = limits[seviye]["msg"]
    atilan = user_msg_count.get(key, 0)
    kalan = max(0, gereken - atilan)
    await msg.reply(
        f"👤 **Durum:**\n"
        f"🔹 Seviye: {seviye}\n"
        f"📨 Mesaj: {atilan}/{gereken}\n"
        f"⏳ Kalan: {kalan} mesaj\n"
        f"🎁 Günlük Hak: {veri['grant_count']}/{max_grant}"
    )

@app.on_message(filters.command("yetkiver") & filters.user(admin_id))
async def yetki_ver(_, msg: Message):
    if not msg.reply_to_message and len(msg.command) < 2:
        return await msg.reply("⚠️ Kullanım: /yetkiver @kullanici")
    uid = msg.reply_to_message.from_user.id if msg.reply_to_message else (await app.get_users(msg.command[1].lstrip("@"))).id
    yetkili_adminler.add(uid)
    save_json(ADMINS_FILE, list(yetkili_adminler))
    await msg.reply(f"✅ `{uid}` ID'li kullanıcıya yetki verildi.")

@app.on_message(filters.command("yetkial") & filters.user(admin_id))
async def yetki_al(_, msg: Message):
    if not msg.reply_to_message and len(msg.command) < 2:
        return await msg.reply("⚠️ Kullanım: /yetkial @kullanici")
    uid = msg.reply_to_message.from_user.id if msg.reply_to_message else (await app.get_users(msg.command[1].lstrip("@"))).id
    if uid == admin_id: return await msg.reply("❌ Bot sahibinin yetkisi alınamaz.")
    yetkili_adminler.discard(uid)
    save_json(ADMINS_FILE, list(yetkili_adminler))
    await msg.reply(f"🚫 `{uid}` ID'li kullanıcının yetkisi kaldırıldı.")

@app.on_message(filters.command("hakkinda"))
async def hakkinda(_, msg): await msg.reply("🤖 Aktiflik takip botu. Kullanıcıların mesaj sayılarına göre seviye atlayıp kısa süreli medya izni kazanmasını sağlar.")

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
            await msg.reply(f"🎉 Tebrikler! Seviye {seviye} tamamlandı. {lim['süre']} sn medya izni verildi.")
            try:
                await app.restrict_chat_member(cid, uid, ChatPermissions(can_send_media_messages=True))
                await asyncio.sleep(lim["süre"])
                await app.restrict_chat_member(cid, uid, ChatPermissions(can_send_media_messages=False))
                await msg.reply("⌛️ Sticker/GIF iznin sona erdi.")
            except Exception as e:
                await msg.reply(f"❌ Telegram hatası:\n{e}")
            save_json(USERDATA_FILE, convert_keys_to_str(user_data))
            save_json(COUNTS_FILE, convert_keys_to_str(user_msg_count))
            save_json(IZIN_FILE, convert_keys_to_str(izin_sureleri))

@app.on_chat_member_updated()
async def yeni_bot(_, cmu: ChatMemberUpdated):
    if cmu.new_chat_member and cmu.new_chat_member.user.id == (await app.get_me()).id:
        await app.send_message(cmu.chat.id, "👋 Selam! Aktiflik Takip Botuyum. Menü için /menu yazabilirsin.")

print("🚀 Bot başlatılıyor...")
app.run()
print("❌ Bot durdu.")
