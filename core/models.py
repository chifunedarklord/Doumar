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

    # ── AI Productivity Fields ────────────────────────────────────────────────
    work_style: str = "balanced"
    focus_hours: int = 4
    sleep_time: str = "23:00"
    wake_time: str = "07:00"
    peak_productivity_hours: str = "[9,10,14,15]"
    stress_level: int = 5
    energy_level: int = 7
    preferred_work_duration: int = 50
    break_duration: int = 10

    # ── Context Fields ─────────────────────────────────────────────────────
    timezone: str = "Asia/Ho_Chi_Minh"
    work_start: str = "08:00"
    work_end: str = "18:00"
    role: str = "other"
    work_env: str = "remote"
    deadline_sensitivity: str = "medium"

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
    
    # ── AI Behavior Fields ────────────────────────────────────────────────────
    postpone_count: int = 0           # Số lần delay/postpone
    interruption_count: int = 0       # Số lần bị gián đoạn khi làm
    focus_score: float = 0.0          # Điểm tập trung khi làm task này
    deadline_type: str = "soft"       # hard / soft / estimated
    project_id: Optional[str] = None  # ID project thuộc về

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
        from core.i18n import t as _t
        if not self.due_date:
            return _t("no_due_date")
        d = date.fromisoformat(self.due_date)
        today = date.today()
        diff = (d - today).days
        if diff == 0:   return _t("due_today_display")
        if diff == 1:   return _t("due_tomorrow_display")
        if diff == -1:  return _t("due_yesterday_display")
        if diff < 0:    return _t("overdue_days", n=abs(diff))
        if diff <= 7:   return _t("days_left", n=diff)
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


# ─── ProductivityLog ──────────────────────────────────────────────────────────

@dataclass
class ProductivityLog:
    """Theo dõi hiệu suất từng ngày của user."""
    id: Optional[int]
    user_id: str
    date: str                         # ISO date
    productivity_score: float = 0.0
    burnout_risk: float = 0.0
    focus_time_minutes: int = 0
    completed_tasks_count: int = 0

    def to_dict(self):
        return asdict(self)


# ─── Project ──────────────────────────────────────────────────────────────────

@dataclass
class Project:
    id: str
    user_id: str = ""
    name: str = ""
    description: str = ""
    color: str = "#7C3AED"
    status: str = "active"
    priority: str = "medium"
    due_date: Optional[str] = None
    created_at: str = field(default_factory=lambda: datetime.now().isoformat())
    updated_at: str = field(default_factory=lambda: datetime.now().isoformat())

    def to_dict(self):
        return asdict(self)

    @staticmethod
    def from_dict(d: dict) -> "Project":
        return Project(**d)
