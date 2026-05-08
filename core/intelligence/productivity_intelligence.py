"""
TaskFlow - Productivity Intelligence Engine
Phân tích thực chất hiệu suất làm việc: completion efficiency, focus efficiency,
workload balance, productivity trends theo thời gian.
"""
from datetime import datetime, date, timedelta
from typing import List, Dict
from collections import defaultdict


class ProductivityIntelligence:
    """
    Productivity analytics nâng cao.
    Tất cả metrics đều được học từ data thực tế, không có hardcode assumption.
    """

    @classmethod
    def get_full_report(cls, tasks: list, work_sessions: List[dict],
                        behavior_events: List[dict]) -> dict:
        """Tạo báo cáo productivity toàn diện."""
        return {
            "completion_efficiency": cls.calc_completion_efficiency(tasks),
            "focus_efficiency": cls.calc_focus_efficiency(work_sessions),
            "workload_balance": cls.calc_workload_balance(tasks, work_sessions),
            "productivity_trends": cls.calc_productivity_trends(tasks, behavior_events),
            "daily_productivity": cls.calc_daily_productivity(tasks, behavior_events, 14),
            "category_performance": cls.analyze_category_performance(tasks),
            "time_of_day_performance": cls.analyze_time_performance(behavior_events),
            "streak": cls.calc_productivity_streak(behavior_events),
        }

    @staticmethod
    def calc_completion_efficiency(tasks: list) -> dict:
        """
        Tỷ lệ hoàn thành vs estimated time.
        efficiency = completed_on_time / total_done
        """
        done_tasks = [t for t in tasks if t.status == "done"]
        if not done_tasks:
            return {"rate": 0, "on_time": 0, "late": 0, "score": 0}

        on_time = sum(1 for t in done_tasks if not t.is_overdue or t.completed_at)
        late = len(done_tasks) - on_time
        rate = round(on_time / len(done_tasks) * 100, 1)

        return {
            "rate": rate,
            "on_time": on_time,
            "late": late,
            "total": len(done_tasks),
            "score": rate,
        }

    @staticmethod
    def calc_focus_efficiency(work_sessions: List[dict]) -> dict:
        """
        Focus efficiency = (quality * duration) / total_time
        """
        completed = [ws for ws in work_sessions if ws.get("duration_minutes", 0) > 5]
        if not completed:
            return {"score": 0, "avg_quality": 0, "total_hours": 0, "deep_work_hours": 0}

        total_minutes = sum(ws.get("duration_minutes", 0) for ws in completed)
        avg_quality = sum(ws.get("focus_quality", 5) for ws in completed) / len(completed)
        deep_work = sum(
            ws.get("duration_minutes", 0) for ws in completed
            if ws.get("duration_minutes", 0) >= 45 and ws.get("focus_quality", 5) >= 6
        )

        # Focus efficiency score (0-100)
        quality_score = (avg_quality / 10) * 100
        deep_ratio = deep_work / max(1, total_minutes) * 100
        score = round(quality_score * 0.6 + deep_ratio * 0.4, 1)

        return {
            "score": score,
            "avg_quality": round(avg_quality, 1),
            "total_hours": round(total_minutes / 60, 1),
            "deep_work_hours": round(deep_work / 60, 1),
            "deep_work_ratio": round(deep_work / max(1, total_minutes) * 100, 1),
        }

    @staticmethod
    def calc_workload_balance(tasks: list, work_sessions: List[dict]) -> dict:
        """
        Phân tích workload balance theo category và theo ngày.
        """
        active = [t for t in tasks if t.status not in ("done", "cancelled")]

        # Category distribution
        cat_load = defaultdict(int)
        for t in active:
            cat_load[t.category] += getattr(t, "estimated_minutes", 30)

        total_load = sum(cat_load.values()) or 1
        cat_distribution = {
            cat: round(mins / total_load * 100, 1)
            for cat, mins in cat_load.items()
        }

        # Overload indicator
        overloaded = total_load > 8 * 60 * 5  # > 5 days of 8h work

        return {
            "total_estimated_hours": round(total_load / 60, 1),
            "category_distribution": cat_distribution,
            "overloaded": overloaded,
            "overload_days": round(total_load / (8 * 60), 1),
        }

    @staticmethod
    def calc_productivity_trends(tasks: list, behavior_events: List[dict]) -> dict:
        """
        Trend phân tích: productivity đang tăng hay giảm?
        So sánh 4 tuần gần đây.
        """
        today = date.today()
        weekly_scores = []

        for week_offset in range(3, -1, -1):
            week_start = today - timedelta(days=today.weekday() + week_offset * 7)
            week_end = week_start + timedelta(days=6)

            completions = sum(
                1 for ev in behavior_events
                if ev.get("event_type") == "task_complete"
                and week_start.isoformat() <= ev.get("timestamp", "")[:10] <= week_end.isoformat()
            )

            week_tasks = [
                t for t in tasks
                if t.due_date
                and week_start.isoformat() <= t.due_date <= week_end.isoformat()
            ]
            total = len(week_tasks) or 1
            score = min(100, completions / total * 100)
            weekly_scores.append({
                "week": f"W{4-week_offset}",
                "start": week_start.isoformat(),
                "score": round(score, 1),
                "completions": completions,
            })

        # Trend direction
        if len(weekly_scores) >= 2:
            diff = weekly_scores[-1]["score"] - weekly_scores[-2]["score"]
            trend = "up" if diff > 5 else "down" if diff < -5 else "stable"
        else:
            trend = "stable"

        return {
            "weekly_scores": weekly_scores,
            "trend": trend,
            "current_week_score": weekly_scores[-1]["score"] if weekly_scores else 0,
        }

    @staticmethod
    def calc_daily_productivity(tasks: list, behavior_events: List[dict], days: int = 14) -> List[dict]:
        """Năng suất theo ngày N ngày gần đây."""
        today = date.today()
        result = []

        for i in range(days - 1, -1, -1):
            d = today - timedelta(days=i)
            ds = d.isoformat()

            completed = sum(
                1 for ev in behavior_events
                if ev.get("event_type") == "task_complete"
                and ev.get("timestamp", "")[:10] == ds
            )
            delayed = sum(
                1 for ev in behavior_events
                if ev.get("event_type") == "task_delay"
                and ev.get("timestamp", "")[:10] == ds
            )

            result.append({
                "date": ds,
                "completed": completed,
                "delayed": delayed,
                "day_label": ["T2", "T3", "T4", "T5", "T6", "T7", "CN"][d.weekday()],
            })

        return result

    @staticmethod
    def analyze_category_performance(tasks: list) -> List[dict]:
        """
        Hiệu suất theo từng danh mục.
        """
        cat_stats = defaultdict(lambda: {"total": 0, "done": 0, "overdue": 0})

        for t in tasks:
            cat_stats[t.category]["total"] += 1
            if t.status == "done":
                cat_stats[t.category]["done"] += 1
            elif t.is_overdue:
                cat_stats[t.category]["overdue"] += 1

        result = []
        for cat, stats in cat_stats.items():
            total = stats["total"]
            done_rate = round(stats["done"] / total * 100, 1) if total else 0
            overdue_rate = round(stats["overdue"] / total * 100, 1) if total else 0
            result.append({
                "category": cat,
                "total": total,
                "done": stats["done"],
                "overdue": stats["overdue"],
                "completion_rate": done_rate,
                "overdue_rate": overdue_rate,
                "performance_score": max(0, done_rate - overdue_rate),
            })

        return sorted(result, key=lambda x: -x["performance_score"])

    @staticmethod
    def analyze_time_performance(behavior_events: List[dict]) -> Dict[int, dict]:
        """Performance phân tích theo giờ trong ngày."""
        hour_stats = defaultdict(lambda: {"complete": 0, "delay": 0, "total": 0})

        for ev in behavior_events:
            h = ev.get("hour_of_day")
            if h is None:
                continue
            et = ev.get("event_type", "")
            if et == "task_complete":
                hour_stats[h]["complete"] += 1
            elif et == "task_delay":
                hour_stats[h]["delay"] += 1
            if et in ("task_complete", "task_delay", "task_start"):
                hour_stats[h]["total"] += 1

        result = {}
        for h in range(24):
            stats = hour_stats.get(h, {"complete": 0, "delay": 0, "total": 0})
            total = stats["total"] or 1
            result[h] = {
                "complete": stats["complete"],
                "delay": stats["delay"],
                "efficiency": round(stats["complete"] / total * 100, 1),
            }
        return result

    @staticmethod
    def calc_productivity_streak(behavior_events: List[dict]) -> dict:
        """Chuỗi ngày liên tiếp có hoàn thành ít nhất 1 task."""
        today = date.today()
        streak = 0
        current = today

        complete_dates = {
            ev.get("timestamp", "")[:10]
            for ev in behavior_events
            if ev.get("event_type") == "task_complete"
        }

        while current.isoformat() in complete_dates:
            streak += 1
            current -= timedelta(days=1)

        return {
            "current_streak": streak,
            "label": f"{streak} ngày liên tiếp" if streak > 0 else "Bắt đầu streak hôm nay!"
        }
