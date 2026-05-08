"""
TaskFlow - SQLAlchemy ORM Definitions
"""
import json
from datetime import datetime
from typing import Optional, List
from sqlalchemy import String, Integer, Float, Boolean, Text, ForeignKey, create_engine, JSON
from sqlalchemy.orm import DeclarativeBase, Mapped, mapped_column, relationship, sessionmaker
from pathlib import Path

DATA_DIR = Path(__file__).parent.parent / "data"
DATA_DIR.mkdir(exist_ok=True)
DB_PATH = DATA_DIR / "taskflow_v2.db"
DATABASE_URL = f"sqlite:///{DB_PATH}"

engine = create_engine(DATABASE_URL, echo=False, pool_pre_ping=True)
SessionLocal = sessionmaker(autocommit=False, autoflush=False, bind=engine)

class Base(DeclarativeBase):
    pass

class UserModel(Base):
    __tablename__ = "users"
    id: Mapped[str] = mapped_column(String, primary_key=True)
    username: Mapped[str] = mapped_column(String, unique=True, index=True)
    email: Mapped[str] = mapped_column(String, unique=True, index=True)
    password_hash: Mapped[str] = mapped_column(String)
    full_name: Mapped[str] = mapped_column(String, default="")
    avatar_color: Mapped[str] = mapped_column(String, default="#707070")
    created_at: Mapped[str] = mapped_column(String, default=lambda: datetime.now().isoformat())
    settings: Mapped[dict] = mapped_column(JSON, default=dict)
    
    # New AI Productivity Fields
    work_style: Mapped[str] = mapped_column(String, default="balanced")
    focus_hours: Mapped[int] = mapped_column(Integer, default=4)
    sleep_time: Mapped[str] = mapped_column(String, default="23:00")
    wake_time: Mapped[str] = mapped_column(String, default="07:00")
    peak_productivity_hours: Mapped[str] = mapped_column(String, default="[9,10,14,15]")
    stress_level: Mapped[int] = mapped_column(Integer, default=5)
    energy_level: Mapped[int] = mapped_column(Integer, default=7)
    preferred_work_duration: Mapped[int] = mapped_column(Integer, default=50) # minutes
    break_duration: Mapped[int] = mapped_column(Integer, default=10) # minutes
    # Context fields
    timezone: Mapped[str] = mapped_column(String, default="Asia/Ho_Chi_Minh")
    work_start: Mapped[str] = mapped_column(String, default="08:00")
    work_end: Mapped[str] = mapped_column(String, default="18:00")
    role: Mapped[str] = mapped_column(String, default="other")
    work_env: Mapped[str] = mapped_column(String, default="remote")
    deadline_sensitivity: Mapped[str] = mapped_column(String, default="medium")

class SessionModel(Base):
    __tablename__ = "sessions"
    user_id: Mapped[str] = mapped_column(String, primary_key=True)

class TaskModel(Base):
    __tablename__ = "tasks"
    id: Mapped[str] = mapped_column(String, primary_key=True)
    user_id: Mapped[str] = mapped_column(String, index=True)
    title: Mapped[str] = mapped_column(String)
    description: Mapped[str] = mapped_column(String, default="")
    category: Mapped[str] = mapped_column(String, default="personal")
    priority: Mapped[str] = mapped_column(String, default="medium")
    status: Mapped[str] = mapped_column(String, default="todo")
    due_date: Mapped[Optional[str]] = mapped_column(String, nullable=True)
    due_time: Mapped[Optional[str]] = mapped_column(String, nullable=True)
    start_date: Mapped[Optional[str]] = mapped_column(String, nullable=True)
    reminder_minutes: Mapped[int] = mapped_column(Integer, default=0)
    complexity: Mapped[str] = mapped_column(String, default="medium")
    estimated_minutes: Mapped[int] = mapped_column(Integer, default=30)
    tags: Mapped[list] = mapped_column(JSON, default=list)
    subtasks: Mapped[list] = mapped_column(JSON, default=list)
    notes: Mapped[str] = mapped_column(String, default="")
    created_at: Mapped[str] = mapped_column(String, default=lambda: datetime.now().isoformat())
    updated_at: Mapped[str] = mapped_column(String, default=lambda: datetime.now().isoformat())
    completed_at: Mapped[Optional[str]] = mapped_column(String, nullable=True)
    is_recurring: Mapped[bool] = mapped_column(Boolean, default=False)
    recur_pattern: Mapped[str] = mapped_column(String, default="")

    # AI-powered fields
    impact_score: Mapped[float] = mapped_column(Float, default=5.0)
    risk_level: Mapped[str] = mapped_column(String, default="low")
    energy_required: Mapped[str] = mapped_column(String, default="medium")
    focus_required: Mapped[str] = mapped_column(String, default="medium")
    difficulty_level: Mapped[int] = mapped_column(Integer, default=5)
    motivation_score: Mapped[float] = mapped_column(Float, default=5.0)
    dependencies: Mapped[list] = mapped_column(JSON, default=list)
    actual_minutes: Mapped[int] = mapped_column(Integer, default=0)
    workload_score: Mapped[float] = mapped_column(Float, default=5.0)
    ai_priority_score: Mapped[float] = mapped_column(Float, default=50.0)
    
    # New AI fields
    postpone_count: Mapped[int] = mapped_column(Integer, default=0)
    interruption_count: Mapped[int] = mapped_column(Integer, default=0)
    focus_score: Mapped[float] = mapped_column(Float, default=0.0)
    deadline_type: Mapped[str] = mapped_column(String, default="soft")
    project_id: Mapped[Optional[str]] = mapped_column(String, nullable=True)

class ChatSessionModel(Base):
    __tablename__ = "chat_sessions"
    id: Mapped[str] = mapped_column(String, primary_key=True)
    user_id: Mapped[str] = mapped_column(String, index=True)
    title: Mapped[str] = mapped_column(String, default="Chat mới")
    updated_at: Mapped[str] = mapped_column(String)
    created_at: Mapped[str] = mapped_column(String)

class ChatMessageModel(Base):
    __tablename__ = "chat_messages"
    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    session_id: Mapped[str] = mapped_column(String, ForeignKey("chat_sessions.id", ondelete="CASCADE"), index=True)
    user_id: Mapped[str] = mapped_column(String)
    role: Mapped[str] = mapped_column(String)
    text: Mapped[str] = mapped_column(String)
    timestamp: Mapped[str] = mapped_column(String)

class UserBehaviorModel(Base):
    __tablename__ = "user_behavior"
    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    user_id: Mapped[str] = mapped_column(String, index=True)
    event_type: Mapped[str] = mapped_column(String, index=True)
    event_data: Mapped[dict] = mapped_column(JSON, default=dict)
    hour_of_day: Mapped[Optional[int]] = mapped_column(Integer, nullable=True)
    day_of_week: Mapped[Optional[int]] = mapped_column(Integer, nullable=True)
    timestamp: Mapped[str] = mapped_column(String)

class WorkSessionModel(Base):
    __tablename__ = "work_sessions"
    id: Mapped[str] = mapped_column(String, primary_key=True)
    user_id: Mapped[str] = mapped_column(String, index=True)
    task_id: Mapped[Optional[str]] = mapped_column(String, nullable=True)
    started_at: Mapped[str] = mapped_column(String)
    ended_at: Mapped[Optional[str]] = mapped_column(String, nullable=True)
    duration_minutes: Mapped[int] = mapped_column(Integer, default=0)
    focus_quality: Mapped[int] = mapped_column(Integer, default=5)
    interruptions: Mapped[int] = mapped_column(Integer, default=0)
    notes: Mapped[str] = mapped_column(String, default="")

class AIMemoryModel(Base):
    __tablename__ = "ai_memory"
    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    user_id: Mapped[str] = mapped_column(String, index=True)
    memory_type: Mapped[str] = mapped_column(String)
    key: Mapped[str] = mapped_column(String)
    value: Mapped[str] = mapped_column(String)  # stored as json string
    confidence: Mapped[float] = mapped_column(Float, default=0.5)
    updated_at: Mapped[str] = mapped_column(String)

class AnalyticsCacheModel(Base):
    __tablename__ = "analytics_cache"
    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    user_id: Mapped[str] = mapped_column(String)
    metric_name: Mapped[str] = mapped_column(String)
    metric_value: Mapped[str] = mapped_column(String) # stored as json string
    computed_at: Mapped[str] = mapped_column(String)

class ProductivityLogModel(Base):
    __tablename__ = "productivity_logs"
    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    user_id: Mapped[str] = mapped_column(String, index=True)
    date: Mapped[str] = mapped_column(String)
    productivity_score: Mapped[float] = mapped_column(Float, default=0.0)
    burnout_risk: Mapped[float] = mapped_column(Float, default=0.0)
    focus_time_minutes: Mapped[int] = mapped_column(Integer, default=0)
    completed_tasks_count: Mapped[int] = mapped_column(Integer, default=0)

class ProjectModel(Base):
    __tablename__ = "projects"
    id: Mapped[str] = mapped_column(String, primary_key=True)
    user_id: Mapped[str] = mapped_column(String, index=True)
    name: Mapped[str] = mapped_column(String)
    description: Mapped[str] = mapped_column(String, default="")
    color: Mapped[str] = mapped_column(String, default="#5B4FBE")
    status: Mapped[str] = mapped_column(String, default="active")
    priority: Mapped[str] = mapped_column(String, default="medium")
    due_date: Mapped[Optional[str]] = mapped_column(String, nullable=True)
    created_at: Mapped[str] = mapped_column(String)
    updated_at: Mapped[str] = mapped_column(String)

class ProjectProgressModel(Base):
    __tablename__ = "project_progress"
    id: Mapped[str] = mapped_column(String, primary_key=True)
    user_id: Mapped[str] = mapped_column(String)
    name: Mapped[str] = mapped_column(String)
    description: Mapped[str] = mapped_column(String, default="")
    target_date: Mapped[Optional[str]] = mapped_column(String, nullable=True)
    status: Mapped[str] = mapped_column(String, default="active")
    task_ids: Mapped[list] = mapped_column(JSON, default=list)
    created_at: Mapped[str] = mapped_column(String)
    updated_at: Mapped[str] = mapped_column(String)

# Initialize schema
Base.metadata.create_all(bind=engine)
