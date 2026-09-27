"""M4: session_students sxemasi + orbita session tekshiruvi + tozalash."""
import sqlite3
from pathlib import Path

DB = Path(__file__).resolve().parent.parent / "data" / "avtomaktab.db"
con = sqlite3.connect(DB)
con.row_factory = sqlite3.Row

print("== session_students schema ==")
print(" ", con.execute("SELECT sql FROM sqlite_master WHERE type='table' AND name='session_students'").fetchone()[0])

print("\n== eng oxirgi lesson_sessions (5) ==")
for r in con.execute("SELECT id, date, start_time, end_time, instructor_id, status, notes, created_at FROM lesson_sessions ORDER BY id DESC LIMIT 5").fetchall():
    print(" ", dict(r))

print("\n== ularga tegishli session_students ==")
for r in con.execute("SELECT id, session_id, student_id, student_status FROM session_students ORDER BY id DESC LIMIT 8").fetchall():
    print(" ", dict(r))

print("\n== practice_requests holati ==")
for r in con.execute("SELECT id, student_id, status, processed_at, session_id FROM practice_requests ORDER BY id").fetchall():
    print(" ", dict(r))

# Tozalash: burst test natijalari (req4 -> pending qaytarish; orbita session o'chirish)
sid = con.execute("SELECT id FROM lesson_sessions WHERE status='scheduled' AND notes LIKE '%so''rov #1%' ORDER BY id DESC LIMIT 1").fetchone()
print("\n== tozalash ==")
if sid:
    print("orphan session:", sid["id"], "-> delete")
    con.execute("DELETE FROM session_students WHERE session_id=?", (sid["id"],))
    con.execute("DELETE FROM lesson_sessions WHERE id=?", (sid["id"],))
else:
    print("orphan session topilmadi (yoki qidiruv shartiga tushmadi)")
# req 4 ni pending holatiga qaytarish (mening reject testim bekor qilinadi)
con.execute("UPDATE practice_requests SET status='pending', processed_at='', admin_note='', session_id=NULL WHERE id=4")
con.commit()
print("req 4 -> pending qaytarildi")
con.close()