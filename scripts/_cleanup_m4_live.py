"""M4 live testdan qolgan ma'lumotlarni tozalaydi: so'rovlar 5,6 va sessiya 20."""
import sqlite3
import sys
from pathlib import Path

DB = Path(__file__).resolve().parent.parent / "data" / "avtomaktab.db"
REQS = (5, 6)
SID = 20

con = sqlite3.connect(DB)
try:
    cur = con.cursor()
    cur.execute("DELETE FROM session_students WHERE session_id=?", (SID,))
    cur.execute("DELETE FROM notifications WHERE data LIKE ?", (f'%"session_id": {SID}%',))
    cur.execute("DELETE FROM lesson_sessions WHERE id=?", (SID,))
    cur.execute("DELETE FROM practice_requests WHERE id IN (?,?)", REQS)
    cur.execute("DELETE FROM audit_logs WHERE entity_type='practice_requests' AND entity_id IN (?,?)", REQS)
    con.commit()
    print("tozalandi:", cur.rowcount, "o'zgarish(siz) amalga oshirildi")
finally:
    con.close()
sys.exit(0)