"""
TaskFlow - SQLAlchemy ORM Definitions
Kết nối SQL Server (pyodbc). Yêu cầu cấu hình DB_SERVER trong .env.
"""
import os
import logging
from datetime import datetime
from typing import Optional, List
from sqlalchemy import String, Integer, Float, Boolean, Text, ForeignKey, create_engine, JSON, Unicode, UnicodeText
from sqlalchemy.orm import DeclarativeBase, Mapped, mapped_column, relationship, sessionmaker

logger = logging.getLogger(__name__)

try:
    from dotenv import load_dotenv
    load_dotenv()
except ImportError:
    pass


def _build_mssql_odbc_connect() -> str:
    """Trả về chuỗi odbc_connect cho SQL Server. Raise nếu chưa cấu hình."""
    server   = os.environ.get("DB_SERVER", "").strip()
    database = os.environ.get("DB_NAME", "taskflow").strip()
    username = os.environ.get("DB_USERNAME", "").strip()
    password = os.environ.get("DB_PASSWORD", "").strip()
    driver   = os.environ.get("DB_DRIVER", "ODBC Driver 17 for SQL Server").strip()

    if not server:
        raise RuntimeError(
            "[TaskFlow] DB_SERVER chưa được cấu hình.\n"
            "Tạo file .env từ .env.example và điền DB_SERVER."
        )

    parts = [
        f"DRIVER={{{driver}}}",
        f"SERVER={server}",
        f"DATABASE={database}",
    ]
    if username and password:
        parts += [f"UID={username}", f"PWD={password}"]
    else:
        parts.append("Trusted_Connection=yes")
    parts.append("TrustServerCertificate=yes")

    return ";".join(parts) + ";"


def _create_engine_mssql():
    from urllib.parse import quote_plus

    explicit_url = os.environ.get("DATABASE_URL", "").strip()
    if explicit_url:
        connect_url = explicit_url
    else:
        odbc_connect = _build_mssql_odbc_connect()
        connect_url = f"mssql+pyodbc:///?odbc_connect={quote_plus(odbc_connect)}"

    try:
        import pyodbc  # noqa: F401
    except ModuleNotFoundError:
        raise RuntimeError(
            "[TaskFlow] pyodbc chưa được cài. Chạy: pip install pyodbc"
        )

    eng = create_engine(
        connect_url,
        echo=False,
        pool_pre_ping=True,
        connect_args={"fast_executemany": True},
    )
    with eng.connect():
        pass

    server_hint = os.environ.get("DB_SERVER", "")
    print(f"[TaskFlow] Connected to SQL Server: {server_hint}/{os.environ.get('DB_NAME', 'taskflow')}")
    logger.info("Connected to SQL Server.")
    return eng


engine = _create_engine_mssql()
DB_BACKEND = "mssql"
SessionLocal = sessionmaker(autocommit=False, autoflush=False, bind=engine)

class Base(DeclarativeBase):
    pass

class UserModel(Base):
    __tablename__ = "users"
    id: Mapped[str] = mapped_column(Unicode(36), primary_key=True)
    username: Mapped[str] = mapped_column(Unicode(100), unique=True, index=True)
    email: Mapped[str] = mapped_column(Unicode(255), unique=True, index=True)
    password_hash: Mapped[str] = mapped_column(Unicode(255))
    full_name: Mapped[str] = mapped_column(Unicode(200), default="")
    avatar_color: Mapped[str] = mapped_column(Unicode(20), default="#707070")
    created_at: Mapped[str] = mapped_column(Unicode(50), default=lambda: datetime.now().isoformat())
    settings: Mapped[dict] = mapped_column(JSON, default=dict)

    # AI Productivity Fields
    work_style: Mapped[str] = mapped_column(Unicode(50), default="balanced")
    focus_hours: Mapped[int] = mapped_column(Integer, default=4)
    sleep_time: Mapped[str] = mapped_column(Unicode(10), default="23:00")
    wake_time: Mapped[str] = mapped_column(Unicode(10), default="07:00")
    peak_productivity_hours: Mapped[str] = mapped_column(Unicode(100), default="[9,10,14,15]")
    stress_level: Mapped[int] = mapped_column(Integer, default=5)
    energy_level: Mapped[int] = mapped_column(Integer, default=7)
    preferred_work_duration: Mapped[int] = mapped_column(Integer, default=50)
    break_duration: Mapped[int] = mapped_column(Integer, default=10)
    timezone: Mapped[str] = mapped_column(Unicode(50), default="Asia/Ho_Chi_Minh")
    work_start: Mapped[str] = mapped_column(Unicode(10), default="08:00")
    work_end: Mapped[str] = mapped_column(Unicode(10), default="18:00")
    role: Mapped[str] = mapped_column(Unicode(50), default="other")
    work_env: Mapped[str] = mapped_column(Unicode(50), default="remote")
    deadline_sensitivity: Mapped[str] = mapped_column(Unicode(20), default="medium")

class SessionModel(Base):
    __tablename__ = "sessions"
    user_id: Mapped[str] = mapped_column(Unicode(36), primary_key=True)

class TaskModel(Base):
    __tablename__ = "tasks"
    id: Mapped[str] = mapped_column(Unicode(36), primary_key=True)
    user_id: Mapped[str] = mapped_column(Unicode(36), index=True)
    title: Mapped[str] = mapped_column(Unicode(500))
    description: Mapped[str] = mapped_column(UnicodeText, default="")
    category: Mapped[str] = mapped_column(Unicode(50), default="personal")
    priority: Mapped[str] = mapped_column(Unicode(20), default="medium")
    status: Mapped[str] = mapped_column(Unicode(20), default="todo")
    due_date: Mapped[Optional[str]] = mapped_column(Unicode(20), nullable=True)
    due_time: Mapped[Optional[str]] = mapped_column(Unicode(10), nullable=True)
    start_date: Mapped[Optional[str]] = mapped_column(Unicode(20), nullable=True)
    reminder_minutes: Mapped[int] = mapped_column(Integer, default=0)
    complexity: Mapped[str] = mapped_column(Unicode(20), default="medium")
    estimated_minutes: Mapped[int] = mapped_column(Integer, default=30)
    tags: Mapped[list] = mapped_column(JSON, default=list)
    subtasks: Mapped[list] = mapped_column(JSON, default=list)
    notes: Mapped[str] = mapped_column(UnicodeText, default="")
    created_at: Mapped[str] = mapped_column(Unicode(50), default=lambda: datetime.now().isoformat())
    updated_at: Mapped[str] = mapped_column(Unicode(50), default=lambda: datetime.now().isoformat())
    completed_at: Mapped[Optional[str]] = mapped_column(Unicode(50), nullable=True)
    is_recurring: Mapped[bool] = mapped_column(Boolean, default=False)
    recur_pattern: Mapped[str] = mapped_column(Unicode(100), default="")

    # AI-powered fields
    impact_score: Mapped[float] = mapped_column(Float, default=5.0)
    risk_level: Mapped[str] = mapped_column(Unicode(20), default="low")
    energy_required: Mapped[str] = mapped_column(Unicode(20), default="medium")
    focus_required: Mapped[str] = mapped_column(Unicode(20), default="medium")
    difficulty_level: Mapped[int] = mapped_column(Integer, default=5)
    motivation_score: Mapped[float] = mapped_column(Float, default=5.0)
    dependencies: Mapped[list] = mapped_column(JSON, default=list)
    actual_minutes: Mapped[int] = mapped_column(Integer, default=0)
    workload_score: Mapped[float] = mapped_column(Float, default=5.0)
    ai_priority_score: Mapped[float] = mapped_column(Float, default=50.0)
    postpone_count: Mapped[int] = mapped_column(Integer, default=0)
    interruption_count: Mapped[int] = mapped_column(Integer, default=0)
    focus_score: Mapped[float] = mapped_column(Float, default=0.0)
    deadline_type: Mapped[str] = mapped_column(Unicode(20), default="soft")
    project_id: Mapped[Optional[str]] = mapped_column(Unicode(36), nullable=True)

class ChatSessionModel(Base):
    __tablename__ = "chat_sessions"
    id: Mapped[str] = mapped_column(Unicode(36), primary_key=True)
    user_id: Mapped[str] = mapped_column(Unicode(36), index=True)
    title: Mapped[str] = mapped_column(Unicode(500), default="Chat mới")
    updated_at: Mapped[str] = mapped_column(Unicode(50))
    created_at: Mapped[str] = mapped_column(Unicode(50))

class ChatMessageModel(Base):
    __tablename__ = "chat_messages"
    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    session_id: Mapped[str] = mapped_column(Unicode(36), ForeignKey("chat_sessions.id", ondelete="CASCADE"), index=True)
    user_id: Mapped[str] = mapped_column(Unicode(36))
    role: Mapped[str] = mapped_column(Unicode(20))
    text: Mapped[str] = mapped_column(UnicodeText)
    timestamp: Mapped[str] = mapped_column(Unicode(50))

class UserBehaviorModel(Base):
    __tablename__ = "user_behavior"
    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    user_id: Mapped[str] = mapped_column(Unicode(36), index=True)
    event_type: Mapped[str] = mapped_column(Unicode(50), index=True)
    event_data: Mapped[dict] = mapped_column(JSON, default=dict)
    hour_of_day: Mapped[Optional[int]] = mapped_column(Integer, nullable=True)
    day_of_week: Mapped[Optional[int]] = mapped_column(Integer, nullable=True)
    timestamp: Mapped[str] = mapped_column(Unicode(50))

class WorkSessionModel(Base):
    __tablename__ = "work_sessions"
    id: Mapped[str] = mapped_column(Unicode(36), primary_key=True)
    user_id: Mapped[str] = mapped_column(Unicode(36), index=True)
    task_id: Mapped[Optional[str]] = mapped_column(Unicode(36), nullable=True)
    started_at: Mapped[str] = mapped_column(Unicode(50))
    ended_at: Mapped[Optional[str]] = mapped_column(Unicode(50), nullable=True)
    duration_minutes: Mapped[int] = mapped_column(Integer, default=0)
    focus_quality: Mapped[int] = mapped_column(Integer, default=5)
    interruptions: Mapped[int] = mapped_column(Integer, default=0)
    notes: Mapped[str] = mapped_column(UnicodeText, default="")

class AIMemoryModel(Base):
    __tablename__ = "ai_memory"
    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    user_id: Mapped[str] = mapped_column(Unicode(36), index=True)
    memory_type: Mapped[str] = mapped_column(Unicode(50))
    key: Mapped[str] = mapped_column(Unicode(100))
    value: Mapped[str] = mapped_column(UnicodeText)
    confidence: Mapped[float] = mapped_column(Float, default=0.5)
    updated_at: Mapped[str] = mapped_column(Unicode(50))

class AnalyticsCacheModel(Base):
    __tablename__ = "analytics_cache"
    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    user_id: Mapped[str] = mapped_column(Unicode(36))
    metric_name: Mapped[str] = mapped_column(Unicode(100))
    metric_value: Mapped[str] = mapped_column(UnicodeText)
    computed_at: Mapped[str] = mapped_column(Unicode(50))

class ProductivityLogModel(Base):
    __tablename__ = "productivity_logs"
    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    user_id: Mapped[str] = mapped_column(Unicode(36), index=True)
    date: Mapped[str] = mapped_column(Unicode(20))
    productivity_score: Mapped[float] = mapped_column(Float, default=0.0)
    burnout_risk: Mapped[float] = mapped_column(Float, default=0.0)
    focus_time_minutes: Mapped[int] = mapped_column(Integer, default=0)
    completed_tasks_count: Mapped[int] = mapped_column(Integer, default=0)

class ProjectModel(Base):
    __tablename__ = "projects"
    id: Mapped[str] = mapped_column(Unicode(36), primary_key=True)
    user_id: Mapped[str] = mapped_column(Unicode(36), index=True)
    name: Mapped[str] = mapped_column(Unicode(500))
    description: Mapped[str] = mapped_column(UnicodeText, default="")
    color: Mapped[str] = mapped_column(Unicode(20), default="#5B4FBE")
    status: Mapped[str] = mapped_column(Unicode(20), default="active")
    priority: Mapped[str] = mapped_column(Unicode(20), default="medium")
    due_date: Mapped[Optional[str]] = mapped_column(Unicode(20), nullable=True)
    created_at: Mapped[str] = mapped_column(Unicode(50))
    updated_at: Mapped[str] = mapped_column(Unicode(50))

class ProjectProgressModel(Base):
    __tablename__ = "project_progress"
    id: Mapped[str] = mapped_column(Unicode(36), primary_key=True)
    user_id: Mapped[str] = mapped_column(Unicode(36))
    name: Mapped[str] = mapped_column(Unicode(500))
    description: Mapped[str] = mapped_column(UnicodeText, default="")
    target_date: Mapped[Optional[str]] = mapped_column(Unicode(20), nullable=True)
    status: Mapped[str] = mapped_column(Unicode(20), default="active")
    task_ids: Mapped[list] = mapped_column(JSON, default=list)
    created_at: Mapped[str] = mapped_column(Unicode(50))
    updated_at: Mapped[str] = mapped_column(Unicode(50))

# Initialize schema
Base.metadata.create_all(bind=engine)
