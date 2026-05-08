"""
Migration v2 -> v3: context fields on users, deadline_type + project_id on tasks,
and creates the projects table.
Run once: python scripts/migrate_v2_to_v3.py
"""
import sqlite3
from pathlib import Path

DB_PATH = Path(__file__).parent.parent / "data" / "taskflow_v2.db"

MIGRATIONS = [
    # Users table — context fields
    "ALTER TABLE users ADD COLUMN timezone TEXT DEFAULT 'Asia/Ho_Chi_Minh'",
    "ALTER TABLE users ADD COLUMN work_start TEXT DEFAULT '08:00'",
    "ALTER TABLE users ADD COLUMN work_end TEXT DEFAULT '18:00'",
    "ALTER TABLE users ADD COLUMN role TEXT DEFAULT 'other'",
    "ALTER TABLE users ADD COLUMN work_env TEXT DEFAULT 'remote'",
    "ALTER TABLE users ADD COLUMN deadline_sensitivity TEXT DEFAULT 'medium'",
    # Tasks table
    "ALTER TABLE tasks ADD COLUMN deadline_type TEXT DEFAULT 'soft'",
    "ALTER TABLE tasks ADD COLUMN project_id TEXT",
    # Projects table (new)
    """CREATE TABLE IF NOT EXISTS projects (
        id TEXT PRIMARY KEY,
        user_id TEXT NOT NULL,
        name TEXT NOT NULL,
        description TEXT DEFAULT '',
        color TEXT DEFAULT '#5B4FBE',
        status TEXT DEFAULT 'active',
        priority TEXT DEFAULT 'medium',
        due_date TEXT,
        created_at TEXT NOT NULL,
        updated_at TEXT NOT NULL
    )""",
]


def run():
    conn = sqlite3.connect(DB_PATH)
    cur = conn.cursor()
    for sql in MIGRATIONS:
        try:
            cur.execute(sql)
            print(f"OK: {sql[:70].strip()}...")
        except sqlite3.OperationalError as e:
            if "duplicate column" in str(e).lower() or "already exists" in str(e).lower():
                print(f"SKIP (already exists): {sql[:50].strip()}...")
            else:
                print(f"ERROR: {e} — {sql[:70].strip()}")
    conn.commit()
    conn.close()
    print("\nMigration complete.")


if __name__ == "__main__":
    run()
