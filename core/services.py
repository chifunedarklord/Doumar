"""
TaskFlow - Services Layer
Chứa toàn bộ business logic của ứng dụng.
Screens chỉ được gọi tầng này, không gọi trực tiếp database / models.
"""
import bcrypt
import uuid
from datetime import datetime
from typing import Optional, List

from core.models import User, Task
from core.database import Storage


# ─── Auth Service ─────────────────────────────────────────────────────────────

class AuthService:
    """Xử lý đăng ký, đăng nhập, phiên làm việc."""

    @staticmethod
    def hash_password(password: str) -> str:
        """Hash password using bcrypt with salt."""
        salt = bcrypt.gensalt()
        return bcrypt.hashpw(password.encode('utf-8'), salt).decode('utf-8')
    
    @staticmethod
    def verify_password(password: str, hashed: str) -> bool:
        """Verify password against bcrypt hash."""
        try:
            return bcrypt.checkpw(password.encode('utf-8'), hashed.encode('utf-8'))
        except ValueError:
            # Fallback for old SHA-256 hashes
            import hashlib
            return hashlib.sha256(password.encode('utf-8')).hexdigest() == hashed

    @classmethod
    def register(
        cls,
        username: str,
        email: str,
        password: str,
        full_name: str = "",
    ) -> tuple[bool, str]:
        if Storage.find_user(username=username):
            return False, "Tên đăng nhập đã tồn tại"
        if Storage.find_user(email=email):
            return False, "Email đã được sử dụng"
        if len(password) < 6:
            return False, "Mật khẩu tối thiểu 6 ký tự"
        user = User(
            id=str(uuid.uuid4()),
            username=username,
            email=email,
            password_hash=cls.hash_password(password),
            full_name=full_name or username,
        )
        Storage.save_user(user)
        return True, "Đăng ký thành công"

    @classmethod
    def login(
        cls, username: str, password: str
    ) -> tuple[bool, str, Optional[User]]:
        user = Storage.find_user(username=username)
        if not user:
            return False, "Tên đăng nhập không tồn tại", None
        if not cls.verify_password(password, user.password_hash):
            return False, "Mât khâu không dúng", None
        Storage.set_session(user.id)
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
    def change_password(
        cls, user: User, old_password: str, new_password: str, confirm_password: str
    ) -> tuple[bool, str]:
        if not old_password or not new_password:
            return False, "Vui lòng nhập đầy đủ!"
        if not cls.verify_password(old_password, user.password_hash):
            return False, "Mát khẩu cái không dúng!"
        if new_password != confirm_password:
            return False, "Mật khẩu mới không khớp!"
        if len(new_password) < 6:
            return False, "Mật khẩu tối thiểu 6 ký tự!"
        user.password_hash = cls.hash_password(new_password)
        Storage.save_user(user)
        return True, "Đã đổi mật khẩu thành công ✓"

    @staticmethod
    def update_profile(user: User, full_name: str, avatar_color: str) -> User:
        user.full_name = full_name or user.username
        user.avatar_color = avatar_color
        Storage.save_user(user)
        return user


# ─── Task Service ─────────────────────────────────────────────────────────────

class TaskService:
    """Xử lý toàn bộ nghiệp vụ liên quan đến Task."""

    @staticmethod
    def get_tasks(user_id: str) -> List[Task]:
        """Lấy tất cả task của user."""
        return Storage.get_tasks(user_id)

    @staticmethod
    def get_filtered_tasks(
        user_id: str,
        search: str = "",
        category: str = "all",
        status: str = "all",
        priority: str = "all",
    ) -> List[Task]:
        """Lấy task đã lọc và sắp xếp."""
        tasks = Storage.get_tasks(user_id)
        q = search.lower()
        if q:
            tasks = [
                t for t in tasks
                if q in t.title.lower() or q in t.description.lower()
            ]
        if category != "all":
            tasks = [t for t in tasks if t.category == category]
        if status != "all":
            tasks = [t for t in tasks if t.status == status]
        if priority != "all":
            tasks = [t for t in tasks if t.priority == priority]

        def sort_key(t: Task):
            pri_order = {"high": 0, "medium": 1, "low": 2}
            return (
                0 if t.is_overdue else 1,
                t.due_date or "9999",
                pri_order.get(t.priority, 1),
            )

        return sorted(tasks, key=sort_key)

    @staticmethod
    def save_task(task: Task):
        """Lưu (tạo mới hoặc cập nhật) một task."""
        Storage.save_task(task)

    @staticmethod
    def delete_task(task_id: str):
        """Xóa task theo ID."""
        Storage.delete_task(task_id)

    @staticmethod
    def toggle_done(task: Task) -> Task:
        """Đảo trạng thái done / todo của task và lưu lại."""
        task.status = "done" if task.status != "done" else "todo"
        if task.status == "done":
            task.completed_at = datetime.now().isoformat()
        else:
            task.completed_at = None
        Storage.save_task(task)
        return task

    @staticmethod
    def get_stats(user_id: str) -> dict:
        """Tổng hợp số liệu thống kê task của user."""
        from datetime import date
        tasks = Storage.get_tasks(user_id)
        today_str = date.today().isoformat()
        total     = len(tasks)
        done      = sum(1 for t in tasks if t.status == "done")
        in_prog   = sum(1 for t in tasks if t.status == "in_progress")
        overdue   = sum(1 for t in tasks if t.is_overdue)
        today     = [t for t in tasks if t.due_date == today_str and t.status != "done"]
        return {
            "total":   total,
            "done":    done,
            "in_prog": in_prog,
            "overdue": overdue,
            "today":   today,
            "completion_pct": int(done / total * 100) if total else 0,
        }

    @staticmethod
    def check_reminders(user_id: str, notified: set) -> List[Task]:
        """Trả về danh sách task cần nhắc nhở (chưa thông báo)."""
        now = datetime.now()
        curr_date = now.strftime("%Y-%m-%d")
        curr_time = now.strftime("%H:%M")
        tasks = Storage.get_tasks(user_id)
        due_now = []
        for t in tasks:
            if t.status != "done" and t.reminder_minutes > 0:
                tdate = t.start_date or t.due_date
                ttime = t.due_time
                if tdate == curr_date and ttime == curr_time:
                    if t.id not in notified:
                        notified.add(t.id)
                        due_now.append(t)
        return due_now
