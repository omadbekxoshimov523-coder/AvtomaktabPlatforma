# 🚗 AVTOMAKTAB — Amaliy mashg'ulotlarni boshqarish platformasi

Avtomaktabdagi amaliy haydovchilik mashg'ulotlarini to'liq boshqaradigan **real, to'liq ishlaydigan** platforma (demo emas).

## 🚀 Ishga tushirish (2 qadam)

1. **`RUN.bat`** faylini bosing (ikki marta).
2. Brauzer avtomatik `http://127.0.0.1:8080/` ochiladi.

> Hech qanday qo'shimcha o'rnatish shart emas — faqat Python 3.12+ kerak.
> Backend: Python stdlib (`http.server`). Ma'lumotlar bazasi: **SQLite** (real, `data/avtomaktab.db`).
> Bitta server, bitta port (8080): port band bo'lsa, ikkinchi nusxa o'zi chiqib ketadi.

## 🔑 Demo hisoblar

| Rol | Login | Parol |
|---|---|---|
| 🛡️ Admin | `admin` | `admin123` |
| 👨‍🏫 Instruktor (Akmal Karimov) | `usrL_00001` | `usrP_00001` |
| 👨‍🏫 Instruktor (Jasur Aliyev) | `usrL_00002` | `usrP_00002` |
| 👨‍🏫 Instruktor (Vali Hasanov) | `usrL_00003` | `usrP_00003` |
| 👨‍🎓 Talaba (Omadbek) | `usrL_00004` | `usrP_00004` |
| 👨‍🎓 Talaba (Ali) | `usrL_00005` | `usrP_00005` |
| 👨‍🎓 Talaba (Vali) | `usrL_00006` | `usrP_00006` |
| 👨‍🎓 Talaba (Hasan) | `usrL_00007` | `usrP_00007` |

Ochiq ro'yxatdan o'tish **yo'q** — barcha foydalanuvchilarni admin yaratadi (login/parol avtomatik: `usrL_00001`, `usrP_00001`, ...).

## ✅ Asosiy qoidalar (bajarilgan)

- **Har bir instruktorning o'zi bitta avtomobili bor** (`assigned_car_id`).
- Mashg'ulot yaratishda **avtomobil tanlanmaydi** — instruktor tanlanadi, tizim avtomatik avtomobil va sig'imni aniqlaydi.
- **Capacity** avtomobilning `practice_capacity` qiymatidan olinadi (masalan Cobalt = 4).
- **Avtomobil almashtirilsa**, eski mashg'ulotlar tarixda eski avtomobil bilan qoladi (`car_plate_snapshot`, `capacity_snapshot`).
- Instruktor bandligi, talaba bandligi, ish jadvali, tanaffus, avtomobil holati — **backend majburiy tekshiradi**.
- Ochiq registratsiya yo'q, parollar **scrypt hash** sifatida saqlanadi.
- Xavfsizlik: HttpOnly cookie, SameSite, CSRF himoyasi, RBAC, rate-limit, soft-delete, audit log.

## 🗂️ Loyiha tuzilishi

```
AvtomaktabPlatforma/
├── server.py              # HTTP server (stdlib), statik + API routing
├── RUN.bat                # ishga tushirish
├── RUN_TESTS.bat          # testlarni ishga tushirish
├── app/                   # backend modullari
│   ├── db.py              # SQLite sxemasi (20+ jadval)
│   ├── auth.py            # scrypt parol, session, RBAC, rate-limit
│   ├── rules.py           # 10 ta majburiy business tekshiruv
│   ├── api.py             # barcha REST endpointlar
│   ├── notify.py          # bildirishnomalar + audit log
│   ├── reports.py         # kunlik/haftalik/oylik hisobotlar
│   ├── export.py          # CSV / XLSX / PDF eksport
│   └── seed.py            # demo ma'lumotlar (birinchi ishga tushirishda)
├── web/                   # frontend (SPA)
│   ├── index.html         # login + app qobig'i
│   ├── css/styles.css     # dizayn tizimi (responsive)
│   └── js/
│       ├── i18n.js        # 🇺🇿 UZ / 🇷🇺 RU / 🇬🇧 EN tarjimalar
│       ├── app.js         # marshrutlash, login, bildirishnomalar
│       ├── views-admin.js, views-instructor.js, views-student.js
│       ├── shared.js, ui.js, api.js
├── data/                  # avtomaktab.db + backups/ (avtomatik yaratiladi)
├── bot/                   # 🤖 Telegram bot (aiogram 3)
│   ├── main.py            # kirish nuqtasi (polling) + error handler
│   ├── config.py          # .env dan sozlash (BOT_TOKEN, ADMIN_IDS)
│   ├── db.py              # bazaviy qatlam (SQLite): avtomaktablar, users, clicks
│   ├── i18n.py            # UZ / RU / EN tarjimalar
│   ├── keyboards.py       # inline tugmalar
│   ├── .env.example       # namuna konfiguratsiya (tokensiz)
│   ├── requirements.txt   # aiogram, python-dotenv, qrcode
│   ├── handlers/          # start.py, schools.py (callbacks), admin.py
│   └── Dockerfile         # bot uchun image
└── tests/test_api.py      # avtomatik testlar (login, users, cars, sessions, security)
```

## 🧪 Testlar

`RUN_TESTS.bat` — avtomatik testlar quyidagilarni tekshiradi:
login (to'g'ri/noto'g'ri/blok), rol redirect, avtomatik login/parol, sequence,
bulk, dublikat, avtomobil yaratish/biriktirish/status/capacity/almashtirish,
session yaratish/avtomatik avtomobil/capacity/start/finish/cancel/reschedule,
**RBAC** (talaba → admin panelga kira olmaydi, instruktor boshqa instruktor
sessionini boshqarmaydi), parol hech qayerda ochiq ko'rinmasligi.

## 🔍 Qo'shimcha QA vositalari (ixtiyoriy)

- `py tools_js_check.py` — barcha JS fayllarni mini-lexer bilan tekshiradi
  (qavs balansi, noto'g'ri `{ "" }` shorthand kabi sintaksis xatolar).
- `py tools_qa_i18n.py` — `t("...")` chaqiruvlari i18n lug'atida bormi,
  yo'qotilgan kalit yo'qmi tekshiradi.
- `py tools_qa_smoke.py` — ishlayotgan serverda (127.0.0.1:8080) login +
  asosiy endpointlarni jonli tekshiradi (cookie orqali).

## 🌐 Tillar

🇺🇿 O'zbek (default) · 🇷🇺 Русский · 🇬🇧 English — login sahifasida va yuqori navbarda.

## 🔮 Kelajak uchun arxitektura tayyor

`branches` jadvali, `practice_requests`, `messages` (Telegram/SMS qo'shish oson),
multi-filial va kengaytirish uchun ajratilgan modullar.

---

# 🌍 Production (jonli muhit) uchun qo'llanma

## Talab qilinadigan dasturlar

| Dastur | Minimal versiya | Qayerda kerak |
|---|---|---|
| Python | 3.12+ | lokal ishlab chiqish |
| Docker + Docker Compose | 24+, v2 | server (VPS) da deploy |
| Git | 2.x | GitHub'ga yuklash |
| Node.js | **kerak emas** | frontend oddiy fayllar |

> Ilova **faqat Python stdlib** ishlatadi — `requirements.txt`, `npm install`
> degan narsalar yo'q, bu deploy'ni juda oson qiladi.

## Muhit o'zgaruvchilari (.env)

1. `copy .env.example .env` (yoki Linux: `cp .env.example .env`)
2. Kamida quyidagilarni to'ldiring:
   ```env
   HOST=0.0.0.0
   PORT=8080
   ADMIN_INITIAL_PASSWORD=kuchli_parol_123      # birinchi ishga tushirishda admin
   APP_PORT=8080
   BACKUP_RETENTION_DAYS=14
   ```
3. `.env` **github'ga yuklanmaydi** — `.gitignore`da qattiq qayd etilgan.

## Docker bilan ishga tushirish (server)

```bash
# 1) Kodni serverga ko'chirish (yoki git clone)
git clone https://github.com/omadbekxoshimov523-coder/AvtomaktabPlatforma.git
cd AvtomaktabPlatforma

# 2) .env yaratish va to'ldirish
cp .env.example .env
nano .env

# 3) Qurish va ishga tushirish
docker compose -f docker-compose.prod.yml up -d --build

# 4) Tekshirish
curl http://127.0.0.1:8080/api/health   # {"ok": true, "app": "Avtomaktab"}
docker compose -f docker-compose.prod.yml ps
```

- SQLite baza **named volume** (`avtomaktab-data`) da saqlanadi — container
  qayta qurilsa ham ma'lumot yo'qolmaydi.
- Zaxira fayllar hostdagi `./backups/` papkasiga tushadi.
- Yangi versiya chiqishi: `git pull && docker compose -f docker-compose.prod.yml up -d --build`

## CI/CD (GitHub Actions)

`.github/workflows/deploy.yml` — `main` branch'ga har push'da:

1. **Test** — `python -m tests.test_api` (78 test) + JS/i18n tekshiruvlari
2. **Build** — Docker image qurilib, health-check bilan smoke-test
3. **Deploy** — VPS'ga SSH orqali `docker compose up -d --build`
4. **Xato** — deploy to'xtaydi, GitHub bildiradi; ixtiyoriy Telegram xabari

GitHub repo → *Settings → Secrets and variables → Actions* da quyidagi
secret'larni qo'shing: `VPS_HOST`, `VPS_USER`, `VPS_SSH_KEY`, `VPS_APP_DIR`.

## Sayt (GitHub Pages)

**Manzil:** <https://omadbekxoshimov523-coder.github.io/AvtomaktabPlatforma/>

`site/index.html` — bitta fayl, tashqi resurssiz (shrift/rasm/JS yo'q).
`.github/workflows/pages.yml` `site/`'ni har push'da GitHub Pages'ga
joylashtiradi.

> **Muhim:** bu **faqat ko'rsatish (landing) sahifasi**. Platformaning o'zi
> GitHub Pages'da **ishlamaydi** — sababi ikkita:
> 1. GitHub Pages faqat statik fayl beradi, Python'ni ishga tushirmaydi.
>    Platforma esa `server.py` (`http.server` + `sqlite3`) bilan ishlaydi.
> 2. Frontend `/api/*` so'rovlarini shu serverga yuboradi
>    (`web/js/api.js:12`) — Pages'da bularga 404 qaytadi, ya'ni login
>    ishlamaydi.
>
> Shuning uchun **haqiqiy login sahifasi serverga (VPS) joylashtirilishi
> kerak**. Buni tayyorlab qo'yganmiz: yuqoridagi CI/CD + Docker.
> Server tayyor bo'lgach, `.env`dagi `PLATFORM_URL` ni o'zgartiring yoki
> Telegram'da `/set_url https://…` yuboring — bot darhol yangilaydi.

## Zaxira (backup) va tiklash

### Avtomatik zaxira (kuniga bir marta)

```bash
# VPS'da: crontab -e  qator qo'shish:
0 2 * * * /opt/avtomaktab/scripts/backup_cron.sh >> /var/log/avtomaktab-backup.log 2>&1
```

- Zaxira online (server ishlayotganda) `VACUUM INTO` orqali olinadi — yaxlit snapshot.
- `./backups/db_YYYYMMDD_HHMMSS.db` — har kuni yangi fayl.
- `BACKUP_RETENTION_DAYS` (standart 14) dan eski nusxalar o'chiriladi.
- **Tavsiya:** zaxirani bulutda saqlang — `.env`ga
  `RCLONE_REMOTE=b2:avtomaktab-backups` qo'ying (Backblaze B2 bepul ~10GB,
  yoki S3). Yana oddiyron: kunlik zaxirani boshqa kompyuterga/haydovchaga
  `scp` qilib oling.

### Qo'lda zaxira

```bash
# Lokal (Windows: py scripts\db_backup.py)
py scripts/db_backup.py

# Serverda (container ichida)
docker compose -f docker-compose.prod.yml exec app python scripts/db_backup.py --out /app/data/backups/db_manual.db
```

### Tiklash (restore)

```bash
# 1) Ilovani to'xtatish (baza fayli band bo'lmasligi uchun)
docker compose -f docker-compose.prod.yml stop app

# 2) Zaxira faylni container'ga berib tiklash (--replace: mavjud DB ustiga yozadi)
docker compose -f docker-compose.prod.yml run --rm \
  -v avtomaktab-data:/app/data \
  -v ./backups:/app/data/backups \
  app python scripts/db_restore.py --replace /app/data/backups/db_<SANA>.db

# 3) Qayta ishga tushirish
docker compose -f docker-compose.prod.yml up -d

# Lokal variant: py scripts\db_restore.py data\backups\db_<SANA>.db --replace
```

> Diqqat: `--replace` mavjud DB'ni o'chiradi. Restore'dan oldin yangi zaxira
> olish tavsiya: `py scripts/db_backup.py`.

## Tavsiya etilgan hosting

| Variant | Narx | Murakkablik | Docker | Avtomatik deploy |
|---|---|---|---|---|
| **VPS: Hetzner CX22 / DigitalOcean** ⭐ | ~$4–6/oy | O'rta | ✅ to'liq | GitHub Actions bilan |
| Railway.app | ~$5/oy dan | Past | ✅ (volume pullik) | ✅ |
| Render.com | ~$7/oy dan | Past | ✅ (disk pullik) | ✅ |

**Tavsiya: VPS (Hetzner Cloud CX22 — €4.3/oy) + GitHub Actions.** Sababi:
loyiha bitta yengil jarayon + SQLite; baza volume'da saqlanadi, zaxira va
cron bizning skript bilan ishlaydi, narx barqaror va to'liq nazorat bor.
Railway/Render yechimi ham ishlaydi, lekin SQLite uchun doimiy disk pullik
tarifda bo'ladi va zaxira/cron ustidan nazorat kamroq.

---

# 🤖 Telegram bot (avtomaktablar katalogi)

Foydalanuvchi brauzerda manzil qidirmaydi — `@<bot_username>` ochib,
avtomaktab tugmasini bosadi va shu platformaning login sahifasiga o'tadi.

## Ishlash printsipi

0. Platforma **avtomatik ulanadi**: `.env` dagi `PLATFORM_URL` bo'lsa, bot
   ishga tushganda o'sha platforma ro'yxatga qo'shiladi (takror ishga tushsa
   yangilanadi, xarojasiz). `/start` → Platforma nomi ostida **«🔗 Platformaga
   kirish»** tugmasi chiqadi, `/qr platforma` esa tayyor QR kod beradi.
1. `/start` → salomlashuv + **inline tugmalar** (faol avtomaktablar ro'yxati)
2. Avtomaktab tugmasi bosiladi → **kartochka** (nom, hudud, manzil, telefon)
   + **«🔗 Platformaga kirish»** tugmasi (login URL)
3. Birinchi `/start`da til tanlanadi (default O'zbekcha), keyin `/lang` bilan
   o'zgartiriladi — UZ / RU / EN
4. **Deep link**: `t.me/<bot>?start=<slug>` — QR kod orqali to'g'ridan-to'g'ri
   shu avtomaktab ochiladi (admin `/qr` bilan QR yasaydi)
5. Admin `/stats` — qaysi avtomaktab necha marta tanlanganini ko'radi
6. Admin `/set_url https://…` — platforma manzilini Telegram'dan darhol
   yangilaydi (serverga kirmasdan). Platforma `.env` dagi `PLATFORM_URL`
   yoki shu buyruq orqali belgilanadi.

## Sozlash (.env)

Loyiha ildizidagi `.env` faylga (namuna: `bot/.env.example`, python-dotenv
o'qib beradi — qiymat faqat `.env` da, kodda **qattiq yozilmaydi**):

```env
BOT_TOKEN=123456789:AA...          # @BotFather → /newbot  (SHART)
ADMIN_IDS=123456789,987654321      # admin Telegram user_id, vergul bilan (alias: BOT_ADMINS)
BOT_DEFAULT_LANG=uz                # uz | ru | en
PLATFORM_NAME=Avtomaktab Platforma # bot ro'yxatidagi platforma nomi
PLATFORM_URL=https://avtomaktab.uz # platformaning login URL'i (bo'sh = qo'shilmaydi)
# BOT_DB=data/bot.db               # ixtiyoriy
```

`PLATFORM_URL` — platforma joylashtirilgach to'ldiriladi. Bot shu manzilni
o'zi ro'yxatga oladi va yangilasa ham o'zini qayta qo'shmaydi. Platforma
bo'lmasa, avtomaktablarni `/add_school` orqali qo'lda kiritish mumkin.

Lokal sinash:
```bash
py -m pip install -r bot/requirements.txt
py -m bot.main        # polling rejimida ishga tushadi
```
Deploy (VPS, asosiy platforma bilan birga):
```bash
docker compose -f docker-compose.prod.yml up -d --build
docker compose -f docker-compose.prod.yml logs -f bot
```
`restart: unless-stopped` — server qayta yuklansa ham bot o'z-o'zidan ishga tushadi.

## Admin buyruqlari (faqat `ADMIN_IDS` dagi foydalanuvchilar)

| Buyruq | Vazifasi |
|---|---|
| `/add_school` | yangi avtomaktab qo'shish (bosqichma-bosqich) |
| `/list_schools` | barcha avtomaktablar ro'yxati (faol/o'chirilgan) |
| `/edit_school` | nomi/URL/manzil/telefon/hudud/logotipni tahrirlash |
| `/set_status` | faollikni o'zgartirish (vaqtincha yashirish) |
| `/remove_school` | butunlay o'chirish (alias: `/delete_school`) |
| `/stats` | bosishlar statistikasi |
| `/qr <id\|slug>` | QR-kod (deep link: `t.me/<bot>?start=<slug>`) |
| `/cancel` | joriy amalni bekor qilish |

**Ma'lumotlar bazasi:** alohida **SQLite** (`data/bot.db`, Docker'da `bot-data`
volume). Sababi: asosiy platforma ham SQLite ishlatadi (PostgreSQL yo'q), bot
jadvalidagi ma'lumot kam va sez o'zgarmaydi — alohida baza esa botni
ishlayotgan koddan butunlay ajratadi va `depends_on: db` bog'lanishiga
hojat qoldirmaydi. Jadval `avtomaktablar`: `id, nomi, slug, login_url,
logotip_url, manzil, telefon, tuman, faol` + `users`, `clicks` (statistika).
Migratsiya kerak bo'lsa, `bot/db.py` ichidagi `BotDB` — yagona o'zgarish nuqtasi.

**Asosiy platforma bilan bog'liqlik:** bot platforma kodiga tegmaydi — faqat
uning **login URL'ini** saqlaydi. Shu sababli platforma yangilansa, bot
kodi yangilanishiga ehtiyoj yo'q; `PLATFORM_URL` o'zgarganda bot URL'ni
o'z-o'zidan yangilaydi.
