"""
TaskFlow - Behavioral Analytics
Phân tích deadline compliance, estimation accuracy, procrastination patterns, workload.
"""
from datetime import datetime, date, timedelta
from collections import defaultdict
from typing import List, Dict


class DeadlineAnalytics:
    """Tỷ lệ hoàn thành đúng hạn theo danh mục."""

    @staticmethod
    def calculate_compliance(tasks: list) -> dict:
        """
        So sánh completed_at với due_date để đánh giá on-time rate.
        Returns: {on_time, late, compliance_rate, by_category}
        """
        completed = [t for t in tasks if t.status == "done" and t.due_date]
        if not completed:
            return {"on_time": 0, "late": 0, "compliance_rate": 0.0, "by_category": {}, "samples": 0}

        on_time = 0
        late = 0
        by_cat: Dict[str, dict] = defaultdict(lambda: {"on_time": 0, "late": 0})

        for t in completed:
            try:
                finished = (t.completed_at or t.updated_at or "")[:10]
                if finished and finished <= t.due_date:
                    on_time += 1
                    by_cat[t.category]["on_time"] += 1
                else:
                    late += 1
                    by_cat[t.category]["late"] += 1
            except Exception:
                continue

        total = on_time + late
        rate = round(on_time / total * 100, 1) if total else 0.0

        cat_compliance = {}
        for cat, counts in by_cat.items():
            t_count = counts["on_time"] + counts["late"]
            cat_compliance[cat] = {
                "on_time": counts["on_time"],
                "late": counts["late"],
                "rate": round(counts["on_time"] / t_count * 100, 1) if t_count else 0.0,
            }

        return {
            "on_time": on_time,
            "late": late,
            "compliance_rate": rate,
            "by_category": cat_compliance,
            "samples": total,
        }


class EstimationAnalytics:
    """Độ chính xác ước tính thời gian."""

    @staticmethod
    def analyze_accuracy(tasks: list, work_sessions: List[dict]) -> dict:
        """
        Tính error% giữa estimated_minutes và actual thời gian từ work_sessions.
        error > 0 → bạn underestimate (thực tế lâu hơn ước tính)
        Returns: {avg_error_pct, tendency, samples, by_category}
        """
        task_actual: Dict[str, int] = defaultdict(int)
        for ws in work_sessions:
            tid = ws.get("task_id")
            if tid:
                task_actual[tid] += ws.get("duration_minutes", 0)

        errors = []
        by_cat: Dict[str, list] = defaultdict(list)

        for t in tasks:
            if t.status != "done":
                continue
            est = getattr(t, "estimated_minutes", 0) or 0
            actual = task_actual.get(t.id, getattr(t, "actual_minutes", 0) or 0)
            if est <= 0 or actual <= 0:
                continue
            error_pct = (actual - est) / est * 100
            errors.append(error_pct)
            by_cat[t.category].append(error_pct)

        if not errors:
            return {"avg_error_pct": 0.0, "tendency": "accurate", "samples": 0, "by_category": {}}

        avg_error = sum(errors) / len(errors)

        def _tendency(e: float) -> str:
            return "underestimate" if e > 20 else "overestimate" if e < -20 else "accurate"

        cat_stats = {}
        for cat, errs in by_cat.items():
            avg = sum(errs) / len(errs)
            cat_stats[cat] = {
                "avg_error_pct": round(avg, 1),
                "tendency": _tendency(avg),
                "samples": len(errs),
            }

        return {
            "avg_error_pct": round(avg_error, 1),
            "tendency": _tendency(avg_error),
            "samples": len(errors),
            "by_category": cat_stats,
        }


class ProcrastinationDetector:
    """Phát hiện hành vi trì hoãn và category nguy cơ cao."""

    @staticmethod
    def detect(tasks: list, behavior_events: List[dict]) -> dict:
        """
        Returns: {procrastination_score, high_risk_categories, worst_time_of_day,
                  total_delays, postponed_tasks}
        """
        active = [t for t in tasks if t.status not in ("done", "cancelled")]
        high_postpone = [t for t in active if getattr(t, "postpone_count", 0) >= 2]

        delay_events = [
            e for e in behavior_events
            if e.get("event_type") in ("task_delay", "overdue_ack")
        ]

        cat_delays: Dict[str, int] = defaultdict(int)
        hour_delays: Dict[int, int] = defaultdict(int)

        for ev in delay_events:
            cat = ev.get("event_data", {}).get("category", "unknown")
            cat_delays[cat] += 1
            h = ev.get("hour_of_day") or 12
            hour_delays[int(h)] += 1

        high_risk_categories = [
            {"category": c, "delay_count": cnt}
            for c, cnt in sorted(cat_delays.items(), key=lambda x: -x[1])[:3]
        ]

        worst_time = None
        if hour_delays:
            worst_h = max(hour_delays.items(), key=lambda x: x[1])[0]
            worst_time = "sáng" if worst_h < 12 else "chiều" if worst_h < 18 else "tối"

        score = min(100, len(high_postpone) * 8 + len(delay_events) * 3)

        return {
            "procrastination_score": score,
            "high_risk_categories": high_risk_categories,
            "worst_time_of_day": worst_time,
            "total_delays": len(delay_events),
            "postponed_tasks": len(high_postpone),
        }


class WorkloadAnalyzer:
    """Phân tích overcommit và tải công việc theo ngày."""

    DAILY_CAPACITY = 5  # Số task khuyến nghị tối đa / ngày

    @classmethod
    def analyze(cls, tasks: list) -> dict:
        """
        Returns: {overcommit_score, weekly_load, overcommitted_days, total_active}
        """
        active = [t for t in tasks if t.status not in ("done", "cancelled") and t.due_date]

        by_date: Dict[str, list] = defaultdict(list)
        for t in active:
            by_date[t.due_date].append(t)

        overcommitted = [
            {"date": d, "task_count": len(ts), "excess": len(ts) - cls.DAILY_CAPACITY}
            for d, ts in sorted(by_date.items())
            if len(ts) > cls.DAILY_CAPACITY
        ][:3]

        today_str = date.today().isoformat()
        week_end_str = (date.today() + timedelta(days=7)).isoformat()
        weekly_load = sum(
            1 for t in active
            if today_str <= t.due_date <= week_end_str
        )

        overcommit_score = min(100, max(0, (weekly_load - 15) * 6))

        return {
            "overcommit_score": overcommit_score,
            "weekly_load": weekly_load,
            "overcommitted_days": overcommitted,
            "total_active": len(active),
        }


class BehavioralAnalytics:
    """Facade — tổng hợp tất cả phân tích hành vi."""

    @classmethod
    def run_all(cls, tasks: list, behavior_events: List[dict], work_sessions: List[dict]) -> dict:
        return {
            "deadline_compliance": DeadlineAnalytics.calculate_compliance(tasks),
            "estimation_accuracy": EstimationAnalytics.analyze_accuracy(tasks, work_sessions),
            "procrastination": ProcrastinationDetector.detect(tasks, behavior_events),
            "workload": WorkloadAnalyzer.analyze(tasks),
        }
