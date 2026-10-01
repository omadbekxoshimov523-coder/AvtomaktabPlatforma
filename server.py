"""AVTOMAKTAB — Amaliy mashg'ulotlarni boshqarish platformasi
Server: faqat Python stdlib (http.server + sqlite3). Hech qanday qo'shimcha o'rnatish shart emas.

Ishga tushirish:
    py server.py            (yoki RUN.bat)
Brauzer: http://127.0.0.1:8080/
"""
import base64
import hmac
import json
import mimetypes
import os
import re
import sys
import urllib.parse
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
from pathlib import Path

ROOT = Path(__file__).resolve().parent
DATA_DIR = ROOT / "data"
BACKUP_DIR = DATA_DIR / "backups"
WEB_DIR = ROOT / "web"

# ---- `.env` ni YUKLASH (faqat python stdlib, hech qanday qo'shimcha paket yo'q)
# MUHIM: bu qator `HOST`/`PORT`/`ADMIN_INITIAL_PASSWORD`/`YANDEX_MAPS_API_KEY`
# dan OLDIN bajarilishi kerak. Haqiqiy muhit o'zgaruvchilari `.env` dan ustun
# turadi (Docker `env_file` shu bilan ishlaydi). `.env` yo'q bo'lsa — xatosiz
# davom etiladi. `.env` `.gitignore`'da: hech qachon commit qilinmaydi.
from app.config import load_dotenv  # noqa: E402

load_dotenv()

DB_PATH = Path(os.environ.get("AVTOMAKTAB_DB") or (DATA_DIR / "avtomaktab.db"))
# Telefon/kabel tarmog'idan kirish uchun 0.0.0.0 (barcha interfeyslar).
# Faqat lokalga qaytish uchun: HOST=127.0.0.1 shaklida ishga tushiring.
HOST = os.environ.get("HOST") or "0.0.0.0"
PORT = int(os.environ.get("PORT") or 8080)

# Windows konsolida o'zbekcha belgilar (—, →) xato bermasligi uchun
for _s in (sys.stdout, sys.stderr):
    try:
        _s.reconfigure(encoding="utf-8", errors="replace")
    except Exception:
        pass

os.makedirs(DATA_DIR, exist_ok=True)
os.makedirs(BACKUP_DIR, exist_ok=True)

from app.db import init_db
from app.api import Api, configure
from app.auth import TAB_HEADER, api_rate_allowed
from app.seed import seed


def start_backend() -> None:
    db = init_db(str(DB_PATH))
    configure(str(DB_PATH), str(DATA_DIR), str(BACKUP_DIR))
    seed(db)
    return db


DB = start_backend()

# Xavfsizlik sarlavhalari uchun doimiy headerlar
SECURITY_HEADERS = {
    "X-Content-Type-Options": "nosniff",
    "X-Frame-Options": "DENY",
    "Referrer-Policy": "no-referrer",
    "Cache-Control": "no-store",
}

STATIC_TYPES = {
    ".html": "text/html; charset=utf-8",
    ".css": "text/css; charset=utf-8",
    ".js": "application/javascript; charset=utf-8",
    ".svg": "image/svg+xml",
    ".png": "image/png",
    ".jpg": "image/jpeg",
    ".jpeg": "image/jpeg",
    ".webp": "image/webp",
    ".ico": "image/x-icon",
    ".json": "application/json; charset=utf-8",
}


class Handler(BaseHTTPRequestHandler):
    protocol_version = "HTTP/1.1"
    server_version = "AvtomaktabServer/1.0"

    # ---------------------------------------------------------------- utillar
    def _send_json(self, status: int, payload, extra_headers=None):
        data = json.dumps(payload, ensure_ascii=False).encode("utf-8")
        self.send_response(status)
        self.send_header("Content-Type", "application/json; charset=utf-8")
        self.send_header("Content-Length", str(len(data)))
        for k, v in SECURITY_HEADERS.items():
            self.send_header(k, v)
        for k, v in (extra_headers or {}).items():
            self.send_header(k, v)
        self.end_headers()
        self.wfile.write(data)

    def _send_file(self, path: Path, download_name: str = None, mime: str = None):
        if not path.is_file():
            return self._send_json(404, {"ok": False, "error": "not_found"})
        data = path.read_bytes()
        ctype = mime or STATIC_TYPES.get(path.suffix.lower(), "application/octet-stream")
        self.send_response(200)
        self.send_header("Content-Type", ctype)
        self.send_header("Content-Length", str(len(data)))
        if download_name:
            d = urllib.parse.quote(download_name)
            self.send_header("Content-Disposition", f"attachment; filename*=UTF-8''{d}")
        for k, v in SECURITY_HEADERS.items():
            self.send_header(k, v)
        self.end_headers()
        self.wfile.write(data)

    def _cookie(self, name: str):
        raw = self.headers.get("Cookie") or ""
        for part in raw.split(";"):
            part = part.strip()
            if part.startswith(name + "="):
                return urllib.parse.unquote(part[len(name) + 1:])
        return None

    def _client_key(self) -> str:
        return self.client_address[0]

    def _read_body(self) -> dict:
        length = int(self.headers.get("Content-Length") or 0)
        # Tanavvul chegarasi: 5MB rasm (base64'da ~6.7MB) sig'ishi uchun 8MB.
        # Rasm hajmi baribir API darajasida (≤5MB) tekshiriladi.
        if length <= 0 or length > 8_000_000:
            return {}
        raw = self.rfile.read(length)
        try:
            return json.loads(raw.decode("utf-8"))
        except Exception:
            return {}

    # ---------------------------------------------------------------- routing
    def _handle(self, method: str):
        parsed = urllib.parse.urlparse(self.path)
        path = parsed.path
        query = {k: v[0] for k, v in urllib.parse.parse_qs(parsed.query).items()}

        # API
        if path.startswith("/api/"):
            return self._api(method, path[len("/api/"):], query)

        # Statik fayllar; / -> web/index.html
        if path in ("/", ""):
            return self._send_file(WEB_DIR / "index.html")
        rel = path.lstrip("/")
        # path traversal bloklansin
        if ".." in rel:
            return self._send_json(400, {"ok": False, "error": "bad_path"})
        f = (WEB_DIR / rel).resolve()
        if not str(f).startswith(str(WEB_DIR.resolve())):
            return self._send_json(400, {"ok": False, "error": "bad_path"})
        if f.is_dir():
            f = f / "index.html"
        if f.suffix == "" and not f.exists():
            f = f.with_name(f.name + ".html")
        if f.exists():
            return self._send_file(f)
        return self._send_file(WEB_DIR / "index.html")  # SPA fallback

    def _client_ip(self) -> str:
        """Mijoz IP manzili. Proksi (nginx/Cloudflare) orqasida
        `X-Forwarded-For` dagi birinchi qiymat ishlatiladi — faqat
        `TRUSTED_PROXY=1` yoqilgan holatda (boshqasida hujjatlashtirilgan
        `client_address` ishonchli hisoblanadi)."""
        if os.environ.get("TRUSTED_PROXY") == "1":
            xff = (self.headers.get("X-Forwarded-For") or "").strip()
            if xff:
                return xff.split(",")[0].strip()
        return self.client_address[0] if self.client_address else ""

    def _is_https(self) -> bool:
        """So'rov HTTPS orqali kelayotganmi (teskari proksi orqali ham)."""
        if (self.headers.get("X-Forwarded-Proto") or "").strip().lower() == "https":
            return True
        return (self.headers.get("X-Forwarded-Ssl") or "").strip().lower() == "on"

    def _cookie_attrs(self) -> str:
        """BAND 6: `sid` cookie'si — HttpOnly + SameSite=Lax (+ Secure
        bo'lsa HTTPS orqali). `Secure` faqat HTTPS'da qo'shiladi — aks
        holda localhost/http da cookie brauzerda saqlanmay qoladi."""
        attrs = "Path=/; HttpOnly; SameSite=Lax"
        if self._is_https() or os.environ.get("COOKIE_SECURE") == "1":
            attrs += "; Secure"
        return attrs

    def _api(self, method: str, sub: str, query: dict):
        # Cookie'dan QURILMA kaliti olinadi; tab kaliti — so'rov sarlavhasidan.
        # Ikkalasi birgalikda sessiyani belgilaydi, shuning uchun bitta brauzerdagi
        # turli tab'lar bir-birining foydalanuvchisini ko'ra olmaydi.
        token = self._cookie("sid")
        tab = (self.headers.get(TAB_HEADER) or "").strip() or None
        api = Api(DB, token, tab)
        client_ip = self._client_ip()

        if method == "GET" and sub == "health":
            return self._send_json(200, {"ok": True, "app": "Avtomaktab"})

        # BAND 6: umumiy API rate limit (bir IP'dan juda ko'p so'rov — DoS ga qarshi)
        if not api_rate_allowed(client_ip):
            return self._send_json(429, {"ok": False, "error": "rate_limited"})

        # BAND 6 — CSRF HIMOYASI (ikki qatlamli):
        #   1) `X-Requested-With: Avtomaktab` YOKI same-origin `Origin`.
        #      Oddiy (cross-site) `<form>`/`fetch` so'rovida IKKALASI ham
        #      bo'lmaydi yoki `Origin` boshqa domen bo'ladi -> rad etiladi.
        #   2) SESSIYAGA BOG'LIQ CSRF token: `sessions_ring.csrf_token`.
        #      Eski global `csrf_session` sozlamasi EMASLADI — u barcha
        #      foydalanuvchilar uchun bir xil bo'lgani uchun himoya
        #      bermasdi. Token `sid` cookie'sida EMAS (HttpOnly), faqat
        #      javob tanasida qaytariladi va `X-CSRF-Token` sarlavhasi orqali
        #      yuboriladi — XSS orqali o'g'irlab bo'lmaydi.
        #      >>> Token YO'Q bo'lsa ham RAD etiladi. Aks holda hujjumchi
        #      sarlavhani umuman yubormaydi (`sent == ""`) va butun qatlam
        #      hech qachon ishga tushmasdi (2000-yilgi CSRF "himoyasi").
        if method not in ("GET", "HEAD") and not sub.startswith("auth/login"):
            origin = (self.headers.get("Origin") or "").strip()
            same_origin = bool(origin) and (
                origin.startswith("http://%s" % HOST) or origin.startswith("https://%s" % HOST))
            if self.headers.get("X-Requested-With") != "Avtomaktab" and not same_origin:
                return self._send_json(403, {"ok": False, "error": "csrf_origin"})
            expected = (api.session or {}).get("csrf_token") or ""
            sent = (self.headers.get("X-CSRF-Token") or "").strip()
            if expected and not hmac.compare_digest(sent, expected):
                # `sent` bo'sh bo'lsa ham, boshqa sessiyaning token'i
                # bo'lsa ham, noto'g'ri bo'lsa ham — 403.
                return self._send_json(403, {"ok": False, "error": "csrf_invalid"})

        body = self._read_body()

        # LOGIN — maxsus holat: cookie berish kerak
        if method == "POST" and sub == "auth/login":
            status, payload = api.auth_login(body, client_ip)
            extra = {}
            if status == 200 and payload.get("token"):
                remember = bool(body.get("remember"))
                # MODUL 3 — "Meni eslab qolish":
                #   yoqilgan  -> 30 kun (Max-Age beriladi, brauzer qayta ochilganda ham saqlanadi)
                #   o'chirilgan -> Max-Age BERILMAYDI = "session cookie": brauzer
                #                  yopilganda avtomatik o'chadi (sessiya cookie'si).
                base = f"sid={urllib.parse.quote(payload['token'])}; " + self._cookie_attrs()
                cookie = base + ("; Max-Age=2592000" if remember else "")
                extra = {"Set-Cookie": cookie}
                payload.pop("token", None)
            return self._send_json(status, payload, extra)

        if method == "POST" and sub == "auth/logout":
            status, payload = api.auth_logout()
            if tab:
                # Tab'ga xos rejim: cookie'da QURILMA kaliti turibdi, u boshqa
                # tab'lar uchun ham kerak. Uni o'chirsak, qo'shni tab'lar
                # sessiyasini yo'qotamiz. Qurilma kaliti credential emas —
                # o'zi bilan kirish mumkin emas — shuning uchun saqlanadi.
                return self._send_json(status, payload)
            extra = {"Set-Cookie": "sid=; " + self._cookie_attrs() + "; Max-Age=0"}
            return self._send_json(status, payload, extra)

        status, payload = api.route(method, sub, query, body)

        # Eksport (fayl yuklab olish) — base64 -> fayl
        if payload.get("download"):
            dl = payload["download"]
            raw = base64.b64decode(dl["b64"])
            self.send_response(200)
            self.send_header("Content-Type", dl["mime"])
            self.send_header("Content-Disposition", f"attachment; filename*=UTF-8''{urllib.parse.quote(dl['filename'])}")
            self.send_header("Content-Length", str(len(raw)))
            for k, v in SECURITY_HEADERS.items():
                self.send_header(k, v)
            self.end_headers()
            self.wfile.write(raw)
            return
        return self._send_json(status, payload)

    # ------------------------------------------------- HTTP metodlar
    def do_GET(self): self._handle("GET")
    def do_POST(self): self._handle("POST")
    def do_PUT(self): self._handle("PUT")
    def do_DELETE(self): self._handle("DELETE")

    def log_message(self, fmt, *args):
        if "/api/" in (self.path or ""):
            sys.stderr.write("[api] %s %s\n" % (self.command, self.path))


def main() -> None:
    print("=" * 62)
    print("  AVTOMAKTAB — Amaliy mashg'ulotlarni boshqarish platformasi")
    print("=" * 62)
    print(f"  Server:  http://{HOST}:{PORT}")
    print(f"  Baza:    {DB_PATH}")
    print("  Tugatish uchun: Ctrl+C")
    print("-" * 62)
    print("  Demo hisoblar:")
    print("    Admin       → login: admin   / parol: admin123")
    print("    Intruktorlar→ usrL_00001 / usrP_00001 (Akmal Karimov)")
    print("    Talabalar   → usrL_00004 / usrP_00004 (Omadbek Xoshimov)")
    print("=" * 62)

    # BITTA YO'L: bitta server, bitta port. Agar 8080 band bo'lsa (boshqa
    # server yoki ilova), bu nusxa boshlanmaydi. Aks holda Windows'da ikkita
    # server bir portga yopishib, har so'rov ikkalasiga noaniq taqsimlanardi.
    import socket
    _probe = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
    try:
        _probe.settimeout(2)
        if _probe.connect_ex((HOST, PORT)) == 0:
            print(f"  Port {PORT} band — server allaqachon ishlamoqda yoki")
            print("  portni boshqa dastur egallagan.")
            print(f"  Brauzerda oching: http://{HOST}:{PORT}/")
            return
    finally:
        _probe.close()

    server = ThreadingHTTPServer((HOST, PORT), Handler)
    try:
        # M12: avtomatik eslatmalar — fon thread (har 40 soniyada tekshiradi)
        import time as _t
        import threading as _th

        def _reminder_loop():
            from app.api import ensure_reminders
            while True:
                try:
                    ensure_reminders(DB)
                except Exception:
                    pass  # eslatma xatosi server ishini buzmasin
                _t.sleep(40)

        _th.Thread(target=_reminder_loop, daemon=True).start()
        server.serve_forever()
    except KeyboardInterrupt:
        print("\nServer to'xtatildi.")
        server.shutdown()


if __name__ == "__main__":
    main()