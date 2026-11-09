"""
TaskFlow - Repositories Layer
Handles data access using SQLAlchemy ORM and converts to/from dataclasses.
"""
import json
import uuid
from datetime import datetime
from typing import Optional, List

from core.orm import (
    SessionLocal, UserModel, SessionModel, TaskModel, ChatSessionModel,
    ChatMessageModel, UserBehaviorModel, WorkSessionModel, AIMemoryModel,
    AnalyticsCacheModel, ProductivityLogModel,
)
from core.models import User, Task, WorkSession, BehaviorEvent, AIMemory, ProductivityLog

class Storage:
    """SQLAlchemy Repository Facade — Maintains backwards compatibility."""
    
    # ── Users ──────────────────────────────────────────────────────────────────
    @classmethod
    def get_users(cls) -> List[User]:
        with SessionLocal() as db:
            models = db.query(UserModel).all()
            return [cls._orm_to_user(m) for m in models]

    @classmethod
    def save_user(cls, user: User):
        with SessionLocal() as db:
            db_user = db.query(UserModel).filter(UserModel.id == user.id).first()
            if not db_user:
                db_user = UserModel(id=user.id)
                db.add(db_user)
            
            db_user.username = user.username
            db_user.email = user.email
            db_user.password_hash = user.password_hash
            db_user.full_name = user.full_name
            db_user.avatar_color = user.avatar_color
            db_user.created_at = user.created_at
            db_user.settings = user.settings
            db_user.work_style = getattr(user, "work_style", "balanced")
            db_user.focus_hours = getattr(user, "focus_hours", 4)
            db_user.sleep_time = getattr(user, "sleep_time", "23:00")
            db_user.wake_time = getattr(user, "wake_time", "07:00")
            db_user.peak_productivity_hours = getattr(user, "peak_productivity_hours", "[9,10,14,15]")
            db_user.stress_level = getattr(user, "stress_level", 5)
            db_user.energy_level = getattr(user, "energy_level", 7)
            db_user.preferred_work_duration = getattr(user, "preferred_work_duration", 50)
            db_user.break_duration = getattr(user, "break_duration", 10)
            db_user.timezone = getattr(user, "timezone", "Asia/Ho_Chi_Minh")
            db_user.work_start = getattr(user, "work_start", "08:00")
            db_user.work_end = getattr(user, "work_end", "18:00")
            db_user.role = getattr(user, "role", "other")
            db_user.work_env = getattr(user, "work_env", "remote")
            db_user.deadline_sensitivity = getattr(user, "deadline_sensitivity", "medium")
            db.commit()

    @classmethod
    def find_user(cls, username: str = None, email: str = None) -> Optional[User]:
        with SessionLocal() as db:
            query = db.query(UserModel)
            if username:
                model = query.filter(UserModel.username == username).first()
            elif email:
                model = query.filter(UserModel.email == email).first()
            else:
                return None
            return cls._orm_to_user(model) if model else None

    @staticmethod
    def _orm_to_user(m: UserModel) -> User:
        return User(
            id=m.id, username=m.username, email=m.email, password_hash=m.password_hash,
            full_name=m.full_name, avatar_color=m.avatar_color, created_at=m.created_at,
            settings=m.settings,
            work_style=getattr(m, "work_style", "balanced"),
            focus_hours=getattr(m, "focus_hours", 4),
            sleep_time=getattr(m, "sleep_time", "23:00"),
            wake_time=getattr(m, "wake_time", "07:00"),
            peak_productivity_hours=getattr(m, "peak_productivity_hours", "[9,10,14,15]"),
            stress_level=getattr(m, "stress_level", 5),
            energy_level=getattr(m, "energy_level", 7),
            preferred_work_duration=getattr(m, "preferred_work_duration", 50),
            break_duration=getattr(m, "break_duration", 10),
            timezone=getattr(m, "timezone", "Asia/Ho_Chi_Minh"),
            work_start=getattr(m, "work_start", "08:00"),
            work_end=getattr(m, "work_end", "18:00"),
            role=getattr(m, "role", "other"),
            work_env=getattr(m, "work_env", "remote"),
            deadline_sensitivity=getattr(m, "deadline_sensitivity", "medium"),
        )

    # ── Session (login) ────────────────────────────────────────────────────────
    @classmethod
    def get_session(cls) -> Optional[str]:
        with SessionLocal() as db:
            model = db.query(SessionModel).first()
            return model.user_id if model else None

    @classmethod
    def set_session(cls, user_id: Optional[str]):
        with SessionLocal() as db:
            db.query(SessionModel).delete()
            if user_id:
                db.add(SessionModel(user_id=user_id))
            db.commit()

    # ── Tasks ──────────────────────────────────────────────────────────────────
    @classmethod
    def get_tasks(cls, user_id: str) -> List[Task]:
        with SessionLocal() as db:
            models = db.query(TaskModel).filter(TaskModel.user_id == user_id).all()
            return [cls._orm_to_task(m) for m in models]

    @classmethod
    def save_task(cls, task: Task, expected_revision=None) -> bool:
        """Save task (upsert). Returns True if this was a new task, False if update."""
        from core.workspace import validate_task
        validate_task(task)
        task.updated_at = datetime.now().isoformat()
        with SessionLocal() as db:
            if expected_revision is not None and db.bind.dialect.name == 'sqlite':
                from sqlalchemy import text
                db.execute(text('BEGIN IMMEDIATE'))
            m = db.query(TaskModel).filter(TaskModel.id == task.id).first()
            if expected_revision is not None and (m is None or m.updated_at != expected_revision):
                raise ValueError('Công việc đã thay đổi. Sao chép nội dung đang sửa rồi mở lại công việc để xem bản mới.')
            if m is not None and m.user_id != task.user_id:
                raise ValueError("Công việc không thuộc tài khoản hiện tại.")
            is_new = m is None
            previous_title = m.title if m is not None else None
            was_done = not is_new and m.status == "done"
            if is_new:
                m = TaskModel(id=task.id)
                db.add(m)
            
            m.user_id = task.user_id
            m.title = task.title
            if previous_title is not None and previous_title != task.title:
                from core.orm import ScheduleBlockModel
                db.query(ScheduleBlockModel).filter_by(user_id=task.user_id, task_id=task.id).update({'title': task.title})
            m.description = task.description
            m.category = task.category
            m.priority = task.priority
            m.status = task.status
            m.due_date = task.due_date
            m.due_time = task.due_time
            m.start_date = task.start_date
            m.reminder_minutes = task.reminder_minutes
            m.complexity = task.complexity
            m.estimated_minutes = task.estimated_minutes
            m.tags = task.tags
            m.subtasks = task.subtasks
            m.notes = task.notes
            m.created_at = task.created_at
            m.updated_at = task.updated_at
            m.completed_at = task.completed_at
            m.is_recurring = task.is_recurring
            m.recur_pattern = task.recur_pattern
            m.impact_score = getattr(task, "impact_score", 5.0)
            m.risk_level = getattr(task, "risk_level", "low")
            m.energy_required = getattr(task, "energy_required", "medium")
            m.focus_required = getattr(task, "focus_required", "medium")
            m.difficulty_level = getattr(task, "difficulty_level", 5)
            m.motivation_score = getattr(task, "motivation_score", 5.0)
            m.dependencies = getattr(task, "dependencies", [])
            m.actual_minutes = getattr(task, "actual_minutes", 0)
            m.workload_score = getattr(task, "workload_score", 5.0)
            m.ai_priority_score = getattr(task, "ai_priority_score", 50.0)
            m.postpone_count = getattr(task, "postpone_count", 0)
            m.interruption_count = getattr(task, "interruption_count", 0)
            m.focus_score = getattr(task, "focus_score", 0.0)
            m.deadline_type = getattr(task, "deadline_type", "soft")
            m.project_id = getattr(task, "project_id", None)
            if task.status == "done" and task.is_recurring and not was_done:
                from core.task_rules import next_occurrence
                from dataclasses import asdict
                # One successor per occurrence, including after undo/re-complete
                # on a later day. Retain lineage when a successor is trashed.
                lineage_key = "next:" + task.id
                lineage = db.query(AIMemoryModel).filter_by(user_id=task.user_id, memory_type="recurrence", key=lineage_key).first()
                if lineage is None:
                    following = next_occurrence(task)
                    db.flush()
                    if following and db.get(TaskModel, following.id) is None:
                        db.add(TaskModel(**asdict(following)))
                    if following:
                        db.add(AIMemoryModel(user_id=task.user_id, memory_type="recurrence", key=lineage_key,
                                             value=following.id, confidence=1.0, updated_at=datetime.now().isoformat()))
            db.commit()
        return is_new

    @classmethod
    def delete_task(cls, task_id: str):
        with SessionLocal() as db:
            db.query(TaskModel).filter(TaskModel.id == task_id).delete()
            db.commit()

    @staticmethod
    def _orm_to_task(m: TaskModel) -> Task:
        t = Task(
            id=m.id, user_id=m.user_id, title=m.title, description=m.description,
            category=m.category, priority=m.priority, status=m.status,
            due_date=m.due_date, due_time=m.due_time, start_date=m.start_date,
            reminder_minutes=m.reminder_minutes, complexity=m.complexity,
            estimated_minutes=m.estimated_minutes, tags=m.tags or [],
            subtasks=m.subtasks or [], notes=m.notes, created_at=m.created_at,
            updated_at=m.updated_at, completed_at=m.completed_at,
            is_recurring=m.is_recurring, recur_pattern=m.recur_pattern
        )
        t.impact_score = m.impact_score
        t.risk_level = m.risk_level
        t.energy_required = m.energy_required
        t.focus_required = m.focus_required
        t.difficulty_level = m.difficulty_level
        t.motivation_score = m.motivation_score
        t.dependencies = m.dependencies or []
        t.actual_minutes = m.actual_minutes
        t.workload_score = m.workload_score
        t.ai_priority_score = m.ai_priority_score
        t.postpone_count = getattr(m, "postpone_count", 0)
        t.interruption_count = getattr(m, "interruption_count", 0)
        t.focus_score = getattr(m, "focus_score", 0.0)
        t.deadline_type = getattr(m, "deadline_type", "soft")
        t.project_id = getattr(m, "project_id", None)
        return t

    # ── Chat Sessions ──────────────────────────────────────────────────────────
    @classmethod
    def get_chat_sessions(cls, user_id: str) -> list:
        with SessionLocal() as db:
            models = db.query(ChatSessionModel).filter(ChatSessionModel.user_id == user_id).order_by(ChatSessionModel.updated_at.desc()).all()
            result = []
            for m in models:
                msgs = db.query(ChatMessageModel).filter(ChatMessageModel.session_id == m.id).order_by(ChatMessageModel.id.asc()).all()
                result.append({
                    "id": m.id,
                    "title": m.title,
                    "updated_at": m.updated_at,
                    "messages": [{"role": msg.role, "text": msg.text, "timestamp": msg.timestamp} for msg in msgs]
                })
            return result

    @classmethod
    def get_chat_session(cls, user_id: str, session_id: str) -> Optional[dict]:
        with SessionLocal() as db:
            m = db.query(ChatSessionModel).filter(ChatSessionModel.id == session_id, ChatSessionModel.user_id == user_id).first()
            if not m:
                return None
            msgs = db.query(ChatMessageModel).filter(ChatMessageModel.session_id == session_id).order_by(ChatMessageModel.id.asc()).all()
            return {
                "id": m.id,
                "title": m.title,
                "updated_at": m.updated_at,
                "messages": [{"role": msg.role, "text": msg.text, "timestamp": msg.timestamp} for msg in msgs]
            }

    @classmethod
    def create_chat_session(cls, user_id: str, title: str = "Chat mới") -> str:
        sid = str(uuid.uuid4())
        now = datetime.now().isoformat()
        with SessionLocal() as db:
            db.add(ChatSessionModel(id=sid, user_id=user_id, title=title, updated_at=now, created_at=now))
            db.commit()
        return sid

    @classmethod
    def add_chat_message(cls, user_id: str, session_id: str, role: str, text: str):
        now = datetime.now().isoformat()
        with SessionLocal() as db:
            db.add(ChatMessageModel(session_id=session_id, user_id=user_id, role=role, text=text, timestamp=now))
            count = db.query(ChatMessageModel).filter(ChatMessageModel.session_id == session_id).count()
            sess = db.query(ChatSessionModel).filter(ChatSessionModel.id == session_id).first()
            if sess:
                if sess.title == "Chat mới" and role == "user" and count <= 2:
                    sess.title = text[:30] + ("..." if len(text) > 30 else "")
                sess.updated_at = now
            db.commit()

    @classmethod
    def clear_chat_history(cls, user_id: str):
        with SessionLocal() as db:
            db.query(ChatMessageModel).filter(ChatMessageModel.user_id == user_id).delete()
            db.query(ChatSessionModel).filter(ChatSessionModel.user_id == user_id).delete()
            db.commit()

    @classmethod
    def delete_chat_session(cls, user_id: str, session_id: str):
        with SessionLocal() as db:
            db.query(ChatSessionModel).filter(ChatSessionModel.id == session_id, ChatSessionModel.user_id == user_id).delete()
            db.commit()

    # ── Behavior Events ────────────────────────────────────────────────────────
    @classmethod
    def log_behavior(cls, user_id: str, event_type: str, event_data: dict = None,
                     hour_of_day: int = None, day_of_week: int = None):
        now = datetime.now()
        with SessionLocal() as db:
            db.add(UserBehaviorModel(
                user_id=user_id, event_type=event_type, event_data=event_data or {},
                hour_of_day=hour_of_day if hour_of_day is not None else now.hour,
                day_of_week=day_of_week if day_of_week is not None else now.weekday(),
                timestamp=now.isoformat()
            ))
            db.commit()

    @classmethod
    def get_behavior_events(cls, user_id: str, event_type: str = None, limit: int = 500) -> List[dict]:
        with SessionLocal() as db:
            query = db.query(UserBehaviorModel).filter(UserBehaviorModel.user_id == user_id)
            if event_type:
                query = query.filter(UserBehaviorModel.event_type == event_type)
            models = query.order_by(UserBehaviorModel.timestamp.desc()).limit(limit).all()
            return [{"event_type": m.event_type, "event_data": m.event_data, "hour_of_day": m.hour_of_day, "timestamp": m.timestamp} for m in models]

    # ── Work Sessions ──────────────────────────────────────────────────────────
    @classmethod
    def save_work_session(cls, ws: WorkSession):
        with SessionLocal() as db:
            m = db.query(WorkSessionModel).filter(WorkSessionModel.id == ws.id).first()
            if not m:
                m = WorkSessionModel(id=ws.id, user_id=ws.user_id, task_id=ws.task_id, started_at=ws.started_at)
                db.add(m)
            m.ended_at = ws.ended_at
            m.duration_minutes = ws.duration_minutes
            m.focus_quality = ws.focus_quality
            m.notes = ws.notes
            db.commit()

    @classmethod
    def get_work_sessions(cls, user_id: str, limit: int = 100) -> List[dict]:
        with SessionLocal() as db:
            models = db.query(WorkSessionModel).filter(WorkSessionModel.user_id == user_id).order_by(WorkSessionModel.started_at.desc()).limit(limit).all()
            return [
                {
                    "id": m.id,
                    "user_id": m.user_id,
                    "task_id": m.task_id,
                    "started_at": m.started_at,
                    "ended_at": m.ended_at,
                    "duration_minutes": m.duration_minutes,
                    "focus_quality": getattr(m, "focus_quality", 5),
                    "interruptions": getattr(m, "interruptions", 0),
                }
                for m in models
            ]

    # ── AI Memory ──────────────────────────────────────────────────────────────
    @classmethod
    def set_memory(cls, user_id: str, memory_type: str, key: str, value, confidence: float = 0.5):
        now = datetime.now().isoformat()
        with SessionLocal() as db:
            m = db.query(AIMemoryModel).filter(AIMemoryModel.user_id == user_id, AIMemoryModel.memory_type == memory_type, AIMemoryModel.key == key).first()
            if not m:
                m = AIMemoryModel(user_id=user_id, memory_type=memory_type, key=key)
                db.add(m)
            m.value = json.dumps(value) if not isinstance(value, str) else value
            m.confidence = confidence
            m.updated_at = now
            db.commit()

    @classmethod
    def get_memory(cls, user_id: str, memory_type: str = None) -> List[dict]:
        with SessionLocal() as db:
            query = db.query(AIMemoryModel).filter(AIMemoryModel.user_id == user_id)
            if memory_type:
                query = query.filter(AIMemoryModel.memory_type == memory_type)
            models = query.order_by(AIMemoryModel.updated_at.desc()).all()
            res = []
            for m in models:
                try:
                    val = json.loads(m.value)
                except:
                    val = m.value
                res.append({"memory_type": m.memory_type, "key": m.key, "value": val, "confidence": m.confidence, "updated_at": m.updated_at})
            return res

    @classmethod
    def get_memory_value(cls, user_id: str, memory_type: str, key: str, default=None):
        with SessionLocal() as db:
            m = db.query(AIMemoryModel).filter(AIMemoryModel.user_id == user_id, AIMemoryModel.memory_type == memory_type, AIMemoryModel.key == key).first()
            if not m: return default
            try: return json.loads(m.value)
            except: return m.value

    # ── Analytics Cache ────────────────────────────────────────────────────────
    @classmethod
    def set_analytics(cls, user_id: str, metric_name: str, metric_value):
        now = datetime.now().isoformat()
        with SessionLocal() as db:
            m = db.query(AnalyticsCacheModel).filter(AnalyticsCacheModel.user_id == user_id, AnalyticsCacheModel.metric_name == metric_name).first()
            if not m:
                m = AnalyticsCacheModel(user_id=user_id, metric_name=metric_name)
                db.add(m)
            m.metric_value = json.dumps(metric_value) if not isinstance(metric_value, str) else metric_value
            m.computed_at = now
            db.commit()

    @classmethod
    def get_analytics(cls, user_id: str, metric_name: str, default=None):
        with SessionLocal() as db:
            m = db.query(AnalyticsCacheModel).filter(AnalyticsCacheModel.user_id == user_id, AnalyticsCacheModel.metric_name == metric_name).first()
            if not m: return default
            try: return json.loads(m.metric_value)
            except: return m.metric_value

    @classmethod
    def delete_memory(cls, user_id: str, memory_type: str, key: str):
        with SessionLocal() as db:
            db.query(AIMemoryModel).filter(
                AIMemoryModel.user_id == user_id,
                AIMemoryModel.memory_type == memory_type,
                AIMemoryModel.key == key
            ).delete()
            db.commit()

    @classmethod
    def save_project(cls, project):
        """Lưu project thông qua ProjectService (tương thích backward)."""
        from core.services import ProjectService
        ProjectService.save_project(project)
