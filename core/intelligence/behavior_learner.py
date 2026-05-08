"""
TaskFlow - BehaviorLearner
Học hành vi người dùng từ dữ liệu thực: work sessions, events, task history.
Không hardcode — hoàn toàn data-driven.
"""
from datetime import datetime, date, timedelta
from collections import defaultdict
from typing import List, Dict, Optional, Tuple
import math


class BehaviorLearner:
    """
    Adaptive learning engine. Phân tích lịch sử để học thói quen thực tế.
    Thay thế hoàn toàn các giả định cố định (hardcoded peak hours, etc.)
    """

    # ── Peak Hour Learning ────────────────────────────────────────────────────

    @staticmethod
    def learn_peak_hours(behavior_events: List[dict], work_sessions: List[dict]) -> List[int]:
        """
        Học giờ làm việc hiệu quả nhất từ dữ liệu thực tế.
        Kết hợp: task completion events + work session quality.
        """
        hour_weights = defaultdict(float)

        # 1. Từ task_complete events — weight by recency
        now = datetime.now()
        for ev in behavior_events:
            if ev.get("event_type") != "task_complete":
                continue
            h = ev.get("hour_of_day")
            if h is None:
                continue
            # Recency decay: events gần đây có trọng số cao hơn
            try:
                ts = datetime.fromisoformat(ev.get("timestamp", now.isoformat()))
                days_ago = max(0, (now - ts).days)
                recency_weight = math.exp(-days_ago / 30)  # decay over 30 days
            except Exception:
                recency_weight = 0.5
            hour_weights[h] += 2.0 * recency_weight

        # 2. Từ work sessions — weight by focus_quality
        for ws in work_sessions:
            started = ws.get("started_at", "")
            quality = ws.get("focus_quality", 5)
            duration = ws.get("duration_minutes", 0)
            if not started or duration < 10:
                continue
            try:
                dt = datetime.fromisoformat(started)
                h = dt.hour
                days_ago = max(0, (now - dt).days)
                recency_weight = math.exp(-days_ago / 30)
                # Normalize quality 1-10 to 0.5-1.5
                quality_weight = 0.5 + (quality / 10.0)
                hour_weights[h] += quality_weight * recency_weight
            except Exception:
                continue

        if not hour_weights:
            return [9, 10, 14, 15]  # default fallback chỉ khi hoàn toàn không có data

        # Lấy top 4 giờ
        sorted_hours = sorted(hour_weights.items(), key=lambda x: -x[1])
        return sorted([h for h, _ in sorted_hours[:4]])

    # ── Productivity Score by Hour ────────────────────────────────────────────

    @staticmethod
    def learn_hourly_productivity(behavior_events: List[dict]) -> Dict[int, float]:
        """Tỷ lệ hoàn thành task theo từng giờ. Normalized 0-1."""
        hour_complete = defaultdict(int)
        hour_total = defaultdict(int)

        for ev in behavior_events:
            h = ev.get("hour_of_day")
            if h is None:
                continue
            et = ev.get("event_type", "")
            if et == "task_complete":
                hour_complete[h] += 1
            if et in ("task_complete", "task_start", "task_delay", "task_skip"):
                hour_total[h] += 1

        result = {}
        for h in range(24):
            total = hour_total.get(h, 0)
            result[h] = round(hour_complete.get(h, 0) / total, 3) if total > 0 else 0.0
        return result

    # ── Delay Pattern Learning ────────────────────────────────────────────────

    @staticmethod
    def learn_delay_patterns(behavior_events: List[dict]) -> Dict[str, dict]:
        """
        Học category/priority nào hay bị delay nhất.
        Returns: {category: {count, avg_delay_days, risk_score}}
        """
        patterns = defaultdict(lambda: {"count": 0, "delay_score": 0.0})

        for ev in behavior_events:
            if ev.get("event_type") not in ("task_delay", "overdue_ack"):
                continue
            data = ev.get("event_data", {})
            cat = data.get("category", "unknown")
            patterns[cat]["count"] += 1
            patterns[cat]["delay_score"] += 1.0

        # Normalize thành risk_score 0-1
        max_count = max((v["count"] for v in patterns.values()), default=1)
        result = {}
        for cat, info in patterns.items():
            result[cat] = {
                "count": info["count"],
                "risk_score": round(info["count"] / max_count, 2)
            }
        return result

    # ── Focus Duration Learning ───────────────────────────────────────────────

    @staticmethod
    def learn_optimal_focus_duration(work_sessions: List[dict]) -> int:
        """
        Học thời gian focus tối ưu của user từ work sessions.
        Tìm duration mà focus_quality cao nhất.
        """
        if not work_sessions:
            return 25  # default Pomodoro

        buckets = defaultdict(list)  # {duration_bucket: [quality]}
        for ws in work_sessions:
            duration = ws.get("duration_minutes", 0)
            quality = ws.get("focus_quality", 5)
            if duration < 5:
                continue
            # Bucket by 5-minute intervals
            bucket = (duration // 5) * 5
            buckets[bucket].append(quality)

        if not buckets:
            return 25

        best_bucket = max(buckets.items(), key=lambda x: sum(x[1]) / len(x[1]))
        return best_bucket[0]

    # ── Weekly Productivity Score ─────────────────────────────────────────────

    @staticmethod
    def calc_weekly_productivity_score(tasks: list, behavior_events: List[dict]) -> float:
        """
        Score tuần này dựa trên actual completion rate + delay ratio.
        """
        today = date.today()
        week_start = today - timedelta(days=today.weekday())
        week_end = today

        week_tasks = [
            t for t in tasks
            if t.due_date
            and week_start <= date.fromisoformat(t.due_date) <= week_end
        ]

        if not week_tasks:
            # Nếu không có task trong tuần, dùng recent completions
            recent_complete = sum(
                1 for ev in behavior_events
                if ev.get("event_type") == "task_complete"
                and ev.get("timestamp", "")[:10] >= week_start.isoformat()
            )
            return min(100.0, recent_complete * 15.0)

        done = sum(1 for t in week_tasks if t.status == "done")
        overdue = sum(1 for t in week_tasks if t.is_overdue)

        completion_rate = done / len(week_tasks)
        overdue_penalty = overdue / len(week_tasks) * 0.4

        # Bonus for behavior events (task starts, focus sessions)
        activity_bonus = min(0.15, sum(
            1 for ev in behavior_events
            if ev.get("event_type") in ("session_start", "task_start")
            and ev.get("timestamp", "")[:10] >= week_start.isoformat()
        ) * 0.01)

        score = max(0.0, min(1.0, completion_rate - overdue_penalty + activity_bonus))
        return round(score * 100, 1)

    # ── Energy Level Detection ────────────────────────────────────────────────

    @staticmethod
    def estimate_current_energy(behavior_events: List[dict], work_sessions: List[dict]) -> int:
        """
        Ước tính mức năng lượng hiện tại (1-10) dựa trên:
        - Số giờ đã làm hôm nay
        - Số task hoàn thành hôm nay
        - Thời gian nghỉ
        """
        today_str = date.today().isoformat()
        today_sessions = [
            ws for ws in work_sessions
            if ws.get("started_at", "")[:10] == today_str
        ]
        total_worked = sum(ws.get("duration_minutes", 0) for ws in today_sessions)

        # Base energy = 10, trừ dần theo giờ làm việc
        energy = 10 - min(6, total_worked // 60)  # -1 mỗi giờ, tối đa -6

        # Bonus nếu còn ít việc hôm nay
        today_completions = sum(
            1 for ev in behavior_events[-50:]
            if ev.get("event_type") == "task_complete"
            and ev.get("timestamp", "")[:10] == today_str
        )
        energy = min(10, energy + min(2, today_completions // 2))

        return max(1, int(energy))

    # ── Stress Level Detection ────────────────────────────────────────────────

    @staticmethod
    def estimate_stress_level(tasks: list, behavior_events: List[dict]) -> int:
        """
        Ước tính mức stress hiện tại (1-10) dựa trên:
        - Số overdue tasks
        - Số task high priority
        - Delay frequency gần đây
        """
        active = [t for t in tasks if t.status not in ("done", "cancelled")]
        overdue_count = sum(1 for t in active if t.is_overdue)
        high_count = sum(1 for t in active if t.priority == "high")

        recent_delays = sum(
            1 for ev in behavior_events[-20:]
            if ev.get("event_type") in ("task_delay", "overdue_ack")
        )

        stress = 2  # baseline
        stress += min(4, overdue_count)          # +1 per overdue, max +4
        stress += min(2, high_count // 2)         # +1 per 2 high priority
        stress += min(2, recent_delays)           # +1 per recent delay

        return max(1, min(10, int(stress)))

    # ── Work Style Detection ──────────────────────────────────────────────────

    @staticmethod
    def detect_work_style(work_sessions: List[dict]) -> str:
        """
        Phát hiện work style từ session patterns.
        Returns: 'deep_worker' | 'sprint_worker' | 'balanced' | 'scattered'
        """
        if not work_sessions:
            return "balanced"

        durations = [ws.get("duration_minutes", 0) for ws in work_sessions if ws.get("duration_minutes", 0) > 5]
        if not durations:
            return "balanced"

        avg_duration = sum(durations) / len(durations)
        long_sessions = sum(1 for d in durations if d > 60)
        short_sessions = sum(1 for d in durations if d < 20)

        if avg_duration > 60 and long_sessions > len(durations) * 0.5:
            return "deep_worker"
        elif avg_duration < 25 and short_sessions > len(durations) * 0.5:
            return "sprint_worker"
        elif short_sessions > len(durations) * 0.4 and long_sessions > len(durations) * 0.3:
            return "scattered"
        return "balanced"
