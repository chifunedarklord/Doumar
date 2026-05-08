"""
TaskFlow - Recommendation Engine
Gợi ý thực tế, actionable, dựa trên behavior data thật sự.
"""
from datetime import datetime, date, timedelta
from typing import List, Dict


class RecommendationEngine:
    """
    Tạo recommendations thực tế dựa trên:
    - Behavior patterns
    - Current state (stress, energy)
    - Burnout risk
    - Task history
    - Delay patterns
    """

    @classmethod
    def get_recommendations(
        cls,
        tasks: list,
        behavior_events: List[dict],
        work_sessions: List[dict],
        burnout: dict,
        user_context: dict = None,
        behavior_analytics: dict = None,
    ) -> List[dict]:
        """
        Main method: tạo danh sách recommendations có độ ưu tiên.
        """
        ctx = user_context or {}
        recs = []

        # 1. Burnout warning (highest priority)
        recs.extend(cls._burnout_recs(burnout))

        # 2. Overdue tasks
        recs.extend(cls._overdue_recs(tasks))

        # 3. Postponed tasks detection
        recs.extend(cls._postponed_recs(tasks))

        # 4. Large task splitting
        recs.extend(cls._split_task_recs(tasks))

        # 5. Peak hour reminder
        recs.extend(cls._peak_hour_recs(tasks, ctx))

        # 6. Focus decay warning
        recs.extend(cls._focus_decay_recs(work_sessions))

        # 7. Category balance
        recs.extend(cls._category_balance_recs(tasks))

        # 8. Empty today
        recs.extend(cls._daily_planning_recs(tasks))

        # 9. Positive reinforcement
        recs.extend(cls._positive_recs(tasks, behavior_events))

        # 10-13. Behavioral analytics recommendations (when data available)
        if behavior_analytics:
            recs.extend(cls._estimation_recs(behavior_analytics.get("estimation_accuracy", {})))
            recs.extend(cls._deadline_risk_recs(tasks, behavior_analytics.get("deadline_compliance", {})))
            recs.extend(cls._procrastination_recs(behavior_analytics.get("procrastination", {})))
            recs.extend(cls._overcommit_recs(behavior_analytics.get("workload", {})))

        critical_types = {"burnout_critical", "overdue_alert"}

        # Filter: dismissed in last 24h
        dismissed_24h = cls._recently_dismissed_types(behavior_events)
        if dismissed_24h:
            recs = [r for r in recs
                    if r.get("type") not in dismissed_24h or r.get("type") in critical_types]

        # Filter: dismissed 3+ times in 14 days → suppress completely
        chronic_dismissed = cls._chronic_dismissed_types(behavior_events)
        if chronic_dismissed:
            recs = [r for r in recs
                    if r.get("type") not in chronic_dismissed or r.get("type") in critical_types]

        # Sort: boost types that were accepted recently
        accepted_counts = cls._recently_accepted_types(behavior_events)
        priority_order  = {"critical": 0, "high": 1, "medium": 2, "low": 3}

        def _sort_key(r):
            base  = priority_order.get(r.get("priority", "low"), 3)
            boost = min(1.0, accepted_counts.get(r.get("type", ""), 0) * 0.2)
            return base - boost

        recs.sort(key=_sort_key)
        return recs[:6]

    @staticmethod
    def _recently_dismissed_types(behavior_events: List[dict]) -> set:
        """Rec types dismissed in the last 24 hours."""
        cutoff = (datetime.now() - timedelta(hours=24)).isoformat()
        dismissed = set()
        for ev in behavior_events:
            if ev.get("event_type") != "recommendation_dismissed":
                continue
            if ev.get("timestamp", "") < cutoff:
                continue
            rec_type = ev.get("event_data", {}).get("rec_type", "")
            if rec_type:
                dismissed.add(rec_type)
        return dismissed

    @staticmethod
    def _recently_accepted_types(behavior_events: List[dict]) -> Dict[str, int]:
        """Count of accepted rec types in the last 7 days — used to boost priority."""
        cutoff = (datetime.now() - timedelta(days=7)).isoformat()
        accepted: Dict[str, int] = {}
        for ev in behavior_events:
            if ev.get("event_type") != "recommendation_accepted":
                continue
            if ev.get("timestamp", "") < cutoff:
                continue
            rec_type = ev.get("event_data", {}).get("rec_type", "")
            if rec_type:
                accepted[rec_type] = accepted.get(rec_type, 0) + 1
        return accepted

    @staticmethod
    def _chronic_dismissed_types(behavior_events: List[dict]) -> set:
        """Rec types dismissed 3+ times in the last 14 days — suppressed completely."""
        cutoff = (datetime.now() - timedelta(days=14)).isoformat()
        counts: Dict[str, int] = {}
        for ev in behavior_events:
            if ev.get("event_type") != "recommendation_dismissed":
                continue
            if ev.get("timestamp", "") < cutoff:
                continue
            rec_type = ev.get("event_data", {}).get("rec_type", "")
            if rec_type:
                counts[rec_type] = counts.get(rec_type, 0) + 1
        return {rt for rt, cnt in counts.items() if cnt >= 3}

    @staticmethod
    def _burnout_recs(burnout: dict) -> List[dict]:
        level = burnout.get("level", "low")
        recs = []
        if level == "critical":
            recs.append({
                "type": "burnout_critical",
                "icon": "🚨",
                "title": "Nguy cơ kiệt sức NGHIÊM TRỌNG",
                "message": "Dừng nhận task mới ngay. " + (burnout.get("suggestions", ["Nghỉ ngơi"])[0]),
                "priority": "critical",
                "action": "rest",
            })
        elif level == "high":
            recs.append({
                "type": "burnout_high",
                "icon": "⚠️",
                "title": "Cảnh báo kiệt sức",
                "message": burnout.get("suggestions", ["Giảm workload"])[0] if burnout.get("suggestions") else "Hãy nghỉ ngơi",
                "priority": "high",
                "action": "reduce_workload",
            })
        return recs

    @staticmethod
    def _overdue_recs(tasks: list) -> List[dict]:
        active = [t for t in tasks if t.status not in ("done", "cancelled")]
        overdue = [t for t in active if t.is_overdue]
        if not overdue:
            return []
        overdue_sorted = sorted(overdue, key=lambda t: t.due_date or "")
        worst = overdue_sorted[0]
        return [{
            "type": "overdue_alert",
            "icon": "📅",
            "title": f"{len(overdue)} task đang quá hạn",
            "message": f"Cũ nhất: '{worst.title[:25]}' — cần xử lý ngay hoặc đổi deadline",
            "priority": "high",
            "action": "view_tasks",
            "data": {"task_id": worst.id},
        }]

    @staticmethod
    def _postponed_recs(tasks: list) -> List[dict]:
        active = [t for t in tasks if t.status not in ("done", "cancelled")]
        postponed = sorted(
            [t for t in active if getattr(t, "postpone_count", 0) >= 3],
            key=lambda t: -t.postpone_count
        )
        if not postponed:
            return []
        p = postponed[0]
        return [{
            "type": "habit_warning",
            "icon": "🔄",
            "title": f"Đã dời '{p.title[:20]}...' {p.postpone_count} lần!",
            "message": "Task này có rào cản tâm lý. Thử chia nhỏ thành 4 bước hoặc loại khỏi danh sách.",
            "priority": "high",
            "action": "split_or_cancel",
            "data": {"task_id": p.id},
        }]

    @staticmethod
    def _split_task_recs(tasks: list) -> List[dict]:
        active = [t for t in tasks if t.status not in ("done", "cancelled")]
        large = [t for t in active if getattr(t, "estimated_minutes", 30) > 120]
        if not large:
            return []
        large_task = large[0]
        est_h = large_task.estimated_minutes // 60
        est_m = large_task.estimated_minutes % 60
        return [{
            "type": "split_task",
            "icon": "✂️",
            "title": f"Task '{large_task.title[:20]}...' quá lớn",
            "message": f"Ước tính {est_h}h{est_m}p — nên chia thành 3-4 subtask để dễ hoàn thành hơn.",
            "priority": "medium",
            "action": "split_task",
            "data": {"task_id": large_task.id},
        }]

    @staticmethod
    def _peak_hour_recs(tasks: list, ctx: dict) -> List[dict]:
        peak_hours = ctx.get("peak_hours", [])
        current_hour = ctx.get("current_hour", datetime.now().hour)
        if not peak_hours or current_hour not in peak_hours:
            return []
        active = [t for t in tasks if t.status not in ("done", "cancelled")]
        hard_tasks = [t for t in active if t.priority == "high"
                      and getattr(t, "energy_required", "medium") == "high"]
        if not hard_tasks:
            return []
        return [{
            "type": "peak_focus",
            "icon": "⚡",
            "title": "Đang trong Peak Hour!",
            "message": f"Đây là lúc tốt nhất để làm '{hard_tasks[0].title[:25]}' — task khó nhất của bạn.",
            "priority": "medium",
            "action": "start_focus",
            "data": {"task_id": hard_tasks[0].id},
        }]

    @staticmethod
    def _focus_decay_recs(work_sessions: List[dict]) -> List[dict]:
        from core.intelligence.focus_engine import FocusEngine
        decay = FocusEngine.detect_focus_decay(work_sessions)
        if not decay.get("decay_detected"):
            return []
        return [{
            "type": "focus_break",
            "icon": "🧘",
            "title": "Focus đang giảm — cần nghỉ",
            "message": decay.get("recommendation", "Nghỉ 15 phút trước khi tiếp tục."),
            "priority": "medium",
            "action": "take_break",
        }]

    @staticmethod
    def _category_balance_recs(tasks: list) -> List[dict]:
        active = [t for t in tasks if t.status not in ("done", "cancelled")]
        if len(active) < 5:
            return []
        cat_counts = {}
        for t in active:
            cat_counts[t.category] = cat_counts.get(t.category, 0) + 1
        dominant = max(cat_counts.items(), key=lambda x: x[1])
        if dominant[1] > len(active) * 0.6:
            return [{
                "type": "category_imbalance",
                "icon": "⚖️",
                "title": f"Quá nhiều task '{dominant[0]}'",
                "message": f"{dominant[1]}/{len(active)} task thuộc cùng danh mục — cân nhắc cân bằng lại.",
                "priority": "low",
                "action": None,
            }]
        return []

    @staticmethod
    def _daily_planning_recs(tasks: list) -> List[dict]:
        today_str = date.today().isoformat()
        active = [t for t in tasks if t.status not in ("done", "cancelled")]
        today_tasks = [t for t in active if t.due_date == today_str]
        if not today_tasks and active:
            return [{
                "type": "plan_day",
                "icon": "🗓️",
                "title": "Chưa có kế hoạch hôm nay",
                "message": "Chọn 1-3 task để tập trung hoàn thành hôm nay. Đừng để ngày trôi qua không có mục tiêu.",
                "priority": "low",
                "action": "view_tasks",
            }]
        return []

    @staticmethod
    def _positive_recs(tasks: list, behavior_events: List[dict]) -> List[dict]:
        """Positive reinforcement — tạo động lực."""
        today_str = date.today().isoformat()
        completed_today = sum(
            1 for ev in behavior_events
            if ev.get("event_type") == "task_complete"
            and ev.get("timestamp", "")[:10] == today_str
        )
        if completed_today >= 5:
            return [{
                "type": "achievement",
                "icon": "🏆",
                "title": f"Tuyệt vời! Đã hoàn thành {completed_today} task hôm nay",
                "message": "Năng suất cao! Hãy đảm bảo nghỉ ngơi đủ để duy trì phong độ.",
                "priority": "low",
                "action": None,
            }]
        return []

    @staticmethod
    def _estimation_recs(estimation: dict) -> List[dict]:
        """Cảnh báo khi estimation accuracy kém."""
        tendency = estimation.get("tendency", "accurate")
        error_pct = estimation.get("avg_error_pct", 0)
        samples = estimation.get("samples", 0)
        if samples < 3 or tendency == "accurate":
            return []
        if tendency == "underestimate":
            msg = f"Bạn thường underestimate {abs(error_pct):.0f}% — hãy cộng thêm buffer khi ước tính task mới."
        else:
            msg = f"Bạn ước tính nhiều hơn thực tế {abs(error_pct):.0f}% — có thể giảm thời gian ước tính."
        return [{
            "type": "estimation_warning",
            "icon": "⏱️",
            "title": "Estimation chưa chính xác",
            "message": msg,
            "priority": "medium",
            "action": None,
        }]

    @staticmethod
    def _deadline_risk_recs(tasks: list, compliance: dict) -> List[dict]:
        """Cảnh báo task sắp đến hạn có rủi ro cao."""
        rate = compliance.get("compliance_rate", 100)
        samples = compliance.get("samples", 0)
        if samples < 5 or rate >= 70:
            return []
        return [{
            "type": "deadline_risk",
            "icon": "📋",
            "title": f"Tỷ lệ đúng hạn chỉ {rate:.0f}%",
            "message": "Hãy đặt deadline sớm hơn 1-2 ngày so với thực tế để tạo buffer.",
            "priority": "medium",
            "action": "view_tasks",
        }]

    @staticmethod
    def _procrastination_recs(procrastination: dict) -> List[dict]:
        """Gợi ý khi phát hiện pattern trì hoãn."""
        score = procrastination.get("procrastination_score", 0)
        high_risk = procrastination.get("high_risk_categories", [])
        worst_time = procrastination.get("worst_time_of_day")
        if score < 20 or not high_risk:
            return []
        cat_name = high_risk[0].get("category", "")
        time_hint = f" (hay xảy ra vào buổi {worst_time})" if worst_time else ""
        return [{
            "type": "procrastination_alert",
            "icon": "⏳",
            "title": f"Hay trì hoãn task '{cat_name}'",
            "message": f"Danh mục này thường bị delay{time_hint}. Thử làm 5 phút đầu tiên ngay bây giờ.",
            "priority": "medium",
            "action": "view_tasks",
        }]

    @staticmethod
    def _overcommit_recs(workload: dict) -> List[dict]:
        """Cảnh báo overcommit workload."""
        score = workload.get("overcommit_score", 0)
        weekly_load = workload.get("weekly_load", 0)
        overcommitted = workload.get("overcommitted_days", [])
        if score < 30:
            return []
        msg = f"{weekly_load} task trong 7 ngày tới"
        if overcommitted:
            d = overcommitted[0]
            msg += f" — {d['date']} có {d['task_count']} task cùng hạn"
        return [{
            "type": "overcommit_warning",
            "icon": "📦",
            "title": "Workload quá tải",
            "message": f"{msg}. Nên rải deadline hoặc hoãn một số task.",
            "priority": "medium",
            "action": "view_tasks",
        }]

    @staticmethod
    def explain_priority(task, user_context: dict = None) -> str:
        """
        AI explanation cho một task — tại sao được ưu tiên.
        """
        from core.intelligence.priority_engine import AdaptivePriorityEngine
        reasons = AdaptivePriorityEngine.explain_score(task, user_context)
        if not reasons:
            return ""
        header = f"Task này được ưu tiên vì:\n"
        return header + "\n".join(f"• {r}" for r in reasons)
