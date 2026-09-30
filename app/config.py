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


def public_map_config() -> dict:
    """`GET /api/config` uchun — FAQAT ommaviy ma'lumot.

    Hech qanday parol, token yoki sirli kalit shu yerda QAYTMAYDI.
    Yandex Maps JS API kaliti ommaviy (brauzerda ko'rinishi shart).
    """
    key = yandex_api_key()
    return {
        "provider": map_provider(),
        "api_key": key,
        "enabled": bool(key) and map_provider() != "none",
        "center": map_center(),
        "zoom": map_center()["zoom"],
        # Quyidagi ikki qiymat frontend uchun qulaylik (server ularni
        # ishlatmaydi, lekin JS bitta manbadan oladi).
        "region": "Tashkent",
    }
