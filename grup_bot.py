from pyrogram import Client, filters
from pyrogram.types import ChatPermissions, Message, ChatMemberUpdated, InlineKeyboardMarkup, InlineKeyboardButton, CallbackQuery
from pyrogram.enums import ChatMemberStatus
from datetime import datetime
import asyncio
import time
import json
import os
from dotenv import load_dotenv

---------- küçük yardımcılar ----------

def convert_keys_to_str(d):
return {str(k): v for k, v in d.items()}

def parse_time(val, unit):
return int(val) * {"saniye": 1, "dakika": 60, "saat": 3600}.get(unit, 1)

def str_tuple_to_tuple(s):
return tuple(map(int, s.strip("()").split(",")))

def load_json(path, default):
return json.load(open(path, "r", encoding="utf-8")) if os.path.exists(path) else default

def save_json(path, data):
json.dump(data, open(path, "w", encoding="utf-8"), indent=4, ensure_ascii=False)

---------- env ----------

load_dotenv()
api_id = int(os.getenv("API_ID"))
api_hash = os.getenv("API_HASH")
bot_token = os.getenv("BOT_TOKEN")
admin_id = int(os.getenv("OWNER_ID"))

---------- dosya yolları ----------

LIMITS_FILE = "limits.json"     # { chat_id: { seviye: {msg, süre} } }
USERDATA_FILE = "users.json"    # { "(chat_id, user_id)": {...} }
COUNTS_FILE = "counts.json"     # { "(chat_id, user_id)": sayi }
IZIN_FILE = "izinler.json"      # { "(chat_id, user_id)": bitis_ts }
ADMINS_FILE = "admins.json"     # { chat_id: [user_id, ...] }  -> GRUP BAZLI BOT-ADMIN
GRANTS_FILE = "grants.json"     # { chat_id: max_grant }       -> GRUP BAZLI HAK SAYISI

---------- veriyi yükle ----------

limits = {int(k): {int(sk): sv for sk, sv in v.items()} for k, v in load_json(LIMITS_FILE, {}).items()}
user_data = load_json(USERDATA_FILE, {})
user_msg_count = {str_tuple_to_tuple(k): v for k, v in load_json(COUNTS_FILE, {}).items()}
izin_sureleri = {str_tuple_to_tuple(k): v for k, v in load_json(IZIN_FILE, {}).items()}

GRUP BAZLI admin listesi

_raw_admins = load_json(ADMINS_FILE, {})
group_admins = {int(k): set(v) for k, v in _raw_admins.items()}  # {chat_id: set(user_ids)}

GRUP BAZLI max_grant

_raw_grants = load_json(GRANTS_FILE, {})
group_max_grant = {int(k): int(v) for k, v in _raw_grants.items()}
DEFAULT_MAX_GRANT = 2

---------- bot ----------

app = Client("bot", api_id=api_id, api_hash=api_hash, bot_token=bot_token, in_memory=True)

---------- yetki kontrol ----------

def get_chat_max_grant(chat_id: int) -> int:
return group_max_grant.get(chat_id, DEFAULT_MAX_GRANT)

def set_chat_max_grant(chat_id: int, val: int):
group_max_grant[chat_id] = int(val)
save_json(GRANTS_FILE, {str(k): v for k, v in group_max_grant.items()})

def is_group_bot_admin(chat_id: int, user_id: int) -> bool:
# owner her zaman geçerli
if user_id == admin_id:
return True
admins = group_admins.get(chat_id, set())
return user_id in admins

async def ensure_group_admin_bucket(chat_id: int):
if chat_id not in group_admins:
group_admins[chat_id] = set()
save_json(ADMINS_FILE, {str(k): list(v) for k, v in group_admins.items()})

async def add_group_admin(chat_id: int, user_id: int):
await ensure_group_admin_bucket(chat_id)
group_admins[chat_id].add(user_id)
save_json(ADMINS_FILE, {str(k): list(v) for k, v in group_admins.items()})

async def remove_group_admin(chat_id: int, user_id: int):
await ensure_group_admin_bucket(chat_id)
if user_id in group_admins[chat_id]:
group_admins[chat_id].remove(user_id)
save_json(ADMINS_FILE, {str(k): list(v) for k, v in group_admins.items()})

---------- /menu ----------

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

---------- callback ----------

@app.on_callback_query()
async def buton(_, cb: CallbackQuery):
data = cb.data
cid = cb.message.chat.id

if data == "kapat":  
    await cb.message.delete()  
    return  

elif data == "help":  
    await cb.message.edit_text(  
        "🆘 Yardım Menüsü:\n\n"  
        "🧱 /seviyeayar [seviye] [mesaj] [süre]\n"  
        " Örnek: /seviyeayar 2 10 1 dakika\n"  
        " ➡️ Seviye 2 için 10 mesaj ve 1 dakika medya izni tanımlar.\n\n"  
        "🎯 /hakayarla [adet]\n"  
        " ➡️ (Grup bazlı) Günlük maksimum izin sayısını belirler.\n\n"  
        "📊 /seviyelistesi\n"  
        " ➡️ Ayarlanmış tüm seviyeleri listeler.\n\n"  
        "🧹 /verisil\n"  
        " ➡️ Tüm kullanıcı verilerini sıfırlar. (Sadece bot-admin/owner)\n\n"  
        "📌 /durumum\n"  
        " ➡️ Seviyeniz, kalan mesaj ve hak durumunuz.\n\n"  
        "🛡️ /yetkiver @kullanici (veya mesajına yanıtla)\n"  
        "🚫 /yetkial @kullanici (veya mesajına yanıtla)\n"  
        " ➡️ (Grup bazlı) Bot-admin ekle/çıkar. Owner + o grubun bot-adminleri kullanabilir.\n\n"  
        "ℹ️ /hakkinda\n"  
        " ➡️ Bot hakkında bilgi.",  
        reply_markup=InlineKeyboardMarkup([[InlineKeyboardButton("◀️ Geri", callback_data="geri")]])  
    )  

elif data == "limits":  
    if cid not in limits or not limits[cid]:  
        await cb.message.edit_text(  
            "⚠️ Bu grupta ayarlanmış seviye yok.",  
            reply_markup=InlineKeyboardMarkup([[InlineKeyboardButton("◀️ Geri", callback_data="geri")]])  
        )  
        return  
    text = "📊 Seviye Listesi:\n\n"  
    for s in sorted(limits[cid].keys()):  
        l = limits[cid][s]  
        text += f"🔹 Seviye {s}: {l['msg']} mesaj → {l['süre']} sn izin\n"  
    await cb.message.edit_text(text, reply_markup=InlineKeyboardMarkup([[InlineKeyboardButton("◀️ Geri", callback_data="geri")]]))  

elif data == "settings":  
    gmax = get_chat_max_grant(cid)  
    await cb.message.edit_text(  
        f"⚙️ Ayarlar (Grup Bazlı)\n\n"  
        f"🎁 Günlük hak: {gmax}\n"  
        "➡️ /hakayarla [adet]",  
        reply_markup=InlineKeyboardMarkup([[InlineKeyboardButton("◀️ Geri", callback_data="geri")]])  
    )  

elif data == "adminlistesi":  
    await ensure_group_admin_bucket(cid)  
    metin = "👥 Bot-Adminler (Bu Grup):\n"  
    showed = False  
    for uid in group_admins.get(cid, set()):  
        if uid == admin_id:  
            continue  # owner gizli  
        try:  
            u = await app.get_users(uid)  
            if u.username:  
                metin += f"• @{u.username}\n"  
            else:  
                metin += f"• {u.first_name}\n"  
            showed = True  
        except:  
            continue  
    if not showed:  
        metin += "• (boş)\n"  
    await cb.message.edit_text(metin, reply_markup=InlineKeyboardMarkup([[InlineKeyboardButton("◀️ Geri", callback_data="geri")]]))  

elif data == "geri":  
    await cb.message.delete()  
    await menu(_, cb.message)

---------- komutlar ----------

@app.on_message(filters.command("seviyeayar"))
async def set_limit(_, msg: Message):
cid = msg.chat.id
uid = msg.from_user.id
if not is_group_bot_admin(cid, uid):
return
try:
_, seviye, mesaj, süre_deger, süre_birim = msg.text.split()
sure_saniye = parse_time(int(süre_deger), süre_birim)
if cid not in limits:
limits[cid] = {}
limits[cid][int(seviye)] = {"msg": int(mesaj), "süre": sure_saniye}
save_json(LIMITS_FILE, {str(k): v for k, v in limits.items()})
await msg.reply(f"✅ Seviye {seviye} ayarlandı.")
except Exception:
await msg.reply("⚠️ Kullanım: /seviyeayar [seviye] [mesaj] [saniye|dakika|saat]")

@app.on_message(filters.command("hakayarla"))
async def set_grant(_, msg: Message):
cid = msg.chat.id
uid = msg.from_user.id
if not is_group_bot_admin(cid, uid):
return
try:
adet = int(msg.text.split()[1])
set_chat_max_grant(cid, adet)
await msg.reply(f"✅ (Grup) Günlük hak: {adet}")
except Exception:
await msg.reply("⚠️ Kullanım: /hakayarla [adet]")

@app.on_message(filters.command("verisil"))
async def reset_all(_, msg: Message):
cid = msg.chat.id
uid = msg.from_user.id
if not is_group_bot_admin(cid, uid):
return
# SADECE BU GRUBUN verilerini temizle
# user_data / counts / izinler tuple key'li: (cid, uid)
keys_ud = [k for k in list(user_data.keys()) if k.startswith(f"({cid},")]
for k in keys_ud:
user_data.pop(k, None)

keys_uc = [k for k in list(user_msg_count.keys()) if k[0] == cid]  
for k in keys_uc:  
    user_msg_count.pop(k, None)  

keys_iz = [k for k in list(izin_sureleri.keys()) if k[0] == cid]  
for k in keys_iz:  
    izin_sureleri.pop(k, None)  

save_json(USERDATA_FILE, convert_keys_to_str(user_data))  
save_json(COUNTS_FILE, convert_keys_to_str(user_msg_count))  
save_json(IZIN_FILE, convert_keys_to_str(izin_sureleri))  
await msg.reply("✅ Bu grubun kullanıcı verileri silindi.")

@app.on_message(filters.command("durumum"))
async def user_status(_, msg: Message):
uid, cid = msg.from_user.id, msg.chat.id
key = f"({cid}, {uid})"
if key not in user_data:
return await msg.reply("ℹ️ Kayıtlı verin yok.")
veri = user_data[key]
sev = veri["seviye"]
gerek = limits.get(cid, {}).get(sev, {}).get("msg", 0)
atilan = user_msg_count.get((cid, uid), 0)
kalan = max(0, gerek - atilan)
gmax = get_chat_max_grant(cid)
await msg.reply(
f"👤 Durum Bilgin (Bu Grup):\n"
f"🔹 Seviye: {sev}\n"
f"📨 Mesaj: {atilan}/{gerek}\n"
f"⏳ Kalan: {kalan}\n"
f"🎁 Hak: {veri['grant_count']}/{gmax}"
)

/yetkiver ve /yetkial: owner + o grubun bot-adminleri kullanabilir. Etki sadece o grup.

@app.on_message(filters.command("yetkiver"))
async def add_admin_cmd(_, msg: Message):
cid = msg.chat.id
uid = msg.from_user.id
if not is_group_bot_admin(cid, uid):
return await msg.reply("❌ Yetkin yok.")
target_id = None
try:
if msg.reply_to_message:
target_id = msg.reply_to_message.from_user.id
elif len(msg.command) >= 2:
target_id = (await app.get_users(msg.command[1].lstrip("@"))).id
else:
return await msg.reply("⚠️ Yanıtla veya kullanıcı adı gir.")
await add_group_admin(cid, target_id)
await msg.reply(f"✅ {target_id} bu grup için bot-admin yapıldı.")
except Exception as e:
await msg.reply(f"❌ Hata: {e}")

@app.on_message(filters.command("yetkial"))
async def remove_admin_cmd(_, msg: Message):
cid = msg.chat.id
uid = msg.from_user.id
if not is_group_bot_admin(cid, uid):
return await msg.reply("❌ Yetkin yok.")
try:
if msg.reply_to_message:
target_id = msg.reply_to_message.from_user.id
elif len(msg.command) >= 2:
target_id = (await app.get_users(msg.command[1].lstrip("@"))).id
else:
return await msg.reply("⚠️ Yanıtla veya kullanıcı adı gir.")
if target_id == admin_id:
return await msg.reply("❌ Owner kaldırılamaz.")
await remove_group_admin(cid, target_id)
await msg.reply(f"🚫 {target_id} bu grupta bot-admin listesinden çıkarıldı.")
except Exception as e:
await msg.reply(f"❌ Hata: {e}")

--- seviye listesi komutu (grup bazlı) ---

@app.on_message(filters.command("seviyelistesi"))
async def seviyelistesi_cmd(_, msg: Message):
cid = msg.chat.id
if cid not in limits or not limits[cid]:
return await msg.reply("⚠️ Bu grupta ayarlanmış seviye yok.")
text = "📊 Seviye Listesi (Bu Grup):\n\n"
for s in sorted(limits[cid].keys()):
l = limits[cid][s]
text += f"🔹 Seviye {s}: {l['msg']} mesaj → {l['süre']} sn izin\n"
await msg.reply(text)

@app.on_message(filters.command("hakkinda"))
async def about_info(_, msg: Message):
await msg.reply("🤖 Medya Kontrol Botu\nMesaj sayısına göre medya erişimi verir.\n🛠 Geliştirici: @Ankateamiletisim")

@app.on_message(filters.private & filters.command("start"))
async def start_command(_, msg: Message):
btn = InlineKeyboardMarkup([
[InlineKeyboardButton("➕ Gruba Ekle", url=f"https://t.me/{(await app.get_me()).username}?startgroup=true")],
])
await msg.reply(
"👋 Selam! Ben Medya Kontrol botuyum. Mesajlara göre medya izni verir, pasifliği bitiririm.\n\n"
"👇 Aşağıdan beni grubuna ekle:",
reply_markup=btn
)

---------- mesaj takibi ----------

@app.on_message(filters.group & ~filters.service)
async def takip_et(_, msg: Message):
uid, cid = msg.from_user.id, msg.chat.id
if is_group_bot_admin(cid, uid):
return

key = f"({cid}, {uid})"  
now = time.time()  
today = str(datetime.now().date())  

if key not in user_data or user_data[key]["date"] != today:  
    user_data[key] = {"seviye": 0, "grant_count": 0, "date": today}  
    user_msg_count[(cid, uid)] = 0  

# izin penceresi aktifse sayaç artmasın  
if now < izin_sureleri.get((cid, uid), 0):  
    return  

# sayaç artır  
user_msg_count[(cid, uid)] += 1  

grup_limitleri = limits.get(cid, {})  
for seviye in sorted(grup_limitleri.keys()):  
    lim = grup_limitleri[seviye]  
    if (user_msg_count[(cid, uid)] >= lim["msg"]   
        and seviye > user_data[key]["seviye"]  
        and user_data[key]["grant_count"] < get_chat_max_grant(cid)):  

        user_data[key]["seviye"] = seviye  
        user_data[key]["grant_count"] += 1  
        user_msg_count[(cid, uid)] = 0  
        izin_sureleri[(cid, uid)] = now + lim["süre"]  

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

# kalıcı kaydet  
save_json(USERDATA_FILE, convert_keys_to_str(user_data))  
save_json(COUNTS_FILE, convert_keys_to_str(user_msg_count))  
save_json(IZIN_FILE, convert_keys_to_str(izin_sureleri))

---------- gruba eklenme olayı ----------

@app.on_chat_member_updated()
async def yeni_katilim(_, cmu: ChatMemberUpdated):
try:
me = await app.get_me()
# bot gruba yeni eklendiyse
if cmu.new_chat_member and cmu.new_chat_member.user.id == me.id:
cid = cmu.chat.id
await ensure_group_admin_bucket(cid)

adder_id = None  
        # ekleyen kullanıcıyı bulmayı dene  
        if cmu.from_user:  
            adder_id = cmu.from_user.id  

        if adder_id:  
            await add_group_admin(cid, adder_id)  
            try:  
                u = await app.get_users(adder_id)  
                who = f"@{u.username}" if u.username else f"{u.first_name}"  
            except:  
                who = str(adder_id)  
            await app.send_message(  
                cid,  
                f"✅ Bot eklendi. {who} bu grup için bot-admin yapıldı."  
            )  
        else:  
            # ekleyeni bulamadık -> ban yetkisi olan ilk yöneticiyi seç  
            chosen = None  
            async for m in app.get_chat_members(cid, filter="administrators"):  
                # skip botların kendisi  
                if m.user.is_bot:  
                    continue  
                perms = m.privileges  
                # can_restrict_members varsa uygundur  
                if perms and getattr(perms, "can_restrict_members", False):  
                    chosen = m.user.id  
                    break  
            if chosen:  
                await add_group_admin(cid, chosen)  
                try:  
                    u = await app.get_users(chosen)  
                    who = f"@{u.username}" if u.username else f"{u.first_name}"  
                except:  
                    who = str(chosen)  
                await app.send_message(  
                    cid,  
                    f"ℹ️ Botu kimin eklediğini bulamadım. "  
                    f"Ban yetkisi olan ilk yöneticiyi bot-admin yaptım: {who}"  
                )  
            else:  
                await app.send_message(  
                    cid,  
                    "⚠️ Bot-admin atayamadım. Bir yönetici /yetkiver ile bot-admin belirlesin."  
                )  

        # bilgilendirme  
        await app.send_message(  
            cid,  
            "👋 Selam! Bu grupta aktiflikleri takip edeceğim.\n\n"  
            "✅ Sağlıklı çalışmam için aşağıdaki izinler gerekli:\n"  
            "• Kullanıcıları kısıtlama (Ban yetkisi)\n"  
            "• Mesaj silme\n\n"  
            "🔧 Bu izinleri grup ayarlarından bana vermezsen görevimi yapamam.\n"  
            "/menu komutu ile başlayabilirsin."  
        )  
except Exception as e:  
    print("on_chat_member_updated error:", e)

---------- başlangıç ----------

print("🚀 Bot başlatılıyor...")
app.run()
