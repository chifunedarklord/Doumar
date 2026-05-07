from google import genai
from google.genai import types
from core.services import TaskService, ChatService, BehaviorService, AnalyticsService, AIMemoryService


def _build_context(user_id: str) -> str:
    """Xây dựng context phong phú cho AI gồm tasks, behavior, analytics, memory."""
    tasks = TaskService.get_tasks(user_id)

    # Tasks chưa xong
    task_lines = []
    for t in tasks:
        if t.status != "done":
            overdue_tag = " [QUÁ HẠN]" if t.is_overdue else ""
            task_lines.append(
                f"- {t.title}{overdue_tag} | Danh mục: {t.category} | "
                f"Ưu tiên: {t.priority} | Độ khó: {t.difficulty_level}/10 | "
                f"Năng lượng cần: {t.energy_required} | "
                f"Dự kiến: {t.estimated_minutes}p | Hạn: {t.due_date or 'Chưa set'} | "
                f"AI Score: {t.ai_priority_score:.0f}/100"
            )
    tasks_text = "CÔNG VIỆC ĐANG CÓ:\n" + ("\n".join(task_lines) if task_lines else "Không có công việc nào.")

    # Behavior summary
    peak_hours = BehaviorService.get_peak_hours(user_id)
    productivity_score = BehaviorService.get_productivity_score(user_id)
    peak_str = ", ".join(f"{h:02d}:00" for h in peak_hours) if peak_hours else "Chưa có dữ liệu"

    behavior_text = (
        f"\nPHÂN TÍCH HÀNH VI USER:\n"
        f"- Giờ vàng làm việc: {peak_str}\n"
        f"- Productivity score tuần này: {productivity_score:.0f}/100\n"
    )

    # Analytics summary (nhanh, không full report)
    done = sum(1 for t in tasks if t.status == "done")
    overdue = sum(1 for t in tasks if t.is_overdue)
    total = len(tasks)
    analytics_text = (
        f"\nSTATISTICS:\n"
        f"- Tổng công việc: {total} | Hoàn thành: {done} | Quá hạn: {overdue}\n"
        f"- Tỷ lệ hoàn thành: {int(done/total*100) if total else 0}%\n"
    )

    # AI Memory
    memory_text = AIMemoryService.get_context_summary(user_id)

    return "\n".join(filter(None, [tasks_text, behavior_text, analytics_text, memory_text]))


def _get_system_prompt(context: str) -> str:
    from datetime import datetime
    now = datetime.now()
    return f"""Bạn là Doumar, trợ lý năng suất AI thông minh của TaskFlow.
Thời gian hiện tại: {now.strftime('%A %d/%m/%Y %H:%M')}

{context}

NGUYÊN TẮC TRẢ LỜI:
1. Phân tích công việc dựa trên dữ liệu thực tế được cung cấp ở trên.
2. Ưu tiên task có AI Score cao và đang quá hạn.
3. Gợi ý chia nhỏ task có estimated_minutes > 90 phút thành Pomodoro 25 phút.
4. Nhận biết giờ vàng làm việc và gợi ý task phù hợp.
5. Cảnh báo nếu user có dấu hiệu quá tải (nhiều task overdue, nhiều task high priority).
6. Phản hồi bằng Markdown rõ ràng, dùng danh sách và in đậm cho điểm quan trọng.
7. Ngắn gọn, thực tế, tập trung vào hành động cụ thể."""


def get_ai_reply(settings: dict, message: str, user_id: str,
                 session_id: str, image_path: str = None) -> str:
    return get_gemini_reply(message, user_id, session_id, image_path)


def get_gemini_reply(message: str, user_id: str, session_id: str,
                     image_path: str = None) -> str:
    try:
        # Update AI memory từ behavior data
        try:
            AIMemoryService.update_from_behavior(user_id)
        except Exception:
            pass

        client = genai.Client(api_key="AIzaSyC8mHmcAJRGNQb1i3inw_dXEWEV4K-bWsU")
        context = _build_context(user_id)
        sys_prompt = _get_system_prompt(context)

        session = ChatService.get_session(user_id, session_id)
        history = session["messages"] if session else []
        contents = []

        for i, msg in enumerate(history):
            role = "user" if msg["role"] == "user" else "model"
            is_last = (i == len(history) - 1)
            if is_last and role == "user" and image_path:
                parts = []
                with open(image_path, "rb") as f:
                    img_data = f.read()
                ext = image_path.split('.')[-1].lower()
                mime = f"image/{ext}" if ext in ["jpg","jpeg","png","webp"] else "image/jpeg"
                parts.append(types.Part.from_bytes(data=img_data, mime_type=mime))
                parts.append(types.Part.from_text(text="Hãy phân tích hình ảnh và tạo task phù hợp. " + msg["text"]))
                contents.append(types.Content(role=role, parts=parts))
            else:
                contents.append(types.Content(role=role, parts=[types.Part.from_text(text=msg["text"])]))

        if not contents:
            contents.append(types.Content(role="user", parts=[types.Part.from_text(text=message)]))

        response = client.models.generate_content(
            model='gemini-2.5-flash',
            contents=contents,
            config=types.GenerateContentConfig(system_instruction=sys_prompt)
        )
        return response.text

    except Exception as e:
        err = str(e)
        if "429" in err or "quota" in err.lower():
            return "⚠️ API đã hết lượt sử dụng. Vui lòng chờ hoặc kiểm tra Google AI Studio."
        return f"⚠️ Lỗi Gemini API: {err}"
