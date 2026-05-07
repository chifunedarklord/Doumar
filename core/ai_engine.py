"""
TaskFlow - AI Engine
Priority Engine, Behavior Analyzer, Burnout Detector, Smart Scheduler, Recommendation Engine
"""
from datetime import datetime, date, timedelta
from typing import List, Dict, Optional
from collections import defaultdict


# ─── Priority Engine ──────────────────────────────────────────────────────────

class PriorityEngine:
    """Tính dynamic priority score (0-100) cho task dựa trên nhiều yếu tố."""

    @staticmethod
    def calculate_score(task, user_context: dict = None) -> float:
        ctx = user_context or {}
        score = 0.0

        # 1. Deadline urgency (30%)
        if task.due_date:
            days = task.days_until_due
            if days is None:
                deadline_score = 0
            elif days < 0:
                deadline_score = 100  # Overdue
            elif days == 0:
                deadline_score = 95
            elif days == 1:
                deadline_score = 85
            elif days <= 3:
                deadline_score = 70
            elif days <= 7:
                deadline_score = 50
            elif days <= 14:
                deadline_score = 30
            else:
                deadline_score = max(0, 30 - days)
        else:
            deadline_score = 10
        score += deadline_score * 0.30

        # 2. Impact score (25%)
        score += (getattr(task, "impact_score", 5.0) / 10.0) * 100 * 0.25

        # 3. Priority level (20%)
        pri_map = {"high": 100, "medium": 60, "low": 30}
        score += pri_map.get(task.priority, 60) * 0.20

        # 4. Risk level (15%)
        risk_map = {"high": 100, "medium": 60, "low": 20}
        score += risk_map.get(getattr(task, "risk_level", "low"), 20) * 0.15

        # 5. Current energy fit (10%)
        current_hour = ctx.get("current_hour", datetime.now().hour)
        peak_hours = ctx.get("peak_hours", [9, 10, 11])
        energy_req = getattr(task, "energy_required", "medium")
        if current_hour in peak_hours and energy_req == "high":
            energy_fit = 100
        elif current_hour not in peak_hours and energy_req == "low":
            energy_fit = 80
        else:
            energy_fit = 50
        score += energy_fit * 0.10

        return min(100.0, max(0.0, round(score, 1)))

    @classmethod
    def rank_tasks(cls, tasks: list, user_context: dict = None) -> list:
        scored = []
        for t in tasks:
            if t.status not in ("done", "cancelled"):
                s = cls.calculate_score(t, user_context)
                scored.append((s, t))
        scored.sort(key=lambda x: -x[0])
        return [t for _, t in scored]


# ─── Behavior Analyzer ────────────────────────────────────────────────────────

class BehaviorAnalyzer:
    """Phân tích pattern hành vi user từ dữ liệu lịch sử."""

    @staticmethod
    def get_peak_hours(behavior_events: list) -> List[int]:
        """Tìm giờ user hoàn thành task nhiều nhất."""
        hour_counts = defaultdict(int)
        for ev in behavior_events:
            if ev.get("event_type") == "task_complete":
                h = ev.get("hour_of_day")
                if h is not None:
                    hour_counts[h] += 1
        if not hour_counts:
            return [9, 10, 11]  # Default morning peak
        sorted_hours = sorted(hour_counts.items(), key=lambda x: -x[1])
        return [h for h, _ in sorted_hours[:3]]

    @staticmethod
    def get_productivity_by_hour(behavior_events: list) -> Dict[int, float]:
        """Tỷ lệ hoàn thành task theo từng giờ trong ngày."""
        hour_complete = defaultdict(int)
        hour_total = defaultdict(int)
        for ev in behavior_events:
            h = ev.get("hour_of_day")
            if h is None:
                continue
            if ev.get("event_type") == "task_complete":
                hour_complete[h] += 1
            if ev.get("event_type") in ("task_complete", "task_start", "task_delay"):
                hour_total[h] += 1
        result = {}
        for h in range(24):
            total = hour_total.get(h, 0)
            result[h] = hour_complete[h] / total if total > 0 else 0.0
        return result

    @staticmethod
    def get_delay_patterns(behavior_events: list) -> Dict[str, int]:
        """Loại task hay bị delay."""
        category_delays = defaultdict(int)
        for ev in behavior_events:
            if ev.get("event_type") == "task_delay":
                cat = ev.get("event_data", {}).get("category", "unknown")
                category_delays[cat] += 1
        return dict(category_delays)

    @staticmethod
    def calc_daily_productivity(tasks: list, days: int = 7) -> List[Dict]:
        """Năng suất theo ngày trong N ngày gần đây."""
        result = []
        today = date.today()
        for i in range(days - 1, -1, -1):
            d = today - timedelta(days=i)
            day_done = sum(
                1 for t in tasks
                if t.status == "done" and t.completed_at
                and t.completed_at[:10] == d.isoformat()
            )
            result.append({"date": d.isoformat(), "completed": day_done})
        return result

    @staticmethod
    def calc_weekly_score(tasks: list, behavior_events: list) -> float:
        """Productivity score tuần này (0-100)."""
        today = date.today()
        week_start = today - timedelta(days=today.weekday())
        week_tasks = [
            t for t in tasks
            if t.due_date and date.fromisoformat(t.due_date) >= week_start
            and date.fromisoformat(t.due_date) <= today
        ]
        if not week_tasks:
            return 75.0
        done_this_week = sum(1 for t in week_tasks if t.status == "done")
        overdue_this_week = sum(1 for t in week_tasks if t.is_overdue)
        completion_rate = done_this_week / len(week_tasks)
        overdue_penalty = overdue_this_week / len(week_tasks) * 0.3
        return round(min(100.0, max(0.0, (completion_rate - overdue_penalty) * 100)), 1)


# ─── Burnout Detector ─────────────────────────────────────────────────────────

class BurnoutDetector:
    """Phát hiện nguy cơ kiệt sức dựa trên patterns làm việc."""

    @staticmethod
    def get_risk(tasks: list, work_sessions: list, behavior_events: list) -> dict:
        risk_score = 0
        reasons = []
        suggestions = []

        # 1. Overdue rate
        active = [t for t in tasks if t.status not in ("done", "cancelled")]
        if active:
            overdue_rate = sum(1 for t in active if t.is_overdue) / len(active)
            if overdue_rate > 0.5:
                risk_score += 30
                reasons.append(f"{int(overdue_rate*100)}% công việc đang quá hạn")
                suggestions.append("Xem xét lại deadline hoặc giảm số lượng task")
            elif overdue_rate > 0.3:
                risk_score += 15
                reasons.append("Nhiều công việc sắp quá hạn")

        # 2. High-priority overload
        high_count = sum(1 for t in active if t.priority == "high")
        if high_count > 5:
            risk_score += 20
            reasons.append(f"Có {high_count} task ưu tiên cao cùng lúc")
            suggestions.append("Chuyển một số task sang ưu tiên trung bình")

        # 3. Long continuous work sessions
        today_sessions = [
            ws for ws in work_sessions
            if ws.get("started_at", "")[:10] == date.today().isoformat()
            and ws.get("duration_minutes", 0) > 0
        ]
        total_today = sum(ws.get("duration_minutes", 0) for ws in today_sessions)
        if total_today > 480:  # > 8 hours
            risk_score += 25
            reasons.append(f"Đã làm việc {total_today//60}h{total_today%60}p hôm nay")
            suggestions.append("Hãy nghỉ ngơi và bổ sung năng lượng")
        elif total_today > 360:
            risk_score += 10
            reasons.append("Thời gian làm việc hôm nay khá dài")

        # 4. Consecutive task delays
        recent_delays = sum(
            1 for ev in behavior_events[-20:]
            if ev.get("event_type") == "task_delay"
        )
        if recent_delays >= 5:
            risk_score += 25
            reasons.append("Liên tục trì hoãn nhiều công việc gần đây")
            suggestions.append("Chia nhỏ task và bắt đầu từ bước nhỏ nhất")

        # Determine level
        if risk_score >= 60:
            level = "critical"
            label = "Nguy hiểm"
            color = "#EF4444"
        elif risk_score >= 35:
            level = "high"
            label = "Cao"
            color = "#F59E0B"
        elif risk_score >= 15:
            level = "medium"
            label = "Trung bình"
            color = "#3B82F6"
        else:
            level = "low"
            label = "Thấp"
            color = "#10B981"

        if not suggestions:
            suggestions.append("Tiếp tục duy trì nhịp làm việc tốt!")

        return {
            "score": min(100, risk_score),
            "level": level,
            "label": label,
            "color": color,
            "reasons": reasons,
            "suggestions": suggestions,
        }


# ─── Smart Scheduler ──────────────────────────────────────────────────────────

class SmartScheduler:
    """Đề xuất lịch làm việc thông minh."""

    @staticmethod
    def suggest_today(tasks: list, peak_hours: List[int],
                      user_context: dict = None) -> List[dict]:
        """Trả về danh sách task được sắp xếp cho hôm nay."""
        ctx = user_context or {}
        active = [t for t in tasks if t.status not in ("done", "cancelled")]

        # Score và rank
        ranked = PriorityEngine.rank_tasks(active, {"peak_hours": peak_hours, **ctx})

        slots = []
        current_hour = datetime.now().hour
        slot_hour = max(current_hour, peak_hours[0] if peak_hours else 9)

        # Tránh xếp liên tiếp task khó
        prev_difficulty = "low"
        for task in ranked[:6]:
            difficulty = getattr(task, "energy_required", "medium")
            # Nếu task khó liên tiếp, chèn task nhẹ
            if prev_difficulty == "high" and difficulty == "high":
                difficulty = "medium"

            est = getattr(task, "estimated_minutes", 30)
            slots.append({
                "task": task,
                "suggested_hour": slot_hour,
                "duration_minutes": est,
                "block_type": "deep_work" if difficulty == "high" else "regular",
            })
            slot_hour = min(slot_hour + max(1, est // 60 + 1), 21)
            prev_difficulty = difficulty

        return slots

    @staticmethod
    def suggest_focus_blocks(tasks: list, peak_hours: List[int]) -> List[dict]:
        """Tạo focus blocks Pomodoro."""
        blocks = []
        for h in peak_hours:
            blocks.append({
                "start_hour": h,
                "duration": 25,
                "type": "focus",
                "label": f"Focus Block {h:02d}:00–{h:02d}:25"
            })
            blocks.append({
                "start_hour": h,
                "duration": 5,
                "type": "break",
                "label": "Nghỉ ngắn"
            })
        return blocks


# ─── Recommendation Engine ────────────────────────────────────────────────────

class RecommendationEngine:
    """Tạo gợi ý thực tế cho user."""

    @staticmethod
    def get_suggestions(tasks: list, behavior_events: list,
                        burnout: dict, peak_hours: List[int]) -> List[dict]:
        suggestions = []
        active = [t for t in tasks if t.status not in ("done", "cancelled")]

        # 1. Burnout warning
        if burnout["level"] in ("high", "critical"):
            suggestions.append({
                "type": "rest",
                "icon": "😴",
                "title": "Nguy cơ kiệt sức",
                "message": burnout["suggestions"][0] if burnout["suggestions"] else "Hãy nghỉ ngơi",
                "priority": "high",
            })

        # 2. Large tasks — suggest splitting
        large = [t for t in active if getattr(t, "estimated_minutes", 30) > 120]
        if large:
            suggestions.append({
                "type": "split_task",
                "icon": "✂️",
                "title": f"Chia nhỏ task \"{large[0].title[:20]}...\"",
                "message": f"Task này ước tính {large[0].estimated_minutes} phút — nên chia thành subtasks",
                "priority": "medium",
            })

        # 3. Overdue tasks
        overdue = [t for t in active if t.is_overdue]
        if overdue:
            suggestions.append({
                "type": "reschedule",
                "icon": "📅",
                "title": f"{len(overdue)} task đang quá hạn",
                "message": "Xem xét lại deadline hoặc đánh dấu không cần thiết",
                "priority": "high",
            })

        # 4. Peak hour reminder
        current_hour = datetime.now().hour
        if peak_hours and current_hour in peak_hours:
            high_tasks = [t for t in active if t.priority == "high"]
            if high_tasks:
                suggestions.append({
                    "type": "focus_priority",
                    "icon": "⚡",
                    "title": "Giờ vàng làm việc!",
                    "message": f"Đây là peak hour của bạn — hãy làm \"{high_tasks[0].title[:25]}\"",
                    "priority": "medium",
                })

        # 5. No tasks today
        today_str = date.today().isoformat()
        today_tasks = [t for t in active if t.due_date == today_str]
        if not today_tasks and active:
            suggestions.append({
                "type": "plan_day",
                "icon": "🗓️",
                "title": "Chưa có kế hoạch hôm nay",
                "message": "Hãy chọn 1-3 task để tập trung hoàn thành hôm nay",
                "priority": "low",
            })

        return suggestions[:5]
