"""
TaskFlow - Focus Engine
Phân tích focus patterns, distraction trends, optimal break timing.
"""
from datetime import datetime, date, timedelta
from typing import List, Dict, Optional
from collections import defaultdict
import math


class FocusEngine:
    """
    Phân tích và tối ưu hóa khả năng tập trung của user.
    Dựa trên work sessions thực tế, không hardcode.
    """

    @staticmethod
    def analyze_focus_quality(work_sessions: List[dict]) -> dict:
        """
        Phân tích chất lượng focus từ work sessions.
        """
        if not work_sessions:
            return {
                "avg_focus_quality": 5.0,
                "max_focus_duration": 25,
                "focus_trend": "stable",
                "deep_work_ratio": 0.0,
                "total_focus_hours": 0,
                "sessions_count": 0,
            }

        completed = [ws for ws in work_sessions if ws.get("duration_minutes", 0) > 5]
        if not completed:
            return {"avg_focus_quality": 5.0, "max_focus_duration": 25,
                    "focus_trend": "stable", "deep_work_ratio": 0.0,
                    "total_focus_hours": 0, "sessions_count": 0}

        qualities = [ws.get("focus_quality", 5) for ws in completed]
        durations = [ws.get("duration_minutes", 0) for ws in completed]

        avg_quality = sum(qualities) / len(qualities)
        total_minutes = sum(durations)
        deep_work_sessions = sum(1 for d in durations if d >= 45)
        deep_work_ratio = deep_work_sessions / len(completed)

        # Focus trend: so sánh 5 session gần nhất với 5 trước đó
        focus_trend = "stable"
        if len(qualities) >= 10:
            recent = sum(qualities[-5:]) / 5
            older = sum(qualities[-10:-5]) / 5
            if recent > older + 0.5:
                focus_trend = "improving"
            elif recent < older - 0.5:
                focus_trend = "declining"

        # Max focus duration có quality cao (>= 7)
        good_sessions = [
            ws.get("duration_minutes", 0) for ws in completed
            if ws.get("focus_quality", 5) >= 7
        ]
        max_focus = max(good_sessions) if good_sessions else 25

        return {
            "avg_focus_quality": round(avg_quality, 1),
            "max_focus_duration": max_focus,
            "focus_trend": focus_trend,
            "deep_work_ratio": round(deep_work_ratio, 2),
            "total_focus_hours": round(total_minutes / 60, 1),
            "sessions_count": len(completed),
        }

    @staticmethod
    def get_focus_heatmap(work_sessions: List[dict]) -> Dict[int, float]:
        """
        Focus heatmap theo giờ trong ngày (0-23).
        Value = average focus quality (0-10).
        """
        hour_data = defaultdict(list)

        for ws in work_sessions:
            started = ws.get("started_at", "")
            quality = ws.get("focus_quality", 5)
            duration = ws.get("duration_minutes", 0)
            if not started or duration < 10:
                continue
            try:
                h = datetime.fromisoformat(started).hour
                hour_data[h].append(quality)
            except Exception:
                continue

        heatmap = {}
        for h in range(24):
            vals = hour_data.get(h, [])
            heatmap[h] = round(sum(vals) / len(vals), 1) if vals else 0.0
        return heatmap

    @staticmethod
    def get_weekly_focus_heatmap(work_sessions: List[dict]) -> Dict[str, float]:
        """
        Focus heatmap theo ngày trong tuần.
        Key: 'Mon', 'Tue', ...
        """
        days = ["Mon", "Tue", "Wed", "Thu", "Fri", "Sat", "Sun"]
        day_data = defaultdict(list)

        for ws in work_sessions:
            started = ws.get("started_at", "")
            quality = ws.get("focus_quality", 5)
            if not started:
                continue
            try:
                dt = datetime.fromisoformat(started)
                day_name = days[dt.weekday()]
                day_data[day_name].append(quality)
            except Exception:
                continue

        return {
            day: round(sum(day_data.get(day, [])) / max(1, len(day_data.get(day, []))), 1)
            for day in days
        }

    @staticmethod
    def detect_focus_decay(work_sessions: List[dict]) -> dict:
        """
        Phát hiện focus degradation — làm việc càng lâu focus càng giảm.
        """
        today_sessions = sorted(
            [ws for ws in work_sessions
             if ws.get("started_at", "")[:10] == date.today().isoformat()
             and ws.get("duration_minutes", 0) > 5],
            key=lambda x: x.get("started_at", "")
        )

        if len(today_sessions) < 2:
            return {"decay_detected": False, "recommendation": ""}

        qualities = [ws.get("focus_quality", 5) for ws in today_sessions]

        # Linear regression slope
        n = len(qualities)
        x_mean = (n - 1) / 2
        y_mean = sum(qualities) / n
        numerator = sum((i - x_mean) * (q - y_mean) for i, q in enumerate(qualities))
        denominator = sum((i - x_mean) ** 2 for i in range(n))

        slope = numerator / denominator if denominator != 0 else 0

        if slope < -0.5:
            return {
                "decay_detected": True,
                "rate": round(abs(slope), 2),
                "recommendation": "Focus đang giảm rõ rệt. Nên nghỉ 15-20 phút trước khi tiếp tục.",
            }
        return {"decay_detected": False, "recommendation": ""}

    @staticmethod
    def suggest_optimal_pomodoro(work_sessions: List[dict]) -> dict:
        """
        Gợi ý thời gian Pomodoro tối ưu cho user cụ thể này.
        """
        if not work_sessions:
            return {"work_minutes": 25, "break_minutes": 5, "source": "default"}

        # Tìm duration có average quality cao nhất
        duration_quality = defaultdict(list)
        for ws in work_sessions:
            d = ws.get("duration_minutes", 0)
            q = ws.get("focus_quality", 5)
            if d < 5:
                continue
            bucket = max(5, (d // 5) * 5)
            duration_quality[bucket].append(q)

        if not duration_quality:
            return {"work_minutes": 25, "break_minutes": 5, "source": "default"}

        best = max(duration_quality.items(), key=lambda x: sum(x[1]) / len(x[1]))
        optimal_work = best[0]
        optimal_break = max(5, optimal_work // 5)

        return {
            "work_minutes": optimal_work,
            "break_minutes": optimal_break,
            "source": "learned",
        }
