# Telegram-sticker
# 🤖 Telegram Grup Yönetim Botu

Bu proje, **Telegram gruplarının yönetimini kolaylaştırmak** ve **katılımcıların etkileşimini artırmak** amacıyla geliştirilmiş bir **kullanıcı botudur** (userbot). Pyrogram kütüphanesi kullanılarak yazılmıştır.

---

## 🎯 Botun Amacı

Telegram grupları büyüdükçe, kullanıcı davranışlarını yönetmek zorlaşır. Bu botun amacı:

- **Pasif kullanıcıları aktif hale getirmek**
- **Medya gönderimlerini (çıkartma, gif, müzik vb.) kontrollü şekilde serbest bırakmak**
- **Karmaşık izin yapılarını basit komutlarla yönetilebilir hale getirmek**
- **Grup içi düzeni korumak için otomatik sınırlamalar getirmek**
- **Kimin ne zaman ne yaptığına dair log tutmak**

Özetle, bu bot sayesinde grup yöneticileri **daha az komutla daha çok kontrol** sahibi olur.

---

## 🚀 Temel Özellikler

- 🎯 **Seviye sistemi**: Kullanıcılar attıkları mesaj sayısına göre seviyeye ulaşır. Belirli seviyelere ulaşanlara medya izinleri otomatik verilir.
- ⏱️ **Süreli izinler**: Kullanıcılara belirli süreliğine çıkartma, GIF, müzik gönderme gibi haklar tanınabilir.
- ⚙️ **Ayar menüsü**: Seviye limitleri, izin süresi, kaç kez hak verileceği gibi ayarlar komutla değiştirilebilir.
- 📊 **Kullanıcı istatistikleri**: Her kullanıcı, hangi seviyede olduğunu ve bir üst seviye için ne kadar mesaj atması gerektiğini görebilir.
- 🔐 **Yetki sistemi**: Belirli komutları sadece bot sahibi veya yetki verilen kişiler kullanabilir.
- 📁 **Veri kaydı**: Kullanıcı, ayar ve log verileri `.json` dosyalarına kayıt edilir ve bot yeniden başlatıldığında korunur.
- 🖱️ **Inline menüler**: Tüm menüler ve yardım ekranları butonlu ve kullanıcı dostudur.

---

## 📌 Gereksinimler

- Python 3.8 veya üstü
- Pyrogram
- Tgcrypto
- python-dotenv

Kurulum:
```bash
pip install -r requirements.txt


---

⚙️ Kurulum

1. Reponun kopyasını al:

git clone https://github.com/kullanici/bot-adi.git
cd bot-adi


2. .env dosyasını oluştur ve bilgileri doldur:

API_ID=TELEGRAM_API_ID
API_HASH=TELEGRAM_API_HASH
BOT_TOKEN=TELEGRAM_BOT_TOKEN
OWNER_ID=SENIN_TELEGRAM_IDN


3. Botu başlat:

python bot.py



> Not: Eğer kullanıcı botu olarak çalışıyorsa .session dosyan mevcut olmalı.




---

📚 Komut Listesi

Komut	Açıklama	Kim Kullanabilir

/start	Başlangıç ve yardım mesajı	Herkes
/menu	Butonlu genel menü	Herkes
/limits	Seviye ayarlarını göster	Herkes
/userinfo	Kullanıcı istatistiklerini gösterir	Herkes
/setlimit <tip> <sayı>	Seviye limitini değiştirir	Yalnızca admin
/reset	Günlük sayaçları sıfırlar	Yalnızca admin
/giveme @kullanici	Kullanıcıya komut yetkisi verir	Yalnızca admin
/revoke @kullanici	Yetkisini alır	Yalnızca admin



---

🧩 Örnek Kullanım Senaryosu

1. Grup üyeleri mesaj atarak seviye kazanır.


2. Belirli seviyeye ulaştıklarında, bot otomatik olarak onlara çıkartma/gif gönderme hakkı tanır.


3. Yetkili kişiler /setlimit komutuyla bu sınırları değiştirebilir.


4. /menu komutuyla tüm işlemler butonlarla yapılabilir.


5. /userinfo ile her kullanıcı kendi ilerlemesini görebilir.


6. Bot her gün sayaçları sıfırlar, ancak veri kaybı yaşanmaz.




---

🔒 Güvenlik

Komut yetkileri sadece bot sahibi veya /giveme ile yetki verilen kullanıcılardadır.

Tüm ayarlar ve veriler kalıcı .json dosyalarında saklanır.



---

🔍 Geliştirme ve Katkı

Botu geliştirmek istiyorsan, pull request gönderebilir veya issues bölümünden sorun bildirebilirsin. Kod Python'da yazılmıştır, geliştirici dostudur.


---

📄 Lisans

MIT Lisansı — detaylar için LICENSE dosyasına bak.

