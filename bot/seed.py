"""Bot bazasiga boshlang'ich (TEST) avtomaktab yozuvlarini qo'shish.

Ishga tushirish:
    Lokal:   py -m bot.seed
    Docker:  docker compose -f docker-compose.prod.yml exec bot python -m bot.seed

Skript IDEMPOTENT: mavjud slug'lar bo'lsa, qayta qo'shmaydi.
O'chirish uchun:  py -m bot.seed --clear   (faqat TEST yozuvlarini o'chiradi)
"""
import sys

from .config import load_db_path
from .db import BotDB
from .utils import slugify

# Namuna yozuvlar — `example` domaini RFC 2606 bo'yicha maxsus band qilingan,
# ya'ni haqiqiy saytga olib chiqmaydi. Sinovdan keyin /remove_school yoki
# /edit_school orqali haqiqiy avtomaktablarga almashtiring.
SEED_SCHOOLS = [
    {
        "nomi": "Avtomaktab Chilonzor (TEST)",
        "login_url": "https://chilonzor.example.avtomaktab.uz",
        "tuman": "Chilonzor tumani",
        "manzil": "Chilonzor ko'chasi, 12-uy",
        "telefon": "+998 90 123 45 67",
    },
    {
        "nomi": "Avtomaktab Yunusobod (TEST)",
        "login_url": "https://yunusobod.example.avtomaktab.uz",
        "tuman": "Yunusobod tumani",
        "manzil": "Yunusobod ko'chasi, 45-uy",
        "telefon": "+998 90 765 43 21",
    },
]

TEST_MARK = "(TEST)"


def _is_test(school: dict) -> bool:
    return TEST_MARK in (school["nomi"] or "")


def seed(db: BotDB) -> int:
    """Seed yozuvlarini qo'shadi, qaytaradi: nechta YANGI qo'shildi."""
    added = 0
    for s in SEED_SCHOOLS:
        slug = slugify(s["nomi"])
        if db.get_school_by_slug(slug):
            print(f"  = allaqon bor (ID {db.get_school_by_slug(slug)['id']}): {s['nomi']}")
            continue
        sid = db.add_school(
            s["nomi"], slug, s["login_url"],
            manzil=s.get("manzil", ""), telefon=s.get("telefon", ""), tuman=s.get("tuman", ""),
        )
        added += 1
        print(f"  + qo'shildi (ID {sid}): {s['nomi']}  ->  {s['login_url']}")
    return added


def clear(db: BotDB) -> int:
    """Faqat TEST yozuvlarini o'chiradi (real avtomaktablar tegilmaydi)."""
    removed = 0
    for school in db.list_schools(active_only=False):
        if _is_test(school):
            db.delete_school(school["id"])
            removed += 1
            print(f"  - o'chirildi (ID {school['id']}): {school['nomi']}")
    return removed


def main() -> int:
    path = load_db_path()
    db = BotDB(path)
    total = len(db.list_schools(active_only=False))
    print(f"Baza: {path} (hozir {total} ta avtomaktab)")

    if "--clear" in sys.argv:
        print("\nTEST yozuvlari o'chirilmoqda...")
        print(f"  O'chirilgan: {clear(db)}")
    else:
        print("\nSeed yozuvlar qo'shilmoqda...")
        added = seed(db)
        print(f"  Yangi qo'shildi: {added}")
        if added:
            print("\nEndi Telegram'da botga /start yozib, tugmalarni sinab ko'ring.")
            print("Deep link: t.me/<bot_username>?start=" + slugify(SEED_SCHOOLS[0]["nomi"]))

    total = len(db.list_schools(active_only=False))
    print(f"\nXulosa: bazada jami {total} ta avtomaktab.")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
