#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""SQLite backup (VACUUM INTO — WAL mode'da xavfsiz, onlayn).

Loyiha SQLite (stdlib sqlite3) ishlatgani uchun Docker/Postgres shart EMAS.
Bu skript ma'lumotlar bazasini yopmasdan (online) xavfsiz nusxa oladi:

  py scripts/db_backup.py                 -> data/backups/db_<sana>_<vaqt>.db
  py scripts/db_backup.py --out my.db     -> aniq nom bilan

VACUUM INTO yaxlit (consistent) snapshot beradi — WAL rejimida ham.
"""
import argparse, os, sqlite3, sys, hashlib
from datetime import datetime

def resolve_db():
    for key, default in (("AVTOMAKTAB_DB", "data/avtomaktab.db"),
                         ("AVTOMAKTAB_DB_PATH", None)):
        v = os.environ.get(key) or (os.environ.get("AVTOMAKTAB_DB_PATH") if False else None)
        if v: return v
    if os.path.exists(os.environ.get("AVTOMAKTAB_DB", "data/avtomaktab.db")):
        return os.environ.get("AVTOMAKTAB_DB")
    # rejissyor ildizida ishga tushirilganda web/../data? yo'q — oddiy yo'l
    return os.environ.get("AVTOMAKTAB_DB", "data/avtomaktab.db")

def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--db", default=None, help="Sourceda SQLite fayl (standart: env AVTOMAKTAB_DB yoki data/avtomaktab.db)")
    ap.add_argument("--out", default=None, help="Chiqish nusxa manzili (standart: data/backups/db_<timestamp>.db)")
    ap.add_argument("--no-integrity", action="store_true", help="Nusxadan so'ng integrity_check o'tkazmaslik")
    a = ap.parse_args()

    src = a.db or resolve_db()
    if not os.path.exists(src):
        print(f"XATO: manba fayl topilmadi: {src}")
        sys.exit(1)

    backup_dir = os.path.join("data", "backups")
    os.makedirs(backup_dir, exist_ok=True)
    out = a.out or os.path.join(backup_dir, "db_" + datetime.now().strftime("%Y%m%d_%H%M%S") + ".db")

    # 1) VACUUM INTO — WAL'da ham yaxlit snapshot
    con = sqlite3.connect(src)
    try:
        con.execute("VACUUM INTO ?", (out,))
    finally:
        con.close()
    print(f"✓ Nusxa olindi: {out} ({os.path.getsize(out)} bayt)")

    # 2) Nusxani tekshirish
    if not a.no_integrity:
        vc = sqlite3.connect(out)
        ok = vc.execute("PRAGMA integrity_check").fetchone()[0]
        vc.close()
        if ok != "ok":
            print(f"✗ integrity_check: {ok}")
            sys.exit(2)
        print("✓ integrity_check: ok")

    # 3) Nazorat summasi
    h = hashlib.sha256()
    with open(out, "rb") as f:
        for b in iter(lambda: f.read(1 << 20), b""):
            h.update(b)
    print(f"✓ sha256: {h.hexdigest()}")
    print("OK")

if __name__ == "__main__":
    main()
