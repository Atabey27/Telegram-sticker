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

limits = {int(k): v for k, v in load_json(LIMITS_FILE, {}).items()}
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
    if data == "kapat":
        await cb.message.delete()
        return
    elif data == "help":
        await cb.message.edit_text(
            "**🆘 Yardım Menüsü:**\n\n"
            "🧱 `/seviyeayar [seviye] [mesaj] [süre] [birim]`\n"
            " Örnek: `/seviyeayar 2 10 1 dakika`\n"
            " ➡️ Seviye 2 için 10 mesaj ve 1 dakika medya izni tanımlar.\n\n"
            "🎯 `/hakayarla [adet]`\n"
            " ➡️ Kullanıcının bir gün içinde alabileceği maksimum izin sayısını belirler.\n\n"
            "📊 `/seviyelistesi`\n"
            " ➡️ Ayarlanmış tüm seviyeleri listeler.\n\n"
            "🧹 `/verisil`\n"
            " ➡️ Tüm kullanıcı verilerini sıfırlar. (Yalnızca yetkililer)\n\n"
            "📌 `/durumum`\n"
            " ➡️ Seviyenizi, kalan mesaj sayınızı ve haklarınızı gösterir.\n\n"
            "🛡️ `/yetkiver @kullanici`\n"
            " ➡️ Kullanıcıya yetki verir. (Sadece bot sahibi)\n\n"
            "🚫 `/yetkial @kullanici`\n"
            " ➡️ Kullanıcının yetkisini alır. (Sadece bot sahibi)\n\n"
            "ℹ️ `/hakkinda`\n"
            " ➡️ Bot hakkında bilgi verir.",
            reply_markup=InlineKeyboardMarkup([[InlineKeyboardButton("◀️ Geri", callback_data="geri")]])
        )
    elif data == "limits":
        if not limits:
            await cb.message.edit_text("⚠️ Ayarlanmış seviye yok.", reply_markup=InlineKeyboardMarkup([[InlineKeyboardButton("◀️ Geri", callback_data="geri")]]))
            return
        text = "📊 **Seviye Listesi:**\n\n"
        for s in sorted(limits.keys()):
            l = limits[s]
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
        _, seviye, mesaj, süre_deger, süre_birim = msg.text.split()
        sure_saniye = parse_time(int(süre_deger), süre_birim)
        limits[int(seviye)] = {"msg": int(mesaj), "süre": sure_saniye}
        save_json(LIMITS_FILE, limits)
        await msg.reply(f"✅ Seviye {seviye} ayarlandı.")
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
    user_data.clear(); user_msg_count.clear(); izin_sureleri.clear()
    save_json(USERDATA_FILE, convert_keys_to_str(user_data))
    save_json(COUNTS_FILE, convert_keys_to_str(user_msg_count))
    save_json(IZIN_FILE, convert_keys_to_str(izin_sureleri))
    await msg.reply("✅ Tüm kullanıcı verileri silindi.")

@app.on_message(filters.command("seviyelistesi"))
async def list_limits(_, msg):
    if not is_authorized(msg.from_user.id): return
    if not limits:
        await msg.reply("⚠️ Henüz seviye ayarı yapılmamış.")
        return
    text = "📋 **Seviye Listesi:**\n"
    for s in sorted(limits.keys()):
        l = limits[s]
        text += f"🔹 Seviye {s}: {l['msg']} mesaj → {l['süre']} sn\n"
    await msg.reply(text)

@app.on_message(filters.command("durumum"))
async def user_status(_, msg):
    uid, cid = msg.from_user.id, msg.chat.id
    key = f"({cid}, {uid})"
    if key not in user_data: return await msg.reply("ℹ️ Kayıtlı verin yok.")
    veri = user_data[key]
    sev = veri["seviye"]
    gerek = limits.get(sev, {}).get("msg", 0)
    atilan = user_msg_count.get(key, 0)
    kalan = max(0, gerek - atilan)
    await msg.reply(f"👤 **Durum Bilgin:**\n🔹 Seviye: {sev}\n📨 Mesaj: {atilan}/{gerek}\n⏳ Kalan: {kalan}\n🎁 Hak: {veri['grant_count']}/{max_grant}")

@app.on_message(filters.command("yetkiver") & filters.user(admin_id))
async def add_admin(_, msg):
    if not msg.reply_to_message and len(msg.command) < 2: return await msg.reply("⚠️ Yanıtla veya kullanıcı adı gir.")
    uid = msg.reply_to_message.from_user.id if msg.reply_to_message else (await app.get_users(msg.command[1].lstrip("@"))).id
    yetkili_adminler.add(uid)
    save_json(ADMINS_FILE, list(yetkili_adminler))
    await msg.reply(f"✅ `{uid}` yetkili yapıldı.")

@app.on_message(filters.command("yetkial") & filters.user(admin_id))
async def remove_admin(_, msg):
    if not msg.reply_to_message and len(msg.command) < 2: return await msg.reply("⚠️ Yanıtla veya kullanıcı adı gir.")
    uid = msg.reply_to_message.from_user.id if msg.reply_to_message else (await app.get_users(msg.command[1].lstrip("@"))).id
    if uid == admin_id: return await msg.reply("❌ Bot sahibi kaldırılamaz.")
    yetkili_adminler.discard(uid)
    save_json(ADMINS_FILE, list(yetkili_adminler))
    await msg.reply(f"🚫 `{uid}` yetkisi alındı.")

@app.on_message(filters.command("hakkinda"))
async def about_info(_, msg):
    await msg.reply("🤖 Aktiflik Botu\nKullanıcıların mesajlarıyla seviye atlamasını sağlar ve süreli medya izni verir.\n🛠 Geliştirici: @Atabey27")

@app.on_message(filters.private & filters.command("start"))
async def start_command(_, msg):
    btn = InlineKeyboardMarkup([
        [InlineKeyboardButton("➕ Gruba Ekle", url=f"https://t.me/{(await app.get_me()).username}?startgroup=true")],
    ])
    await msg.reply(
        "👋 Selam! Ben aktiflik botuyum. Beni bir gruba ekleyerek mesajlara göre kullanıcıları takip edebilirim.\n\n"
        "👇 Hemen aşağıdan beni grubuna ekle:",
        reply_markup=btn
    )

@app.on_message(filters.group & ~filters.service)
async def takip_et(_, msg):
    uid, cid = msg.from_user.id, msg.chat.id
    if uid in yetkili_adminler: return
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
    if cmu.new_chat_member and cmu.new_chat_member.user.id == (await app.get_me()).id:
        await app.send_message(
            cmu.chat.id,
            "👋 Selam! Ben bu grupta aktiflikleri takip edeceğim.\n\n"
            "✅ Sağlıklı çalışmam için aşağıdaki izinleri vermen gerekiyor:\n"
            "• Kullanıcıları kısıtlama (mute/izin verme)\n"
            "• Mesaj silme\n\n"
            "🔧 Bu izinleri **grup ayarlarından** bana vermezsen görevimi yapamam.\n"
            "`\n/menu` komutu ile başlayabilirsin."
        )

print("🚀 Bot başlatılıyor...")
app.run()
