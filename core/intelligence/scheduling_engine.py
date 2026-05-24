"""
TaskFlow - Smart Scheduling Engine
Tự động sắp xếp lịch làm việc dựa trên peak hours, energy, workload.
Tránh overload, xen kẽ task khó/dễ, tạo focus blocks thực tế.
"""
from datetime import datetime, date, timedelta
from typing import List, Dict, Optional
from collections import defaultdict


class SchedulingEngine:
    """
    Tạo lịch làm việc thông minh:
    - Xếp task theo peak productivity hours
    - Tránh heavy tasks liên tục
    - Tạo Pomodoro focus blocks
    - Cân bằng workload theo ngày
    - Auto-split task lớn
    """

    MAX_DAILY_WORK_HOURS = 8
    DEEP_WORK_THRESHOLD_MINUTES = 60   # Task > 60min = deep work
    SHORT_TASK_THRESHOLD_MINUTES = 20  # Task < 20min = quick win

    @classmethod
    def build_daily_schedule(
        cls,
        tasks: list,
        peak_hours: List[int],
        user_context: dict = None,
        optimal_focus_minutes: int = 25,
    ) -> List[dict]:
        """
        Tạo lịch ngày cho user.
        Returns: list of schedule slots sorted by suggested_hour.
        """
        ctx = user_context or {}
        energy_level = ctx.get("energy_level", 7)
        stress_level = ctx.get("stress_level", 5)
        current_hour = ctx.get("current_hour", datetime.now().hour)

        active = [t for t in tasks if t.status not in ("done", "cancelled")]
        if not active:
            return []

        # Sort bằng priority score
        from core.intelligence.priority_engine import AdaptivePriorityEngine
        ranked = AdaptivePriorityEngine.rank_tasks(active, ctx)

        slots = []
        total_planned_minutes = 0
        max_minutes = cls.MAX_DAILY_WORK_HOURS * 60
        prev_block_type = "regular"

        # Determine starting slot hour
        if peak_hours:
            slot_hour = max(current_hour, min(peak_hours))
        else:
            slot_hour = max(current_hour, 9)

        for task in ranked:
            if total_planned_minutes >= max_minutes:
                break

            est = max(5, getattr(task, "estimated_minutes", 30))
            energy_req = getattr(task, "energy_required", "medium")
            difficulty = getattr(task, "difficulty_level", 5)

            # Xác định block type
            if est >= cls.DEEP_WORK_THRESHOLD_MINUTES and difficulty >= 6:
                block_type = "deep_work"
            elif est <= cls.SHORT_TASK_THRESHOLD_MINUTES:
                block_type = "quick_win"
            else:
                block_type = "regular"

            # Tránh deep_work liên tiếp
            if block_type == "deep_work" and prev_block_type == "deep_work":
                # Xen kẽ break hoặc quick win
                break_slot = {
                    "type": "break",
                    "suggested_hour": slot_hour,
                    "duration_minutes": 10,
                    "block_type": "break",
                    "task": None,
                    "label": "☕ Nghỉ giải lao",
                }
                slots.append(break_slot)
                slot_hour = cls._advance_hour(slot_hour, 10)

            # Khi stress cao → skip deep work tasks
            if stress_level >= 8 and difficulty >= 8:
                continue

            # Khi energy thấp → skip high-energy tasks
            if energy_level <= 3 and energy_req == "high":
                continue

            # Ưu tiên peak hours cho deep work
            if block_type == "deep_work" and peak_hours:
                # Tìm peak hour gần nhất sau slot_hour
                future_peaks = [h for h in peak_hours if h >= slot_hour]
                if future_peaks:
                    slot_hour = min(future_peaks)

            slots.append({
                "type": "task",
                "task": task,
                "suggested_hour": slot_hour,
                "duration_minutes": est,
                "block_type": block_type,
                "energy_required": energy_req,
                "priority_score": getattr(task, "ai_priority_score", 50),
            })

            total_planned_minutes += est
            slot_hour = cls._advance_hour(slot_hour, est)
            prev_block_type = block_type

            # Thêm break mỗi 90 phút nếu chưa đủ
            if total_planned_minutes % 90 < est and total_planned_minutes > 90:
                break_slot = {
                    "type": "break",
                    "suggested_hour": slot_hour,
                    "duration_minutes": 10,
                    "block_type": "break",
                    "task": None,
                    "label": "🧘 Break ngắn",
                }
                slots.append(break_slot)
                slot_hour = cls._advance_hour(slot_hour, 10)

        return slots

    @staticmethod
    def _advance_hour(current_hour: int, minutes: int) -> int:
        """Advance hour by minutes, cap at 22."""
        new_hour = current_hour + minutes // 60
        return min(22, new_hour)

    @classmethod
    def build_focus_blocks(cls, peak_hours: List[int], optimal_minutes: int = 25) -> List[dict]:
        """Tạo Pomodoro focus blocks từ peak hours."""
        blocks = []
        break_time = max(5, optimal_minutes // 5)
        for h in peak_hours:
            blocks.append({
                "start_hour": h,
                "start_minute": 0,
                "duration": optimal_minutes,
                "type": "focus",
                "label": f"🎯 Focus {h:02d}:00–{h:02d}:{optimal_minutes:02d}",
            })
            blocks.append({
                "start_hour": h,
                "start_minute": optimal_minutes,
                "duration": break_time,
                "type": "break",
                "label": f"☕ Break {h:02d}:{optimal_minutes:02d}",
            })
        return blocks

    @classmethod
    def auto_split_task(cls, task, context: str = "", use_ai: bool = True) -> List[dict]:
        """
        Auto-split task lon thanh subtasks.
        Thu Gemini truoc, fallback ve template neu AI fail.
        """
        est = getattr(task, "estimated_minutes", 30)
        category = task.category
        title = task.title

        if est <= 60:
            return []

        if use_ai:
            ai_subtasks = cls._ai_split_task(title, category, est, context)
            if ai_subtasks:
                return ai_subtasks

        templates = {
            "work": [
                "Lập kế hoạch & xác định yêu cầu",
                "Thực hiện phần core/chính",
                "Review & kiểm tra",
                "Tổng hợp & báo cáo",
            ],
            "education": [
                "Đọc & nghiên cứu tài liệu",
                "Ghi chép & tóm tắt",
                "Thực hành / bài tập",
                "Ôn tập & kiểm tra lại",
            ],
            "health": [
                "Lên kế hoạch cụ thể",
                "Bắt đầu thực hiện",
                "Theo dõi & điều chỉnh",
            ],
            "finance": [
                "Thu thập & phân tích số liệu",
                "Lập kế hoạch tài chính",
                "Thực hiện & theo dõi",
            ],
            "personal": [
                "Xác định mục tiêu cụ thể",
                "Chuẩn bị & lên kế hoạch",
                "Thực hiện",
                "Hoàn thiện & kiểm tra",
            ],
        }

        parts = templates.get(category, templates["personal"])
        part_time = est // len(parts)
        return [
            {
                "id": f"sub_{i+1}",
                "title": f"{part_title} — {title[:20]}",
                "estimated_minutes": part_time,
                "status": "todo",
                "order": i + 1,
            }
            for i, part_title in enumerate(parts)
        ]

    @staticmethod
    def _ai_split_task(title: str, category: str, estimated_minutes: int,
                       context: str = "") -> List[dict]:
        """Dung Gemini de chia task. Tra ve [] neu fail."""
        try:
            import os, json as _json
            from google import genai
            from google.genai import types

            api_key = os.getenv("GEMINI_API_KEY", "")
            if not api_key:
                return []

            client = genai.Client(api_key=api_key)
            context_line = f"\nBối cảnh thêm: {context}" if context else ""
            prompt = (
                f'Hãy chia task sau thành 3–5 bước con cụ thể, thực tế, có thể thực hiện ngay.\n\n'
                f'Task: "{title}"\n'
                f'Danh mục: {category}\n'
                f'Thời gian ước tính: {estimated_minutes} phút{context_line}\n\n'
                f'Yêu cầu:\n'
                f'- Mỗi bước phải có tên rõ ràng bằng tiếng Việt (có dấu đầy đủ)\n'
                f'- Tên bước ngắn gọn, bắt đầu bằng động từ hành động (Lên kế hoạch, Thực hiện, Kiểm tra...)\n'
                f'- Tổng estimated_minutes của tất cả bước phải đúng bằng {estimated_minutes}\n\n'
                f'Trả về JSON array thuần túy — KHÔNG có markdown, KHÔNG có giải thích:\n'
                f'[{{"title": "...", "estimated_minutes": 30}}, ...]'
            )
            response = client.models.generate_content(
                model="gemini-2.0-flash",
                contents=prompt,
                config=types.GenerateContentConfig(
                    thinking_config=types.ThinkingConfig(thinking_budget=0),
                    max_output_tokens=500,
                ),
            )
            text = response.text.strip()
            if text.startswith("```"):
                text = text.split("```")[1]
                if text.startswith("json"):
                    text = text[4:]
            text = text.strip()

            items = _json.loads(text)
            if not isinstance(items, list):
                return []
            result = []
            for i, item in enumerate(items[:6]):
                if not isinstance(item, dict) or "title" not in item:
                    continue
                result.append({
                    "id": f"sub_{i+1}",
                    "title": str(item["title"])[:80],
                    "estimated_minutes": max(5, int(item.get("estimated_minutes", 15))),
                    "status": "todo",
                    "order": i + 1,
                })
            return result if len(result) >= 2 else []
        except Exception as e:
            print(f"[AI Split] Failed: {e}")
            return []

    @classmethod
    def suggest_today(
        cls,
        tasks: list,
        peak_hours: List[int],
        user_context: dict = None,
    ) -> List[dict]:
        """Wrapper for build_daily_schedule — used by dashboard."""
        ctx = user_context or {}
        user_id = ctx.get("user_id")

        optimal_focus = 25
        if user_id:
            try:
                from core.services import AIMemoryService
                mem_val = AIMemoryService.recall_value(
                    user_id, "preference", "preferred_focus_duration"
                )
                if mem_val and isinstance(mem_val, (int, float)):
                    optimal_focus = int(mem_val)
            except Exception:
                pass

        slots = cls.build_daily_schedule(
            tasks=tasks,
            peak_hours=peak_hours,
            user_context=ctx,
            optimal_focus_minutes=optimal_focus,
        )

        work_start = ctx.get("work_start_hour", 7)
        work_end   = ctx.get("work_end_hour", 22)
        return [
            s for s in slots
            if s.get("task") is not None           # skip break slots
            and work_start <= s.get("suggested_hour", 12) <= work_end
        ]

    @classmethod
    def detect_overload_risk(cls, tasks: list, planned_minutes: int) -> dict:
        """Phát hiện nguy cơ overload ngày hôm nay."""
        active = [t for t in tasks if t.status not in ("done", "cancelled")]
        today_str = date.today().isoformat()
        today_tasks = [t for t in active if t.due_date == today_str]

        total_estimated = sum(getattr(t, "estimated_minutes", 30) for t in today_tasks)

        if total_estimated > cls.MAX_DAILY_WORK_HOURS * 60:
            return {
                "risk": "high",
                "message": f"Công việc hôm nay ước tính {total_estimated//60}h{total_estimated%60}p — vượt giới hạn!",
                "recommendation": "Dời ít nhất 1-2 task low-priority sang ngày mai.",
            }
        elif total_estimated > 300:
            return {
                "risk": "medium",
                "message": f"Lịch hôm nay khá dày ({total_estimated//60}h{total_estimated%60}p).",
                "recommendation": "Hãy đảm bảo có đủ breaks giữa các task.",
            }
        return {"risk": "low", "message": "Lịch hôm nay hợp lý.", "recommendation": ""}
