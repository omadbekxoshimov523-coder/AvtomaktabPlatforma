"""M1-LIVE qoldiq sessiyalarini tozalaydi."""
import sqlite3
import sys
from pathlib import Path

DB = Path(__file__).resolve().parent.parent / "data" / "avtomaktab.db"
con = sqlite3.connect(DB)
try:
    cur = con.cursor()
    rows = cur.execute("SELECT id FROM lesson_sessions WHERE notes='M1-LIVE'").fetchall()
    for (sid,) in rows:
        cur.execute("DELETE FROM session_students WHERE session_id=?", (sid,))
        cur.execute("DELETE FROM notifications WHERE data LIKE ?", (f'%"session_id": {sid}%',))
        cur.execute("DELETE FROM lesson_sessions WHERE id=?", (sid,))
        cur.execute("DELETE FROM audit_logs WHERE entity_type='lesson_sessions' AND entity_id=?", (sid,))
    con.commit()
    print("tozalandi:", len(rows), "sessiya")
finally:
    con.close()
sys.exit(0)