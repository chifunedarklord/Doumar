"""
TaskFlow - Demo Data Seeder
Tạo 2 project, 12+ task và WorkSession để demo Dashboard, Calendar, Insights.

Gọi trực tiếp:  python scripts/seed_demo_data.py <username>
Gọi từ UI:      seed_for_user(user_id)
"""
import sys
import uuid
import logging
from datetime import datetime, date, timedelta

logger = logging.getLogger(__name__)


def seed_for_user(user_id: str) -> str:
    """Seed demo data. Returns summary message."""
    from core.database import Storage
    from core.models import Task, WorkSession, Project

    today = date.today()

    # ── 2 Projects ────────────────────────────────────────────
    proj1 = Project(
        id=str(uuid.uuid4()), user_id=user_id,
        name="Đồ án Đồ họa Máy tính",
        description="Xây dựng cảnh văn phòng 3D bằng OpenGL — môn INT1311",
        color="#5B4FBE", status="active", priority="high",
        due_date=(today + timedelta(days=21)).isoformat(),
        created_at=datetime.now().isoformat(), updated_at=datetime.now().isoformat(),
    )
    proj2 = Project(
        id=str(uuid.uuid4()), user_id=user_id,
        name="Ôn thi Cuối kỳ",
        description="Ôn tập các môn thi cuối kỳ học kỳ 2",
        color="#10B981", status="active", priority="high",
        due_date=(today + timedelta(days=14)).isoformat(),
        created_at=datetime.now().isoformat(), updated_at=datetime.now().isoformat(),
    )
    Storage.save_project(proj1)
    Storage.save_project(proj2)

    def _t(title, cat, pri, status, due_delta, desc="", est=30,
           proj=None, due_time=None, reminder=0, done=False):
        due = (today + timedelta(days=due_delta)).isoformat()
        return Task(
            id=str(uuid.uuid4()), user_id=user_id,
            title=title, description=desc, category=cat, priority=pri,
            status=status,
            due_date=due, due_time=due_time,
            estimated_minutes=est, reminder_minutes=reminder,
            project_id=proj,
            created_at=datetime.now().isoformat(), updated_at=datetime.now().isoformat(),
            completed_at=datetime.now().isoformat() if done else None,
            ai_priority_score=80 if pri == "high" else 50 if pri == "medium" else 30,
        )

    task_list = [
        # ── OVERDUE (quá hạn) ─────────────────────────────────
        _t("Nộp báo cáo tiến độ đồ họa", "work", "high", "todo", -4,
           desc="Nộp cho GVHD trước 8h00 sáng — ĐÃ QUÁ HẠN",
           est=60, proj=proj1.id, due_time="08:00", reminder=30),
        _t("Sửa lỗi camera xoay 3D", "work", "high", "in_progress", -2,
           desc="Camera bị flip khi góc > 180°, cần fix quaternion",
           est=90, proj=proj1.id),

        # ── TODAY ─────────────────────────────────────────────
        _t("Họp nhóm review code OpenGL", "work", "medium", "todo", 0,
           desc="Review pull request, phân công nhiệm vụ tuần sau",
           est=45, proj=proj1.id, due_time="14:00", reminder=15),
        _t("Ôn tập CSDL — Chương 4 & 5", "education", "high", "todo", 0,
           desc="Transaction, Concurrency Control, Recovery",
           est=90, proj=proj2.id, due_time="19:00", reminder=30),

        # ── UPCOMING (sắp đến) ────────────────────────────────
        _t("Thêm ánh sáng và bóng đổ (Phong Shading)", "work", "high", "todo", 2,
           desc="Cài đặt ambient + diffuse + specular lighting model",
           est=120, proj=proj1.id),
        _t("Làm bài tập Java — Buổi 8", "education", "medium", "todo", 3,
           desc="Bài tập Design Pattern: Factory, Observer, Strategy",
           est=60, proj=proj2.id),
        _t("Viết báo cáo đồ án — Phần mô hình", "work", "high", "todo", 5,
           desc="Mô tả mô hình 3D, thuật toán render, camera control",
           est=150, proj=proj1.id),
        _t("Ôn Python — Machine Learning cơ bản", "education", "medium", "todo", 6,
           desc="Sklearn: KNN, Decision Tree, SVM, Naive Bayes",
           est=90, proj=proj2.id),
        _t("Thanh toán học phí học kỳ 2", "finance", "high", "todo", 7,
           desc="Thanh toán qua cổng sinh viên — deadline cuối kỳ",
           est=20, reminder=1440),
        _t("Quay video demo đồ án", "work", "medium", "todo", 10,
           desc="Quay màn hình demo cảnh 3D, có lời thuyết minh",
           est=60, proj=proj1.id),

        # ── DONE ─────────────────────────────────────────────
        _t("Lên ý tưởng cảnh văn phòng 3D", "work", "medium", "done", -10,
           desc="Thiết kế bố cục: bàn, ghế, đèn, cửa sổ",
           est=45, proj=proj1.id, done=True),
        _t("Vẽ mô hình bàn ghế cơ bản", "work", "medium", "done", -7,
           desc="Dùng GL_QUADS và GL_TRIANGLES, có texture đơn giản",
           est=90, proj=proj1.id, done=True),
        _t("Cài đặt môi trường OpenGL + GLUT", "work", "low", "done", -14,
           desc="Setup VS Code + MinGW + freeglut, test hello world",
           est=30, proj=proj1.id, done=True),
        _t("Ôn lại SQL cơ bản — JOIN, Subquery", "education", "medium", "done", -5,
           desc="Ôn lại INNER JOIN, LEFT JOIN, EXISTS, IN subquery",
           est=60, proj=proj2.id, done=True),
    ]

    from core.services import TaskService
    for t in task_list:
        try:
            TaskService.save_task(t)
        except Exception:
            logger.exception("seed task failed: %s", t.title)

    # ── WorkSessions ──────────────────────────────────────────
    done_tasks = [t for t in task_list if t.status == "done"]
    sessions_created = 0

    for i, t in enumerate(done_tasks):
        try:
            start_dt = datetime.now() - timedelta(days=i + 2, hours=3)
            end_dt   = start_dt + timedelta(minutes=t.estimated_minutes or 40)
            ws = WorkSession(
                id=str(uuid.uuid4()), user_id=user_id, task_id=t.id,
                started_at=start_dt.isoformat(), ended_at=end_dt.isoformat(),
                duration_minutes=t.estimated_minutes or 40,
                focus_quality=min(9, 8 - i % 3), notes="",
            )
            Storage.save_work_session(ws)
            sessions_created += 1
        except Exception:
            logger.exception("seed work session failed")

    # Extra focus sessions today (so Dashboard shows focus time)
    for minutes_ago, duration, quality in [(180, 50, 8), (60, 25, 7)]:
        try:
            start_dt = datetime.now() - timedelta(minutes=minutes_ago)
            end_dt   = start_dt + timedelta(minutes=duration)
            ws = WorkSession(
                id=str(uuid.uuid4()), user_id=user_id, task_id=None,
                started_at=start_dt.isoformat(), ended_at=end_dt.isoformat(),
                duration_minutes=duration, focus_quality=quality, notes="",
            )
            Storage.save_work_session(ws)
            sessions_created += 1
        except Exception:
            logger.exception("seed today session failed")

    done_count  = sum(1 for t in task_list if t.status == "done")
    overdue_cnt = sum(1 for t in task_list if t.is_overdue)
    today_cnt   = sum(1 for t in task_list
                       if t.due_date == today.isoformat() and t.status != "done")

    return (
        f"✓ Đã tạo demo data:\n"
        f"  • 2 project (Đồ họa OpenGL, Ôn thi)\n"
        f"  • {len(task_list)} task "
        f"({overdue_cnt} quá hạn, {today_cnt} hôm nay, {done_count} done)\n"
        f"  • {sessions_created} work sessions\n"
        f"  → Vào Dashboard, Calendar và Insights để xem dữ liệu!"
    )


if __name__ == "__main__":
    import os
    sys.path.insert(0, os.path.dirname(os.path.dirname(__file__)))

    if len(sys.argv) < 2:
        print("Usage: python scripts/seed_demo_data.py <username>")
        sys.exit(1)

    from core.database import Storage
    user = Storage.find_user(username=sys.argv[1])
    if not user:
        print(f"User '{sys.argv[1]}' not found.")
        sys.exit(1)

    print(f"Seeding for: {user.username}")
    print(seed_for_user(user.id))
