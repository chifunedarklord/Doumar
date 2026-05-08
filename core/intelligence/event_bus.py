"""
TaskFlow - Event Bus
Lightweight event-driven architecture cho AI triggers và analytics updates.
"""
from typing import Callable, Dict, List
from datetime import datetime
import threading


class EventBus:
    """
    Simple in-process event bus.
    Events: task_completed, task_overdue, burnout_warning,
            session_ended, analytics_update, recommendation_trigger
    """
    _instance = None
    _lock = threading.Lock()

    def __init__(self):
        self._subscribers: Dict[str, List[Callable]] = {}
        self._event_log: List[dict] = []

    @classmethod
    def get_instance(cls) -> "EventBus":
        if cls._instance is None:
            with cls._lock:
                if cls._instance is None:
                    cls._instance = EventBus()
        return cls._instance

    def subscribe(self, event_type: str, callback: Callable):
        if event_type not in self._subscribers:
            self._subscribers[event_type] = []
        self._subscribers[event_type].append(callback)

    def publish(self, event_type: str, data: dict = None):
        """Publish event, dispatch to all subscribers in background thread."""
        event = {
            "type": event_type,
            "data": data or {},
            "timestamp": datetime.now().isoformat(),
        }
        self._event_log.append(event)

        # Dispatch in background to avoid blocking UI
        def _dispatch():
            for callback in self._subscribers.get(event_type, []):
                try:
                    callback(event)
                except Exception as e:
                    print(f"[EventBus] Error in {event_type} handler: {e}")

        t = threading.Thread(target=_dispatch, daemon=True)
        t.start()

    def get_recent_events(self, limit: int = 50) -> List[dict]:
        return self._event_log[-limit:]


# Event type constants
class Events:
    TASK_COMPLETED = "task_completed"
    TASK_OVERDUE = "task_overdue"
    TASK_DELAYED = "task_delayed"
    SESSION_STARTED = "session_started"
    SESSION_ENDED = "session_ended"
    BURNOUT_WARNING = "burnout_warning"
    ANALYTICS_UPDATE = "analytics_update"
    RECOMMENDATION_TRIGGER = "recommendation_trigger"
    MEMORY_UPDATE = "memory_update"
    DAILY_REVIEW = "daily_review"
    RECOMMENDATION_ACCEPTED = "recommendation_accepted"
    RECOMMENDATION_DISMISSED = "recommendation_dismissed"
