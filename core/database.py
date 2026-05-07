"""
TaskFlow - Database Layer (SQLite)
Chịu trách nhiệm đọc / ghi dữ liệu qua SQLite.
Không chứa business logic.
"""
import sqlite3
import json
import uuid
import threading
from pathlib import Path
from datetime import datetime
from typing import Optional, List

from core.models import User, Task

# ─── Database path ────────────────────────────────────────────────────────────

DATA_DIR = Path.home() / ".taskflow"
DATA_DIR.mkdir(exist_ok=True)

DB_PATH = DATA_DIR / "taskflow.db"

# Thread-local storage để mỗi thread có connection riêng
_local = threading.local()


# ─── Connection Management ────────────────────────────────────────────────────

def get_connection() -> sqlite3.Connection:
    """Trả về connection SQLite của thread hiện tại (tạo mới nếu chưa có)."""
    if not hasattr(_local, "conn") or _local.conn is None:
        _local.conn = sqlite3.connect(str(DB_PATH), check_same_thread=False)
        _local.conn.row_factory = sqlite3.Row
        _local.conn.execute("PRAGMA journal_mode=WAL")
        _local.conn.execute("PRAGMA foreign_keys=ON")
    return _local.conn


def close_connection():
    """Đóng connection của thread hiện tại."""
    if hasattr(_local, "conn") and _local.conn:
        _local.conn.close()
        _local.conn = None


# ─── Schema Init ──────────────────────────────────────────────────────────────

def init_db():
    """Khởi tạo tất cả các bảng nếu chưa tồn tại."""
    conn = get_connection()
    conn.executescript("""
        CREATE TABLE IF NOT EXISTS users (
            id            TEXT PRIMARY KEY,
            username      TEXT UNIQUE NOT NULL,
            email         TEXT UNIQUE NOT NULL,
            password_hash TEXT NOT NULL,
            full_name     TEXT DEFAULT '',
            avatar_color  TEXT DEFAULT '#707070',
            created_at    TEXT NOT NULL,
            settings      TEXT DEFAULT '{}'
        );

        CREATE TABLE IF NOT EXISTS sessions (
            user_id TEXT PRIMARY KEY
        );

        CREATE TABLE IF NOT EXISTS tasks (
            id                TEXT PRIMARY KEY,
            user_id           TEXT NOT NULL,
            title             TEXT NOT NULL,
            description       TEXT DEFAULT '',
            category          TEXT DEFAULT 'personal',
            priority          TEXT DEFAULT 'medium',
            status            TEXT DEFAULT 'todo',
            due_date          TEXT,
            due_time          TEXT,
            start_date        TEXT,
            reminder_minutes  INTEGER DEFAULT 0,
            complexity        TEXT DEFAULT 'medium',
            estimated_minutes INTEGER DEFAULT 30,
            tags              TEXT DEFAULT '[]',
            subtasks          TEXT DEFAULT '[]',
            notes             TEXT DEFAULT '',
            created_at        TEXT NOT NULL,
            updated_at        TEXT NOT NULL,
            completed_at      TEXT,
            is_recurring      INTEGER DEFAULT 0,
            recur_pattern     TEXT DEFAULT ''
        );

        CREATE TABLE IF NOT EXISTS chat_sessions (
            id         TEXT PRIMARY KEY,
            user_id    TEXT NOT NULL,
            title      TEXT DEFAULT 'Chat mới',
            updated_at TEXT NOT NULL,
            created_at TEXT NOT NULL
        );

        CREATE TABLE IF NOT EXISTS chat_messages (
            id         INTEGER PRIMARY KEY AUTOINCREMENT,
            session_id TEXT NOT NULL,
            user_id    TEXT NOT NULL,
            role       TEXT NOT NULL,
            text       TEXT NOT NULL,
            timestamp  TEXT NOT NULL,
            FOREIGN KEY (session_id) REFERENCES chat_sessions(id) ON DELETE CASCADE
        );

        CREATE INDEX IF NOT EXISTS idx_tasks_user ON tasks(user_id);
        CREATE INDEX IF NOT EXISTS idx_chat_sessions_user ON chat_sessions(user_id);
        CREATE INDEX IF NOT EXISTS idx_chat_messages_session ON chat_messages(session_id);
    """)
    conn.commit()
    _apply_migrations(conn)


def _apply_migrations(conn: sqlite3.Connection):
    """Thêm các cột còn thiếu vào schema cũ (idempotent)."""
    existing = {row[1] for row in conn.execute("PRAGMA table_info(users)").fetchall()}
    if "settings" not in existing:
        conn.execute("ALTER TABLE users ADD COLUMN settings TEXT DEFAULT '{}'")
    if "avatar_color" not in existing:
        conn.execute("ALTER TABLE users ADD COLUMN avatar_color TEXT DEFAULT '#707070'")

    existing_tasks = {row[1] for row in conn.execute("PRAGMA table_info(tasks)").fetchall()}
    task_cols = {
        "description":       "TEXT DEFAULT ''",
        "due_time":          "TEXT",
        "start_date":        "TEXT",
        "reminder_minutes":  "INTEGER DEFAULT 0",
        "complexity":        "TEXT DEFAULT 'medium'",
        "estimated_minutes": "INTEGER DEFAULT 30",
        "tags":              "TEXT DEFAULT '[]'",
        "subtasks":          "TEXT DEFAULT '[]'",
        "notes":             "TEXT DEFAULT ''",
        "completed_at":      "TEXT",
        "is_recurring":      "INTEGER DEFAULT 0",
        "recur_pattern":     "TEXT DEFAULT ''",
    }
    for col, typedef in task_cols.items():
        if col not in existing_tasks:
            conn.execute(f"ALTER TABLE tasks ADD COLUMN {col} {typedef}")

    conn.commit()


# ─── Storage ──────────────────────────────────────────────────────────────────

class Storage:
    """SQLite persistence — chỉ đọc/ghi, không xử lý nghiệp vụ."""

    # ── Users ──────────────────────────────────────────────────────────────────

    @classmethod
    def get_users(cls) -> List[User]:
        conn = get_connection()
        rows = conn.execute("SELECT * FROM users").fetchall()
        return [cls._row_to_user(r) for r in rows]

    @classmethod
    def save_user(cls, user: User):
        conn = get_connection()
        conn.execute("""
            INSERT INTO users (id, username, email, password_hash, full_name, avatar_color, created_at, settings)
            VALUES (?,?,?,?,?,?,?,?)
            ON CONFLICT(id) DO UPDATE SET
                username=excluded.username,
                email=excluded.email,
                password_hash=excluded.password_hash,
                full_name=excluded.full_name,
                avatar_color=excluded.avatar_color,
                settings=excluded.settings
        """, (user.id, user.username, user.email, user.password_hash,
              user.full_name, user.avatar_color, user.created_at,
              json.dumps(user.settings)))
        conn.commit()

    @classmethod
    def find_user(cls, username: str = None, email: str = None) -> Optional[User]:
        conn = get_connection()
        if username:
            row = conn.execute("SELECT * FROM users WHERE username=?", (username,)).fetchone()
        elif email:
            row = conn.execute("SELECT * FROM users WHERE email=?", (email,)).fetchone()
        else:
            return None
        return cls._row_to_user(row) if row else None

    @staticmethod
    def _row_to_user(row) -> User:
        import dataclasses
        valid_keys = {f.name for f in dataclasses.fields(User)}
        d = {k: v for k, v in dict(row).items() if k in valid_keys}
        d["settings"] = json.loads(d.get("settings", "{}") or "{}")
        return User(**d)

    # ── Session (login) ────────────────────────────────────────────────────────

    @classmethod
    def get_session(cls) -> Optional[str]:
        conn = get_connection()
        row = conn.execute("SELECT user_id FROM sessions LIMIT 1").fetchone()
        return row["user_id"] if row else None

    @classmethod
    def set_session(cls, user_id: Optional[str]):
        conn = get_connection()
        conn.execute("DELETE FROM sessions")
        if user_id:
            conn.execute("INSERT INTO sessions (user_id) VALUES (?)", (user_id,))
        conn.commit()

    # ── Tasks ──────────────────────────────────────────────────────────────────

    @classmethod
    def get_tasks(cls, user_id: str) -> List[Task]:
        conn = get_connection()
        rows = conn.execute(
            "SELECT * FROM tasks WHERE user_id=?", (user_id,)
        ).fetchall()
        return [cls._row_to_task(r) for r in rows]

    @classmethod
    def save_task(cls, task: Task):
        task.updated_at = datetime.now().isoformat()
        conn = get_connection()
        conn.execute("""
            INSERT INTO tasks
            (id, user_id, title, description, category, priority, status,
             due_date, due_time, start_date, reminder_minutes, complexity,
             estimated_minutes, tags, subtasks, notes, created_at, updated_at,
             completed_at, is_recurring, recur_pattern)
            VALUES (?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?)
            ON CONFLICT(id) DO UPDATE SET
                title=excluded.title, description=excluded.description,
                category=excluded.category, priority=excluded.priority,
                status=excluded.status, due_date=excluded.due_date,
                due_time=excluded.due_time, start_date=excluded.start_date,
                reminder_minutes=excluded.reminder_minutes,
                complexity=excluded.complexity,
                estimated_minutes=excluded.estimated_minutes,
                tags=excluded.tags, subtasks=excluded.subtasks,
                notes=excluded.notes, updated_at=excluded.updated_at,
                completed_at=excluded.completed_at,
                is_recurring=excluded.is_recurring,
                recur_pattern=excluded.recur_pattern
        """, (
            task.id, task.user_id, task.title, task.description,
            task.category, task.priority, task.status,
            task.due_date, task.due_time, task.start_date,
            task.reminder_minutes, task.complexity, task.estimated_minutes,
            json.dumps(task.tags), json.dumps(task.subtasks), task.notes,
            task.created_at, task.updated_at, task.completed_at,
            int(task.is_recurring), task.recur_pattern
        ))
        conn.commit()

    @classmethod
    def delete_task(cls, task_id: str):
        conn = get_connection()
        conn.execute("DELETE FROM tasks WHERE id=?", (task_id,))
        conn.commit()

    @staticmethod
    def _row_to_task(row) -> Task:
        d = dict(row)
        d["tags"]         = json.loads(d.get("tags", "[]") or "[]")
        d["subtasks"]     = json.loads(d.get("subtasks", "[]") or "[]")
        d["is_recurring"] = bool(d.get("is_recurring", 0))
        return Task(**d)

    # ── Chat Sessions ──────────────────────────────────────────────────────────

    @classmethod
    def get_chat_sessions(cls, user_id: str) -> list:
        conn = get_connection()
        rows = conn.execute(
            "SELECT * FROM chat_sessions WHERE user_id=? ORDER BY updated_at DESC",
            (user_id,)
        ).fetchall()
        sessions = []
        for row in rows:
            sid = row["id"]
            msgs = conn.execute(
                "SELECT role, text, timestamp FROM chat_messages WHERE session_id=? ORDER BY id ASC",
                (sid,)
            ).fetchall()
            sessions.append({
                "id":         sid,
                "title":      row["title"],
                "updated_at": row["updated_at"],
                "messages":   [dict(m) for m in msgs]
            })
        return sessions

    @classmethod
    def get_chat_session(cls, user_id: str, session_id: str) -> Optional[dict]:
        conn = get_connection()
        row = conn.execute(
            "SELECT * FROM chat_sessions WHERE id=? AND user_id=?",
            (session_id, user_id)
        ).fetchone()
        if not row:
            return None
        msgs = conn.execute(
            "SELECT role, text, timestamp FROM chat_messages WHERE session_id=? ORDER BY id ASC",
            (session_id,)
        ).fetchall()
        return {
            "id":         row["id"],
            "title":      row["title"],
            "updated_at": row["updated_at"],
            "messages":   [dict(m) for m in msgs]
        }

    @classmethod
    def create_chat_session(cls, user_id: str, title: str = "Chat mới") -> str:
        conn = get_connection()
        sid = str(uuid.uuid4())
        now = datetime.now().isoformat()
        conn.execute(
            "INSERT INTO chat_sessions (id, user_id, title, updated_at, created_at) VALUES (?,?,?,?,?)",
            (sid, user_id, title, now, now)
        )
        conn.commit()
        return sid

    @classmethod
    def add_chat_message(cls, user_id: str, session_id: str, role: str, text: str):
        conn = get_connection()
        now = datetime.now().isoformat()
        conn.execute(
            "INSERT INTO chat_messages (session_id, user_id, role, text, timestamp) VALUES (?,?,?,?,?)",
            (session_id, user_id, role, text, now)
        )
        # Cập nhật tiêu đề session từ tin nhắn user đầu tiên
        count = conn.execute(
            "SELECT COUNT(*) as c FROM chat_messages WHERE session_id=?", (session_id,)
        ).fetchone()["c"]
        current_title = conn.execute(
            "SELECT title FROM chat_sessions WHERE id=?", (session_id,)
        ).fetchone()
        if current_title and current_title["title"] == "Chat mới" and role == "user" and count <= 2:
            new_title = text[:30] + ("..." if len(text) > 30 else "")
            conn.execute(
                "UPDATE chat_sessions SET title=?, updated_at=? WHERE id=?",
                (new_title, now, session_id)
            )
        else:
            conn.execute(
                "UPDATE chat_sessions SET updated_at=? WHERE id=?",
                (now, session_id)
            )
        conn.commit()

    @classmethod
    def clear_chat_history(cls, user_id: str):
        conn = get_connection()
        conn.execute("DELETE FROM chat_messages WHERE user_id=?", (user_id,))
        conn.execute("DELETE FROM chat_sessions WHERE user_id=?", (user_id,))
        conn.commit()

    @classmethod
    def delete_chat_session(cls, user_id: str, session_id: str):
        conn = get_connection()
        conn.execute(
            "DELETE FROM chat_sessions WHERE id=? AND user_id=?",
            (session_id, user_id)
        )
        conn.commit()


# Tự động khởi tạo database khi import module
init_db()
