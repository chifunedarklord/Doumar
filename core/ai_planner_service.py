"""
TaskFlow - AI Planner Service
Detect planning intent, call Gemini for structured JSON plan, fallback gracefully.
"""
import re
import json
import logging
from datetime import datetime, date, timedelta
from typing import Optional

logger = logging.getLogger(__name__)

# ── Intent detection ──────────────────────────────────────────────────────────

_PLAN_TRIGGERS = [
    "kế hoạch", "lên kế hoạch", "sắp xếp lịch", "chia lịch",
    "lịch trình", "lập kế hoạch", "lên lịch", "chia thời gian",
    "sắp xếp", "phân chia lịch",
]

_INTENT_MAP = {
    "study_plan": [
        "ôn thi", "ôn luyện", "học bài", "lịch học", "ôn tập",
        "học tiếng", "ôn csdl", "ôn java", "ôn python", "học kỹ năng",
        "học môn", "đọc sách", "self study",
    ],
    "project_plan": [
        "đồ án", "báo cáo", "lập trình", "opengl", "làm app",
        "làm website", "làm phần mềm", "dự án", "làm đồ án",
        "làm báo cáo", "làm video", "làm game", "thiết kế",
    ],
    "travel_plan": [
        "đi chơi", "du lịch", "hẹn hò", "đi biển", "đi núi",
        "chuyến đi", "tham quan", "đi đà lạt", "đi hội an",
        "đi nước ngoài", "đi phượt",
    ],
    "work_plan": [
        "kế hoạch làm việc", "công việc tuần", "công việc ngày mai",
        "nhiệm vụ tuần", "kế hoạch công việc",
    ],
    "content_plan": [
        "nội dung mạng", "youtube", "tiktok", "instagram",
        "đăng bài", "làm content", "viết bài",
    ],
    "business_plan": [
        "bán hàng", "marketing", "kinh doanh", "chăm sóc khách",
        "doanh thu", "chiến lược",
    ],
    "health_plan": [
        "tập luyện", "gym", "ăn kiêng", "giảm cân", "chạy bộ",
        "thể dục", "sức khỏe", "tập thể thao", "cardio", "tăng cân",
    ],
    "daily_plan": [
        "ngày mai", "tuần này", "tuần tới", "kế hoạch hôm nay",
        "kế hoạch ngày", "kế hoạch tuần", "kế hoạch tháng",
    ],
    "event_plan": [
        "sinh nhật", "họp nhóm", "thuyết trình", "sự kiện",
        "tổ chức", "buổi tiệc", "seminar", "workshop",
    ],
}

# Intents strong enough to trigger planning without explicit trigger word
_STRONG_INTENTS = {"project_plan", "travel_plan", "study_plan", "health_plan"}

_REFINE_OPTIONS_BASE = [
    "Chi tiết từng bước hơn",
    "Chia theo giờ cụ thể",
    "Thêm deadline và nhắc việc",
    "Chia nhỏ thành task để lưu vào app",
    "Tối ưu theo thời gian rảnh",
    "Tối ưu theo ngân sách",
    "Thêm phương án dự phòng",
]

_REFINE_OPTIONS_BY_INTENT = {
    "travel_plan": [
        "Địa điểm cụ thể",
        "Quán ăn / cafe gợi ý",
        "Lịch trình theo giờ",
        "Phương án trời mưa",
        "Đồ cần chuẩn bị",
        "Tối ưu ngân sách",
    ],
    "study_plan": [
        "Chia lịch học theo ngày",
        "Thêm bài tập cần làm",
        "Thêm tài liệu học",
        "Thêm thời gian ôn tập",
        "Thêm deadline",
        "Tạo task lưu vào app",
    ],
    "project_plan": [
        "Chi tiết từng ngày",
        "Chia theo giờ cụ thể",
        "Thêm checklist kỹ thuật",
        "Phân công theo vai trò",
        "Thêm milestone",
        "Tạo task lưu vào app",
    ],
    "health_plan": [
        "Lịch tập theo ngày",
        "Kế hoạch ăn uống",
        "Thêm mục tiêu cụ thể",
        "Thêm bài tập dự phòng",
        "Theo dõi tiến độ",
    ],
}

_INTENT_LABELS = {
    "study_plan":    "📚 Học tập",
    "project_plan":  "💻 Dự án",
    "travel_plan":   "✈️ Du lịch",
    "work_plan":     "💼 Công việc",
    "content_plan":  "🎬 Nội dung",
    "business_plan": "🏪 Kinh doanh",
    "health_plan":   "💪 Sức khoẻ",
    "daily_plan":    "📅 Ngày / Tuần",
    "event_plan":    "🎉 Sự kiện",
    "unknown":       "📌 Kế hoạch",
}


def detect_plan_intent(text: str) -> Optional[str]:
    """Return intent string if text is a planning request, else None."""
    lower = text.lower()
    has_trigger = any(kw in lower for kw in _PLAN_TRIGGERS)

    matched = None
    for intent, keywords in _INTENT_MAP.items():
        if any(kw in lower for kw in keywords):
            matched = intent
            break

    if has_trigger:
        return matched or "daily_plan"
    if matched in _STRONG_INTENTS:
        return matched
    return None


def get_intent_label(intent: str) -> str:
    return _INTENT_LABELS.get(intent or "unknown", "📌 Kế hoạch")


def get_refine_options(intent: str) -> list:
    return _REFINE_OPTIONS_BY_INTENT.get(intent, _REFINE_OPTIONS_BASE)


# ── Planner system prompt ─────────────────────────────────────────────────────

def _get_planner_prompt(context: str) -> str:
    today = date.today()
    tomorrow = today + timedelta(days=1)
    return f"""Bạn là AI Planner cá nhân của TaskFlow. LUÔN trả về JSON hợp lệ. KHÔNG dùng markdown, KHÔNG có text ngoài JSON.

Hôm nay: {today.isoformat()} ({today.strftime('%A')})
Ngày mai: {tomorrow.isoformat()}

DỮ LIỆU NGƯỜI DÙNG (từ SQL Server):
{context}

=== SCHEMA: YÊU CẦU LẬP KẾ HOẠCH ===
{{
  "type": "plan_result",
  "intent": "study_plan|project_plan|travel_plan|work_plan|content_plan|business_plan|health_plan|daily_plan|event_plan|unknown",
  "title": "Tiêu đề kế hoạch ngắn gọn (tối đa 60 ký tự)",
  "summary": "Tóm tắt 1-2 câu về kế hoạch và mục tiêu",
  "assumptions": ["Giả định khi thiếu thông tin — luôn có nếu info chưa đủ"],
  "personalization_used": ["Danh sách thói quen/dữ liệu người dùng đã áp dụng, vd: giờ vàng 9h-11h, năng lượng cao buổi sáng, hay trì hoãn task work"],
  "plan": [
    {{
      "time_or_step": "Ngày 1 / Bước 1 / Buổi sáng 8:00-10:00",
      "title": "Tên giai đoạn / mục tiêu",
      "details": ["Hoạt động cụ thể 1", "Hoạt động cụ thể 2", "Hoạt động cụ thể 3"]
    }}
  ],
  "suggested_tasks": [
    {{
      "title": "Tên task ngắn gọn có thể thực hiện",
      "description": "Mô tả thêm nếu cần",
      "priority": "high|medium|low",
      "estimated_minutes": 60,
      "due_date": "YYYY-MM-DD hoặc null",
      "due_time": "HH:MM hoặc null",
      "category": "work|personal|health|finance|education"
    }}
  ],
  "follow_up_question": "Câu hỏi ngắn để tinh chỉnh kế hoạch (1 câu duy nhất)",
  "refine_options": ["Chi tiết từng bước hơn", "Chia theo giờ cụ thể", "Thêm deadline và nhắc việc", "Chia nhỏ thành task để lưu vào app", "Tối ưu theo thời gian rảnh", "Tối ưu theo ngân sách", "Thêm phương án dự phòng"]
}}

=== SCHEMA: CHAT THƯỜNG ===
{{"type": "normal_chat", "message": "Câu trả lời tiếng Việt, tối đa 150 từ, tự nhiên"}}

=== SCHEMA: TẠO TASK ĐƠN LẺ ===
{{"type": "task_create", "title": "...", "description": "...", "category": "work|personal|health|finance|education", "priority": "high|medium|low", "due_date": "YYYY-MM-DD hoặc null", "due_time": "HH:MM hoặc null", "estimated_minutes": 30, "reminder_minutes": 15}}

=== NGUYÊN TẮC BẮT BUỘC ===
1. LUÔN tạo kế hoạch nháp ngay — KHÔNG hỏi thông tin trước rồi mới làm
2. Nếu thiếu thông tin (địa điểm, ngân sách, v.v.): tạo với giả định hợp lý, ghi rõ vào "assumptions"
3. plan phải có 3-7 bước tùy loại, mỗi bước có 2-4 details
4. suggested_tasks phải có 3-6 task cụ thể, có thể lưu vào app ngay
5. Luôn có follow_up_question (1 câu duy nhất) và refine_options
6. personalization_used: liệt kê thói quen/dữ liệu trong [LEARNED HABITS] và [CURRENT STATE] đã dùng để lập kế hoạch
7. Kế hoạch phải cá nhân hóa: task khó → giờ vàng, task nhẹ → giờ thấp năng lượng, category hay trì hoãn → chia nhỏ
8. Ngôn ngữ: Tiếng Việt hoàn toàn
9. JSON thuần túy — KHÔNG backtick, KHÔNG ```json"""


# ── Main API call ─────────────────────────────────────────────────────────────

def get_plan_response(message: str, user_id: str,
                      last_plan: dict = None, image_path: str = None) -> dict:
    """
    Call Gemini for a structured planning response.
    Returns dict with 'type' key: plan_result | normal_chat | task_create.
    Supports optional image_path for image analysis.
    Never raises — always returns a valid dict.
    """
    try:
        from utils.ai_helper import _API_KEY, _MODEL_CHAIN, _call_gemini, _get_cached_context
    except Exception:
        logger.exception("Failed to import ai_helper")
        return _make_fallback_plan(message, detect_plan_intent(message))

    if not _API_KEY:
        logger.warning("No API key — using fallback plan")
        return _make_fallback_plan(message, detect_plan_intent(message))

    try:
        context = _get_cached_context(user_id)
    except Exception:
        context = ""

    sys_prompt = _get_planner_prompt(context)

    # When refining, include previous plan summary in user message
    user_content = message
    if last_plan and last_plan.get("type") == "plan_result":
        plan_steps = last_plan.get("plan", [])
        steps_text = "\n".join(
            f"  - {s.get('time_or_step', '')}: {s.get('title', '')}"
            for s in plan_steps[:5]
        )
        user_content = (
            f"[Đang chỉnh sửa kế hoạch: {last_plan.get('title', '')}]\n"
            f"Tóm tắt hiện tại: {last_plan.get('summary', '')}\n"
            f"Các bước hiện tại:\n{steps_text}\n\n"
            f"[Yêu cầu chỉnh sửa]: {message}"
        )

    try:
        from google import genai
        from google.genai import types
        import time as _time

        client = genai.Client(api_key=_API_KEY)

        # Build parts: image first (if provided), then text
        parts = []
        if image_path:
            try:
                with open(image_path, "rb") as f:
                    img_data = f.read()
                ext = image_path.rsplit(".", 1)[-1].lower()
                mime_map = {"jpg": "image/jpeg", "jpeg": "image/jpeg",
                            "png": "image/png", "webp": "image/webp",
                            "gif": "image/gif", "bmp": "image/bmp"}
                mime = mime_map.get(ext, "image/jpeg")
                parts.append(types.Part.from_bytes(data=img_data, mime_type=mime))
            except Exception:
                logger.warning("Failed to load image for plan response: %s", image_path)

        parts.append(types.Part.from_text(text=user_content))
        contents = [types.Content(role="user", parts=parts)]

        last_err = None
        for model in _MODEL_CHAIN:
            for attempt in range(2):
                try:
                    resp = _call_gemini(client, model, contents, sys_prompt)
                    result = _parse_response(resp.text, message)
                    return result
                except Exception as e:
                    last_err = str(e)
                    if attempt == 0:
                        _time.sleep(1.0)

        logger.warning("All models failed: %s", last_err)
        return _make_fallback_plan(message, detect_plan_intent(message))

    except Exception:
        logger.exception("get_plan_response unexpected error")
        return _make_fallback_plan(message, detect_plan_intent(message))


# ── Response parsing ──────────────────────────────────────────────────────────

def _parse_response(raw: str, original_message: str) -> dict:
    """Parse Gemini output into a dict. Falls back gracefully."""
    if not raw or not raw.strip():
        return _make_fallback_plan(original_message, detect_plan_intent(original_message))

    text = re.sub(r"^```[a-z]*\n?", "", raw.strip()).rstrip("`").strip()

    # Find outermost JSON object
    json_match = re.search(r"\{[\s\S]*\}", text)
    if json_match:
        text = json_match.group(0)

    try:
        data = json.loads(text)
        if not isinstance(data, dict) or "type" not in data:
            raise ValueError("No 'type' key")

        # Ensure required plan fields exist
        if data["type"] == "plan_result":
            data.setdefault("assumptions", [])
            data.setdefault("personalization_used", [])
            data.setdefault("plan", [])
            data.setdefault("suggested_tasks", [])
            data.setdefault("follow_up_question",
                            "Bạn muốn mình chỉnh kế hoạch chi tiết hơn theo phần nào?")
            data.setdefault("refine_options", _REFINE_OPTIONS_BASE)

        return data

    except Exception as e:
        logger.warning("JSON parse failed: %s | preview: %.200s", e, raw)
        intent = detect_plan_intent(original_message)
        if intent:
            return _make_fallback_plan(original_message, intent)
        # Return raw text as normal chat if not a plan request
        return {"type": "normal_chat", "message": raw[:600]}


# ── Fallback plan ─────────────────────────────────────────────────────────────

def _make_fallback_plan(message: str, intent: str = None) -> dict:
    """Generic plan template when AI is unavailable."""
    intent = intent or "unknown"
    today = date.today()
    tomorrow = (today + timedelta(days=1)).isoformat()
    refine_opts = get_refine_options(intent)

    return {
        "type": "plan_result",
        "intent": intent,
        "title": f"Kế hoạch: {message[:55]}{'...' if len(message) > 55 else ''}",
        "summary": "Kế hoạch mẫu — AI hiện không khả dụng. Bạn có thể chỉnh chi tiết hơn bên dưới.",
        "assumptions": [
            "Thông tin chi tiết chưa được cung cấp",
            "Tạm giả định thời gian và nguồn lực mặc định",
            "AI đang offline — kế hoạch được tạo bằng mẫu dự phòng",
        ],
        "personalization_used": [],
        "plan": [
            {
                "time_or_step": "Bước 1",
                "title": "Xác định mục tiêu rõ ràng",
                "details": [
                    "Ghi rõ kết quả cần đạt được",
                    "Đặt deadline cụ thể",
                    "Xác định tài nguyên cần có",
                ],
            },
            {
                "time_or_step": "Bước 2",
                "title": "Chia nhỏ công việc",
                "details": [
                    "Tách việc lớn thành các phần nhỏ 30-60 phút",
                    "Sắp xếp theo thứ tự ưu tiên",
                    "Ước tính thời gian cho từng phần",
                ],
            },
            {
                "time_or_step": "Bước 3",
                "title": "Thực hiện và theo dõi tiến độ",
                "details": [
                    "Bắt đầu với task quan trọng nhất",
                    "Dùng Focus Timer để tập trung",
                    "Cập nhật trạng thái task sau khi xong",
                ],
            },
        ],
        "suggested_tasks": [
            {
                "title": "Xác định mục tiêu và timeline",
                "description": "Ghi rõ mục tiêu, deadline và tài nguyên cần có",
                "priority": "high",
                "estimated_minutes": 30,
                "due_date": tomorrow,
                "due_time": None,
                "category": "personal",
            },
            {
                "title": "Liệt kê công việc cần làm",
                "description": "Chia nhỏ thành các task cụ thể và ước tính thời gian",
                "priority": "high",
                "estimated_minutes": 45,
                "due_date": tomorrow,
                "due_time": None,
                "category": "personal",
            },
            {
                "title": "Bắt đầu thực hiện bước đầu tiên",
                "description": "Dùng Focus Timer để tập trung làm không gián đoạn",
                "priority": "medium",
                "estimated_minutes": 60,
                "due_date": tomorrow,
                "due_time": None,
                "category": "personal",
            },
        ],
        "follow_up_question": "Bạn muốn mình chỉnh kế hoạch chi tiết hơn theo phần nào?",
        "refine_options": refine_opts,
    }
