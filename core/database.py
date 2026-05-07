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

from core.models import User, Task, WorkSession, BehaviorEvent, AIMemory

# ─── Database path ────────────────────────────────────────────────────────────

DATA_DIR = Path(__file__).parent.parent / "data"
DATA_DIR.mkdir(exist_ok=True)
DB_PATH = DATA_DIR / "taskflow.db"

_local = threading.local()


# ─── Connection Management ────────────────────────────────────────────────────

def get_connection() -> sqlite3.Connection:
    if not hasattr(_local, "conn") or _local.conn is None:
        _local.conn = sqlite3.connect(str(DB_PATH), check_same_thread=False)
        _local.conn.row_factory = sqlite3.Row
        _local.conn.execute("PRAGMA journal_mode=WAL")
        _local.conn.execute("PRAGMA foreign_keys=ON")
    return _local.conn


def close_connection():
    if hasattr(_local, "conn") and _local.conn:
        _local.conn.close()
        _local.conn = None


# ─── Schema Init ──────────────────────────────────────────────────────────────

def init_db():
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
            recur_pattern     TEXT DEFAULT '',
            impact_score      REAL DEFAULT 5.0,
            risk_level        TEXT DEFAULT 'low',
            energy_required   TEXT DEFAULT 'medium',
            focus_required    TEXT DEFAULT 'medium',
            difficulty_level  INTEGER DEFAULT 5,
            motivation_score  REAL DEFAULT 5.0,
            dependencies      TEXT DEFAULT '[]',
            actual_minutes    INTEGER DEFAULT 0,
            workload_score    REAL DEFAULT 5.0,
            ai_priority_score REAL DEFAULT 50.0
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

        -- ── AI / Behavior Tables ────────────────────────────────────────────

        CREATE TABLE IF NOT EXISTS user_behavior (
            id           INTEGER PRIMARY KEY AUTOINCREMENT,
            user_id      TEXT NOT NULL,
            event_type   TEXT NOT NULL,
            event_data   TEXT DEFAULT '{}',
            hour_of_day  INTEGER,
            day_of_week  INTEGER,
            timestamp    TEXT NOT NULL
        );

        CREATE TABLE IF NOT EXISTS work_sessions (
            id               TEXT PRIMARY KEY,
            user_id          TEXT NOT NULL,
            task_id          TEXT,
            started_at       TEXT NOT NULL,
            ended_at         TEXT,
            duration_minutes INTEGER DEFAULT 0,
            focus_quality    INTEGER DEFAULT 5,
            notes            TEXT DEFAULT ''
        );

        CREATE TABLE IF NOT EXISTS ai_memory (
            id           INTEGER PRIMARY KEY AUTOINCREMENT,
            user_id      TEXT NOT NULL,
            memory_type  TEXT NOT NULL,
            key          TEXT NOT NULL,
            value        TEXT NOT NULL,
            confidence   REAL DEFAULT 0.5,
            updated_at   TEXT NOT NULL,
            UNIQUE(user_id, memory_type, key)
        );

        CREATE TABLE IF NOT EXISTS analytics_cache (
            id           INTEGER PRIMARY KEY AUTOINCREMENT,
            user_id      TEXT NOT NULL,
            metric_name  TEXT NOT NULL,
            metric_value TEXT NOT NULL,
            computed_at  TEXT NOT NULL,
            UNIQUE(user_id, metric_name)
        );

        CREATE TABLE IF NOT EXISTS project_progress (
            id          TEXT PRIMARY KEY,
            user_id     TEXT NOT NULL,
            name        TEXT NOT NULL,
            description TEXT DEFAULT '',
            target_date TEXT,
            status      TEXT DEFAULT 'active',
            task_ids    TEXT DEFAULT '[]',
            created_at  TEXT NOT NULL,
            updated_at  TEXT NOT NULL
        );

        -- Indexes
        CREATE INDEX IF NOT EXISTS idx_tasks_user ON tasks(user_id);
        CREATE INDEX IF NOT EXISTS idx_tasks_status ON tasks(user_id, status);
        CREATE INDEX IF NOT EXISTS idx_chat_sessions_user ON chat_sessions(user_id);
        CREATE INDEX IF NOT EXISTS idx_chat_messages_session ON chat_messages(session_id);
        CREATE INDEX IF NOT EXISTS idx_behavior_user ON user_behavior(user_id);
        CREATE INDEX IF NOT EXISTS idx_behavior_type ON user_behavior(user_id, event_type);
        CREATE INDEX IF NOT EXISTS idx_work_sessions_user ON work_sessions(user_id);
        CREATE INDEX IF NOT EXISTS idx_ai_memory_user ON ai_memory(user_id);
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
        # AI fields mới
        "impact_score":      "REAL DEFAULT 5.0",
        "risk_level":        "TEXT DEFAULT 'low'",
        "energy_required":   "TEXT DEFAULT 'medium'",
        "focus_required":    "TEXT DEFAULT 'medium'",
        "difficulty_level":  "INTEGER DEFAULT 5",
        "motivation_score":  "REAL DEFAULT 5.0",
        "dependencies":      "TEXT DEFAULT '[]'",
        "actual_minutes":    "INTEGER DEFAULT 0",
        "workload_score":    "REAL DEFAULT 5.0",
        "ai_priority_score": "REAL DEFAULT 50.0",
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
        rows = conn.execute("SELECT * FROM tasks WHERE user_id=?", (user_id,)).fetchall()
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
             completed_at, is_recurring, recur_pattern,
             impact_score, risk_level, energy_required, focus_required,
             difficulty_level, motivation_score, dependencies, actual_minutes,
             workload_score, ai_priority_score)
            VALUES (?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?)
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
                recur_pattern=excluded.recur_pattern,
                impact_score=excluded.impact_score,
                risk_level=excluded.risk_level,
                energy_required=excluded.energy_required,
                focus_required=excluded.focus_required,
                difficulty_level=excluded.difficulty_level,
                motivation_score=excluded.motivation_score,
                dependencies=excluded.dependencies,
                actual_minutes=excluded.actual_minutes,
                workload_score=excluded.workload_score,
                ai_priority_score=excluded.ai_priority_score
        """, (
            task.id, task.user_id, task.title, task.description,
            task.category, task.priority, task.status,
            task.due_date, task.due_time, task.start_date,
            task.reminder_minutes, task.complexity, task.estimated_minutes,
            json.dumps(task.tags), json.dumps(task.subtasks), task.notes,
            task.created_at, task.updated_at, task.completed_at,
            int(task.is_recurring), task.recur_pattern,
            task.impact_score, task.risk_level, task.energy_required,
            task.focus_required, task.difficulty_level, task.motivation_score,
            json.dumps(task.dependencies), task.actual_minutes,
            task.workload_score, task.ai_priority_score,
        ))
        conn.commit()

    @classmethod
    def delete_task(cls, task_id: str):
        conn = get_connection()
        conn.execute("DELETE FROM tasks WHERE id=?", (task_id,))
        conn.commit()

    @staticmethod
    def _row_to_task(row) -> Task:
        import dataclasses
        valid_keys = {f.name for f in dataclasses.fields(Task)}
        d = {k: v for k, v in dict(row).items() if k in valid_keys}
        d["tags"]         = json.loads(d.get("tags", "[]") or "[]")
        d["subtasks"]     = json.loads(d.get("subtasks", "[]") or "[]")
        d["dependencies"] = json.loads(d.get("dependencies", "[]") or "[]")
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

    # ── Behavior Events ────────────────────────────────────────────────────────

    @classmethod
    def log_behavior(cls, user_id: str, event_type: str, event_data: dict = None,
                     hour_of_day: int = None, day_of_week: int = None):
        conn = get_connection()
        now = datetime.now()
        conn.execute(
            """INSERT INTO user_behavior
               (user_id, event_type, event_data, hour_of_day, day_of_week, timestamp)
               VALUES (?,?,?,?,?,?)""",
            (user_id, event_type,
             json.dumps(event_data or {}),
             hour_of_day if hour_of_day is not None else now.hour,
             day_of_week if day_of_week is not None else now.weekday(),
             now.isoformat())
        )
        conn.commit()

    @classmethod
    def get_behavior_events(cls, user_id: str, event_type: str = None,
                            limit: int = 500) -> List[dict]:
        conn = get_connection()
        if event_type:
            rows = conn.execute(
                "SELECT * FROM user_behavior WHERE user_id=? AND event_type=? ORDER BY timestamp DESC LIMIT ?",
                (user_id, event_type, limit)
            ).fetchall()
        else:
            rows = conn.execute(
                "SELECT * FROM user_behavior WHERE user_id=? ORDER BY timestamp DESC LIMIT ?",
                (user_id, limit)
            ).fetchall()
        result = []
        for r in rows:
            d = dict(r)
            d["event_data"] = json.loads(d.get("event_data", "{}") or "{}")
            result.append(d)
        return result

    # ── Work Sessions ──────────────────────────────────────────────────────────

    @classmethod
    def save_work_session(cls, ws: WorkSession):
        conn = get_connection()
        conn.execute("""
            INSERT INTO work_sessions
            (id, user_id, task_id, started_at, ended_at, duration_minutes, focus_quality, notes)
            VALUES (?,?,?,?,?,?,?,?)
            ON CONFLICT(id) DO UPDATE SET
                ended_at=excluded.ended_at,
                duration_minutes=excluded.duration_minutes,
                focus_quality=excluded.focus_quality,
                notes=excluded.notes
        """, (ws.id, ws.user_id, ws.task_id, ws.started_at, ws.ended_at,
              ws.duration_minutes, ws.focus_quality, ws.notes))
        conn.commit()

    @classmethod
    def get_work_sessions(cls, user_id: str, limit: int = 100) -> List[dict]:
        conn = get_connection()
        rows = conn.execute(
            "SELECT * FROM work_sessions WHERE user_id=? ORDER BY started_at DESC LIMIT ?",
            (user_id, limit)
        ).fetchall()
        return [dict(r) for r in rows]

    # ── AI Memory ──────────────────────────────────────────────────────────────

    @classmethod
    def set_memory(cls, user_id: str, memory_type: str, key: str,
                   value, confidence: float = 0.5):
        conn = get_connection()
        now = datetime.now().isoformat()
        conn.execute("""
            INSERT INTO ai_memory (user_id, memory_type, key, value, confidence, updated_at)
            VALUES (?,?,?,?,?,?)
            ON CONFLICT(user_id, memory_type, key) DO UPDATE SET
                value=excluded.value,
                confidence=excluded.confidence,
                updated_at=excluded.updated_at
        """, (user_id, memory_type, key,
              json.dumps(value) if not isinstance(value, str) else value,
              confidence, now))
        conn.commit()

    @classmethod
    def get_memory(cls, user_id: str, memory_type: str = None) -> List[dict]:
        conn = get_connection()
        if memory_type:
            rows = conn.execute(
                "SELECT * FROM ai_memory WHERE user_id=? AND memory_type=? ORDER BY updated_at DESC",
                (user_id, memory_type)
            ).fetchall()
        else:
            rows = conn.execute(
                "SELECT * FROM ai_memory WHERE user_id=? ORDER BY updated_at DESC",
                (user_id,)
            ).fetchall()
        result = []
        for r in rows:
            d = dict(r)
            try:
                d["value"] = json.loads(d["value"])
            except Exception:
                pass
            result.append(d)
        return result

    @classmethod
    def get_memory_value(cls, user_id: str, memory_type: str, key: str, default=None):
        conn = get_connection()
        row = conn.execute(
            "SELECT value FROM ai_memory WHERE user_id=? AND memory_type=? AND key=?",
            (user_id, memory_type, key)
        ).fetchone()
        if not row:
            return default
        try:
            return json.loads(row["value"])
        except Exception:
            return row["value"]

    # ── Analytics Cache ────────────────────────────────────────────────────────

    @classmethod
    def set_analytics(cls, user_id: str, metric_name: str, metric_value):
        conn = get_connection()
        now = datetime.now().isoformat()
        conn.execute("""
            INSERT INTO analytics_cache (user_id, metric_name, metric_value, computed_at)
            VALUES (?,?,?,?)
            ON CONFLICT(user_id, metric_name) DO UPDATE SET
                metric_value=excluded.metric_value,
                computed_at=excluded.computed_at
        """, (user_id, metric_name,
              json.dumps(metric_value) if not isinstance(metric_value, str) else metric_value,
              now))
        conn.commit()

    @classmethod
    def get_analytics(cls, user_id: str, metric_name: str, default=None):
        conn = get_connection()
        row = conn.execute(
            "SELECT metric_value FROM analytics_cache WHERE user_id=? AND metric_name=?",
            (user_id, metric_name)
        ).fetchone()
        if not row:
            return default
        try:
            return json.loads(row["metric_value"])
        except Exception:
            return row["metric_value"]


# Tự động khởi tạo database khi import module
init_db()
