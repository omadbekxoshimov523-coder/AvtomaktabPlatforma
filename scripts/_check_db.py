"""DB holatini tekshirish."""
import sqlite3
from pathlib import Path

con = sqlite3.connect(Path(__file__).resolve().parent.parent / "data" / "avtomaktab.db")
con.row_factory = sqlite3.Row
cur = con.cursor()
print("reqs5/6:", cur.execute("SELECT COUNT(*) FROM practice_requests WHERE id IN (5,6)").fetchone()[0])
print("session20:", cur.execute("SELECT COUNT(*) FROM lesson_sessions WHERE id=20").fetchone()[0])
print("orphan ss:", cur.execute(
    "SELECT COUNT(*) FROM session_students ss LEFT JOIN lesson_sessions ls ON ls.id=ss.session_id WHERE ls.id IS NULL"
).fetchone()[0])
print("pending:")
for r in cur.execute("SELECT id, student_id, preferred_date, preferred_start_time, status FROM practice_requests WHERE status='pending'").fetchall():
    print("  ", dict(r))
con.close()