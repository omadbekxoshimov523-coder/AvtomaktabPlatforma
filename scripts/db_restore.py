#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""SQLite nusxadan tiklash (restore).

Ishlatish:
  py scripts/db_restore.py data/backups/db_20240101_120000.db
  py scripts/db_restore.py --out data/avtomaktab_restored.db data/backups/db_....db

Diqqat: ishchi fayl ustiga yozadigan rejim (--replace) mavjud DB'ni O'CHIRADI.
Xavfsizlik uchun avval db_backup.py bilan yangi nusxa qilish tavsiya qilinadi.
"""
import argparse, os, shutil, sys

def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("src", help="Nusxa (backup) SQLite fayl")
    ap.add_argument("--out", default=None, help="Qayta tiklanadigan manzil (standart: data/avtomaktab.db)")
    ap.add_argument("--replace", action="store_true", help="Mavjud DB'ni ustiga yozish (ogohlantirilgan)")
    a = ap.parse_args()

    if not os.path.exists(a.src):
        print(f"XATO: nusxa topilmadi: {a.src}")
        sys.exit(1)

    dest = a.out or "data/avtomaktab.db"
    if os.path.exists(dest) and not a.replace:
        print(f"XATO: maqsad fayl mavjud: {dest}. --replace flagini ishlating (yoki boshqa --out).")
        sys.exit(2)

    # WAL yordamchi fayllarini ham o'chiramiz (eski holat qolmasin)
    for suf in ("-wal", "-shm"):
        p = dest + suf
        if os.path.exists(p):
            os.remove(p)

    shutil.copy2(a.src, dest)
    print(f"✓ Tiklandi: {dest}  (manba: {a.src}, {os.path.getsize(dest)} bayt)")
    print("OK")

if __name__ == "__main__":
    main()
