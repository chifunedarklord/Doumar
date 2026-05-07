"""
TaskFlow - Services Layer
Chứa toàn bộ business logic của ứng dụng.
"""
import bcrypt
import uuid
from datetime import datetime, date
from typing import Optional, List

from core.models import User, Task, WorkSession, BehaviorEvent
from core.database import Storage


# ─── Auth Service ─────────────────────────────────────────────────────────────

class AuthService:
    @staticmethod
    def hash_password(password: str) -> str:
        salt = bcrypt.gensalt()
        return bcrypt.hashpw(password.encode('utf-8'), salt).decode('utf-8')

    @staticmethod
    def verify_password(password: str, hashed: str) -> bool:
        try:
            return bcrypt.checkpw(password.encode('utf-8'), hashed.encode('utf-8'))
        except ValueError:
            import hashlib
            return hashlib.sha256(password.encode('utf-8')).hexdigest() == hashed

    @classmethod
    def register(cls, username, email, password, full_name="") -> tuple:
        if Storage.find_user(username=username):
            return False, "Tên đăng nhập đã tồn tại"
        if Storage.find_user(email=email):
            return False, "Email đã được sử dụng"
        if len(password) < 6:
            return False, "Mật khẩu tối thiểu 6 ký tự"
        user = User(
            id=str(uuid.uuid4()), username=username, email=email,
            password_hash=cls.hash_password(password),
            full_name=full_name or username,
        )
        Storage.save_user(user)
        return True, "Đăng ký thành công"

    @classmethod
    def login(cls, username, password) -> tuple:
        user = Storage.find_user(username=username)
        if not user:
            return False, "Tên đăng nhập không tồn tại", None
        if not cls.verify_password(password, user.password_hash):
            return False, "Mật khẩu không đúng", None
        Storage.set_session(user.id)
        BehaviorService.log(user.id, "session_start", {"username": username})
        return True, "Đăng nhập thành công", user

    @staticmethod
    def logout():
        Storage.set_session(None)

    @staticmethod
    def get_current_user() -> Optional[User]:
        uid = Storage.get_session()
        if not uid:
            return None
        for u in Storage.get_users():
            if u.id == uid:
                return u
        return None

    @classmethod
    def change_password(cls, user, old_password, new_password, confirm_password) -> tuple:
        if not old_password or not new_password:
            return False, "Vui lòng nhập đầy đủ!"
        if not cls.verify_password(old_password, user.password_hash):
            return False, "Mật khẩu cũ không đúng!"
        if new_password != confirm_password:
            return False, "Mật khẩu mới không khớp!"
        if len(new_password) < 6:
            return False, "Mật khẩu tối thiểu 6 ký tự!"
        user.password_hash = cls.hash_password(new_password)
        Storage.save_user(user)
        return True, "Đã đổi mật khẩu thành công ✓"

    @staticmethod
    def update_profile(user, full_name, avatar_color) -> User:
        user.full_name = full_name or user.username
        user.avatar_color = avatar_color
        Storage.save_user(user)
        return user


# ─── Task Service ─────────────────────────────────────────────────────────────

class TaskService:
    @staticmethod
    def get_tasks(user_id: str) -> List[Task]:
        return Storage.get_tasks(user_id)

    @staticmethod
    def get_filtered_tasks(user_id, search="", category="all",
                           status="all", priority="all") -> List[Task]:
        tasks = Storage.get_tasks(user_id)
        q = search.lower()
        if q:
            tasks = [t for t in tasks if q in t.title.lower() or q in t.description.lower()]
        if category != "all":
            tasks = [t for t in tasks if t.category == category]
        if status != "all":
            tasks = [t for t in tasks if t.status == status]
        if priority != "all":
            tasks = [t for t in tasks if t.priority == priority]

        def sort_key(t):
            return (0 if t.is_overdue else 1, t.due_date or "9999",
                    {"high": 0, "medium": 1, "low": 2}.get(t.priority, 1))

        return sorted(tasks, key=sort_key)

    @staticmethod
    def save_task(task: Task):
        # Auto-calculate workload score
        energy_map = {"low": 3, "medium": 5, "high": 8}
        focus_map  = {"low": 3, "medium": 5, "high": 8}
        task.workload_score = round(
            (energy_map.get(task.energy_required, 5) +
             focus_map.get(task.focus_required, 5) +
             task.difficulty_level) / 3, 1
        )
        Storage.save_task(task)

    @staticmethod
    def delete_task(task_id: str):
        Storage.delete_task(task_id)

    @staticmethod
    def toggle_done(task: Task) -> Task:
        was_done = task.status == "done"
        task.status = "done" if not was_done else "todo"
        if task.status == "done":
            task.completed_at = datetime.now().isoformat()
            BehaviorService.log(task.user_id, "task_complete", {
                "task_id": task.id, "category": task.category,
                "priority": task.priority, "title": task.title,
                "estimated_minutes": task.estimated_minutes,
            })
        else:
            task.completed_at = None
        Storage.save_task(task)
        return task

    @staticmethod
    def mark_delayed(task: Task, reason: str = ""):
        """Ghi nhận task bị trì hoãn."""
        BehaviorService.log(task.user_id, "task_delay", {
            "task_id": task.id, "category": task.category,
            "priority": task.priority, "reason": reason,
        })

    @staticmethod
    def get_stats(user_id: str) -> dict:
        tasks = Storage.get_tasks(user_id)
        today_str = date.today().isoformat()
        total   = len(tasks)
        done    = sum(1 for t in tasks if t.status == "done")
        in_prog = sum(1 for t in tasks if t.status == "in_progress")
        overdue = sum(1 for t in tasks if t.is_overdue)
        today   = [t for t in tasks if t.due_date == today_str and t.status != "done"]
        return {
            "total": total, "done": done, "in_prog": in_prog,
            "overdue": overdue, "today": today,
            "completion_pct": int(done / total * 100) if total else 0,
        }

    @staticmethod
    def check_reminders(user_id: str, notified: set) -> List[Task]:
        from datetime import timedelta
        now = datetime.now()
        tasks = Storage.get_tasks(user_id)
        due_now = []
        for t in tasks:
            if t.status != "done" and getattr(t, "reminder_minutes", 0) > 0:
                tdate = t.due_date or t.start_date
                ttime = t.due_time
                if tdate and ttime:
                    try:
                        dt_obj = datetime.strptime(f"{tdate} {ttime}", "%Y-%m-%d %H:%M")
                        reminder_time = dt_obj - timedelta(minutes=t.reminder_minutes)
                        diff = (now - reminder_time).total_seconds()
                        if 0 <= diff <= 300 and t.id not in notified:
                            notified.add(t.id)
                            due_now.append(t)
                    except Exception:
                        pass
        return due_now


# ─── Chat Service ─────────────────────────────────────────────────────────────

class ChatService:
    @staticmethod
    def get_sessions(user_id: str) -> list:
        return Storage.get_chat_sessions(user_id)

    @staticmethod
    def get_session(user_id: str, session_id: str) -> dict:
        return Storage.get_chat_session(user_id, session_id)

    @staticmethod
    def create_session(user_id: str, title: str = "Chat mới") -> str:
        return Storage.create_chat_session(user_id, title)

    @staticmethod
    def add_message(user_id: str, session_id: str, role: str, text: str):
        Storage.add_chat_message(user_id, session_id, role, text)

    @staticmethod
    def delete_session(user_id: str, session_id: str):
        Storage.delete_chat_session(user_id, session_id)

    @staticmethod
    def clear_all(user_id: str):
        Storage.clear_chat_history(user_id)


# ─── Behavior Service ─────────────────────────────────────────────────────────

class BehaviorService:
    """Ghi nhận và truy vấn dữ liệu hành vi user."""

    @staticmethod
    def log(user_id: str, event_type: str, event_data: dict = None):
        try:
            Storage.log_behavior(user_id, event_type, event_data or {})
        except Exception:
            pass

    @staticmethod
    def get_events(user_id: str, event_type: str = None, limit: int = 300) -> list:
        return Storage.get_behavior_events(user_id, event_type, limit)

    @staticmethod
    def get_peak_hours(user_id: str) -> List[int]:
        from core.ai_engine import BehaviorAnalyzer
        events = Storage.get_behavior_events(user_id, "task_complete", 200)
        return BehaviorAnalyzer.get_peak_hours(events)

    @staticmethod
    def get_productivity_score(user_id: str) -> float:
        from core.ai_engine import BehaviorAnalyzer
        tasks = Storage.get_tasks(user_id)
        events = Storage.get_behavior_events(user_id, limit=200)
        return BehaviorAnalyzer.calc_weekly_score(tasks, events)


# ─── Work Session Service ─────────────────────────────────────────────────────

class WorkSessionService:
    """Quản lý focus/work sessions."""

    @staticmethod
    def start_session(user_id: str, task_id: str = None) -> WorkSession:
        ws = WorkSession(
            id=str(uuid.uuid4()),
            user_id=user_id,
            task_id=task_id,
            started_at=datetime.now().isoformat(),
        )
        Storage.save_work_session(ws)
        BehaviorService.log(user_id, "session_start", {"task_id": task_id})
        return ws

    @staticmethod
    def end_session(ws: WorkSession, focus_quality: int = 5) -> WorkSession:
        ws.ended_at = datetime.now().isoformat()
        start = datetime.fromisoformat(ws.started_at)
        end = datetime.fromisoformat(ws.ended_at)
        ws.duration_minutes = int((end - start).total_seconds() / 60)
        ws.focus_quality = max(1, min(10, focus_quality))

        # Update actual_minutes on task
        if ws.task_id:
            tasks = Storage.get_tasks(ws.user_id)
            for t in tasks:
                if t.id == ws.task_id:
                    t.actual_minutes = (t.actual_minutes or 0) + ws.duration_minutes
                    Storage.save_task(t)
                    break

        Storage.save_work_session(ws)
        BehaviorService.log(ws.user_id, "session_end", {
            "task_id": ws.task_id,
            "duration_minutes": ws.duration_minutes,
            "focus_quality": ws.focus_quality,
        })
        return ws

    @staticmethod
    def get_sessions(user_id: str, limit: int = 50) -> list:
        return Storage.get_work_sessions(user_id, limit)


# ─── Analytics Service ────────────────────────────────────────────────────────

class AnalyticsService:
    """Tổng hợp analytics AI-powered cho user."""

    @staticmethod
    def get_full_report(user_id: str) -> dict:
        from core.ai_engine import BehaviorAnalyzer, BurnoutDetector, RecommendationEngine

        tasks = Storage.get_tasks(user_id)
        events = Storage.get_behavior_events(user_id, limit=500)
        sessions = Storage.get_work_sessions(user_id, limit=100)

        peak_hours = BehaviorAnalyzer.get_peak_hours(events)
        productivity_by_hour = BehaviorAnalyzer.get_productivity_by_hour(events)
        delay_patterns = BehaviorAnalyzer.get_delay_patterns(events)
        daily_productivity = BehaviorAnalyzer.calc_daily_productivity(tasks, 7)
        weekly_score = BehaviorAnalyzer.calc_weekly_score(tasks, events)
        burnout = BurnoutDetector.get_risk(tasks, sessions, events)
        suggestions = RecommendationEngine.get_suggestions(tasks, events, burnout, peak_hours)

        # Basic stats
        total  = len(tasks)
        done   = sum(1 for t in tasks if t.status == "done")
        overdue = sum(1 for t in tasks if t.is_overdue)
        active = [t for t in tasks if t.status not in ("done", "cancelled")]
        completion_rate = int(done / total * 100) if total else 0

        # Focus time (from sessions last 7 days)
        today = date.today()
        week_ago = (today - __import__("datetime").timedelta(days=7)).isoformat()
        recent_sessions = [s for s in sessions if s.get("started_at", "") >= week_ago]
        total_focus_min = sum(s.get("duration_minutes", 0) for s in recent_sessions)

        # Cache the result
        Storage.set_analytics(user_id, "weekly_score", weekly_score)
        Storage.set_analytics(user_id, "burnout_level", burnout["level"])
        Storage.set_analytics(user_id, "peak_hours", peak_hours)

        return {
            "total_tasks": total,
            "done_tasks": done,
            "overdue_tasks": overdue,
            "active_tasks": len(active),
            "completion_rate": completion_rate,
            "weekly_score": weekly_score,
            "burnout": burnout,
            "peak_hours": peak_hours,
            "productivity_by_hour": productivity_by_hour,
            "delay_patterns": delay_patterns,
            "daily_productivity": daily_productivity,
            "total_focus_minutes": total_focus_min,
            "suggestions": suggestions,
        }


# ─── AI Memory Service ────────────────────────────────────────────────────────

class AIMemoryService:
    """Quản lý bộ nhớ dài hạn của AI về user."""

    @staticmethod
    def remember(user_id: str, memory_type: str, key: str,
                 value, confidence: float = 0.7):
        Storage.set_memory(user_id, memory_type, key, value, confidence)

    @staticmethod
    def recall(user_id: str, memory_type: str = None) -> list:
        return Storage.get_memory(user_id, memory_type)

    @staticmethod
    def recall_value(user_id: str, memory_type: str, key: str, default=None):
        return Storage.get_memory_value(user_id, memory_type, key, default)

    @staticmethod
    def update_from_behavior(user_id: str):
        """Cập nhật AI memory từ behavior data."""
        peak_hours = BehaviorService.get_peak_hours(user_id)
        if peak_hours:
            AIMemoryService.remember(user_id, "habit", "peak_hours", peak_hours, 0.8)

        events = Storage.get_behavior_events(user_id, "task_complete", 50)
        if len(events) >= 5:
            avg_hour = sum(e.get("hour_of_day", 9) for e in events) / len(events)
            AIMemoryService.remember(user_id, "habit", "avg_completion_hour",
                                     round(avg_hour, 1), 0.75)

    @staticmethod
    def get_context_summary(user_id: str) -> str:
        """Tóm tắt AI memory thành text cho system prompt."""
        memories = Storage.get_memory(user_id)
        if not memories:
            return ""
        lines = ["BỘ NHỚ AI VỀ USER:"]
        for m in memories[:10]:
            lines.append(f"- [{m['memory_type']}] {m['key']}: {m['value']}")
        return "\n".join(lines)
