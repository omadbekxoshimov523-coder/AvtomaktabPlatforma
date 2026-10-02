"""Platforma konfiguratsiyasi — barcha qiymatlar muhit o'zgaruvchilaridan (.env).

QOID'A: hech qanday kalit kod ichida QATTIQ YOZILMAYDI. Faqat `os.environ`
(read-only) orqali o'qiLadi. `.env` fayl esa `.gitignore`'da va GitHub'ga
hech qachon yuklanmaydi.

MODUL 4 — XARITA:
    MAP_PROVIDER         — "yandex" (default) | "none" (xarita o'chirilgan)
    YANDEX_MAPS_API_KEY  — Yandex Maps JS API kaliti.
                           https://yandex.ru/dev/js/ -> "Подключить API"
                           -> kalitni `.env` ga yozing. KODGA EMAS!
    MAP_CENTER_LAT       — xarita markazining kengligi  (default: Toshkent 41.311081)
    MAP_CENTER_LNG       — xarita markazining uzunligi  (default: Toshkent 69.240562)
    MAP_CENTER_ZOOM      — dastlabki masshtab (default: 12)

ESLATMA: Yandex Maps JS API kaliti OMMAVIY kalit — u brauzerda ishlashi uchun
HTML/JS ichida ko'rinishi SHART (Yandex uni DOMAIN bo'yicha cheklaydi). Shu
uning uchun u `/api/config` orqali qaytariladi. Parol/secret hech qachon shu
endpoint orqali chiqmaydi.
"""
import os
import sys
import threading

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
ENV_PATH = os.path.join(ROOT, ".env")

# Toshkent markazi (Sobiq Xiyobon / Mustaqillik maydoni atrofi)
TASHKENT_LAT = 41.311081
TASHKENT_LNG = 69.240562
TASHKENT_ZOOM = 12

_DOTENV_LOADED = False


def load_dotenv(path: str = ENV_PATH) -> bool:
    """`.env` faylini `os.environ` ga yuklaydi (faqat python stdlib).

    - `.env` yo'q bo'lsa — xatosiz `False` qaytaradi (bu normal holat:
      Docker'da `env_file`/compose qiymatlari beriladi).
    - `.env` OCHILMASA yoki buzilgan bo'lsa — stderr'ga ANIQ xato yoziladi
      (jim qolmaydi), lekin server ishlashda davom etadi.
    - ALLERTAQCHON o'rnatilgan muhit o'zgaruvchilari QAYTA yozilmaydi
      (haqiqiy muhit `.env` dan ustun turadi — Docker shu bilan ishlaydi).
    """
    global _DOTENV_LOADED
    if _DOTENV_LOADED:
        return True
    _DOTENV_LOADED = True
    if not os.path.isfile(path):
        return False
    try:
        with open(path, encoding="utf-8-sig") as f:
            for lineno, raw in enumerate(f, 1):
                line = raw.strip()
                if not line or line.startswith("#"):
                    continue
                if line.lower().startswith("export "):
                    line = line[7:].strip()
                if "=" not in line:
                    try:
                        sys.stderr.write(
                            "[config] .env:%d — '=' belgisi yo'q, qator tashlab ketildi: %r\n"
                            % (lineno, raw.strip()[:60]))
                    except Exception:
                        pass
                    continue
                key, _, val = line.partition("=")
                key = key.strip()
                if not key:
                    continue
                # Faqat oxirgi qiymatni oladi: # belgisi ICHIDA bo'lsa
                # (masalan parol "#abc") kesib tashlanmasligi kerak.
                val = val.strip()
                if len(val) >= 2 and val[0] == val[-1] and val[0] in "\"'":
                    val = val[1:-1]
                os.environ.setdefault(key, val)
        return True
    except OSError as e:
        try:
            sys.stderr.write("[config] .env OCHILMADI (%s): %s\n" % (path, e))
        except Exception:
            pass
        return False
    except Exception as e:  # pragma: no cover
        try:
            sys.stderr.write("[config] .env PARSE xatosi: %s\n" % e)
        except Exception:
            pass
        return False


load_dotenv()


def _env(name: str, default: str = "") -> str:
    v = os.environ.get(name)
    if v is None:
        return default
    v = v.strip()
    return v if v else default


def _num(name: str, default: float) -> float:
    """Muhit o'zgaruvchisini songa aylantiradi; noto'g'ri bo'lsa —
    standart qiymat qaytariladi VA stderr'da aniq xato yoziladi."""
    raw = os.environ.get(name)
    if raw is None or not raw.strip():
        return default
    try:
        return float(raw.strip().replace(",", "."))
    except ValueError:
        try:
            sys.stderr.write(
                "[config] %s='%s' — SON EMAS, standart qiymat %s ishlatildi\n"
                % (name, raw.strip()[:40], default))
        except Exception:
            pass
        return default


def map_provider() -> str:
    return _env("MAP_PROVIDER", "yandex").lower()


def yandex_api_key() -> str:
    return _env("YANDEX_MAPS_API_KEY")


def yandex_geocoder_key() -> str:
    """BAND 1: AUTOCOMPLETE uchun Yandex Geocoder kaliti.

    Yandex Maps JS API kaliti va Geocoder (manzil qidirish) kaliti — bu
    Yandex'da BIR xil API hisobiga tegadi, lekin JS moduli ichida
    `ymaps.geocoder` faqat JS API kaliti bilan ishlaydi. Alohida
    `YANDEX_GEOCODER_API_KEY` berilgan bo'lsa — u ishlatiladi, aks holda
    `YANDEX_MAPS_API_KEY`.

    Hech qanday kalit TOPILMASA — `""` qaytariladi: frontend "xarita
    sozlanmagan" deb aniq xabar beradi. Soxta kalit QO'YILMAYDI.
    """
    return _env("YANDEX_GEOCODER_API_KEY") or _env("YANDEX_MAPS_API_KEY")


def map_center() -> dict:
    """Xarita markazi. Toshkent — standart (`.env` da o'zgartirilishi mumkin)."""
    return {
        "lat": _num("MAP_CENTER_LAT", TASHKENT_LAT),
        "lng": _num("MAP_CENTER_LNG", TASHKENT_LNG),
        "zoom": int(_num("MAP_CENTER_ZOOM", TASHKENT_ZOOM)),
    }


def maps_enabled() -> bool:
    """Xarita umuman yoqilganmi va kaliti bormi."""
    return map_provider() != "none" and bool(yandex_api_key())


# ======================================================================
# MODUL 5 — PAROLLARNI QAYTARIB OCHISH KALITI
#
# Talab: admin foydalanuvchining PAROLINI koʻra va oʻzgartira olishi
# kerak. Parollar `scrypt` bilan BIR TOMONLAMA hash qilingan —
# qaytarib olish MUMKIN EMAS. Shuning uchun qoʻshimcha ravishda parol
# AES-256-GCM bilan SHIFRLANGAN koʻrinishda ham saqlanadi
# (`users.password_enc`), kalit esa shu yerda — `.env` da.
#
# QOID'A: kalit KODGA YOZILMAYDI. `.env` `.gitignore` da, shuning uchun
# GitHub'ga HECH QACHON tushmaydi.
#
# XAVF (bu maxsus talab tufayli qabul qilingan):
#   `.env` + bazaga kirish huqufi bo'lgan kishi BARCHA parollarni ochadi.
#   Bu endi "hash — bir yo'nalishli" model emas. `.env` faylni
#   zaxira nusxa bilan birga saqlash SHART.
# ======================================================================
CREDENTIALS_KEY_ENV = "CREDENTIALS_KEY"

# Kalitni yaratish "check-then-write" — bitta lock bilan himoya qilinadi.
# XAVFSIZLIK UCHUN SHART: agar ikki so'rov parallel ravishda kalit yaratsa,
# `.env` ga IKKITA turli kalit yoziladi va keyingi ishga tushirishda
# boshqa kalit yuklanadi -> eski parollar QAYTARIB OCHILMAYDI.
_CRED_KEY_LOCK = threading.Lock()


def credentials_key() -> str:
    """`.env` dan maxfiy shifrlash kaliti (base64, 32 bayt) — boʻlmasa ""."""
    return _env(CREDENTIALS_KEY_ENV)


def ensure_credentials_key() -> str:
    """Kalitni `.env` faylga BIR MARTA yozadi (yoʻq boʻlsa) va qaytaradi.

    Kalit `os.urandom(32)` dan olinadi — tasodifiy va taxmin qilinmaydi.
    `.env` yoʻq boʻlsa yoki yozib boʻlmaydigan boʻlsa — "" qaytariladi
    (shu holda parol koʻrsatish funksiyasi oʻchirilgan boʻladi, qolgan
    hammasi ishlayveradi).

    Idempotent: kalit mavjud boʻlsa hech narsa yozilmaydi.
    """
    k = credentials_key()
    if k:
        return k
    import base64 as _b64
    import secrets as _secrets
    with _CRED_KEY_LOCK:
        # Lock ichida QAYTA tekshiramiz — boshqa so'rov shu yerda
        # kalitni yozib bo'lgan bo'lishi mumkin.
        k = credentials_key()
        if k:
            return k
        k = _b64.urlsafe_b64encode(_secrets.token_bytes(32)).decode().strip()
        line = ("%s=%s\n" % (CREDENTIALS_KEY_ENV, k))
        try:
            new_file = not os.path.isfile(ENV_PATH)
            with open(ENV_PATH, "a", encoding="utf-8") as f:
                if not new_file:
                    f.write("\n")
                f.write("# MODUL 5: parollarni qaytarib ochish kaliti. "
                        "BU FAYLNI YO'QOTMANG!\n")
                f.write(line)
            os.environ[CREDENTIALS_KEY_ENV] = k
            return k
        except OSError as e:
            try:
                sys.stderr.write("[config] CREDENTIALS_KEY yozilmadi: %s\n" % e)
            except Exception:
                pass
            return ""


def public_map_config() -> dict:
    """`GET /api/config` uchun — FAQAT ommaviy ma'lumot.

    Hech qanday parol, token yoki sirli kalit shu yerda QAYTMAYDI.
    Yandex Maps JS API kaliti ommaviy (brauzerda ko'rinishi shart).
    """
    key = yandex_api_key()
    geo_key = yandex_geocoder_key()
    return {
        "provider": map_provider(),
        "api_key": key,
        # BAND 1: autocomplete uchun. `geocoder_enabled` — kalit yo'q bo'lsa
        # frontend faqat xaritada nuqta bosish + kiritish imkonini taklif qiladi.
        "geocoder_api_key": geo_key,
        "geocoder_enabled": bool(geo_key) and map_provider() != "none",
        "enabled": bool(key) and map_provider() != "none",
        "center": map_center(),
        "zoom": map_center()["zoom"],
        # Quyidagi ikki qiymat frontend uchun qulaylik (server ularni
        # ishlatmaydi, lekin JS bitta manbadan oladi).
        "region": _env("MAP_REGION", "Tashkent"),
        # BAND 1: qidiruv natijalari shu hududga bog'lanadi (masalan "uz").
        "lang": _env("MAP_LANG", "uz"),
    }
