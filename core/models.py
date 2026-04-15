"""
TaskFlow - Data Models
"""
import json
import uuid
from datetime import datetime, date
from dataclasses import dataclass, field, asdict
from typing import Optional, List
from pathlib import Path

DATA_DIR = Path.home() / ".taskflow"
DATA_DIR.mkdir(exist_ok=True)

USERS_FILE  = DATA_DIR / "users.json"
TASKS_FILE  = DATA_DIR / "tasks.json"
SESSION_FILE= DATA_DIR / "session.json"


# ─── MODELS ───────────────────────────────────────────────────────────────────

@dataclass
class User:
    id: str
    username: str
    email: str
    password_hash: str
    full_name: str = ""
    avatar_color: str = "#707070"
    created_at: str = field(default_factory=lambda: datetime.now().isoformat())
    settings: dict = field(default_factory=dict)

    def to_dict(self):
        return asdict(self)

    @staticmethod
    def from_dict(d: dict) -> "User":
        return User(**d)


@dataclass
class Task:
    id: str
    user_id: str
    title: str
    description: str = ""
    category: str = "personal"       # work / personal / health / finance / education
    priority: str = "medium"          # high / medium / low
    status: str = "todo"              # todo / in_progress / done / cancelled
    due_date: Optional[str] = None    # ISO date string
    due_time: Optional[str] = None    # "HH:MM"
    start_date: Optional[str] = None  # ISO date string
    reminder_minutes: int = 0         # 0 = off, 15/30/60/1440 mins before
    tags: List[str] = field(default_factory=list)
    subtasks: List[dict] = field(default_factory=list)
    notes: str = ""                   # additional notes
    created_at: str = field(default_factory=lambda: datetime.now().isoformat())
    updated_at: str = field(default_factory=lambda: datetime.now().isoformat())
    completed_at: Optional[str] = None
    is_recurring: bool = False
    recur_pattern: str = ""           # daily / weekly / monthly

    def to_dict(self):
        return asdict(self)

    @staticmethod
    def from_dict(d: dict) -> "Task":
        return Task(**d)

    @property
    def is_overdue(self) -> bool:
        if self.due_date and self.status not in ("done", "cancelled"):
            return date.fromisoformat(self.due_date) < date.today()
        return False

    @property
    def due_date_display(self) -> str:
        if not self.due_date:
            return "Không có hạn"
        d = date.fromisoformat(self.due_date)
        today = date.today()
        diff = (d - today).days
        if diff == 0:   return "Hôm nay"
        if diff == 1:   return "Ngày mai"
        if diff == -1:  return "Hôm qua"
        if diff < 0:    return f"Quá hạn {abs(diff)} ngày"
        if diff <= 7:   return f"{diff} ngày nữa"
        return d.strftime("%d/%m/%Y")


# ─── STORAGE ──────────────────────────────────────────────────────────────────

class Storage:
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
        path.write_text(json.dumps(data, ensure_ascii=False, indent=2), encoding="utf-8")

    # ── Users ──
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
            if username and u.username == username:   return u
            if email and u.email == email:             return u
        return None

    # ── Session ──
    @classmethod
    def get_session(cls) -> Optional[str]:
        d = cls._load(SESSION_FILE)
        return d.get("user_id")

    @classmethod
    def set_session(cls, user_id: Optional[str]):
        cls._save(SESSION_FILE, {"user_id": user_id})

    # ── Tasks ──
    @classmethod
    def get_tasks(cls, user_id: str) -> List[Task]:
        d = cls._load(TASKS_FILE)
        all_tasks = d.get("tasks", [])
        return [Task.from_dict(t) for t in all_tasks if t.get("user_id") == user_id]

    @classmethod
    def save_task(cls, task: Task):
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


# ─── AUTH ─────────────────────────────────────────────────────────────────────
import hashlib

def hash_password(password: str) -> str:
    return hashlib.sha256(password.encode()).hexdigest()

def register(username: str, email: str, password: str, full_name: str = "") -> tuple[bool, str]:
    if Storage.find_user(username=username):
        return False, "Tên đăng nhập đã tồn tại"
    if Storage.find_user(email=email):
        return False, "Email đã được sử dụng"
    if len(password) < 6:
        return False, "Mật khẩu tối thiểu 6 ký tự"
    user = User(
        id=str(uuid.uuid4()),
        username=username,
        email=email,
        password_hash=hash_password(password),
        full_name=full_name or username,
    )
    Storage.save_user(user)
    return True, "Đăng ký thành công"

def login(username: str, password: str) -> tuple[bool, str, Optional[User]]:
    user = Storage.find_user(username=username)
    if not user:
        return False, "Tên đăng nhập không tồn tại", None
    if user.password_hash != hash_password(password):
        return False, "Mật khẩu không đúng", None
    Storage.set_session(user.id)
    return True, "Đăng nhập thành công", user

def logout():
    Storage.set_session(None)

def get_current_user() -> Optional[User]:
    uid = Storage.get_session()
    if not uid:
        return None
    for u in Storage.get_users():
        if u.id == uid:
            return u
    return None
