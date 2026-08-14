# VALS CLUB — Gerçek Pilot MVP

Bu paket, tek dosyalık görsel demo değil; **çok kullanıcılı, veritabanı kullanan gerçek bir web MVP'sidir.**

## İçerdiği fonksiyonlar

- Kullanıcı kayıt / giriş
- Şifre hashleme
- Günlük giriş ve streak
- Günlük görevler
- XP ve seviye
- Günlük mystery box
- Ürün koleksiyonu
- Ürün kaydında XP
- Home Rating
- XP ile ödül kullanma
- Liderlik tablosu
- Admin ekranı
- Mobil uyumlu PWA temeli
- SQLite veritabanı
- Docker ile çalıştırma

## Bilgisayarda çalıştırma

Python 3.11+ önerilir.

```bash
python -m venv .venv
# Windows:
.venv\Scripts\activate
# macOS/Linux:
source .venv/bin/activate

pip install -r requirements.txt
python app.py
```

Sonra:
`http://localhost:5000`

## Pilot için internetten erişilebilir hale getirme

Bu uygulama Vals sunucusunda veya bir VPS üzerinde çalıştırılabilir. Docker ile:

```bash
docker compose up -d --build
```

Ardından domain + HTTPS reverse proxy eklenir.

## İlk admin hesabı

E-posta: `admin@valsclub.local`  
Şifre: `ChangeMe123!`

**İlk girişten sonra production ortamında bu hesabı ve SECRET_KEY'i mutlaka değiştirin.**

## Pilot başlamadan önce eklenmesi gerekenler

Bu MVP'nin amacı 1 aylık kontrollü şirket içi testtir. Piyasaya açmadan önce özellikle:

1. KVKK / açık rıza ve aydınlatma metinleri
2. E-posta doğrulama / şifre sıfırlama
3. Gerçek ürün seri numarası doğrulama
4. QR kod üretimi
5. Gerçek kupon altyapısı
6. Push bildirimleri
7. Gelişmiş admin paneli
8. Analytics / cohort raporları
9. Rate limiting / CSRF / production security hardening
10. Backup ve hata izleme

eklenmelidir.

## 1 aylık pilotta ölçülecek ana metrikler

- Kayıt olan kullanıcı sayısı
- D1 / D7 / D30 geri dönüş
- Kullanıcı başına haftalık aktif gün
- Günlük görev tamamlama oranı
- Sandık açma oranı
- Ortalama XP
- Ürün kayıt oranı
- Ödül kullanım oranı
- Referral oranı
- 30 günde aktif kalan kullanıcı oranı

**Ana başarı metriği:** 30 gün içinde en az 7 farklı günde geri gelen kullanıcı oranı.
