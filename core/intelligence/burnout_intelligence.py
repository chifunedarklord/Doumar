"""
TaskFlow - Burnout Intelligence
Phân tích đa chiều để dự đoán burnout risk với độ chính xác cao hơn.
"""
from datetime import datetime, date, timedelta
from typing import List, Dict
from collections import defaultdict


class BurnoutIntelligence:
    """
    Burnout detection nâng cao:
    - Productivity drop trends
    - Focus degradation
    - Interruption frequency  
    - Delay accumulation
    - Overtime patterns
    - Deep work exhaustion
    """

    @classmethod
    def get_risk(cls, tasks: list, work_sessions: List[dict],
                  behavior_events: List[dict]) -> dict:
        """
        Trả về burnout risk report đầy đủ.
        """
        risk_score = 0
        risk_factors = []
        suggestions = []
        details = {}

        # 1. Overdue accumulation (0-30 points)
        overdue_factor = cls._analyze_overdue(tasks)
        risk_score += overdue_factor["score"]
        if overdue_factor["reason"]:
            risk_factors.append(overdue_factor["reason"])
        details["overdue"] = overdue_factor

        # 2. High priority overload (0-20 points)
        overload_factor = cls._analyze_high_priority_overload(tasks)
        risk_score += overload_factor["score"]
        if overload_factor["reason"]:
            risk_factors.append(overload_factor["reason"])
        details["overload"] = overload_factor

        # 3. Overtime / excessive work (0-25 points)
        overtime_factor = cls._analyze_overtime(work_sessions)
        risk_score += overtime_factor["score"]
        if overtime_factor["reason"]:
            risk_factors.append(overtime_factor["reason"])
            suggestions.append(overtime_factor.get("suggestion", ""))
        details["overtime"] = overtime_factor

        # 4. Delay frequency trend (0-25 points)
        delay_factor = cls._analyze_delay_trend(behavior_events)
        risk_score += delay_factor["score"]
        if delay_factor["reason"]:
            risk_factors.append(delay_factor["reason"])
            suggestions.append(delay_factor.get("suggestion", ""))
        details["delay_trend"] = delay_factor

        # 5. Focus quality degradation (0-20 points)
        focus_factor = cls._analyze_focus_degradation(work_sessions)
        risk_score += focus_factor["score"]
        if focus_factor["reason"]:
            risk_factors.append(focus_factor["reason"])
        details["focus"] = focus_factor

        # 6. Productivity drop (0-20 points)
        prod_factor = cls._analyze_productivity_drop(tasks, behavior_events)
        risk_score += prod_factor["score"]
        if prod_factor["reason"]:
            risk_factors.append(prod_factor["reason"])
        details["productivity"] = prod_factor

        risk_score = min(100, risk_score)

        # Determine level and default suggestions
        if risk_score >= 70:
            level, label, color = "critical", "Nguy hiểm", "#EF4444"
            if not suggestions:
                suggestions.append("Dừng nhận task mới trong 2-3 ngày")
            suggestions.append("Nên nghỉ ngơi hoàn toàn ít nhất 1 buổi")
        elif risk_score >= 45:
            level, label, color = "high", "Cao", "#F59E0B"
            if not suggestions:
                suggestions.append("Giảm workload ngay hôm nay")
            suggestions.append("Đảm bảo ngủ đủ 7-8 tiếng tối nay")
        elif risk_score >= 20:
            level, label, color = "medium", "Trung bình", "#3B82F6"
            if not suggestions:
                suggestions.append("Lên kế hoạch breaks đầy đủ")
        else:
            level, label, color = "low", "Thấp", "#10B981"
            if not suggestions:
                suggestions.append("Tiếp tục duy trì nhịp làm việc tốt!")

        return {
            "score": risk_score,
            "level": level,
            "label": label,
            "color": color,
            "reasons": [r for r in risk_factors if r],
            "suggestions": [s for s in suggestions if s],
            "details": details,
            "burnout_probability": round(risk_score / 100, 2),
        }

    @staticmethod
    def _analyze_overdue(tasks: list) -> dict:
        active = [t for t in tasks if t.status not in ("done", "cancelled")]
        if not active:
            return {"score": 0, "reason": ""}
        overdue = [t for t in active if t.is_overdue]
        rate = len(overdue) / len(active)
        if rate > 0.5:
            return {"score": 30, "rate": rate,
                    "reason": f"{int(rate*100)}% công việc đang quá hạn"}
        if rate > 0.3:
            return {"score": 15, "rate": rate,
                    "reason": f"{len(overdue)} task đang quá hạn"}
        return {"score": int(rate * 20), "rate": rate, "reason": ""}

    @staticmethod
    def _analyze_high_priority_overload(tasks: list) -> dict:
        active = [t for t in tasks if t.status not in ("done", "cancelled")]
        high_count = sum(1 for t in active if t.priority == "high")
        if high_count > 7:
            return {"score": 20, "count": high_count,
                    "reason": f"{high_count} task ưu tiên cao cùng lúc — quá tải"}
        if high_count > 4:
            return {"score": 10, "count": high_count,
                    "reason": f"{high_count} task ưu tiên cao"}
        return {"score": 0, "count": high_count, "reason": ""}

    @staticmethod
    def _analyze_overtime(work_sessions: List[dict]) -> dict:
        today_str = date.today().isoformat()
        today_sessions = [
            ws for ws in work_sessions
            if ws.get("started_at", "")[:10] == today_str
            and ws.get("duration_minutes", 0) > 0
        ]
        total = sum(ws.get("duration_minutes", 0) for ws in today_sessions)

        # Weekly overtime
        week_ago = (date.today() - timedelta(days=7)).isoformat()
        week_sessions = [
            ws for ws in work_sessions
            if ws.get("started_at", "")[:10] >= week_ago
        ]
        week_total = sum(ws.get("duration_minutes", 0) for ws in week_sessions)

        if total > 600:  # > 10 hours today
            return {"score": 25, "today_hours": total//60,
                    "reason": f"Đã làm {total//60}h{total%60}p hôm nay — cực kỳ nhiều",
                    "suggestion": "Dừng làm việc ngay và nghỉ ngơi"}
        if total > 480:  # > 8 hours
            return {"score": 15, "today_hours": total//60,
                    "reason": f"Đã làm {total//60}h hôm nay",
                    "suggestion": "Hãy nghỉ ngơi và bổ sung năng lượng"}
        if week_total > 3000:  # > 50 hours this week
            return {"score": 10, "week_hours": week_total//60,
                    "reason": f"Tuần này đã làm {week_total//60} giờ"}

        return {"score": max(0, (total - 300) // 30), "today_hours": total//60, "reason": ""}

    @staticmethod
    def _analyze_delay_trend(behavior_events: List[dict]) -> dict:
        # Đếm delay events trong 7 ngày gần đây
        week_ago = (datetime.now() - timedelta(days=7)).isoformat()
        recent_delays = [
            ev for ev in behavior_events
            if ev.get("event_type") in ("task_delay", "overdue_ack")
            and ev.get("timestamp", "") >= week_ago
        ]
        count = len(recent_delays)

        if count >= 10:
            return {"score": 25, "count": count,
                    "reason": f"Đã trì hoãn {count} lần trong 7 ngày — xu hướng tệ",
                    "suggestion": "Chia nhỏ tasks và bắt đầu từ bước nhỏ nhất"}
        if count >= 5:
            return {"score": 15, "count": count,
                    "reason": f"Trì hoãn {count} task tuần này",
                    "suggestion": "Xem xét lại workload hiện tại"}
        if count >= 3:
            return {"score": 5, "count": count, "reason": ""}
        return {"score": 0, "count": count, "reason": ""}

    @staticmethod
    def _analyze_focus_degradation(work_sessions: List[dict]) -> dict:
        """Phát hiện focus quality đang giảm dần."""
        recent = sorted(
            [ws for ws in work_sessions if ws.get("duration_minutes", 0) > 10],
            key=lambda x: x.get("started_at", ""),
            reverse=True
        )[:10]

        if len(recent) < 4:
            return {"score": 0, "reason": ""}

        qualities = [ws.get("focus_quality", 5) for ws in reversed(recent)]
        # So sánh nửa đầu và nửa sau
        mid = len(qualities) // 2
        older_avg = sum(qualities[:mid]) / mid
        recent_avg = sum(qualities[mid:]) / (len(qualities) - mid)

        drop = older_avg - recent_avg
        if drop > 2.0:
            return {"score": 20, "drop": round(drop, 1),
                    "reason": f"Chất lượng tập trung giảm {drop:.1f} điểm gần đây"}
        if drop > 1.0:
            return {"score": 10, "drop": round(drop, 1),
                    "reason": "Focus quality đang có xu hướng giảm"}
        return {"score": 0, "drop": round(drop, 1) if drop > 0 else 0, "reason": ""}

    @staticmethod
    def _analyze_productivity_drop(tasks: list, behavior_events: List[dict]) -> dict:
        """So sánh productivity tuần này vs tuần trước."""
        today = date.today()
        this_week = today - timedelta(days=today.weekday())
        last_week = this_week - timedelta(days=7)

        def count_completions(from_date, to_date):
            return sum(
                1 for ev in behavior_events
                if ev.get("event_type") == "task_complete"
                and from_date.isoformat() <= ev.get("timestamp", "")[:10] <= to_date.isoformat()
            )

        this_count = count_completions(this_week, today)
        last_count = count_completions(last_week, this_week - timedelta(days=1))

        if last_count > 0 and this_count < last_count * 0.5:
            return {"score": 20,
                    "reason": f"Năng suất tuần này ({this_count} task) thấp hơn tuần trước ({last_count} task) rõ rệt"}
        if last_count > 2 and this_count < last_count * 0.7:
            return {"score": 10, "reason": "Năng suất tuần này giảm so với tuần trước"}
        return {"score": 0, "reason": ""}
