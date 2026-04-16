"""
TaskFlow - Database Layer
Chịu trách nhiệm đọc / ghi dữ liệu JSON.
Không chứa business logic.
"""
import json
from pathlib import Path
from typing import Optional, List

from core.models import User, Task

# ─── File paths ───────────────────────────────────────────────────────────────

DATA_DIR     = Path.home() / ".taskflow"
DATA_DIR.mkdir(exist_ok=True)

USERS_FILE   = DATA_DIR / "users.json"
TASKS_FILE   = DATA_DIR / "tasks.json"
SESSION_FILE = DATA_DIR / "session.json"


# ─── Storage ──────────────────────────────────────────────────────────────────

class Storage:
    """Low-level JSON persistence — chỉ đọc/ghi, không xử lý nghiệp vụ."""

    @staticmethod
    def _load(path: Path) -> dict:
        if path.exists():
            try:
                return json.loads(path.read_text(encoding="utf-8"))
            except Exception:
                return {}
        return {}

    @staticmethod
    def _save(path: Path, data):
        path.write_text(
            json.dumps(data, ensure_ascii=False, indent=2),
            encoding="utf-8",
        )

    # ── Users ──────────────────────────────────────────────────────────────────

    @classmethod
    def get_users(cls) -> List[User]:
        d = cls._load(USERS_FILE)
        return [User.from_dict(u) for u in d.get("users", [])]

    @classmethod
    def save_user(cls, user: User):
        d = cls._load(USERS_FILE)
        users = d.get("users", [])
        users = [u for u in users if u["id"] != user.id]
        users.append(user.to_dict())
        cls._save(USERS_FILE, {"users": users})

    @classmethod
    def find_user(cls, username: str = None, email: str = None) -> Optional[User]:
        for u in cls.get_users():
            if username and u.username == username:
                return u
            if email and u.email == email:
                return u
        return None

    # ── Session ────────────────────────────────────────────────────────────────

    @classmethod
    def get_session(cls) -> Optional[str]:
        d = cls._load(SESSION_FILE)
        return d.get("user_id")

    @classmethod
    def set_session(cls, user_id: Optional[str]):
        cls._save(SESSION_FILE, {"user_id": user_id})

    # ── Tasks ──────────────────────────────────────────────────────────────────

    @classmethod
    def get_tasks(cls, user_id: str) -> List[Task]:
        d = cls._load(TASKS_FILE)
        all_tasks = d.get("tasks", [])
        return [Task.from_dict(t) for t in all_tasks if t.get("user_id") == user_id]

    @classmethod
    def save_task(cls, task: Task):
        from datetime import datetime
        task.updated_at = datetime.now().isoformat()
        d = cls._load(TASKS_FILE)
        tasks = d.get("tasks", [])
        tasks = [t for t in tasks if t["id"] != task.id]
        tasks.append(task.to_dict())
        cls._save(TASKS_FILE, {"tasks": tasks})

    @classmethod
    def delete_task(cls, task_id: str):
        d = cls._load(TASKS_FILE)
        tasks = [t for t in d.get("tasks", []) if t["id"] != task_id]
        cls._save(TASKS_FILE, {"tasks": tasks})
