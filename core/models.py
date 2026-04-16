"""
TaskFlow - Data Models
Chỉ chứa dataclass định nghĩa cấu trúc dữ liệu.
Không chứa I/O hay business logic.
"""
import uuid
from datetime import datetime, date
from dataclasses import dataclass, field, asdict
from typing import Optional, List


# ─── User ─────────────────────────────────────────────────────────────────────

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


# ─── Task ─────────────────────────────────────────────────────────────────────

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
