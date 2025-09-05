from pyrogram import Client, filters
from pyrogram.types import ChatPermissions, Message, ChatMemberUpdated, InlineKeyboardMarkup, InlineKeyboardButton, CallbackQuery
from pyrogram.enums import ChatMemberStatus
from datetime import datetime
import asyncio
import time
import json
import os
from dotenv import load_dotenv
import random
from pyrogram.enums import ChatMembersFilter, ChatMemberStatus, ChatType
# ---- NSFW/Sticker analiz bağımlılıkları
from nudenet import NudeDetector
from PIL import Image
import numpy as np
import cv2

# Lottie (.tgs) için pure-python
try:
    from lottie import importers as lottie_importers
    from lottie import exporters as lottie_exporters
    LOTTIE_OK = True
except Exception as _e:
    LOTTIE_OK = False
    print("Lottie kullanılamıyor:", _e)

# ---------- küçük yardımcılar ----------
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

def saniyeyi_donustur(saniye):
    saniye = int(saniye)
    if saniye < 60:
        return f"{saniye} saniye"
    dakika, saniye = divmod(saniye, 60)
    saat, dakika = divmod(dakika, 60)
    metin = ""
    if saat > 0: metin += f"{saat} saat "
    if dakika > 0: metin += f"{dakika} dakika "
    if saniye > 0 and saat == 0: metin += f"{saniye} saniye"
    return metin.strip()



DEBUG = False


# ---------- genel ayarlar ----------

# ---------- HAZIR AYARLAR ----------
HAZIR_AYARLAR = {
    "standart": {
        "limits": {
            "0": {"msg": 1, "süre": 1},
            "1": {"msg": 15, "süre": 180},
            "2": {"msg": 50, "süre": 300},
            "3": {"msg": 100, "süre": 420},
            "4": {"msg": 150, "süre": 1800},
            "5": {"msg": 250, "süre": 3600},
            "6": {"msg": 350, "süre": 4500},
            "7": {"msg": 450, "süre": 5400},
            "8": {"msg": 550, "süre": 6300},
            "9": {"msg": 750, "süre": 6600},
            "10": {"msg": 1000, "süre": 7200}
        },
        "grant": 10  # Günlük maksimum hak
    },
    "hızlı": {
        "limits": {
            "0": {"msg": 1, "süre": 1},
            "1": {"msg": 10, "süre": 120},
            "2": {"msg": 30, "süre": 240},
            "3": {"msg": 60, "süre": 360},
            "4": {"msg": 100, "süre": 600}
        },
        "grant": 5  # Günlük maksimum hak
    },
    "yavaş": {
        "limits": {
            "0": {"msg": 1, "süre": 1},
            "1": {"msg": 20, "süre": 300},
            "2": {"msg": 50, "süre": 600},
            "3": {"msg": 100, "süre": 1200},
            "4": {"msg": 200, "süre": 2400},
            "5": {"msg": 500, "süre": 3600}
        },
        "grant": 3  # Günlük maksimum hak
    }
}

# ---------- env ----------
load_dotenv()
api_id = int(os.getenv("API_ID"))
api_hash = os.getenv("API_HASH")
bot_token = os.getenv("BOT_TOKEN")
admin_id = int(os.getenv("OWNER_ID"))

# ---------- dosya yolları ----------
LIMITS_FILE = "limits.json"
USERDATA_FILE = "users.json"
COUNTS_FILE = "counts.json"
IZIN_FILE = "izinler.json"
ADMINS_FILE = "admins.json"
GRANTS_FILE = "grants.json"
GLOBAL_SCORE_FILE = "global_score.json"
THRESHOLDS_FILE = "thresholds.json"
ANNOUNCE_FILE = "announce.json"

# ---------- veriyi yükle ----------
limits = {int(k): {int(sk): sv for sk, sv in v.items()} for k, v in load_json(LIMITS_FILE, {}).items()}
user_data = load_json(USERDATA_FILE, {})
user_msg_count = {str_tuple_to_tuple(k): v for k, v in load_json(COUNTS_FILE, {}).items()}
izin_sureleri = {str_tuple_to_tuple(k): v for k, v in load_json(IZIN_FILE, {}).items()}
_raw_admins = load_json(ADMINS_FILE, {})
group_admins = {int(k): set(v) for k, v in _raw_admins.items()}
_raw_grants = load_json(GRANTS_FILE, {})
group_max_grant = {int(k): int(v) for k, v in _raw_grants.items()}
DEFAULT_MAX_GRANT = 2
# ---------- SPAM KORUMA ----------
user_media_bucket = {}  # { (chat_id, user_id): {"tokens": X, "last_update": timestamp} }
MEDIA_BUCKET_MAX = 1    # 5 saniye içinde maksimum medya sayısı
MEDIA_BUCKET_REFILL = 0.3333 # Her saniye yenilenen token sayısı (daha yavaş)
last_warning_time = {}  # Son uyarı zamanlarını tutar
# ---------- global güvenlik skoru ----------
DEFAULT_SCORE = 0.90
global_security_score = DEFAULT_SCORE
def load_global_score():
    global global_security_score
    if os.path.exists(GLOBAL_SCORE_FILE):
        data = load_json(GLOBAL_SCORE_FILE, {"score": DEFAULT_SCORE})
        global_security_score = float(data.get("score", DEFAULT_SCORE))
    else:
        save_json(GLOBAL_SCORE_FILE, {"score": DEFAULT_SCORE})
        global_security_score = DEFAULT_SCORE
def save_global_score(new_score: float):
    global global_security_score
    global_security_score = float(new_score)
    save_json(GLOBAL_SCORE_FILE, {"score": global_security_score})

# ---------- NSFW thresholds kalıcı ayarları ----------
DEFAULT_THRESHOLDS = {
    "HARD_THRESHOLD": 0.85,
    "SOFT_THRESHOLD": 0.55,
    "SOFT_HITS_REQUIRED": 2,
    "MIN_SIDE": 512,
    "GIF_MAX_FRAMES": 6,
    "GIF_STEP": 2,
    "KISS_THRESHOLD": 0.33,
    "DEBUG": False
}
def load_thresholds():
    if os.path.exists(THRESHOLDS_FILE):
        try:
            data = load_json(THRESHOLDS_FILE, DEFAULT_THRESHOLDS)
            for k, v in DEFAULT_THRESHOLDS.items():
                data.setdefault(k, v)
            return data
        except Exception:
            return DEFAULT_THRESHOLDS.copy()
    else:
        save_json(THRESHOLDS_FILE, DEFAULT_THRESHOLDS)
        return DEFAULT_THRESHOLDS.copy()
def save_thresholds(d):
    out = {k: d.get(k, DEFAULT_THRESHOLDS[k]) for k in DEFAULT_THRESHOLDS}
    save_json(THRESHOLDS_FILE, out)
THR = load_thresholds()

def thresholds_summary():
    return (f"⚙️ Eşikler/Ayarlar:\n"
            f"• HARD: {THR['HARD_THRESHOLD']}\n"
            f"• SOFT: {THR['SOFT_THRESHOLD']}\n"
            f"• HITS: {THR['SOFT_HITS_REQUIRED']}\n"
            f"• MIN_SIDE: {THR['MIN_SIDE']}\n"
            f"• GIF_MAX_FRAMES: {THR['GIF_MAX_FRAMES']}\n"
            f"• GIF_STEP: {THR['GIF_STEP']}\n"
            f"• KISS_THRESHOLD: {THR['KISS_THRESHOLD']}\n"
            f"• DEBUG: {THR['DEBUG']}")

def _try_float(x):
    try:
        return float(str(x).replace(",", "."))
    except:
        return None

# ---------- /bilgi kalıcılığı (grup bazlı) ----------
announce_map = load_json(ANNOUNCE_FILE, {})
def get_announce(chat_id: int) -> bool:
    return bool(announce_map.get(str(chat_id), True))
def set_announce(chat_id: int, val: bool):
    announce_map[str(chat_id)] = bool(val)
    save_json(ANNOUNCE_FILE, announce_map)

def announce_text(chat_id: int) -> str:
    return "Açık" if get_announce(chat_id) else "Kapalı"

# ---------- varsayılan seviye (0 -> 1 mesaj / 1 saniye) ----------
def ensure_default_level_for(chat_id: int):
    """Varsayılan seviyeyi ekler, ancak sadece gerçekten yoksa"""
    if chat_id not in limits:
        limits[chat_id] = {}
    # Sadece seviye 0 yoksa ekle
    if 0 not in limits[chat_id]:
        limits[chat_id][0] = {"msg": 1, "süre": 1}
        save_json(LIMITS_FILE, {str(k): v for k, v in limits.items()})

# Başlangıçta tüm gruplar için varsayılan seviyeyi kontrol et
_any_change = False
for _cid in list(limits.keys()):
    if 0 not in limits[_cid]:
        limits[_cid][0] = {"msg": 1, "süre": 1}
        _any_change = True
if _any_change:
    save_json(LIMITS_FILE, {str(k): v for k, v in limits.items()})

# ---------- bot ----------
app = Client("bot", api_id=api_id, api_hash=api_hash, bot_token=bot_token, in_memory=True)

# ---------- YETKİ KONTROL MEKANİZMASI ----------

def is_group_bot_admin(chat_id: int, user_id: int) -> bool:
    """Sadece botun kendi özel yönetici listesini kontrol eder."""
    if user_id == admin_id: return True
    admins = group_admins.get(chat_id, set())
    return user_id in admins


async def is_user_authorized(client, chat_id, user_id):
    """NİHAİ KONTROL: Bot sahibi, özel bot yöneticisi VEYA Telegram grup yöneticisi olup olmadığını kontrol eder."""
    
    # ✅ ÖNCE admin listesini senkronize et (EN ÖNEMLİ KISIM)
    await sync_bot_admins_with_telegram(client, chat_id)

    # 1. Bot Sahibi mi?
    if user_id == admin_id:
        return True
    
    # 2. ÖNCE Telegram grubunun kurucusu veya yöneticisi mi?
    try:
        member = await client.get_chat_member(chat_id, user_id)
        if member.status in [ChatMemberStatus.OWNER, ChatMemberStatus.ADMINISTRATOR]:
            return True
    except Exception as e:
        print(f"Telegram yetki kontrolü sırasında hata: {e}")
    
    # 3. SONRA bota özel yönetici listesinde mi?
    if is_group_bot_admin(chat_id, user_id):
        return True
    
    return False


# ---------- YETKİ YÖNETİMİ ----------
def get_chat_max_grant(chat_id: int) -> int:
    return group_max_grant.get(chat_id, DEFAULT_MAX_GRANT)
def set_chat_max_grant(chat_id: int, val: int):
    group_max_grant[chat_id] = int(val)
    save_json(GRANTS_FILE, {str(k): v for k, v in group_max_grant.items()})

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

# ---------- MENÜ VE BUTONLAR ----------

@app.on_message(filters.command("menu"))
async def menu(_, msg: Message):
    if msg.chat.type in ("supergroup", "group"):
        if not await is_user_authorized(app, msg.chat.id, msg.from_user.id):
            return
    btn = InlineKeyboardMarkup([
        [InlineKeyboardButton("📋 Yardım Menüsü", callback_data="help")],
        [InlineKeyboardButton("📊 Seviye Listesi", callback_data="limits")],
        [InlineKeyboardButton("⚙️ Ayarlar", callback_data="settings")],
        [InlineKeyboardButton("👥 Admin Listesi", callback_data="adminlistesi")],
        [InlineKeyboardButton("📖 Bot Açıklaması", callback_data="aciklama")],
        [InlineKeyboardButton("❌ Kapat", callback_data="kapat")]
        
    ])
    await msg.reply("👋 Merhaba! Aşağıdan bir seçenek seç:", reply_markup=btn)

def build_settings_markup(chat_id: int):
    gmax = get_chat_max_grant(chat_id)
    text = (
        f"⚙️ Ayarlar\n\n"
        f"🛡️ **Global Güvenlik Seviyesi: {global_security_score}** (%{int(global_security_score*100)})\n"
        f"{thresholds_summary()}\n"
        f"🎁 Gruba Özel Günlük Hak: {gmax}\n\n"
        "➡️ Değiştirmek için komutları kullanın:\n"
        "`/guvenlik [değer]` (Sadece Bot Sahibi)\n"
        "`/hakayarla [adet]`\n"
        "`/minside`\n"
        "`/gifmax`\n"
        "`/gifstep`\n"
        "`/kiss`\n"
        "`/hard`\n"
        "`/soft`\n"
        "`/hits`\n\n"
        "➡️ Gruplar için Hazır seviye ayarlarını uygulamak için`\n"
        "`/ayaruygula [grup_id]` komutunu kullanın.(Sadece Bot Sahibi)"
    )
    keyboard = InlineKeyboardMarkup([
        [InlineKeyboardButton(f"Bilgi Mesajları: {announce_text(chat_id)}", callback_data="toggle_announce")],
        [InlineKeyboardButton("◀️ Geri", callback_data="geri")]
    ])
    return text, keyboard

@app.on_callback_query()
async def buton(_, cb: CallbackQuery):
    from pyrogram.enums import ChatType
    # Özel mesajlarda yetki kontrolü yapma - enum ile karşılaştırma yap
    if cb.message.chat.type in (ChatType.SUPERGROUP, ChatType.GROUP):
        
        is_authorized = await is_user_authorized(app, cb.message.chat.id, cb.from_user.id)
        
        if not is_authorized:
            await cb.answer("Bu butonları sadece grup yöneticileri kullanabilir.", show_alert=True)
            return
    
    cid = cb.message.chat.id
    data = cb.data
    
    if data == "kapat":
        await cb.message.delete()
        return

    elif data == "help":
        await cb.message.edit_text(
            "🆘 Yardım Menüsü:\n\n"
            "🧱 /seviyeayar [seviye] [mesaj] [süre]\n"
            " ➡️ Örnek: /seviyeayar 2 10 1 dakika\n\n"
            "🎯 /hakayarla [adet]\n"
            " ➡️ Günlük maksimum izin sayısını belirler.\n\n"
            "🧹 /verisil\n"
            " ➡️ Bu grubun kullanıcı verilerini sıfırlar.\n\n"
            "🗑️ /seviyelerisil\n"
            " ➡️ Bu gruptaki TÜM seviye tanımlarını siler.\n\n"
            "📊 /seviyelistesi\n"
            " ➡️ Ayarlanmış tüm seviyeleri listeler.\n\n"
            "📌 /durumum\n"
            " ➡️ Seviyeniz ve kalan hak durumunuz.\n\n"
            "➕ /yetkiver & ➖ /yetkial\n"
            " ➡️ Bot-admin ekle/çıkar.\n\n"
            "🆘 /hakkinda\n"
            " ➡️ Bot hakkında bilgi verir.",

            reply_markup=InlineKeyboardMarkup([[InlineKeyboardButton("◀️ Geri", callback_data="geri")]])
        )

    elif data == "limits":
        ensure_default_level_for(cid)
        if cid not in limits or not limits[cid]:
            return await cb.message.edit_text("⚠️ Bu grupta ayarlanmış seviye yok.",
                                              reply_markup=InlineKeyboardMarkup([[InlineKeyboardButton("◀️ Geri", callback_data="geri")]]))
        text = "📊 Seviye Listesi:\n\n"
        for s in sorted(limits[cid].keys()):
            l = limits[cid][s]
            sure_metni = saniyeyi_donustur(l['süre'])
            text += f"🔹 Seviye {s}: {l['msg']} mesaj → {sure_metni} izin\n"
        await cb.message.edit_text(text, reply_markup=InlineKeyboardMarkup([[InlineKeyboardButton("◀️ Geri", callback_data="geri")]]))

    elif data == "settings":
        text, keyboard = build_settings_markup(cid)
        await cb.message.edit_text(text, reply_markup=keyboard)
    
    elif data == "toggle_announce":
        set_announce(cid, not get_announce(cid))
        text, keyboard = build_settings_markup(cid)
        try:
            await cb.message.edit_text(text, reply_markup=keyboard)
            await cb.answer("Bilgi mesajı ayarı değiştirildi.")
        except:
            await cb.answer("Ayarlar güncel.")

    elif data == "adminlistesi":
        await ensure_group_admin_bucket(cid)
        metin = "👥 Bot-Adminler (Bu Grup):\n"
        showed = False
        for uid in group_admins.get(cid, set()):
            if uid == admin_id: continue
            try:
                u = await app.get_users(uid)
                metin += f"• @{u.username}\n" if u.username else f"• {u.first_name}\n"
                showed = True
            except:
                continue
        if not showed:
            metin += "• (boş)\n"
        await cb.message.edit_text(metin, reply_markup=InlineKeyboardMarkup([[InlineKeyboardButton("◀️ Geri", callback_data="geri")]]))

    elif data == "geri":
        try:
            await cb.message.delete()
        except:
            pass
        # Geri butonuna basıldığında menüyü tekrar göster
        btn = InlineKeyboardMarkup([
            [InlineKeyboardButton("📋 Yardım Menüsü", callback_data="help")],
            [InlineKeyboardButton("📊 Seviye Listesi", callback_data="limits")],
            [InlineKeyboardButton("⚙️ Ayarlar", callback_data="settings")],
            [InlineKeyboardButton("👥 Admin Listesi", callback_data="adminlistesi")],
            [InlineKeyboardButton("📖 Bot Açıklaması", callback_data="aciklama")],
            [InlineKeyboardButton("❌ Kapat", callback_data="kapat")]
        ])
        await cb.message.reply("👋 Merhaba! Aşağıdan bir seçenek seç:", reply_markup=btn)

    # HAZIR AYAR BUTONLARI
    elif data.startswith("hazır_"):
        ayar_tipi = data.split("_")[1]
        
        if ayar_tipi == "iptal":
            await cb.message.delete()
            await cb.answer("İşlem iptal edildi.")
            return
        
        if ayar_tipi in HAZIR_AYARLAR:
            # Hazır ayarı uygula - limits kısmını al
            limits[cid] = {int(k): v for k, v in HAZIR_AYARLAR[ayar_tipi]["limits"].items()}
            # Grant (hak) ayarını da uygula
            group_max_grant[cid] = HAZIR_AYARLAR[ayar_tipi]["grant"]
            
            # Her ikisini de kaydet
            save_json(LIMITS_FILE, {str(k): v for k, v in limits.items()})
            save_json(GRANTS_FILE, {str(k): v for k, v in group_max_grant.items()})
            
            await cb.message.edit_text(
                f"✅ **{ayar_tipi.capitalize()}** ayarları uygulandı!\n\n"
                f"📊 Seviyeler: {len(HAZIR_AYARLAR[ayar_tipi]['limits'])} adet\n"
                f"🎯 Günlük Hak: {HAZIR_AYARLAR[ayar_tipi]['grant']} adet\n\n"
                f"✅ /seviyelistesi komutu ile kontrol edebilirsiniz."
            )
            await cb.answer("Hazır ayar uygulandı!")
        else:
            await cb.answer("Geçersiz ayar tipi!", show_alert=True)

    # GRUPLU HAZIR AYAR BUTONLARI
    elif data.startswith("uygula_"):
        if cb.from_user.id != admin_id:
            await cb.answer("Bu işlem sadece bot sahibi için!", show_alert=True)
            return
            
        parts = data.split("_")
        if parts[1] == "iptal":
            await cb.message.delete()
            await cb.answer("İşlem iptal edildi.")
            return
        
        if len(parts) >= 3:
            ayar_tipi = parts[1]
            hedef_grup_id = int(parts[2])
            
            if ayar_tipi in HAZIR_AYARLAR:
                # Hazır ayarı hedef gruba uygula - limits kısmını al
                limits[hedef_grup_id] = {int(k): v for k, v in HAZIR_AYARLAR[ayar_tipi]["limits"].items()}
                # Grant (hak) ayarını da uygula
                group_max_grant[hedef_grup_id] = HAZIR_AYARLAR[ayar_tipi]["grant"]
                
                # Her ikisini de kaydet
                save_json(LIMITS_FILE, {str(k): v for k, v in limits.items()})
                save_json(GRANTS_FILE, {str(k): v for k, v in group_max_grant.items()})
                
                await cb.message.edit_text(
                    f"✅ **{hedef_grup_id}** grubuna **{ayar_tipi.capitalize()}** ayarları uygulandı!\n\n"
                    f"📊 Seviyeler: {len(HAZIR_AYARLAR[ayar_tipi]['limits'])} adet\n"
                    f"🎯 Günlük Hak: {HAZIR_AYARLAR[ayar_tipi]['grant']} adet\n\n"
                    f"✅ Gruba gidip /seviyelistesi komutu ile kontrol edebilirsiniz."
                )
                await cb.answer("Hazır ayar uygulandı!")
            else:
                await cb.answer("Geçersiz ayar tipi!", show_alert=True)
    elif data == "aciklama":
        try:
            await cb.message.delete()
        except:
            pass
        # Net ve açıklayıcı bot açıklaması
        aciklama_text = (
            "🤖 **Medya Kontrol Botu**\n\n"
            "📌 **Bilgi 1 - Ayarlar:**\n"
            "Eğer bot çok mesaj atıyorsa, bilgi mesajlarını şu şekilde kapatabilirsiniz:\n"
            "• Chata `/menu` yazınız\n"
            "• Oradan `Ayarlar` butonunu seçiniz\n"
            "• `Bilgi Mesajları: Açık` yazan butona basınız\n"
            "• Böylece bilgi mesajları kapanacaktır\n\n"
            "📌 **Bilgi 2 - Bot Özellikleri:**\n"
            "Ben, belirlenen seviyeye ve süreye göre üyelere çıkartma ve GIF atma izni veren, "
            "+18 GIF ve çıkartmaları silen, ayrıca çıkartma/GIF ile spam yapmalarını engelleyen bir botum.\n\n"
            "🔹 **Öne Çıkan Özelliklerim:**\n"
            "• Seviye sistemi ile ödüllendirme\n"
            "• Otomatik +18 içerik temizleme\n"
            "• Akıllı spam koruma sistemi\n"
            "• Kolay yönetim paneli\n\n"
            "⚡ **/menu** yazarak hemen başlayabilirsiniz!\n\n"
            "⚡ **İletişim için lütfen @Ankateamiletisim bağlantı kurunuz.**"
        )
        
        await cb.message.reply(
            aciklama_text,
            reply_markup=InlineKeyboardMarkup([
                
                [InlineKeyboardButton("⚙️ Ayarlar", callback_data="settings"),
                InlineKeyboardButton("◀️ Geri", callback_data="geri")]
            ])
        )
        await cb.answer("Bot özellikleri gösteriliyor")

# >>>>>>>>>>>>>>>>>>>>>>>>>> PATCH 1 (UNION) <<<<<<<<<<<<<<<<<<<<<<<<<<
async def sync_bot_admins_with_telegram(client, chat_id):
    """Telegram adminlerini çek, mevcut bot-admin setiyle BİRLEŞTİR (union)."""
    try:
        # Bot grupta mı?
        try:
            await client.get_chat(chat_id)
        except Exception:
            print(f"⚠️ Bot {chat_id} grubunda değil veya erişim yok")
            return
        
        # Mevcut Telegram adminlerini al
        telegram_admins = set()
        try:
            async for member in client.get_chat_members(chat_id, filter=ChatMembersFilter.ADMINISTRATORS):
                telegram_admins.add(int(member.user.id))
        except Exception as e:
            print(f"⚠️ Admin listesi alınamadı {chat_id}: {e}")
            return
        
        # Mevcut özel bot-admin seti
        existing = group_admins.get(chat_id, set())
        if not isinstance(existing, set):
            existing = set(existing or [])
        
        # OWNER her zaman sette; BİRLEŞTİR
        merged = set(existing) | telegram_admins | {int(admin_id)}
        
        group_admins[chat_id] = merged
        save_json(ADMINS_FILE, {str(k): list(v) for k, v in group_admins.items()})
        
    except Exception as e:
        print(f"Admin senkronizasyon hatası {chat_id}: {e}")

# Her 10 dakikada bir otomatik senkronizasyon
async def auto_sync():
    while True:
        await asyncio.sleep(600)  # 10 dakika
        for chat_id in list(group_admins.keys()):
            try:
                await sync_bot_admins_with_telegram(app, chat_id)
                print(f"✅ {chat_id} grubu otomatik senkronize edildi")
            except Exception as e:
                print(f"Otomatik senkronizasyon hatası {chat_id}: {e}")

# Bot başladığında çalışacak startup fonksiyonu
async def startup_tasks():
    """Bot başladığında çalışacak görevler"""
    print("🤖 Bot başlıyor, admin listeleri senkronize ediliyor...")
    
    # Tüm grupları senkronize et
    for chat_id in list(group_admins.keys()):
        try:
            await sync_bot_admins_with_telegram(app, chat_id)
            print(f"✅ {chat_id} grubu senkronize edildi")
        except Exception as e:
            print(f"Başlangıç senkronizasyon hatası {chat_id}: {e}")
    
    # Otomatik senkronizasyonu başlat
    asyncio.create_task(auto_sync())
    print("✅ Otomatik senkronizasyon başlatıldı")


# >>>>>>>>>>>>>>>>>>>>>>>>>> PATCH 2 (/yetkial temizliği) <<<<<<<<<<<<<<<<<<<<<<<<<<
async def remove_group_admin(chat_id: int, user_id: int):
    await ensure_group_admin_bucket(chat_id)
    if user_id in group_admins[chat_id]:
        group_admins[chat_id].remove(user_id)
        save_json(ADMINS_FILE, {str(k): list(v) for k, v in group_admins.items()})
        
        print(f"⚠️ {user_id} kullanıcısı bot-admin listesinden çıkarıldı, izinler kısıtlanıyor...")

    # İzin penceresi + sayaç + seviye reset
    try:
        izin_key = (chat_id, user_id)
        if izin_key in izin_sureleri:
            izin_sureleri.pop(izin_key)
        
        key_str = f"({chat_id}, {user_id})"
        if key_str in user_data:
            user_data[key_str]["seviye"] = 0
            user_data[key_str]["grant_count"] = 0
            user_data[key_str]["date"] = str(datetime.now().date())

        if (chat_id, user_id) in user_msg_count:
            user_msg_count[(chat_id, user_id)] = 0

        save_json(USERDATA_FILE, convert_keys_to_str(user_data))
        save_json(COUNTS_FILE, convert_keys_to_str(user_msg_count))
        save_json(IZIN_FILE, convert_keys_to_str(izin_sureleri))
        print(f"✅ {user_id} için izin/sayaç/seviye sıfırlandı")
    except Exception as e:
        print(f"❌ remove_group_admin cleanup hatası: {e}")

    # Telegram tarafında medya/diğer mesaj izinlerini kapat
    try:
        izin_kisitla = ChatPermissions(
            can_send_messages=True,
            can_send_media_messages=False,
            can_send_other_messages=False,
            can_send_polls=False,
            can_add_web_page_previews=False,
            can_change_info=False,
            can_invite_users=False,
            can_pin_messages=False
        )
        await app.restrict_chat_member(chat_id, user_id, izin_kisitla)
        print(f"✅ {user_id} kullanıcısının medya izinleri kısıtlandı")
    except Exception as e:
        print(f"❌ İzin kısıtlama hatası: {e}")

@app.on_chat_member_updated()
async def on_chat_member_update(_, cmu: ChatMemberUpdated):
    """Birinin yetkisi değiştiğinde senkronize et ve yetkisi alınan adminin izinlerini kısıtla"""
    
    # 1. Önce senkronizasyon yap
    if cmu.chat.id in group_admins:
        await sync_bot_admins_with_telegram(app, cmu.chat.id)
        print(f"🔄 {cmu.chat.id} grubu üye değişikliği sonrası senkronize edildi")
    
    # 2. Eğer birinin yöneticilik yetkisi alındıysa, onun medya izinlerini kısıtla
    try:
        # Eski ve yeni durumu kontrol et
        old_status = cmu.old_chat_member.status if cmu.old_chat_member else None
        new_status = cmu.new_chat_member.status if cmu.new_chat_member else None
        
        # Eğer yöneticilikten çıkarıldıysa (ADMINISTRATOR -> MEMBER)
        if (old_status == ChatMemberStatus.ADMINISTRATOR and 
            new_status == ChatMemberStatus.MEMBER):
            
            user_id = cmu.new_chat_member.user.id
            chat_id = cmu.chat.id
            
            print(f"⚠️ {user_id} kullanıcısının {chat_id} grubunda yetkisi alındı, izinler kısıtlanıyor...")
            
            # Medya izinlerini kısıtla
            izin_kisitla = ChatPermissions(
                can_send_messages=True,
                can_send_media_messages=False,      # Medya yasak
                can_send_other_messages=False,       # Çıkartma, GIF yasak
                can_send_polls=False,
                can_add_web_page_previews=False,
                can_change_info=False,
                can_invite_users=False,
                can_pin_messages=False
            )
            
            try:
                await app.restrict_chat_member(chat_id, user_id, izin_kisitla)
                print(f"✅ {user_id} kullanıcısının medya izinleri kısıtlandı")
                
                # İzin süresini de sıfırla (varsa)
                izin_key = (chat_id, user_id)
                if izin_key in izin_sureleri:
                    izin_sureleri.pop(izin_key)
                    save_json(IZIN_FILE, convert_keys_to_str(izin_sureleri))
                    print(f"✅ {user_id} kullanıcısının izin süresi sıfırlandı")
                    
            except Exception as e:
                print(f"❌ İzin kısıtlama hatası: {e}")
    
    except Exception as e:
        print(f"Chat member update hatası: {e}")

@app.on_message(filters.command("reload"))
async def manual_sync(_, msg: Message):
    """Manuel senkronizasyon komutu"""
    if await is_user_authorized(app, msg.chat.id, msg.from_user.id):
        await sync_bot_admins_with_telegram(app, msg.chat.id)
        # --- BOT-ADMIN'LERİ TOPTAN UNRESTRICT ET ---
        try:
            admins = group_admins.get(msg.chat.id, set())
            for uid in admins:
                if uid == admin_id:
                    continue
                try:
                    await app.restrict_chat_member(
                        msg.chat.id,
                        uid,
                        ChatPermissions(
                            can_send_messages=True,
                            can_send_media_messages=True,
                            can_send_other_messages=True,  # sticker/GIF
                            can_send_polls=True,
                            can_add_web_page_previews=True,
                            can_change_info=False,
                            can_invite_users=True,
                            can_pin_messages=False
                        )
                    )
                    # varsa süreli izin penceresini temizle
                    izin_sureleri.pop((msg.chat.id, uid), None)
                except Exception as e:
                    print("reload izin açma hatası:", e)
            save_json(IZIN_FILE, convert_keys_to_str(izin_sureleri))
        except Exception as e:
            print("reload admin liste hatası:", e)
        await msg.reply("✅ Admin listesi güncellendi.")

# ================= NSFW TESPİT =================
# Buradan sonraki NSFW, sticker, GIF analiz kodları değişmeden kalabilir.
# ... (NSFW kodlarının geri kalanı buraya gelecek)

# NudeNet modelini yükle
detector = NudeDetector()
# Duyarlı gördüğümüz label seti
NSFW_LABELS = { "FEMALE_BREAST_EXPOSED", "FEMALE_GENITALIA_EXPOSED", "MALE_GENITALIA_EXPOSED", "ANUS_EXPOSED", "BUTTOCKS_EXPOSED", "EXPOSED_BREAST", "EXPOSED_GENITALIA", "EXPOSED_BUTTOCKS", "EXPOSED_ANUS", "BELLY_EXPOSED", "ARMPITS_EXPOSED", "FEET_EXPOSED",}

def preprocess_for_nudenet(in_path: str) -> str:
    try:
        im = Image.open(in_path).convert("RGB")
        w, h = im.size
        m = min(w, h)
        min_side = int(THR.get("MIN_SIDE", 512))
        if m < min_side:
            scale = min_side / m
            im = im.resize((int(w*scale), int(h*scale)), Image.LANCZOS)
        im_np = np.array(im, dtype=np.uint8)
        im_np = cv2.GaussianBlur(im_np, (0, 0), 1.0)
        im_np = cv2.addWeighted(im_np, 1.5, im_np, -0.5, 0)
        out = f"{in_path}.nudeprep.jpg"
        Image.fromarray(im_np).save(out, "JPEG", quality=92)
        return out
    except Exception as e:
        print("preprocess_for_nudenet hata:", e)
        return in_path

def extract_webm_frames_adv(path: str) -> list[str]:
    outs = []
    try:
        max_frames = int(THR.get("GIF_MAX_FRAMES", 6))
        step = max(1, int(THR.get("GIF_STEP", 2)))
        cap = cv2.VideoCapture(path)
        if not cap or not cap.isOpened(): raise RuntimeError("VideoCapture açılamadı")
        total = int(cap.get(cv2.CAP_PROP_FRAME_COUNT) or 0)
        if total <= 0:
            return outs
        idxs = list(range(0, total, step))[:max_frames]
        for i in idxs:
            cap.set(cv2.CAP_PROP_POS_FRAMES, max(0, i))
            ok, frame = cap.read()
            if not ok: continue
            out = f"{path}_f{i}.jpg"
            cv2.imwrite(out, frame)
            outs.append(out)
        cap.release()
    except Exception as e:
        print("extract_webm_frames hata:", e)
    return outs

def nudenet_score_for(path: str) -> float:
    try:
        res = detector.detect(path) or []
        mx = 0.0
        for d in res:
            label = (d.get("label") or d.get("class") or "").upper()
            score = float(d.get("score", 0.0))
            if any(k in label for k in ["BREAST", "GENITAL", "BUTTOCK", "ANUS", "EXPOSED"]):
                mx = max(mx, score)
        return mx
    except Exception as e:
        return 0.0
_FACE_CASCADE = cv2.CascadeClassifier(cv2.data.haarcascades + 'haarcascade_frontalface_default.xml')

def kiss_score(img_path: str) -> float:
    try:
        img = cv2.imread(img_path)
        if img is None: return 0.0
        gray = cv2.cvtColor(img, cv2.COLOR_BGR2GRAY)
        faces = _FACE_CASCADE.detectMultiScale(gray, scaleFactor=1.2, minNeighbors=5, minSize=(40, 40))
        if len(faces) < 2: return 0.0
        faces = sorted(faces, key=lambda r: r[2] * r[3], reverse=True)[:2]
        def center(rect):
            x, y, w, h = rect
            return (x + w / 2.0, y + h / 2.0, w, h)
        c1 = center(faces[0])
        c2 = center(faces[1])
        dx = abs(c1[0] - c2[0])
        dy = abs(c1[1] - c2[1])
        dist = (dx * dx + dy * dy) ** 0.5
        avg_w = (c1[2] + c2[2]) / 2.0
        if avg_w <= 1: return 0.0
        norm = dist / avg_w
        vertical_ok = dy < 0.5 * avg_w
        side_by_side = dx > 0.3 * avg_w
        close_ok = norm < 0.9
        if vertical_ok and side_by_side and close_ok:
            score = max(0.60, min(0.90, 1.0 - norm / 1.2))
            return float(score)
        return 0.0
    except Exception:
        return 0.0
def should_delete(scores: list[float], kiss_scores: list[float]|None=None) -> bool:
    if not scores and not kiss_scores: return False
    hard = float(THR["HARD_THRESHOLD"])
    soft = float(THR["SOFT_THRESHOLD"])
    hits_need = int(THR["SOFT_HITS_REQUIRED"])
    kiss_thr = float(THR.get("KISS_THRESHOLD", 0.33))
    if scores and max(scores) >= hard: return True
    if scores:
        soft_hits = sum(1 for s in scores if s >= soft)
        if soft_hits >= hits_need: return True
    if kiss_scores and max(kiss_scores) >= kiss_thr: return True
    return False

@app.on_message(filters.command("ayaruygula"))
async def ayar_uygula_komut(_, msg: Message):
    if msg.from_user.id != admin_id:
        return await msg.reply("❌ Bu komut sadece bot sahibine özeldir.")
    
    if len(msg.command) < 2:
        return await msg.reply("⚠️ Kullanım: /ayaruygula [grup_id]")
    
    try:
        hedef_grup_id = int(msg.command[1])
    except ValueError:
        return await msg.reply("❌ Geçersiz grup ID! Sayı olmalı.")
    
    # Butonlar ile hazır ayar seçeneklerini göster
    keyboard = InlineKeyboardMarkup([
        [InlineKeyboardButton("🚀 Standart (10 Seviye)", callback_data=f"uygula_standart_{hedef_grup_id}")],
        [InlineKeyboardButton("⚡ Hızlı (4 Seviye)", callback_data=f"uygula_hızlı_{hedef_grup_id}")],
        [InlineKeyboardButton("🐢 Yavaş (5 Seviye)", callback_data=f"uygula_yavaş_{hedef_grup_id}")],
        [InlineKeyboardButton("❌ İptal", callback_data="uygula_iptal")]
    ])
    
    await msg.reply(
    f"🎯 **{hedef_grup_id}** grubuna hangi hazır ayarı uygulamak istersiniz?\n\n"
    "• 🚀 Standart: 10 seviye, 10 hak\n"
    "• ⚡ Hızlı: 4 seviye, 5 hak\n" 
    "• 🐢 Yavaş: 5 seviye, 6 hak",
    reply_markup=keyboard
)

@app.on_message(filters.command("hazırayar"))
async def hazir_ayar_komut(_, msg: Message):
    if not await is_user_authorized(app, msg.chat.id, msg.from_user.id):
        return await msg.reply("❌ Bu komutu sadece yöneticiler kullanabilir.")
    
    # Butonlar ile hazır ayar seçeneklerini göster
    keyboard = InlineKeyboardMarkup([
        [InlineKeyboardButton("🚀 Standart (10 Seviye)", callback_data="hazır_standart")],
        [InlineKeyboardButton("⚡ Hızlı (4 Seviye)", callback_data="hazır_hızlı")],
        [InlineKeyboardButton("🐢 Yavaş (5 Seviye)", callback_data="hazır_yavaş")],
        [InlineKeyboardButton("❌ İptal", callback_data="hazır_iptal")]
    ])
    
    await msg.reply(
        "🎯 Hangi hazır ayarı uygulamak istersiniz?\n\n"
        "• 🚀 Standart: 1-1000 mesaj, 10 seviye\n"
        "• ⚡ Hızlı: 1-100 mesaj, 4 seviye\n"
        "• 🐢 Yavaş: 1-500 mesaj, 5 seviye",
        reply_markup=keyboard
    )


# Spam Koruma
@app.on_message(filters.group & (filters.sticker | filters.animation))
async def media_spam_kontrol(_, msg: Message):
    # Yöneticileri kontrol etme
    if await is_user_authorized(app, msg.chat.id, msg.from_user.id):
        return
    
    uid, cid = msg.from_user.id, msg.chat.id
    key = (cid, uid)
    now = time.time()
    
    # Kova sistemini başlat veya güncelle
    if key not in user_media_bucket:
        user_media_bucket[key] = {"tokens": MEDIA_BUCKET_MAX, "last_update": now}
    else:
        # Zaman geçtikçe tokenları yenile
        time_passed = now - user_media_bucket[key]["last_update"]
        new_tokens = time_passed * MEDIA_BUCKET_REFILL
        user_media_bucket[key]["tokens"] = min(MEDIA_BUCKET_MAX, user_media_bucket[key]["tokens"] + new_tokens)
        user_media_bucket[key]["last_update"] = now
    
    # Token kontrolü - 1 token'dan azsa engelle
    if user_media_bucket[key]["tokens"] < 1:
        # Token yok, spam yapıyor - mesajı sil ve uyar
        try:
            await msg.delete()
            # Son 10 saniye içinde uyarı verilmediyse ver
            if key not in last_warning_time or (now - last_warning_time[key]) > 10:
                uyarı_msg = await msg.reply(
                    f"⚠️ {msg.from_user.mention}, çok hızlı medya gönderiyorsun! "
                    f"Lütfen {MEDIA_BUCKET_MAX} medyayı {int(MEDIA_BUCKET_MAX/MEDIA_BUCKET_REFILL)} saniyeden daha kısa sürede göndermeyin."
                )
                last_warning_time[key] = now
                await asyncio.sleep(8)
                await uyarı_msg.delete()
        except Exception as e:
            print(f"Spam kontrol hatası: {e}")
        return
    
    # Token var, medya göndermesine izin ver ama tokenı azalt
    user_media_bucket[key]["tokens"] -= 1
    user_media_bucket[key]["last_update"] = now

# Uyarı zamanlarını tutmak için
last_warning_time = {}

@app.on_message(filters.group & (filters.sticker | filters.animation | filters.document))
async def media_filter(_, msg: Message):
    # Grup yöneticilerinin attığı medyaları kontrol etme
    if await is_user_authorized(app, msg.chat.id, msg.from_user.id):
        return
    
    tmp = []
    try:
        candidate_images = []
        downloaded_path = None
        
        if msg.sticker:
            downloaded_path = await app.download_media(msg.sticker)
            tmp.append(downloaded_path)
            if msg.sticker.is_video:
                frames = extract_webm_frames_adv(downloaded_path)
                for f in frames:
                    tmp.append(f)
                    candidate_images.append(preprocess_for_nudenet(f))
            elif msg.sticker.is_animated and LOTTIE_OK:
                try:
                    anim = lottie_importers.import_tgs(downloaded_path)
                    step = max(1, int(THR.get("GIF_STEP", 2)))
                    picks = list(range(0, 30, step))[:int(THR.get("GIF_MAX_FRAMES", 6))]
                    for fidx in picks:
                        out_png = f"{downloaded_path}_f{fidx}.png"
                        try:
                            lottie_exporters.export_png(anim, out_png, frame=fidx, scale=2.0)
                            tmp.append(out_png)
                            candidate_images.append(preprocess_for_nudenet(out_png))
                        except Exception: pass
                except Exception as e: print("lottie hata:", e)
            else:
                pp = preprocess_for_nudenet(downloaded_path)
                if pp != downloaded_path: tmp.append(pp)
                candidate_images.append(pp)
        
        elif msg.animation:
            downloaded_path = await app.download_media(msg.animation)
            tmp.append(downloaded_path)
            frames = extract_webm_frames_adv(downloaded_path)
            for f in frames:
                tmp.append(f)
                candidate_images.append(preprocess_for_nudenet(f))

        elif msg.document and (msg.document.mime_type or "") == "image/gif":
            downloaded_path = await app.download_media(msg.document)
            tmp.append(downloaded_path)
            try:
                import imageio.v3 as iio
                step = max(1, int(THR.get("GIF_STEP", 2)))
                limit = int(THR.get("GIF_MAX_FRAMES", 6))
                cnt = 0
                for idx, frame in enumerate(iio.imiter(downloaded_path)):
                    if idx % step == 0:
                        out = f"{downloaded_path}_f{idx}.jpg"
                        Image.fromarray(frame).convert("RGB").save(out, "JPEG", quality=92)
                        tmp.append(out)
                        candidate_images.append(preprocess_for_nudenet(out))
                        cnt += 1
                        if cnt >= limit: break
            except Exception as e: print("gif (image/gif) kare çıkarma hata:", e)

        if not candidate_images: return

        scores = [nudenet_score_for(p) for p in candidate_images]
        kscores = [kiss_score(p) for p in candidate_images]
        
        if should_delete(scores, kscores) or (scores and max(scores) >= global_security_score):
            await msg.delete()

    except Exception as e:
        print(f"Media filter error: {e}")
    finally:
        for p in tmp:
            if p and os.path.exists(p):
                try: os.remove(p)
                except: pass

# ---------- KOMUTLAR ----------
@app.on_message(filters.command("guvenlik"))
async def set_score_cmd(_, msg: Message):
    if msg.from_user.id != admin_id:
        return await msg.reply("❌ Bu komut sadece bot sahibine özeldir.")
    try:
        score_str = msg.text.split()[1].replace(',', '.')
        yeni_skor = float(score_str)
        if not (0.1 <= yeni_skor <= 1.0):
            raise ValueError("Skor 0.1 ile 1.0 arasında olmalı.")
        save_global_score(yeni_skor)
        await msg.reply(f"✅ **Global** güvenlik seviyesi **{yeni_skor}** olarak ayarlandı.")
    except (ValueError, IndexError):
        await msg.reply("⚠️ Örnek: `/guvenlik 0.85`")

@app.on_message(filters.command("log"))
async def cmd_log(_, msg: Message):
    if not await is_user_authorized(app, msg.chat.id, msg.from_user.id): return
    await msg.reply("ℹ️ `/log` komutu devre dışı bırakıldı. DEBUG ayarı dosyadan okunuyor ve Ayarlar menüsünde görüntüleniyor.")

def _is_owner(uid: int) -> bool: return uid == admin_id

@app.on_message(filters.command("hard"))
async def cmd_hard(_, msg: Message):
    if not _is_owner(msg.from_user.id): return
    try:
        val = _try_float(msg.text.split()[1])
        if not (0.0 <= val <= 1.0): raise ValueError
        THR["HARD_THRESHOLD"] = val; save_thresholds(THR)
        await msg.reply(f"✅ HARD eşik: **{val}**")
    except: await msg.reply("Kullanım: `/hard 0.80` (0-1 arası)", quote=True)

@app.on_message(filters.command("soft"))
async def cmd_soft(_, msg: Message):
    if not _is_owner(msg.from_user.id): return
    try:
        val = _try_float(msg.text.split()[1])
        if not (0.0 <= val <= 1.0): raise ValueError
        THR["SOFT_THRESHOLD"] = val; save_thresholds(THR)
        await msg.reply(f"✅ SOFT eşik: **{val}**")
    except: await msg.reply("Kullanım: `/soft 0.55` (0-1 arası)", quote=True)

@app.on_message(filters.command("hits"))
async def cmd_hits(_, msg: Message):
    if not _is_owner(msg.from_user.id): return
    try:
        val = int(msg.text.split()[1])
        if not (1 <= val <= 10): raise ValueError
        THR["SOFT_HITS_REQUIRED"] = val; save_thresholds(THR)
        await msg.reply(f"✅ HITS: **{val}**")
    except: await msg.reply("Kullanım: `/hits 2` (1–10 arası)", quote=True)

@app.on_message(filters.command("minside"))
async def cmd_minside(_, msg: Message):
    if not await is_user_authorized(app, msg.chat.id, msg.from_user.id): return
    try:
        v = int(msg.text.split()[1])
        if not (256 <= v <= 2048): raise ValueError
        THR["MIN_SIDE"] = v; save_thresholds(THR)
        await msg.reply(f"✅ MIN_SIDE: **{v}**")
    except: await msg.reply("Kullanım: `/minside 768` (256-2048)")

@app.on_message(filters.command("gifmax"))
async def cmd_gifmax(_, msg: Message):
    if not await is_user_authorized(app, msg.chat.id, msg.from_user.id): return
    try:
        v = int(msg.text.split()[1])
        if not (3 <= v <= 24): raise ValueError
        THR["GIF_MAX_FRAMES"] = v; save_thresholds(THR)
        await msg.reply(f"✅ GIF_MAX_FRAMES: **{v}**")
    except: await msg.reply("Kullanım: `/gifmax 12` (3-24)")

@app.on_message(filters.command("gifstep"))
async def cmd_gifstep(_, msg: Message):
    if not await is_user_authorized(app, msg.chat.id, msg.from_user.id): return
    try:
        v = int(msg.text.split()[1])
        if not (1 <= v <= 10): raise ValueError
        THR["GIF_STEP"] = v; save_thresholds(THR)
        await msg.reply(f"✅ GIF_STEP: **{v}**")
    except: await msg.reply("Kullanım: `/gifstep 2` (1-10)")

@app.on_message(filters.command("kiss"))
async def cmd_kiss(_, msg: Message):
    if not await is_user_authorized(app, msg.chat.id, msg.from_user.id): return
    try:
        val = _try_float(msg.text.split()[1])
        if not (0.0 <= val <= 1.0): raise ValueError
        THR["KISS_THRESHOLD"] = val; save_thresholds(THR)
        await msg.reply(f"✅ KISS_THRESHOLD: **{val}**")
    except: await msg.reply("Kullanım: `/kiss 0.33` (0.0-1.0)")

@app.on_message(filters.command("bilgi"))
async def cmd_bilgi(_, msg: Message):
    if msg.chat.type not in ("supergroup", "group"): return
    if not await is_user_authorized(app, msg.chat.id, msg.from_user.id): return
    try:
        val = msg.text.split()[1].lower() == "on"
        set_announce(msg.chat.id, val)
        await msg.reply(f"✅ Bilgi mesajları: **{'Açık' if val else 'Kapalı'}**")
    except: await msg.reply("Kullanım: `/bilgi on` veya `/bilgi off`")

@app.on_message(filters.command("seviyeayar"))
async def set_limit(_, msg: Message):
    if not await is_user_authorized(app, msg.chat.id, msg.from_user.id): 
        return
    try:
        _, seviye, mesaj, süre_deger, süre_birim = msg.text.split()
        sure_saniye = parse_time(int(süre_deger), süre_birim)
        
        # Sadece limits dict'ini güncelle, ensure_default_level_for'u çağırma
        if msg.chat.id not in limits:
            limits[msg.chat.id] = {}
            
        limits[msg.chat.id][int(seviye)] = {"msg": int(mesaj), "süre": sure_saniye}
        save_json(LIMITS_FILE, {str(k): v for k, v in limits.items()})
        await msg.reply(f"✅ Seviye {seviye} ayarlandı.")
    except: 
        await msg.reply("⚠️ Kullanım: /seviyeayar [seviye] [mesaj] [süre] [saniye|dakika|saat]")


@app.on_message(filters.command("hakayarla"))
async def set_grant(_, msg: Message):
    if not await is_user_authorized(app, msg.chat.id, msg.from_user.id): return
    try:
        adet = int(msg.text.split()[1])
        set_chat_max_grant(msg.chat.id, adet)
        await msg.reply(f"✅ (Grup) Günlük hak: {adet}")
    except: await msg.reply("⚠️ Kullanım: /hakayarla [adet]")

@app.on_message(filters.command("verisil"))
async def reset_all(_, msg: Message):
    if not await is_user_authorized(app, msg.chat.id, msg.from_user.id): return
    cid = msg.chat.id
    keys_ud = [k for k in list(user_data.keys()) if k.startswith(f"({cid},")]
    for k in keys_ud: user_data.pop(k, None)
    keys_uc = [k for k in list(user_msg_count.keys()) if k[0] == cid]
    for k in keys_uc: user_msg_count.pop(k, None)
    keys_iz = [k for k in list(izin_sureleri.keys()) if k[0] == cid]
    for k in keys_iz: izin_sureleri.pop(k, None)
    save_json(USERDATA_FILE, convert_keys_to_str(user_data))
    save_json(COUNTS_FILE, convert_keys_to_str(user_msg_count))
    save_json(IZIN_FILE, convert_keys_to_str(izin_sureleri))
    await msg.reply("✅ Bu grubun kullanıcı verileri silindi.")

@app.on_message(filters.command("seviyelerisil"))
async def seviyeleri_sil(_, msg: Message):
    if not await is_user_authorized(app, msg.chat.id, msg.from_user.id): return
    if msg.chat.id in limits:
        limits.pop(msg.chat.id, None)
        save_json(LIMITS_FILE, {str(k): v for k, v in limits.items()})
    ensure_default_level_for(msg.chat.id)
    await msg.reply("🗑️ Bu gruptaki tüm seviye ayarları silindi. Varsayılan **Seviye 0 (1 mesaj / 1 sn)** aktif.")

@app.on_message(filters.command("durumum"))
async def user_status(_, msg: Message):
    uid, cid = msg.from_user.id, msg.chat.id
    key = f"({cid}, {uid})"
    today = str(datetime.now().date())
    if key not in user_data:
        user_data[key] = {"seviye": 0, "grant_count": 0, "date": today}
        user_msg_count[(cid, uid)] = 0
    if user_data[key].get("date") != today:
        user_data[key]["date"] = today
        user_data[key]["seviye"] = 0
        user_data[key]["grant_count"] = 0
        user_msg_count[(cid, uid)] = 0
    ensure_default_level_for(cid)
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

@app.on_message(filters.command("yetkiver"))
async def add_admin_cmd(_, msg: Message):
    if not await is_user_authorized(app, msg.chat.id, msg.from_user.id):
        return await msg.reply("❌ Yetkin yok.")
    try:
        if msg.reply_to_message:
            target_id = msg.reply_to_message.from_user.id
        elif len(msg.command) >= 2:
            target_id = (await app.get_users(msg.command[1].lstrip("@"))).id
        else:
            return await msg.reply("⚠️ Yanıtla veya kullanıcı adı gir.")
        await add_group_admin(msg.chat.id, target_id)
        # --- BOT-ADMIN'LERİ TOPTAN UNRESTRICT ET ---
        try:
            admins = group_admins.get(msg.chat.id, set())
            for uid in admins:
                if uid == admin_id:
                    continue
                try:
                    await app.restrict_chat_member(
                        msg.chat.id,
                        uid,
                        ChatPermissions(
                            can_send_messages=True,
                            can_send_media_messages=True,
                            can_send_other_messages=True,  # sticker/GIF
                            can_send_polls=True,
                            can_add_web_page_previews=True,
                            can_change_info=False,
                            can_invite_users=True,
                            can_pin_messages=False
                        )
                    )
                    # varsa süreli izin penceresini temizle
                    izin_sureleri.pop((msg.chat.id, uid), None)
                except Exception as e:
                    print("reload izin açma hatası:", e)
            save_json(IZIN_FILE, convert_keys_to_str(izin_sureleri))
        except Exception as e:
            print("reload admin liste hatası:", e)
        await msg.reply(f"✅ {target_id} bu grup için bot-admin yapıldı.")
    except Exception as e: await msg.reply(f"❌ Hata: {e}")

@app.on_message(filters.command("yetkial"))
async def remove_admin_cmd(_, msg: Message):
    if not await is_user_authorized(app, msg.chat.id, msg.from_user.id):
        return await msg.reply("❌ Yetkin yok.")
    try:
        if msg.reply_to_message:
            target_id = msg.reply_to_message.from_user.id
        elif len(msg.command) >= 2:
            target_id = (await app.get_users(msg.command[1].lstrip("@"))).id
        else:
            return await msg.reply("⚠️ Yanıtla veya kullanıcı adı gir.")
        if target_id == admin_id: return await msg.reply("❌ Owner kaldırılamaz.")
        await remove_group_admin(msg.chat.id, target_id)
        await msg.reply(f"🚫 {target_id} bu grupta bot-admin listesinden çıkarıldı.")
    except Exception as e: await msg.reply(f"❌ Hata: {e}")

@app.on_message(filters.command("seviyelistesi"))
async def seviyelistesi_cmd(_, msg: Message):
    if msg.chat.type in ("supergroup", "group"):
        if not await is_user_authorized(app, msg.chat.id, msg.from_user.id):
            return
    ensure_default_level_for(msg.chat.id)
    if msg.chat.id not in limits or not limits[msg.chat.id]:
        return await msg.reply("⚠️ Bu grupta ayarlanmış seviye yok.")
    text = "📊 Seviye Listesi (Bu Grup):\n\n"
    for s in sorted(limits[msg.chat.id].keys()):
        l = limits[msg.chat.id][s]
        sure_metni = saniyeyi_donustur(l['süre'])
        text += f"🔹 Seviye {s}: {l['msg']} mesaj → {sure_metni} izin\n"
    await msg.reply(text)

@app.on_message(filters.command("hakkinda"))
async def about_info(_, msg: Message):
    if msg.chat.type in ("supergroup", "group"):
        if not await is_user_authorized(app, msg.chat.id, msg.from_user.id):
            return
    await msg.reply("🤖 Medya Kontrol Botu\nMesaj sayısına göre medya izni verir.\n🛠 Geliştirici: @Ankateamiletisim")

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

# ---------- MESAJ TAKİBİ VE SEVİYE SİSTEMİ ----------
@app.on_message(filters.group & ~filters.service)
async def takip_et(_, msg: Message):
    if await is_user_authorized(app, msg.chat.id, msg.from_user.id):
        return

    uid, cid = msg.from_user.id, msg.chat.id
    
    # Sadece bu grup için limits yoksa varsayılan seviyeyi ekle
    if cid not in limits:
        ensure_default_level_for(cid)
    key = f"({cid}, {uid})"
    now = time.time()
    today = str(datetime.now().date())
    
    if key not in user_data or user_data[key].get("date") != today:
        user_data[key] = {"seviye": 0, "grant_count": 0, "date": today}
        user_msg_count[(cid, uid)] = 0
    
    if now < izin_sureleri.get((cid, uid), 0):
        return

    user_msg_count[(cid, uid)] = user_msg_count.get((cid, uid), 0) + 1
    grup_limitleri = limits.get(cid, {})

    for seviye in sorted(grup_limitleri.keys()):
        lim = grup_limitleri[seviye]
        if (user_msg_count.get((cid, uid), 0) >= lim["msg"]
            and seviye > user_data[key].get("seviye", -1)
            and user_data[key].get("grant_count", 0) < get_chat_max_grant(cid)):

            user_data[key]["seviye"] = seviye
            user_data[key]["grant_count"] += 1
            user_msg_count[(cid, uid)] = 0
            izin_sureleri[(cid, uid)] = now + lim["süre"]

            if get_announce(cid):
                sure_metni = saniyeyi_donustur(lim['süre'])
                await msg.reply(f"🎉 Tebrikler! Seviye {seviye} tamamlandı. **{sure_metni}** sticker/GIF izni verildi.")

            izin_ver = ChatPermissions(can_send_messages=True, can_send_media_messages=True, can_send_other_messages=True)
            izin_kisitla = ChatPermissions(can_send_messages=True)
            
            try:
                await app.restrict_chat_member(cid, uid, izin_ver)
                
                # ÖDÜL SÜRESİNİN SONUNDA MEDYA COOLDOWN'ını SIFIRLA
                async def reset_cooldown_after_reward():
                    await asyncio.sleep(lim["süre"])
                    user_last_media.pop((cid, uid), None)
                
                asyncio.create_task(reset_cooldown_after_reward())
                
                await asyncio.sleep(lim["süre"])
                await app.restrict_chat_member(cid, uid, izin_kisitla)
                
                if get_announce(cid):
                    await msg.reply("⌛️ Sticker/GIF iznin sona erdi.")
            except Exception as e:
                print("HATA: Üye kısıtlama/açma sırasında ->", e)

    save_json(USERDATA_FILE, convert_keys_to_str(user_data))
    save_json(COUNTS_FILE, convert_keys_to_str(user_msg_count))
    save_json(IZIN_FILE, convert_keys_to_str(izin_sureleri))

# ---------- GRUP OLAYLARI ----------
@app.on_chat_member_updated()
async def yeni_katilim(_, cmu: ChatMemberUpdated):
    try:
        me = await app.get_me()
        if cmu.new_chat_member and cmu.new_chat_member.user.id == me.id:
            cid = cmu.chat.id
            await ensure_group_admin_bucket(cid)
            ensure_default_level_for(cid)

            adder_id = cmu.from_user.id if cmu.from_user else None

            if adder_id:
                await add_group_admin(cid, adder_id)
                u = await app.get_users(adder_id)
                who = f"@{u.username}" if u.username else f"{u.first_name}"
                await app.send_message(cid, f"✅ Bot eklendi. {who} bu grup için bot-admin yapıldı.")
            else:
                chosen = None
                async for m in app.get_chat_members(cid, filter=ChatMemberStatus.ADMINISTRATORS):
                    if m.user.is_bot: continue
                    if m.privileges and m.privileges.can_restrict_members:
                        chosen = m.user.id; break
                if chosen:
                    await add_group_admin(cid, chosen)
                    u = await app.get_users(chosen)
                    who = f"@{u.username}" if u.username else f"{u.first_name}"
                    await app.send_message(cid, f"ℹ️ Ban yetkisi olan ilk yöneticiyi bot-admin yaptım: {who}")
                else:
                    await app.send_message(cid, "⚠️ Bir yönetici /yetkiver ile bot-admin belirlesin.")

            await app.send_message(
                cid,
                "👋 Selam! Bu grupta aktiflikleri takip edeceğim.\n\n"
                "✅ Gerekli izinler:\n"
                "• Kullanıcıları kısıtlama (Ban yetkisi)\n"
                "• Mesaj silme\n\n"
                "• İzinlerden çıkartma ve GIF izni açık olmalı.\n"
                "/menu komutu ile başlayabilirsin."
            )
    except Exception as e:
        print("on_chat_member_updated error:", e)

# ---------- BAŞLANGIÇ ----------
print("🚀 Bot başlatılıyor...")
load_global_score()

# Botu başlat ve startup görevlerini çalıştır
app.start()
print("✅ Bot başlatıldı")

# Startup görevlerini çalıştır
import asyncio

async def run_startup_tasks():
    await startup_tasks()

# Async görevleri çalıştır
loop = asyncio.get_event_loop()
loop.run_until_complete(run_startup_tasks())

# Botu çalışır durumda tut (idle)
from pyrogram import idle
idle()

# Botu durdur
app.stop()
print("⏹️ Bot durduruldu.")
