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
    complexity: str = "medium"        # easy / medium / hard
    estimated_minutes: int = 30       # estimated completion time
    tags: List[str] = field(default_factory=list)
    subtasks: List[dict] = field(default_factory=list)
    notes: str = ""                   # additional notes
    created_at: str = field(default_factory=lambda: datetime.now().isoformat())
    updated_at: str = field(default_factory=lambda: datetime.now().isoformat())
    completed_at: Optional[str] = None
    is_recurring: bool = False
    recur_pattern: str = ""           # daily / weekly / monthly

    # ── AI-powered fields ──────────────────────────────────────────────────────
    impact_score: float = 5.0         # Mức ảnh hưởng công việc: 1-10
    risk_level: str = "low"           # Rủi ro khi trễ: low / medium / high
    energy_required: str = "medium"   # Năng lượng cần: low / medium / high
    focus_required: str = "medium"    # Sự tập trung cần: low / medium / high
    difficulty_level: int = 5         # Độ khó: 1-10
    motivation_score: float = 5.0     # Mức động lực: 1-10
    dependencies: List[str] = field(default_factory=list)  # List task IDs phụ thuộc
    actual_minutes: int = 0           # Thực tế đã dành (tính từ work_sessions)
    workload_score: float = 5.0       # Workload tổng hợp: calculated by AI engine
    ai_priority_score: float = 50.0   # Dynamic priority score từ AI: 0-100

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

    @property
    def days_until_due(self) -> Optional[int]:
        if not self.due_date:
            return None
        d = date.fromisoformat(self.due_date)
        return (d - date.today()).days


# ─── WorkSession ──────────────────────────────────────────────────────────────

@dataclass
class WorkSession:
    """Theo dõi mỗi phiên làm việc thực tế của user."""
    id: str
    user_id: str
    task_id: Optional[str]            # None = focus session không liên quan task cụ thể
    started_at: str                   # ISO datetime
    ended_at: Optional[str] = None    # None = session đang chạy
    duration_minutes: int = 0         # Tính khi kết thúc
    focus_quality: int = 5            # Chất lượng tập trung: 1-10 (user self-report)
    notes: str = ""

    def to_dict(self):
        return asdict(self)


# ─── BehaviorEvent ────────────────────────────────────────────────────────────

@dataclass
class BehaviorEvent:
    """
    Ghi lại sự kiện hành vi để AI học.
    event_type: task_complete | task_delay | task_start | session_start |
                session_end | task_skip | reschedule | overdue_ack
    """
    id: Optional[int]                 # Auto-increment, None khi chưa save
    user_id: str
    event_type: str
    event_data: dict = field(default_factory=dict)  # JSON metadata
    hour_of_day: int = field(default_factory=lambda: datetime.now().hour)
    day_of_week: int = field(default_factory=lambda: datetime.now().weekday())  # 0=Mon
    timestamp: str = field(default_factory=lambda: datetime.now().isoformat())

    def to_dict(self):
        return asdict(self)


# ─── AIMemory ─────────────────────────────────────────────────────────────────

@dataclass
class AIMemory:
    """
    Bộ nhớ dài hạn của AI về user.
    memory_type: skill | habit | goal | project | performance | preference
    """
    id: Optional[int]
    user_id: str
    memory_type: str
    key: str                          # e.g., "peak_productivity_hour", "preferred_task_size"
    value: str                        # JSON string
    confidence: float = 0.5          # Độ tin cậy: 0-1
    updated_at: str = field(default_factory=lambda: datetime.now().isoformat())

    def to_dict(self):
        return asdict(self)
