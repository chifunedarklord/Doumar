"""
TaskFlow - Database Migration Script (v1 to v2)
Migrates data from raw SQLite taskflow.db to SQLAlchemy taskflow_v2.db
"""
import sqlite3
import json
import os
import sys
from pathlib import Path

# Add project root to sys.path
sys.path.append(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from core.orm import (
    SessionLocal, UserModel, SessionModel, TaskModel, ChatSessionModel,
    ChatMessageModel, UserBehaviorModel, WorkSessionModel, AIMemoryModel,
    AnalyticsCacheModel
)

DATA_DIR = Path(__file__).parent.parent / "data"
OLD_DB_PATH = DATA_DIR / "taskflow.db"

def migrate():
    if not OLD_DB_PATH.exists():
        print(f"Old database not found at {OLD_DB_PATH}. Nothing to migrate.")
        return

    print(f"Connecting to {OLD_DB_PATH}...")
    conn = sqlite3.connect(OLD_DB_PATH)
    conn.row_factory = sqlite3.Row
    
    with SessionLocal() as db:
        print("Migrating Users...")
        for row in conn.execute("SELECT * FROM users"):
            d = dict(row)
            user = db.query(UserModel).filter(UserModel.id == d["id"]).first()
            if not user:
                user = UserModel(id=d["id"])
                db.add(user)
            user.username = d["username"]
            user.email = d["email"]
            user.password_hash = d["password_hash"]
            user.full_name = d.get("full_name", "")
            user.avatar_color = d.get("avatar_color", "#707070")
            user.created_at = d.get("created_at", "")
            try: user.settings = json.loads(d.get("settings", "{}"))
            except: user.settings = {}
        db.commit()

        print("Migrating Sessions...")
        for row in conn.execute("SELECT * FROM sessions"):
            d = dict(row)
            sess = db.query(SessionModel).filter(SessionModel.user_id == d["user_id"]).first()
            if not sess:
                sess = SessionModel(user_id=d["user_id"])
                db.add(sess)
        db.commit()

        print("Migrating Tasks...")
        for row in conn.execute("SELECT * FROM tasks"):
            d = dict(row)
            task = db.query(TaskModel).filter(TaskModel.id == d["id"]).first()
            if not task:
                task = TaskModel(id=d["id"])
                db.add(task)
            task.user_id = d["user_id"]
            task.title = d["title"]
            task.description = d.get("description", "")
            task.category = d.get("category", "personal")
            task.priority = d.get("priority", "medium")
            task.status = d.get("status", "todo")
            task.due_date = d.get("due_date")
            task.due_time = d.get("due_time")
            task.start_date = d.get("start_date")
            task.reminder_minutes = d.get("reminder_minutes", 0)
            task.complexity = d.get("complexity", "medium")
            task.estimated_minutes = d.get("estimated_minutes", 30)
            try: task.tags = json.loads(d.get("tags", "[]"))
            except: task.tags = []
            try: task.subtasks = json.loads(d.get("subtasks", "[]"))
            except: task.subtasks = []
            task.notes = d.get("notes", "")
            task.created_at = d.get("created_at", "")
            task.updated_at = d.get("updated_at", "")
            task.completed_at = d.get("completed_at")
            task.is_recurring = bool(d.get("is_recurring", 0))
            task.recur_pattern = d.get("recur_pattern", "")
            task.impact_score = d.get("impact_score", 5.0)
            task.risk_level = d.get("risk_level", "low")
            task.energy_required = d.get("energy_required", "medium")
            task.focus_required = d.get("focus_required", "medium")
            task.difficulty_level = d.get("difficulty_level", 5)
            task.motivation_score = d.get("motivation_score", 5.0)
            try: task.dependencies = json.loads(d.get("dependencies", "[]"))
            except: task.dependencies = []
            task.actual_minutes = d.get("actual_minutes", 0)
            task.workload_score = d.get("workload_score", 5.0)
            task.ai_priority_score = d.get("ai_priority_score", 50.0)
        db.commit()

        print("Migrating Chat Sessions...")
        for row in conn.execute("SELECT * FROM chat_sessions"):
            d = dict(row)
            m = db.query(ChatSessionModel).filter(ChatSessionModel.id == d["id"]).first()
            if not m:
                m = ChatSessionModel(id=d["id"])
                db.add(m)
            m.user_id = d["user_id"]
            m.title = d.get("title", "Chat mới")
            m.updated_at = d.get("updated_at", "")
            m.created_at = d.get("created_at", "")
        db.commit()

        print("Migrating Chat Messages...")
        try:
            for row in conn.execute("SELECT * FROM chat_messages"):
                d = dict(row)
                m = ChatMessageModel(session_id=d["session_id"], user_id=d["user_id"], role=d["role"], text=d["text"], timestamp=d["timestamp"])
                db.add(m)
            db.commit()
        except Exception as e:
            print(f"Error migrating chat messages: {e}")

        print("Migrating Behavior Events...")
        try:
            for row in conn.execute("SELECT * FROM user_behavior"):
                d = dict(row)
                try: ev = json.loads(d.get("event_data", "{}"))
                except: ev = {}
                m = UserBehaviorModel(user_id=d["user_id"], event_type=d["event_type"], event_data=ev, hour_of_day=d.get("hour_of_day"), day_of_week=d.get("day_of_week"), timestamp=d["timestamp"])
                db.add(m)
            db.commit()
        except Exception as e:
            print(f"Error migrating behavior events: {e}")
            
        print("Migrating Work Sessions...")
        try:
            for row in conn.execute("SELECT * FROM work_sessions"):
                d = dict(row)
                m = db.query(WorkSessionModel).filter(WorkSessionModel.id == d["id"]).first()
                if not m:
                    m = WorkSessionModel(id=d["id"], user_id=d["user_id"], task_id=d.get("task_id"), started_at=d["started_at"], ended_at=d.get("ended_at"), duration_minutes=d.get("duration_minutes", 0), focus_quality=d.get("focus_quality", 5), notes=d.get("notes", ""))
                    db.add(m)
            db.commit()
        except Exception as e:
            print(f"Error migrating work sessions: {e}")

        print("Migration complete!")
    conn.close()

if __name__ == "__main__":
    migrate()
