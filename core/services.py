"""
TaskFlow - Services Layer (Upgraded)
Tích hợp toàn bộ intelligence engines vào business logic.
"""
import logging
import bcrypt
import uuid
from datetime import datetime, date
from typing import Optional, List

from core.models import User, Task, WorkSession, BehaviorEvent
from core.database import Storage

logger = logging.getLogger(__name__)


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

        # Sort by ai_priority_score descending
        def sort_key(t):
            return -getattr(t, "ai_priority_score", 50.0)
        return sorted(tasks, key=sort_key)

    @staticmethod
    def save_task(task: Task):
        # Calculate workload score
        energy_map = {"low": 3, "medium": 5, "high": 8}
        focus_map = {"low": 3, "medium": 5, "high": 8}
        task.workload_score = round(
            (energy_map.get(task.energy_required, 5) +
             focus_map.get(task.focus_required, 5) +
             task.difficulty_level) / 3, 1
        )

        # Recalculate AI priority score using adaptive engine
        try:
            from core.intelligence.priority_engine import AdaptivePriorityEngine
            sessions = Storage.get_work_sessions(task.user_id, 50)
            events = Storage.get_behavior_events(task.user_id, limit=200)

            from core.intelligence.behavior_learner import BehaviorLearner
            peak_hours = BehaviorLearner.learn_peak_hours(events, sessions)
            delay_patterns = BehaviorLearner.learn_delay_patterns(events)
            energy_level = BehaviorLearner.estimate_current_energy(events, sessions)
            stress_level = BehaviorLearner.estimate_stress_level(Storage.get_tasks(task.user_id), events)

            ctx = {
                "peak_hours": peak_hours,
                "current_hour": datetime.now().hour,
                "delay_risk": delay_patterns,
                "energy_level": energy_level,
                "stress_level": stress_level,
            }
            task.ai_priority_score = AdaptivePriorityEngine.calculate_score(task, ctx)
        except Exception:
            logger.exception("AdaptivePriorityEngine failed for task %s", task.id)

        is_new = Storage.save_task(task)

        # Log task creation behavior so AI can learn from it
        if is_new:
            try:
                BehaviorService.log(task.user_id, "task_create", {
                    "task_id": task.id,
                    "title": task.title,
                    "category": task.category,
                    "priority": task.priority,
                    "estimated_minutes": task.estimated_minutes,
                })
            except Exception:
                pass

        # Publish event + invalidate AI context cache
        try:
            from core.intelligence.event_bus import EventBus, Events
            EventBus.get_instance().publish(Events.ANALYTICS_UPDATE, {"user_id": task.user_id})
        except Exception:
            pass

        try:
            from utils.ai_helper import invalidate_context_cache
            invalidate_context_cache(task.user_id)
        except Exception:
            pass

        try:
            AnalyticsService.invalidate_cache(task.user_id)
        except Exception:
            pass

    @staticmethod
    def delete_task(task_id: str, user_id: str = None):
        Storage.delete_task(task_id)
        if user_id:
            try:
                AnalyticsService.invalidate_cache(user_id)
            except Exception:
                pass

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
            # Trigger memory update in background
            try:
                from core.intelligence.event_bus import EventBus, Events
                EventBus.get_instance().publish(Events.TASK_COMPLETED, {
                    "user_id": task.user_id, "task_id": task.id
                })
            except Exception:
                pass
        else:
            task.completed_at = None
        Storage.save_task(task)
        try:
            AnalyticsService.invalidate_cache(task.user_id)
        except Exception:
            pass
        return task

    @staticmethod
    def mark_delayed(task: Task, reason: str = ""):
        BehaviorService.log(task.user_id, "task_delay", {
            "task_id": task.id, "category": task.category,
            "priority": task.priority, "reason": reason,
        })

    @staticmethod
    def get_stats(user_id: str) -> dict:
        tasks = Storage.get_tasks(user_id)
        today_str = date.today().isoformat()
        total = len(tasks)
        done = sum(1 for t in tasks if t.status == "done")
        in_prog = sum(1 for t in tasks if t.status == "in_progress")
        overdue = sum(1 for t in tasks if t.is_overdue)
        today = [t for t in tasks if t.due_date == today_str and t.status != "done"]
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

    @staticmethod
    def split_task(task: Task) -> List[dict]:
        """Auto-split task lớn thành subtasks."""
        from core.intelligence.scheduling_engine import SchedulingEngine
        return SchedulingEngine.auto_split_task(task)


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
            logger.exception("BehaviorService.log failed: user=%s event=%s", user_id, event_type)

    @staticmethod
    def get_events(user_id: str, event_type: str = None, limit: int = 300) -> list:
        return Storage.get_behavior_events(user_id, event_type, limit)

    @staticmethod
    def get_peak_hours(user_id: str) -> List[int]:
        from core.intelligence.behavior_learner import BehaviorLearner
        events = Storage.get_behavior_events(user_id, limit=300)
        sessions = Storage.get_work_sessions(user_id, limit=100)
        return BehaviorLearner.learn_peak_hours(events, sessions)

    @staticmethod
    def get_productivity_score(user_id: str) -> float:
        from core.intelligence.behavior_learner import BehaviorLearner
        tasks = Storage.get_tasks(user_id)
        events = Storage.get_behavior_events(user_id, limit=200)
        return BehaviorLearner.calc_weekly_productivity_score(tasks, events)

    @staticmethod
    def get_user_context(user_id: str) -> dict:
        """Build full user context for AI engines.
        Ưu tiên check-in hôm nay cho energy/stress, survey data cho peak hours."""
        from core.intelligence.behavior_learner import BehaviorLearner
        events = Storage.get_behavior_events(user_id, limit=300)
        sessions = Storage.get_work_sessions(user_id, limit=100)
        tasks = Storage.get_tasks(user_id)

        # Peak hours: dùng survey khi chưa đủ behavior data
        learned_peak = BehaviorLearner.learn_peak_hours(events, sessions)
        survey_peak  = Storage.get_memory_value(user_id, "preference", "peak_hours", None)
        meaningful   = [e for e in events if e.get("event_type") in
                        ("task_complete", "task_start", "session_start")]
        peak_hours = learned_peak if (len(meaningful) >= 20 or survey_peak is None) else (
            survey_peak if isinstance(survey_peak, list) else learned_peak
        )

        delay_patterns = BehaviorLearner.learn_delay_patterns(events)

        # Energy/stress: ưu tiên check-in hôm nay
        checkin_energy = Storage.get_memory_value(user_id, "state", "estimated_energy", None)
        checkin_stress = Storage.get_memory_value(user_id, "state", "estimated_stress", None)
        energy_level = (int(checkin_energy) if checkin_energy is not None
                        else BehaviorLearner.estimate_current_energy(events, sessions))
        stress_level = (int(checkin_stress) if checkin_stress is not None
                        else BehaviorLearner.estimate_stress_level(tasks, events))

        return {
            "peak_hours": peak_hours,
            "current_hour": datetime.now().hour,
            "delay_risk": delay_patterns,
            "energy_level": energy_level,
            "stress_level": stress_level,
            "user_id": user_id,
        }


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

        if ws.task_id:
            tasks = Storage.get_tasks(ws.user_id)
            for t in tasks:
                if t.id == ws.task_id:
                    t.actual_minutes = (t.actual_minutes or 0) + ws.duration_minutes
                    t.interruption_count = getattr(t, "interruption_count", 0)
                    Storage.save_task(t)
                    break

        Storage.save_work_session(ws)
        BehaviorService.log(ws.user_id, "session_end", {
            "task_id": ws.task_id,
            "duration_minutes": ws.duration_minutes,
            "focus_quality": ws.focus_quality,
        })

        # Write estimated energy/stress back to AIMemory after each session
        try:
            from core.intelligence.behavior_learner import BehaviorLearner
            events = Storage.get_behavior_events(ws.user_id, limit=200)
            all_sessions = Storage.get_work_sessions(ws.user_id, limit=50)
            tasks = Storage.get_tasks(ws.user_id)
            estimated_energy = BehaviorLearner.estimate_current_energy(events, all_sessions)
            estimated_stress = BehaviorLearner.estimate_stress_level(tasks, events)
            Storage.set_memory(ws.user_id, "state", "estimated_energy", estimated_energy, 0.8)
            Storage.set_memory(ws.user_id, "state", "estimated_stress", estimated_stress, 0.8)
            # Sync back to User model so all direct reads see live values
            try:
                all_users = Storage.get_users()
                user_obj = next((u for u in all_users if u.id == ws.user_id), None)
                if user_obj:
                    user_obj.energy_level = max(1, min(10, int(estimated_energy)))
                    user_obj.stress_level = max(1, min(10, int(estimated_stress)))
                    Storage.save_user(user_obj)
            except Exception as sync_err:
                print(f"[WorkSession] User sync failed: {sync_err}")
        except Exception:
            pass

        # Trigger memory update
        try:
            from core.intelligence.event_bus import EventBus, Events
            EventBus.get_instance().publish(Events.SESSION_ENDED, {
                "user_id": ws.user_id,
                "duration": ws.duration_minutes,
                "quality": ws.focus_quality,
            })
        except Exception:
            pass

        return ws

    @staticmethod
    def get_sessions(user_id: str, limit: int = 50) -> list:
        return Storage.get_work_sessions(user_id, limit)


# ─── Analytics Service ────────────────────────────────────────────────────────

class AnalyticsService:
    """Tổng hợp analytics AI-powered cho user."""

    _cache = {}
    _CACHE_TTL = 60  # Cache report trong 60 giây

    @classmethod
    def get_full_report(cls, user_id: str) -> dict:
        import time
        now = time.time()
        cached = cls._cache.get(user_id)
        if cached and now - cached['timestamp'] < cls._CACHE_TTL:
            return cached['data']

        from core.intelligence.burnout_intelligence import BurnoutIntelligence
        from core.intelligence.productivity_intelligence import ProductivityIntelligence
        from core.intelligence.recommendation_engine import RecommendationEngine
        from core.intelligence.focus_engine import FocusEngine
        from core.intelligence.behavior_learner import BehaviorLearner
        from core.intelligence.behavioral_analytics import BehavioralAnalytics

        tasks = Storage.get_tasks(user_id)
        events = Storage.get_behavior_events(user_id, limit=500)
        sessions = Storage.get_work_sessions(user_id, limit=100)

        # Build user context — survey data as baseline until enough behavior events
        learned_peak_hours = BehaviorLearner.learn_peak_hours(events, sessions)
        survey_peak_hours  = Storage.get_memory_value(user_id, "preference", "peak_hours", None)
        meaningful_events  = [e for e in events if e.get("event_type") in
                              ("task_complete", "task_start", "session_start")]
        if len(meaningful_events) >= 20 or survey_peak_hours is None:
            peak_hours = learned_peak_hours
        else:
            if isinstance(survey_peak_hours, list):
                peak_hours = survey_peak_hours
            else:
                try:
                    import json as _json
                    peak_hours = _json.loads(survey_peak_hours)
                except Exception:
                    peak_hours = learned_peak_hours

        delay_patterns = BehaviorLearner.learn_delay_patterns(events)

        # Prefer today's check-in over computed values
        checkin_energy = Storage.get_memory_value(user_id, "state", "estimated_energy", None)
        checkin_stress = Storage.get_memory_value(user_id, "state", "estimated_stress", None)
        energy_level = (int(checkin_energy) if checkin_energy is not None
                        else BehaviorLearner.estimate_current_energy(events, sessions))
        stress_level = (int(checkin_stress) if checkin_stress is not None
                        else BehaviorLearner.estimate_stress_level(tasks, events))

        weekly_score = BehaviorLearner.calc_weekly_productivity_score(tasks, events)

        ctx = {
            "peak_hours": peak_hours,
            "current_hour": datetime.now().hour,
            "delay_risk": delay_patterns,
            "energy_level": energy_level,
            "stress_level": stress_level,
            "user_id": user_id,
        }

        burnout = BurnoutIntelligence.get_risk(tasks, sessions, events)
        productivity = ProductivityIntelligence.get_full_report(tasks, sessions, events)
        focus_analysis = FocusEngine.analyze_focus_quality(sessions)
        focus_heatmap = FocusEngine.get_focus_heatmap(sessions)
        pomodoro = FocusEngine.suggest_optimal_pomodoro(sessions)
        behavior_analytics = BehavioralAnalytics.run_all(tasks, events, sessions)
        recommendations = RecommendationEngine.get_recommendations(
            tasks, events, sessions, burnout, ctx, behavior_analytics
        )

        total = len(tasks)
        done = sum(1 for t in tasks if t.status == "done")
        overdue = sum(1 for t in tasks if t.is_overdue)
        active = [t for t in tasks if t.status not in ("done", "cancelled")]

        # Cache key metrics
        Storage.set_analytics(user_id, "weekly_score", weekly_score)
        Storage.set_analytics(user_id, "burnout_level", burnout["level"])
        Storage.set_analytics(user_id, "peak_hours", peak_hours)

        report_data = {
            "total_tasks": total,
            "done_tasks": done,
            "overdue_tasks": overdue,
            "active_tasks": len(active),
            "completion_rate": int(done / total * 100) if total else 0,
            "weekly_score": weekly_score,
            "burnout": burnout,
            "peak_hours": peak_hours,
            "energy_level": energy_level,
            "stress_level": stress_level,
            "productivity": productivity,
            "focus_analysis": focus_analysis,
            "focus_heatmap": focus_heatmap,
            "optimal_pomodoro": pomodoro,
            "daily_productivity": productivity.get("daily_productivity", []),
            "recommendations": recommendations,
            "delay_patterns": delay_patterns,
            "total_focus_minutes": int(focus_analysis.get("total_focus_hours", 0) * 60),
            "suggestions": [r.get("message", "") for r in recommendations],
            "deadline_compliance": behavior_analytics["deadline_compliance"],
            "estimation_accuracy": behavior_analytics["estimation_accuracy"],
            "procrastination": behavior_analytics["procrastination"],
            "workload": behavior_analytics["workload"],
        }

        cls._cache[user_id] = {'timestamp': time.time(), 'data': report_data}
        return report_data

    @classmethod
    def invalidate_cache(cls, user_id: str):
        cls._cache.pop(user_id, None)


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
        from core.intelligence.memory_engine import MemoryEngine
        try:
            tasks = Storage.get_tasks(user_id)
            events = Storage.get_behavior_events(user_id, limit=300)
            sessions = Storage.get_work_sessions(user_id, limit=100)
            MemoryEngine.update_from_behavior(user_id, tasks, events, sessions)
        except Exception:
            logger.exception("AIMemoryService.update_from_behavior failed: user=%s", user_id)

    @staticmethod
    def get_context_summary(user_id: str) -> str:
        """Tóm tắt AI memory thành text cho system prompt."""
        from core.intelligence.memory_engine import MemoryEngine
        return MemoryEngine.get_context_summary(user_id)


# ─── Project Service ──────────────────────────────────────────────────────────

class ProjectService:
    """CRUD + analytics cho Projects."""

    @staticmethod
    def get_projects(user_id: str) -> list:
        return Storage.get_projects(user_id)

    @staticmethod
    def save_project(project) -> None:
        Storage.save_project(project)

    @staticmethod
    def delete_project(project_id: str) -> None:
        Storage.delete_project(project_id)

    @staticmethod
    def get_project_tasks(user_id: str, project_id: str) -> list:
        all_tasks = Storage.get_tasks(user_id)
        return [t for t in all_tasks if getattr(t, "project_id", None) == project_id]

    @staticmethod
    def get_project_stats(user_id: str, project_id: str) -> dict:
        tasks = ProjectService.get_project_tasks(user_id, project_id)
        total = len(tasks)
        done = sum(1 for t in tasks if t.status == "done")
        overdue = sum(1 for t in tasks if getattr(t, "is_overdue", False))
        return {
            "total": total,
            "done": done,
            "overdue": overdue,
            "completion_rate": round(done / total * 100) if total else 0,
        }
