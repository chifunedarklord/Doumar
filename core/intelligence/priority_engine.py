"""
TaskFlow - Adaptive Priority Engine
Priority score dựa trên behavior history, delay probability, stress state.
Không chỉ deadline/impact — adaptive theo thực tế user.
"""
from datetime import datetime, date
from typing import List, Optional
import math


class AdaptivePriorityEngine:
    """
    Priority Score (0-100) tính từ 8 yếu tố động:
    1. Deadline urgency        (25%)
    2. Impact score            (15%)
    3. Priority level          (10%)
    4. Delay probability       (15%) — từ behavior history
    5. Completion probability  (10%) — ngược delay
    6. Stress penalty          (10%) — user đang stress → task khó giảm
    7. Workload penalty        (5%)
    8. Energy fit bonus        (10%) — task phù hợp với mức năng lượng hiện tại
    """

    @staticmethod
    def calculate_score(task, user_context: dict = None) -> float:
        ctx = user_context or {}
        score = 0.0

        # 1. Deadline urgency (25%)
        deadline_score = AdaptivePriorityEngine._deadline_score(task)
        score += deadline_score * 0.25

        # 2. Impact (15%)
        impact = getattr(task, "impact_score", 5.0)
        score += (impact / 10.0) * 100 * 0.15

        # 3. Priority level (10%)
        pri_map = {"high": 100, "medium": 60, "low": 30}
        score += pri_map.get(task.priority, 60) * 0.10

        # 4. Delay probability (15%) — từ behavior data
        delay_risk = ctx.get("delay_risk", {})
        category_risk = delay_risk.get(task.category, {}).get("risk_score", 0.0)
        postpone_bonus = min(40.0, getattr(task, "postpone_count", 0) * 8.0)
        delay_score = min(100.0, category_risk * 100 + postpone_bonus)
        score += delay_score * 0.15

        # 5. Completion probability inverse (10%)
        # Task hay bị delay → cần ưu tiên cao hơn để hoàn thành
        completion_score = max(0, 100 - delay_score)
        score += completion_score * 0.10

        # 6. Stress penalty (10%)
        # Khi user đang stress cao, task khó giảm điểm
        stress_level = ctx.get("stress_level", 5)
        difficulty = getattr(task, "difficulty_level", 5)
        if stress_level >= 7 and difficulty >= 7:
            stress_penalty = -30
        elif stress_level >= 5 and difficulty >= 8:
            stress_penalty = -15
        else:
            stress_penalty = 0
        score += max(-20, stress_penalty) * 0.10

        # 7. Workload penalty (5%)
        workload = ctx.get("daily_workload_minutes", 0)
        if workload > 420:  # >7 hours planned
            score -= 10 * 0.05

        # 8. Energy fit bonus (10%)
        energy_level = ctx.get("energy_level", 7)
        peak_hours = ctx.get("peak_hours", [9, 10, 14, 15])
        current_hour = ctx.get("current_hour", datetime.now().hour)
        energy_fit = AdaptivePriorityEngine._energy_fit_score(
            task, energy_level, current_hour, peak_hours
        )
        score += energy_fit * 0.10

        # Clamp & return
        return round(min(100.0, max(0.0, score)), 1)

    @staticmethod
    def _deadline_score(task) -> float:
        if not task.due_date:
            return 10.0
        days = task.days_until_due
        if days is None:
            return 10.0

        if days < 0:
            base = 100.0 + abs(days) * 2
        elif days == 0:
            base = 95.0
        elif days == 1:
            base = 85.0
        elif days <= 3:
            base = 70.0
        elif days <= 7:
            base = 50.0
        elif days <= 14:
            base = 30.0
        else:
            base = max(0, 30 - days * 0.5)

        deadline_type = getattr(task, "deadline_type", "soft")
        if deadline_type == "hard":
            multiplier = 1.2 if days > 0 else 1.0
        elif deadline_type == "estimated":
            multiplier = 0.8 if days > 7 else 1.0
        else:
            multiplier = 1.0

        return min(100.0, base * multiplier)

    @staticmethod
    def _energy_fit_score(task, energy_level: int, current_hour: int, peak_hours: List[int]) -> float:
        energy_req = getattr(task, "energy_required", "medium")
        focus_req = getattr(task, "focus_required", "medium")

        is_peak = current_hour in peak_hours

        # High energy task + peak hour + high energy user → perfect fit
        if energy_req == "high" and is_peak and energy_level >= 7:
            return 100.0
        # Low energy task + off-peak → good fit
        if energy_req == "low" and not is_peak and energy_level <= 5:
            return 85.0
        # Medium tasks are always ok
        if energy_req == "medium":
            return 70.0 if is_peak else 55.0
        # Mismatch — high energy task when user is tired
        if energy_req == "high" and energy_level <= 4:
            return 20.0
        return 50.0

    @classmethod
    def rank_tasks(cls, tasks: list, user_context: dict = None) -> list:
        """Rank tasks by adaptive priority score. Returns sorted list."""
        ctx = user_context or {}
        scored = []
        for t in tasks:
            if t.status not in ("done", "cancelled"):
                s = cls.calculate_score(t, ctx)
                scored.append((s, t))
        scored.sort(key=lambda x: -x[0])
        return [t for _, t in scored]

    @classmethod
    def explain_score(cls, task, user_context: dict = None) -> List[str]:
        """
        AI Explanation — tại sao task này có điểm như vậy.
        Trả về list các lý do bằng tiếng Việt.
        """
        ctx = user_context or {}
        reasons = []

        days = task.days_until_due
        if days is not None:
            if days < 0:
                reasons.append(f"⚠️ Đã quá hạn {abs(days)} ngày")
            elif days == 0:
                reasons.append("🔴 Hạn chót hôm nay")
            elif days <= 3:
                reasons.append(f"🟡 Còn {days} ngày đến hạn")

        if task.priority == "high":
            reasons.append("🔥 Độ ưu tiên cao")

        postpone = getattr(task, "postpone_count", 0)
        if postpone >= 3:
            reasons.append(f"🔄 Đã bị dời {postpone} lần — xu hướng trì hoãn cao")

        delay_risk = ctx.get("delay_risk", {})
        cat_risk = delay_risk.get(task.category, {}).get("risk_score", 0)
        if cat_risk > 0.5:
            reasons.append(f"📊 Loại '{task.category}' hay bị trì hoãn ({int(cat_risk*100)}% rủi ro)")

        stress = ctx.get("stress_level", 5)
        if stress >= 7 and getattr(task, "difficulty_level", 5) >= 7:
            reasons.append("😰 Task khó khi stress cao — cân nhắc sau")

        energy = ctx.get("energy_level", 7)
        if getattr(task, "energy_required", "medium") == "high" and energy >= 7:
            reasons.append("⚡ Task phù hợp với mức năng lượng hiện tại")

        if not reasons:
            reasons.append("📌 Độ ưu tiên tiêu chuẩn")

        return reasons
