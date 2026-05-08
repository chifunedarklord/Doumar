"""
TaskFlow - Memory Engine
AI Long-term Memory: học và nhớ thói quen người dùng theo thời gian.
Confidence decay, memory consolidation, behavioral insights.
"""
import json
import math
from datetime import datetime, timedelta
from typing import List, Dict, Optional, Any


class MemoryEngine:
    """
    AI memory management:
    - Đọc và ghi memory với confidence scoring
    - Decay memory cũ theo thời gian
    - Consolidate patterns từ behavior data
    - Ưu tiên memory có relevance cao
    """

    DECAY_HALF_LIFE_DAYS = 60  # Memory confidence giảm 50% sau 60 ngày không update

    @classmethod
    def update_from_behavior(cls, user_id: str, tasks: list,
                              behavior_events: List[dict],
                              work_sessions: List[dict]):
        """
        Main method: cập nhật AI memory từ toàn bộ behavior data thực tế.
        Gọi định kỳ (khi session end, daily background).
        """
        from core.database import Storage
        from core.intelligence.behavior_learner import BehaviorLearner

        # 1. Peak hours
        peak_hours = BehaviorLearner.learn_peak_hours(behavior_events, work_sessions)
        cls._save_memory(user_id, "habit", "peak_hours", peak_hours, 0.85)

        # 2. Optimal focus duration
        optimal_focus = BehaviorLearner.learn_optimal_focus_duration(work_sessions)
        cls._save_memory(user_id, "preference", "optimal_focus_minutes", optimal_focus, 0.80)

        # 3. Work style
        work_style = BehaviorLearner.detect_work_style(work_sessions)
        cls._save_memory(user_id, "profile", "work_style", work_style, 0.75)

        # 4. Delay patterns by category
        delay_patterns = BehaviorLearner.learn_delay_patterns(behavior_events)
        cls._save_memory(user_id, "pattern", "delay_patterns", delay_patterns, 0.80)

        # 5. Completion rate overall
        done_count = sum(1 for t in tasks if t.status == "done")
        total = len(tasks) or 1
        cls._save_memory(user_id, "performance", "completion_rate",
                          round(done_count / total, 2), 0.90)

        # 6. Frequent postpone categories
        postponed_cats = {}
        for t in tasks:
            if getattr(t, "postpone_count", 0) >= 2:
                postponed_cats[t.category] = postponed_cats.get(t.category, 0) + 1
        if postponed_cats:
            cls._save_memory(user_id, "pattern", "postpone_categories",
                              postponed_cats, 0.80)

        # 7. Productivity streak
        from core.intelligence.productivity_intelligence import ProductivityIntelligence
        streak = ProductivityIntelligence.calc_productivity_streak(behavior_events)
        cls._save_memory(user_id, "performance", "productivity_streak",
                          streak["current_streak"], 0.95)

        # 8. Today energy estimate
        from core.intelligence.behavior_learner import BehaviorLearner
        energy = BehaviorLearner.estimate_current_energy(behavior_events, work_sessions)
        cls._save_memory(user_id, "state", "estimated_energy", energy, 0.70)

        stress = BehaviorLearner.estimate_stress_level(tasks, behavior_events)
        cls._save_memory(user_id, "state", "estimated_stress", stress, 0.70)

    @staticmethod
    def _save_memory(user_id: str, memory_type: str, key: str, value: Any, confidence: float):
        try:
            from core.database import Storage
            Storage.set_memory(user_id, memory_type, key, value, confidence)
        except Exception:
            pass

    @classmethod
    def apply_confidence_decay(cls, memories: List[dict]) -> List[dict]:
        """
        Giảm confidence của memory cũ theo time decay.
        memories có dạng: [{memory_type, key, value, confidence, updated_at}]
        """
        now = datetime.now()
        result = []
        for m in memories:
            try:
                updated = datetime.fromisoformat(m.get("updated_at", now.isoformat()))
                days_old = max(0, (now - updated).days)
                # Exponential decay
                decay = math.exp(-days_old * math.log(2) / cls.DECAY_HALF_LIFE_DAYS)
                effective_confidence = round(m.get("confidence", 0.5) * decay, 3)
                result.append({**m, "effective_confidence": effective_confidence})
            except Exception:
                result.append({**m, "effective_confidence": m.get("confidence", 0.5)})

        # Sort by effective_confidence desc
        return sorted(result, key=lambda x: -x.get("effective_confidence", 0))

    @classmethod
    def get_context_summary(cls, user_id: str) -> str:
        """
        Tóm tắt AI memory thành text để inject vào system prompt.
        """
        try:
            from core.database import Storage
            memories = Storage.get_memory(user_id)
        except Exception:
            return ""

        if not memories:
            return ""

        # Apply decay
        memories = cls.apply_confidence_decay(memories)
        # Lọc memory có confidence cao (> 0.3)
        relevant = [m for m in memories if m.get("effective_confidence", 0) > 0.3]

        lines = ["📊 THÔNG TIN AI ĐÃ HỌC VỀ USER:"]

        for m in relevant[:12]:
            key = m.get("key", "")
            val = m.get("value", "")
            conf = m.get("effective_confidence", 0.5)
            confidence_str = "✅" if conf > 0.7 else "🔶" if conf > 0.4 else "⚠️"

            if key == "peak_hours":
                lines.append(f"{confidence_str} Giờ vàng: {', '.join(f'{h:02d}h' for h in (val or []))}")
            elif key == "optimal_focus_minutes":
                lines.append(f"{confidence_str} Focus tối ưu: {val} phút")
            elif key == "work_style":
                style_map = {
                    "deep_worker": "Làm việc tập trung dài",
                    "sprint_worker": "Làm nhanh nhiều phiên",
                    "balanced": "Cân bằng",
                    "scattered": "Hay bị phân tán"
                }
                lines.append(f"{confidence_str} Phong cách: {style_map.get(val, val)}")
            elif key == "completion_rate":
                lines.append(f"{confidence_str} Tỷ lệ hoàn thành: {int(float(val)*100)}%")
            elif key == "postpone_categories" and isinstance(val, dict):
                cats = sorted(val.items(), key=lambda x: -x[1])[:2]
                lines.append(f"{confidence_str} Hay trì hoãn: {', '.join(c for c, _ in cats)}")
            elif key == "estimated_energy":
                lines.append(f"{confidence_str} Năng lượng ước tính: {val}/10")
            elif key == "estimated_stress":
                lines.append(f"{confidence_str} Stress ước tính: {val}/10")
            elif key == "productivity_streak":
                if int(val) > 0:
                    lines.append(f"{confidence_str} Streak: {val} ngày liên tiếp")

        return "\n".join(lines)

    @classmethod
    def get_value(cls, user_id: str, memory_type: str, key: str,
                   default=None, min_confidence: float = 0.2):
        """
        Lấy memory value nếu confidence đủ cao.
        """
        try:
            from core.database import Storage
            memories = Storage.get_memory(user_id, memory_type)
        except Exception:
            return default

        for m in memories:
            if m.get("key") != key:
                continue
            # Apply decay
            decayed = cls.apply_confidence_decay([m])
            if decayed and decayed[0].get("effective_confidence", 0) >= min_confidence:
                return m.get("value", default)
        return default
