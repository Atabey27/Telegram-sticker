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


DEBUG = False   # en üste koy


# ---------- env ----------
load_dotenv()
api_id = int(os.getenv("API_ID"))
api_hash = os.getenv("API_HASH")                 # <-- string olmalı
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
THRESHOLDS_FILE = "thresholds.json"   # <-- EKLENDİ

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

# ---------- (EKLENDİ) NSFW thresholds kalıcı ayarları ----------
DEFAULT_THRESHOLDS = {
    "HARD_THRESHOLD": 0.85,   # tek karede kesin sil
    "SOFT_THRESHOLD": 0.55,   # şüpheli kare eşiği
    "SOFT_HITS_REQUIRED": 2,  # şüpheli kare sayısı
    # ---- yeni dinamikler ----
    "MINSIDE": 512,               # preprocess kısa kenar
    "GIFMAX": 8,                  # video/gif için max alınacak kare
    "GIFSTEP": 5,                 # her kaç karede bir örnek
    "KISS_THRESHOLD": 0.35        # kiss skoru eşiği
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
THR = load_thresholds()  # aktif değerler

def thresholds_summary():
    return (f"⚙️ Eşikler:\n"
            f"• HARD: {THR['HARD_THRESHOLD']}\n"
            f"• SOFT: {THR['SOFT_THRESHOLD']}\n"
            f"• HITS: {THR['SOFT_HITS_REQUIRED']}\n"
            f"• MINSIDE: {THR['MINSIDE']}\n"
            f"• GIFMAX: {THR['GIFMAX']}\n"
            f"• GIFSTEP: {THR['GIFSTEP']}\n"
            f"• KISS: {THR['KISS_THRESHOLD']}")

def _try_float(x):
    try:
        return float(str(x).replace(",", "."))
    except:
        return None

# ---------- varsayılan seviye (0 -> 1 mesaj / 1 saniye) ----------
def ensure_default_level_for(chat_id: int):
    if chat_id not in limits:
        limits[chat_id] = {}
    if 0 not in limits[chat_id]:
        limits[chat_id][0] = {"msg": 1, "süre": 1}
        save_json(LIMITS_FILE, {str(k): v for k, v in limits.items()})

_any_change = False
for _cid in list(limits.keys()):
    if 0 not in limits[_cid]:
        limits[_cid][0] = {"msg": 1, "süre": 1}
        _any_change = True
if _any_change:
    save_json(LIMITS_FILE, {str(k): v for k, v in limits.items()})

# ---------- bot ----------
app = Client("bot", api_id=api_id, api_hash=api_hash, bot_token=bot_token, in_memory=True)

# ---------- yetki kontrol ----------
def get_chat_max_grant(chat_id: int) -> int:
    return group_max_grant.get(chat_id, DEFAULT_MAX_GRANT)
def set_chat_max_grant(chat_id: int, val: int):
    group_max_grant[chat_id] = int(val)
    save_json(GRANTS_FILE, {str(k): v for k, v in group_max_grant.items()})
def is_group_bot_admin(chat_id: int, user_id: int) -> bool:
    if user_id == admin_id: return True
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

# ---------- /menu ----------
@app.on_message(filters.command("menu"))
async def menu(_, msg: Message):
    cid = msg.chat.id
    uid = msg.from_user.id
    if msg.chat.type in ("supergroup", "group") and not is_group_bot_admin(cid, uid):
        return
    btn = InlineKeyboardMarkup([
        [InlineKeyboardButton("📋 Yardım Menüsü", callback_data="help")],
        [InlineKeyboardButton("📊 Seviye Listesi", callback_data="limits")],
        [InlineKeyboardButton("⚙️ Ayarlar", callback_data="settings")],
        [InlineKeyboardButton("👥 Admin Listesi", callback_data="adminlistesi")],
        [InlineKeyboardButton("❌ Kapat", callback_data="kapat")]
    ])
    await msg.reply("👋 Merhaba! Aşağıdan bir seçenek seç:", reply_markup=btn)

# ================= NSFW TESPİT =================

# --- OpenCV 'imread' polyfill (bazı build'lerde eksik çıkabiliyor)
if not hasattr(cv2, "imread"):
    try:
        import imageio.v3 as iio
        def _cv2_imread(path):
            arr = iio.imread(path)
            if arr.ndim == 2:
                arr = np.stack([arr]*3, axis=-1)
            # imageio RGB verir -> BGR'e çevir
            return arr[:, :, ::-1].copy()
        cv2.imread = _cv2_imread
        print("cv2.imread polyfill aktif.")
    except Exception as e:
        print("cv2.imread polyfill kurulamıyor:", e)

# NudeNet modelini yükle
detector = NudeDetector()

# Duyarlı gördüğümüz label seti
NSFW_LABELS = {
    "FEMALE_BREAST_EXPOSED",
    "FEMALE_GENITALIA_EXPOSED",
    "MALE_GENITALIA_EXPOSED",
    "ANUS_EXPOSED",
    "BUTTOCKS_EXPOSED",
    # varyant isimler:
    "EXPOSED_BREAST", "EXPOSED_GENITALIA", "EXPOSED_BUTTOCKS", "EXPOSED_ANUS",
    # ekstra:
    "BELLY_EXPOSED", "ARMPITS_EXPOSED", "FEET_EXPOSED",
}

def upscale_min_512(in_path: str) -> str:
    try:
        im = Image.open(in_path).convert("RGB")
        w, h = im.size
        m = min(w, h)
        if m < 512:
            scale = 512 / m
            im = im.resize((int(w*scale), int(h*scale)), Image.LANCZOS)
        out = f"{in_path}.jpg"
        im.save(out, "JPEG", quality=92)
        return out
    except Exception as e:
        print("upscale_min_512 hata:", e)
        return in_path

def extract_webm_frames(path: str) -> list:
    """ .webm / video stickerlardan 0%, 40%, 70% kare al """
    outs = []
    try:
        cap = cv2.VideoCapture(path)
        total = int(cap.get(cv2.CAP_PROP_FRAME_COUNT) or 0)
        if total <= 0:
            # en azından 1 kare okumayı dene
            ok, frame = cap.read()
            if ok:
                out = f"{path}_f0.jpg"
                cv2.imwrite(out, frame)
                outs.append(out)
            cap.release()
            return outs
        picks = sorted(list({0, int(total*0.4), int(total*0.7)}))
        for idx in picks:
            cap.set(cv2.CAP_PROP_POS_FRAMES, max(0, idx))
            ok, frame = cap.read()
            if not ok: continue
            out = f"{path}_f{idx}.jpg"
            cv2.imwrite(out, frame)
            outs.append(out)
        cap.release()
    except Exception as e:
        print("extract_webm_frames hata:", e)
    return outs

def extract_tgs_frames(path: str) -> list:
    outs = []
    if not LOTTIE_OK:
        return outs
    try:
        anim = lottie_importers.import_tgs(path)
        for f in [0, 5, 10]:
            out_png = f"{path}_f{f}.png"
            try:
                lottie_exporters.export_png(anim, out_png, frame=f, scale=2.0)
                outs.append(out_png)
            except Exception:
                pass
    except Exception as e:
        print("lottie hata:", e)
    return outs

def is_path_nsfw(img_path: str, threshold: float) -> bool:
    try:
        res = detector.detect(img_path) or []
        max_score = 0.0
        for d in res:
            label = (d.get("label") or d.get("class") or "").upper()
            score = float(d.get("score", 0.0))
            if label in NSFW_LABELS or any(k in label for k in ["BREAST","GENITAL","BUTTOCK","ANUS"]):
                max_score = max(max_score, score)
        print(f"NudeNet: {os.path.basename(img_path)} max: {max_score}")
        return max_score >= threshold
    except Exception as e:
        print("NudeNet detect hata:", e)
        return False


MIN_SIDE = 512               # en kısa kenarı en az 512 px yap
# (ESKİ sabitler dursun ama karar mekanizması THR’den okur)
HARD_THRESHOLD = 0.85
SOFT_THRESHOLD = 0.55
SOFT_HITS_REQUIRED = 2

def preprocess_for_nudenet(in_path: str) -> str:
    """
    RGB JPEG'e çevir, en kısa kenarı >= 512 px olacak şekilde büyüt,
    hafif keskinlik artır. NudeNet bu tip girdilerde daha stabil.
    """
    try:
        im = Image.open(in_path).convert("RGB")
        w, h = im.size
        m = min(w, h)
        # ---- dinamik MINSIDE ----
        eff_min_side = int(THR.get("MINSIDE", MIN_SIDE))
        if m < eff_min_side:
            scale = eff_min_side / m
            im = im.resize((int(w*scale), int(h*scale)), Image.LANCZOS)

        # hafif keskinlik + kontrast
        im_np = np.array(im, dtype=np.uint8)
        im_np = cv2.GaussianBlur(im_np, (0, 0), 1.0)
        im_np = cv2.addWeighted(im_np, 1.5, im_np, -0.5, 0)

        out = f"{in_path}.nudeprep.jpg"
        Image.fromarray(im_np).save(out, "JPEG", quality=92)
        return out
    except Exception as e:
        print("preprocess_for_nudenet hata:", e)
        return in_path  # en kötü orijinali dön

def extract_webm_frames(path: str, max_frames: int = 8) -> list[str]:
    """
    webm/mp4 için: sabit aralıklı + rastgele kareler.
    """
    outs = []
    try:
        cap = cv2.VideoCapture(path)
        if not cap or not cap.isOpened():
            raise RuntimeError("VideoCapture açılamadı")

        total = int(cap.get(cv2.CAP_PROP_FRAME_COUNT) or 0)
        if total <= 0:
            # imageio fallback
            try:
                import imageio
                import imageio_ffmpeg  # yalnızca ffmpeg var mı diye
                r = imageio.get_reader(path)
                idxs = list(range(0, len(r)))[:max_frames]
                for i in idxs:
                    frame = r.get_data(i)
                    out = f"{path}_f{i}.jpg"
                    cv2.imwrite(out, cv2.cvtColor(frame, cv2.COLOR_RGB2BGR))
                    outs.append(out)
                r.close()
                return outs
            except Exception as e:
                print("imageio fallback hata:", e)
                return outs

        # ---- dinamik GIFMAX & GIFSTEP ----
        eff_max = int(THR.get("GIFMAX", max_frames))
        eff_step = max(1, int(THR.get("GIFSTEP", 5)))

        base = set()
        # step’li örnekleme
        for i in range(0, total, eff_step):
            base.add(i)
            if len(base) >= eff_max:
                break

        # garanti olsun diye birkaç sabit nokta:
        base |= {0, int(total*0.3) if total else 0, int(total*0.6) if total else 0, max(0, total-2)}

        # max sınırı uygula
        base = sorted(list(base))[:eff_max]

        for i in base:
            cap.set(cv2.CAP_PROP_POS_FRAMES, max(0, i))
            ok, frame = cap.read()
            if not ok:
                continue
            out = f"{path}_f{i}.jpg"
            cv2.imwrite(out, frame)
            outs.append(out)
        cap.release()
    except Exception as e:
        print("extract_webm_frames hata:", e)
    return outs

def nudenet_score_for(path: str) -> float:
    """
    Tek görsel için NudeNet'ten 'unsafe' skorların maksimumu.
    (Mevcut detector.detect() mantığınla uyumlu)
    """
    try:
        res = detector.detect(path) or []
        mx = 0.0
        for d in res:
            label = (d.get("label") or d.get("class") or "").upper()
            score = float(d.get("score", 0.0))
            if any(k in label for k in ["BREAST", "GENITAL", "BUTTOCK", "ANUS", "EXPOSED"]):
                mx = max(mx, score)
        if DEBUG:
            print(f"NudeNet: {os.path.basename(path)} max: {mx}")
        return mx
    except Exception as e:
        if DEBUG:
            print("NudeNet detect hata:", e)
        return 0.0

def should_delete(scores: list[float]) -> bool:
    """
    Karar:
      - herhangi bir kare HARD_THRESHOLD’i (THR) geçerse sil
      - ya da SOFT_THRESHOLD’i geçen kare sayısı >= SOFT_HITS_REQUIRED ise sil
    """
    if not scores:
        return False
    if max(scores) >= THR["HARD_THRESHOLD"]:
        return True
    soft_hits = sum(1 for s in scores if s >= THR["SOFT_THRESHOLD"])
    return soft_hits >= int(THR["SOFT_HITS_REQUIRED"])



@app.on_message(filters.group & filters.sticker)
async def sticker_filter(_, msg: Message):
    tmp = []
    try:
        downloaded_path = await app.download_media(msg.sticker)
        tmp.append(downloaded_path)

        candidate_images = []

        if msg.sticker.is_video:
            # webm/mp4 -> çok kare çek
            frames = extract_webm_frames(downloaded_path, max_frames=5)
            for f in frames:
                tmp.append(f)
                candidate_images.append(preprocess_for_nudenet(f))

        elif msg.sticker.is_animated:
            # .tgs -> lottie varsa birkaç frame çıkar (sende zaten var)
            try:
                from lottie import importers as lottie_importers
                from lottie import exporters as lottie_exporters
                anim = lottie_importers.import_tgs(downloaded_path)
                for fidx in [0, 5, 10, 15]:
                    out_png = f"{downloaded_path}_f{fidx}.png"
                    lottie_exporters.export_png(anim, out_png, frame=fidx, scale=2.0)
                    tmp.append(out_png)
                    candidate_images.append(preprocess_for_nudenet(out_png))
            except Exception as e:
                print("lottie hata:", e)

        else:
            # statik .webp/.png -> tek görsel ama ön-işleme şart
            pp = preprocess_for_nudenet(downloaded_path)
            if pp != downloaded_path:
                tmp.append(pp)
            candidate_images.append(pp)

        # Skorları topla
        scores = []
        for p in candidate_images:
            s = nudenet_score_for(p)
            ks = kiss_score(p)
            # yalnızca eşik üstü ise öpüşme skorunu dikkate al
            if ks >= float(THR.get("KISS_THRESHOLD", 0.35)):
                s = max(s, ks)
            scores.append(s)

        # Karar: gelişmiş mantık + global güvenlik skoru fallback
        delete = should_delete(scores) or (scores and max(scores) >= global_security_score)

        if delete:
            try:
                await msg.delete()
            except Exception as e:
                print("delete fail:", e)

    except Exception as e:
        print("sticker_filter hata:", e)
    finally:
        for p in tmp:
            try:
                if p and os.path.exists(p):
                    os.remove(p)
            except:
                pass


# ---------- callback (üyeler kullanamaz) ----------
@app.on_callback_query()
async def buton(_, cb: CallbackQuery):
    cid = cb.message.chat.id
    if cb.message.chat.type in ("supergroup", "group") and not is_group_bot_admin(cid, cb.from_user.id):
        return await cb.answer("Bu menü sadece yöneticilere açık.", show_alert=True)

    data = cb.data
    if data == "kapat":
        await cb.message.delete(); return

    elif data == "help":
        await cb.message.edit_text(
            "🆘 Yardım Menüsü:\n\n"
            "🛡️ /guvenlik [0.1 - 1.0] (Sadece Bot Sahibi)\n"
            " ➡️ Global sticker silme hassasiyetini ayarlar.\n\n"
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
            "ℹ️ /hakkinda\n"
            " ➡️ Bot hakkında bilgi.",
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
        gmax = get_chat_max_grant(cid)
        await cb.message.edit_text(
            f"⚙️ Ayarlar\n\n"
            f"🛡️ **Global Güvenlik Seviyesi: {global_security_score}** (%{int(global_security_score*100)})\n"
            f"{thresholds_summary()}\n\n"  # <-- EKLENDİ
            f"🎁 Gruba Özel Günlük Hak: {gmax}\n\n"
            "➡️ Değiştirmek için komutları kullanın:\n"
            "`/guvenlik [değer]` (Sadece Bot Sahibi)\n"
            "`/hakayarla [adet]`",
            reply_markup=InlineKeyboardMarkup([[InlineKeyboardButton("◀️ Geri", callback_data="geri")]])
        )

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
        await cb.message.delete()
        await menu(_, cb.message)




# --- GIF (Telegram animation) filtresi ---
@app.on_message(filters.group & filters.animation)
async def gif_animation_filter(_, msg: Message):
    tmp = []
    try:
        # Telegram GIF = MP4, video gibi kare al
        downloaded_path = await app.download_media(msg.animation)
        tmp.append(downloaded_path)

        frames = extract_webm_frames(downloaded_path, max_frames=6)
        candidate_images = []
        for f in frames:
            tmp.append(f)
            candidate_images.append(preprocess_for_nudenet(f))

        scores = []
        for p in candidate_images:
            s = nudenet_score_for(p)
            ks = kiss_score(p)
            if ks >= float(THR.get("KISS_THRESHOLD", 0.35)):
                s = max(s, ks)
            scores.append(s)

        delete = should_delete(scores) or (scores and max(scores) >= global_security_score)

        if delete:
            try:
                await msg.delete()
            except Exception as e:
                if DEBUG:
                    print("gif delete fail:", e)
    except Exception as e:
        if DEBUG:
            print("gif_animation_filter hata:", e)
    finally:
        for p in tmp:
            try:
                if p and os.path.exists(p):
                    os.remove(p)
            except:
                pass



# ------------------ Basit "kissing" sezgisi ------------------
# OpenCV Haar yüz modeli (opencv-data içinden gelir)
_FACE_CASCADE = cv2.CascadeClassifier(cv2.data.haarcascades + 'haarcascade_frontalface_default.xml')

def kiss_score(img_path: str) -> float:
    """
    Aynı karede iki yüz varsa ve birbirine çok yakınsa (yan yana),
    0.60 - 0.90 arası bir "risk" skoru döndürür. Aksi halde 0.0.
    """
    try:
        img = cv2.imread(img_path)
        if img is None:
            return 0.0
        gray = cv2.cvtColor(img, cv2.COLOR_BGR2GRAY)

        faces = _FACE_CASCADE.detectMultiScale(gray, scaleFactor=1.2, minNeighbors=5, minSize=(40, 40))
        if len(faces) < 2:
            return 0.0

        # En büyük iki yüz
        faces = sorted(faces, key=lambda r: r[2] * r[3], reverse=True)[:2]

        def center(rect):
            x, y, w, h = rect
            return (x + w / 2.0, y + h / 2.0, w, h)

        c1 = center(faces[0])
        c2 = center(faces[1])

        # Yüzler arası mesafe (piksel) ve normalize et
        dx = abs(c1[0] - c2[0])
        dy = abs(c1[1] - c2[1])
        dist = (dx * dx + dy * dy) ** 0.5
        avg_w = (c1[2] + c2[2]) / 2.0
        if avg_w <= 1:
            return 0.0

        norm = dist / avg_w

        # Şartlar: benzer yükseklik, yan yana ve yakınlık
        vertical_ok = dy < 0.5 * avg_w     # dikey fark küçük
        side_by_side = dx > 0.3 * avg_w    # gerçekten yan yana
        close_ok = norm < 0.9              # yeterince yakın

        if vertical_ok and side_by_side and close_ok:
            # Ne kadar yakınsa skor o kadar yüksek
            # norm ~0.3 -> ~0.9 skor, norm ~0.9 -> ~0.6 skor
            score = max(0.60, min(0.90, 1.0 - norm / 1.2))
            return float(score)

        return 0.0
    except Exception:
        return 0.0



# --- Gerçek .gif dosyası (belge olarak gönderilen) filtresi ---
@app.on_message(filters.group & filters.document)
async def gif_document_filter(_, msg: Message):
    # Sadece image/gif mime’ını hedefle
    try:
        if not msg.document or (msg.document.mime_type or "") != "image/gif":
            return

        tmp = []
        downloaded_path = await app.download_media(msg.document)
        tmp.append(downloaded_path)

        # imageio ile birkaç kare çek (gerçek GIF çok kareli olabilir)
        candidate_images = []
        try:
            import imageio.v3 as iio
            # İlk kare + ortalarından birkaç tanesi
            gif = iio.imiter(downloaded_path)
            frames = []
            # İlk 10 kareden 6 taneye kadar örnekle
            for idx, frame in enumerate(gif):
                if idx in (0, 2, 4, 6, 8, 10):
                    out = f"{downloaded_path}_f{idx}.jpg"
                    Image.fromarray(frame).convert("RGB").save(out, "JPEG", quality=92)
                    tmp.append(out)
                    candidate_images.append(preprocess_for_nudenet(out))
                if idx >= 10:
                    break
        except Exception as e:
            if DEBUG:
                print("gif (image/gif) kare çıkarma hata:", e)

        scores = []
        for p in candidate_images:
            s = nudenet_score_for(p)
            ks = kiss_score(p)
            if ks >= float(THR.get("KISS_THRESHOLD", 0.35)):
                s = max(s, ks)
            scores.append(s)

        delete = should_delete(scores) or (scores and max(scores) >= global_security_score)

        if delete:
            try:
                await msg.delete()
            except Exception as e:
                if DEBUG:
                    print("gif(doc) delete fail:", e)

    except Exception as e:
        if DEBUG:
            print("gif_document_filter hata:", e)
    finally:
        # tmp temizliği
        try:
            for p in tmp:
                if p and os.path.exists(p):
                    os.remove(p)
        except:
            pass




# ---------- komutlar ----------
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

# ---- (EKLENDİ) NSFW threshold komutları (/hard, /soft, /hits)
def _is_owner(uid: int) -> bool:
    return uid == admin_id

@app.on_message(filters.command("hard"))
async def cmd_hard(_, msg: Message):
    if not _is_owner(msg.from_user.id):
        return
    parts = msg.text.split()
    if len(parts) < 2:
        return await msg.reply("Kullanım: `/hard 0.80` (0-1 arası)", quote=True)
    val = _try_float(parts[1])
    if val is None or not (0.0 <= val <= 1.0):
        return await msg.reply("Kullanım: `/hard 0.80` (0-1 arası)", quote=True)
    THR["HARD_THRESHOLD"] = val
    save_thresholds(THR)
    await msg.reply(f"✅ HARD eşik: **{val}**\n\n{thresholds_summary()}", quote=True)

@app.on_message(filters.command("soft"))
async def cmd_soft(_, msg: Message):
    if not _is_owner(msg.from_user.id):
        return
    parts = msg.text.split()
    if len(parts) < 2:
        return await msg.reply("Kullanım: `/soft 0.55` (0-1 arası)", quote=True)
    val = _try_float(parts[1])
    if val is None or not (0.0 <= val <= 1.0):
        return await msg.reply("Kullanım: `/soft 0.55` (0-1 arası)", quote=True)
    THR["SOFT_THRESHOLD"] = val
    save_thresholds(THR)
    await msg.reply(f"✅ SOFT eşik: **{val}**\n\n{thresholds_summary()}", quote=True)

@app.on_message(filters.command("hits"))
async def cmd_hits(_, msg: Message):
    if not _is_owner(msg.from_user.id):
        return
    parts = msg.text.split()
    if len(parts) < 2 or not parts[1].isdigit():
        return await msg.reply("Kullanım: `/hits 2` (1–10 arası)", quote=True)
    val = int(parts[1])
    if val < 1 or val > 10:
        return await msg.reply("Kullanım: `/hits 2` (1–10 arası)", quote=True)
    THR["SOFT_HITS_REQUIRED"] = val
    save_thresholds(THR)
    await msg.reply(f"✅ HITS: **{val}**\n\n{thresholds_summary()}", quote=True)

# ---- (EKLENDİ) Dinamik ayar komutları: /minside, /gifmax, /gifstep, /kiss
@app.on_message(filters.command("minside"))
async def cmd_minside(_, msg: Message):
    if not _is_owner(msg.from_user.id):
        return
    parts = msg.text.split()
    if len(parts) < 2:
        return await msg.reply("Kullanım: `/minside 768`", quote=True)
    try:
        val = int(parts[1])
        if val < 256 or val > 2048:
            return await msg.reply("MINSIDE 256–2048 arası olmalı.", quote=True)
        THR["MINSIDE"] = val
        save_thresholds(THR)
        await msg.reply(f"✅ MINSIDE = **{val}**", quote=True)
    except:
        await msg.reply("Kullanım: `/minside 768`", quote=True)

@app.on_message(filters.command("gifmax"))
async def cmd_gifmax(_, msg: Message):
    if not _is_owner(msg.from_user.id):
        return
    parts = msg.text.split()
    if len(parts) < 2:
        return await msg.reply("Kullanım: `/gifmax 12`", quote=True)
    try:
        val = int(parts[1])
        if val < 1 or val > 40:
            return await msg.reply("GIFMAX 1–40 arası olmalı.", quote=True)
        THR["GIFMAX"] = val
        save_thresholds(THR)
        await msg.reply(f"✅ GIFMAX = **{val}**", quote=True)
    except:
        await msg.reply("Kullanım: `/gifmax 12`", quote=True)

@app.on_message(filters.command("gifstep"))
async def cmd_gifstep(_, msg: Message):
    if not _is_owner(msg.from_user.id):
        return
    parts = msg.text.split()
    if len(parts) < 2:
        return await msg.reply("Kullanım: `/gifstep 2`", quote=True)
    try:
        val = int(parts[1])
        if val < 1 or val > 30:
            return await msg.reply("GIFSTEP 1–30 arası olmalı.", quote=True)
        THR["GIFSTEP"] = val
        save_thresholds(THR)
        await msg.reply(f"✅ GIFSTEP = **{val}**", quote=True)
    except:
        await msg.reply("Kullanım: `/gifstep 2`", quote=True)

@app.on_message(filters.command("kiss"))
async def cmd_kiss(_, msg: Message):
    if not _is_owner(msg.from_user.id):
        return
    parts = msg.text.split()
    if len(parts) < 2:
        return await msg.reply("Kullanım: `/kiss 0.33`", quote=True)
    val = _try_float(parts[1])
    if val is None or not (0.0 <= val <= 1.0):
        return await msg.reply("Kullanım: `/kiss 0.33` (0-1 arası)", quote=True)
    THR["KISS_THRESHOLD"] = val
    save_thresholds(THR)
    await msg.reply(f"💋 KISS threshold: **{val}**", quote=True)

@app.on_message(filters.command("seviyeayar"))
async def set_limit(_, msg: Message):
    cid, uid = msg.chat.id, msg.from_user.id
    if not is_group_bot_admin(cid, uid): return
    try:
        _, seviye, mesaj, süre_deger, süre_birim = msg.text.split()
        sure_saniye = parse_time(int(süre_deger), süre_birim)
        if cid not in limits: limits[cid] = {}
        ensure_default_level_for(cid)
        limits[cid][int(seviye)] = {"msg": int(mesaj), "süre": sure_saniye}
        save_json(LIMITS_FILE, {str(k): v for k, v in limits.items()})
        await msg.reply(f"✅ Seviye {seviye} ayarlandı.")
    except Exception:
        await msg.reply("⚠️ Kullanım: /seviyeayar [seviye] [mesaj] [süre] [saniye|dakika|saat]")

@app.on_message(filters.command("hakayarla"))
async def set_grant(_, msg: Message):
    cid, uid = msg.chat.id, msg.from_user.id
    if not is_group_bot_admin(cid, uid): return
    try:
        adet = int(msg.text.split()[1])
        set_chat_max_grant(cid, adet)
        await msg.reply(f"✅ (Grup) Günlük hak: {adet}")
    except Exception:
        await msg.reply("⚠️ Kullanım: /hakayarla [adet]")

@app.on_message(filters.command("verisil"))
async def reset_all(_, msg: Message):
    cid, uid = msg.chat.id, msg.from_user.id
    if not is_group_bot_admin(cid, uid): return
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
    cid, uid = msg.chat.id, msg.from_user.id
    if not is_group_bot_admin(cid, uid): return
    if cid in limits:
        limits.pop(cid, None)
        save_json(LIMITS_FILE, {str(k): v for k, v in limits.items()})
    ensure_default_level_for(cid)
    await msg.reply("🗑️ Bu gruptaki tüm seviye ayarları silindi. Varsayılan **Seviye 0 (1 mesaj / 1 sn)** aktif.")

@app.on_message(filters.command("durumum"))
async def user_status(_, msg: Message):
    uid, cid = msg.from_user.id, msg.chat.id
    key = f"({cid}, {uid})"
    today = str(datetime.now().date())
    if key not in user_data:
        user_data[key] = {"seviye": 0, "grant_count": 0, "date": today}
        user_msg_count[(cid, uid)] = 0
        save_json(USERDATA_FILE, convert_keys_to_str(user_data))
        save_json(COUNTS_FILE, convert_keys_to_str(user_msg_count))
    if user_data[key].get("date") != today:
        user_data[key]["date"] = today
        user_data[key]["seviye"] = 0
        user_data[key]["grant_count"] = 0
        user_msg_count[(cid, uid)] = 0
        save_json(USERDATA_FILE, convert_keys_to_str(user_data))
        save_json(COUNTS_FILE, convert_keys_to_str(user_msg_count))
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
    cid, uid = msg.chat.id, msg.from_user.id
    if not is_group_bot_admin(cid, uid):
        return await msg.reply("❌ Yetkin yok.")
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
    cid, uid = msg.chat.id, msg.from_user.id
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

@app.on_message(filters.command("seviyelistesi"))
async def seviyelistesi_cmd(_, msg: Message):
    cid, uid = msg.chat.id, msg.from_user.id
    if msg.chat.type in ("supergroup", "group") and not is_group_bot_admin(cid, uid):
        return
    ensure_default_level_for(cid)
    if cid not in limits or not limits[cid]:
        return await msg.reply("⚠️ Bu grupta ayarlanmış seviye yok.")
    text = "📊 Seviye Listesi (Bu Grup):\n\n"
    for s in sorted(limits[cid].keys()):
        l = limits[cid][s]
        sure_metni = saniyeyi_donustur(l['süre'])
        text += f"🔹 Seviye {s}: {l['msg']} mesaj → {sure_metni} izin\n"
    await msg.reply(text)

@app.on_message(filters.command("hakkinda"))
async def about_info(_, msg: Message):
    if msg.chat.type in ("supergroup", "group"):
        if not is_group_bot_admin(msg.chat.id, msg.from_user.id):
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

# ---------- mesaj takibi ----------
@app.on_message(filters.group & ~filters.service)
async def takip_et(_, msg: Message):
    uid, cid = msg.from_user.id, msg.chat.id

    # 🔴 EKLENDİ: adminleri tamamen hariç tut
    if is_group_bot_admin(cid, uid):
        return  

    ensure_default_level_for(cid)
    key = f"({cid}, {uid})"
    now = time.time()
    today = str(datetime.now().date())
    if key not in user_data or user_data[key]["date"] != today:
        user_data[key] = {"seviye": 0, "grant_count": 0, "date": today}
        user_msg_count[(cid, uid)] = 0
    if now < izin_sureleri.get((cid, uid), 0): 
        return

    user_msg_count[(cid, uid)] = user_msg_count.get((cid, uid), 0) + 1
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

            sure_metni = saniyeyi_donustur(lim['süre'])
            await msg.reply(
                f"🎉 Tebrikler! Seviye {seviye} tamamlandı. **{sure_metni}** sticker/GIF izni verildi."
            )

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

    save_json(USERDATA_FILE, convert_keys_to_str(user_data))
    save_json(COUNTS_FILE, convert_keys_to_str(user_msg_count))
    save_json(IZIN_FILE, convert_keys_to_str(izin_sureleri))


# ---------- gruba eklenme olayı ----------
@app.on_chat_member_updated()
async def yeni_katilim(_, cmu: ChatMemberUpdated):
    try:
        me = await app.get_me()
        if cmu.new_chat_member and cmu.new_chat_member.user.id == me.id:
            cid = cmu.chat.id
            await ensure_group_admin_bucket(cid)
            ensure_default_level_for(cid)

            adder_id = None
            if cmu.from_user:
                adder_id = cmu.from_user.id

            if adder_id:
                await add_group_admin(cid, adder_id)
                try:
                    u = await app.get_users(adder_id)
                    who = f"@{u.username}" if u.username else f"{u.first_name}"
                except:
                    who = str(adder_id)
                await app.send_message(cid, f"✅ Bot eklendi. {who} bu grup için bot-admin yapıldı.")
            else:
                chosen = None
                async for m in app.get_chat_members(cid, filter="administrators"):
                    if m.user.is_bot: continue
                    perms = m.privileges
                    if perms and getattr(perms, "can_restrict_members", False):
                        chosen = m.user.id; break
                if chosen:
                    await add_group_admin(cid, chosen)
                    try:
                        u = await app.get_users(chosen)
                        who = f"@{u.username}" if u.username else f"{u.first_name}"
                    except:
                        who = str(chosen)
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

# ---------- başlangıç ----------
print("🚀 Bot başlatılıyor...")
load_global_score()
app.run()
print("⏹️ Bot durduruldu.")
