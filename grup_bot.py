from pyrogram import Client, filters
from pyrogram.types import ChatPermissions, Message, ChatMemberUpdated
from datetime import datetime
import asyncio, time, json, os, re, logging
from dotenv import load_dotenv

# Log dosyasını ayarla
logging.basicConfig(
    filename="bot_log.txt",
    level=logging.INFO,
    format="%(asctime)s - %(levelname)s - %(message)s"
)

# Süreyi saniyeye çevir
def parse_sure(s: str) -> int:
    matches = re.findall(r"(\d+)\s*(saniye|sn|dakika|dk|saat|sa)", s.lower())
    total_seconds = 0
    for value, unit in matches:
        value = int(value)
        if unit in ["saniye", "sn"]:
            total_seconds += value
        elif unit in ["dakika", "dk"]:
            total_seconds += value * 60
        elif unit in ["saat", "sa"]:
            total_seconds += value * 3600
    return total_seconds

def convert_keys_to_str(d: dict) -> dict:
    return {str(k): v for k, v in d.items()}

def load_json(filename, default):
    return json.load(open(filename, "r", encoding="utf-8")) if os.path.exists(filename) else default

def save_json(filename, data):
    json.dump(data, open(filename, "w", encoding="utf-8"), indent=4)

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

limits = {int(k): v for k, v in load_json(LIMITS_FILE, {}).items()}
user_data = load_json(USERDATA_FILE, {})
user_msg_count = {eval(k): v for k, v in load_json(COUNTS_FILE, {}).items()}
izin_sureleri = {eval(k): v for k, v in load_json(IZIN_FILE, {}).items()}
yetkili_adminler = set(load_json(ADMINS_FILE, [admin_id]))
max_grant = 2

app = Client("bot", api_id=api_id, api_hash=api_hash, bot_token=bot_token)

def is_authorized(user_id: int): return user_id in yetkili_adminler

@app.on_message(filters.group & ~filters.service)
async def takip_et(_, msg: Message):
    uid, cid = msg.from_user.id, msg.chat.id
    key = f"({cid}, {uid})"
    now = time.time()
    today = str(datetime.now().date())

    if key not in user_data or user_data[key]["date"] != today:
        user_data[key] = {"seviye": 0, "grant_count": 0, "date": today}
        user_msg_count[key] = 0

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

            await msg.reply(f"🎉 Seviye {seviye} tamamlandı! {lim['süre']} sn boyunca çıkartma ve GIF izni verildi.")

            try:
                izin_ver = ChatPermissions(
                    can_send_messages=True,
                    can_send_stickers=True,
                    can_send_animations=True
                )
                await app.restrict_chat_member(cid, uid, izin_ver)
                await msg.reply("✅ Medya izni verildi: çıkartma + GIF gönderme açık")

                await asyncio.sleep(lim["süre"])

                izin_kisitla = ChatPermissions(
                    can_send_messages=True,
                    can_send_stickers=False,
                    can_send_animations=False
                )
                await app.restrict_chat_member(cid, uid, izin_kisitla)
                await msg.reply("⏳ Medya iznin sona erdi.")
            except Exception as e:
                logging.error(f"Telegram izin hatası: {e}", exc_info=True)
                await msg.reply("❌ Telegram izin veremedi. Bot admin mi kontrol et.")

            save_json(USERDATA_FILE, convert_keys_to_str(user_data))
            save_json(COUNTS_FILE, convert_keys_to_str(user_msg_count))
            save_json(IZIN_FILE, convert_keys_to_str(izin_sureleri))
            break

@app.on_chat_member_updated()
async def yeni_katilim(_, cmu: ChatMemberUpdated):
    if cmu.new_chat_member and cmu.new_chat_member.user.is_bot:
        if cmu.new_chat_member.user.id == (await app.get_me()).id:
            await app.send_message(
                cmu.chat.id,
                "👋 Selam! Ben aktiflik takip botuyum.\n"
                "Mesaj atan kullanıcılar seviye atlar, çıkartma ve GIF izni kazanır.\n"
                "Komutlar için /menu yazabilirsin."
            )

print("✅ Bot başlatılıyor...")
app.run()
