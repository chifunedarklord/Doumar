"""
TaskFlow - AI Helper
Gemini API với retry logic, exponential backoff, và model fallback.
"""
import os
import time
from pathlib import Path
from google import genai
from google.genai import types
from core.services import TaskService, ChatService, BehaviorService, AIMemoryService


def _load_dotenv():
    """Load .env file from project root without requiring python-dotenv."""
    env_path = Path(__file__).parent.parent / ".env"
    if not env_path.exists():
        return
    for line in env_path.read_text(encoding="utf-8").splitlines():
        line = line.strip()
        if not line or line.startswith("#") or "=" not in line:
            continue
        k, v = line.split("=", 1)
        os.environ.setdefault(k.strip(), v.strip().strip('"').strip("'"))


_load_dotenv()

# Model fallback chain: thử lần lượt khi gặp lỗi
_MODEL_CHAIN = [
    "gemini-2.5-flash",
    "gemini-2.0-flash",
    "gemini-1.5-flash",
]
_API_KEY = os.getenv("GEMINI_API_KEY", "")
if not _API_KEY:
    print("[TaskFlow WARNING] GEMINI_API_KEY chưa được cấu hình.")
    print("[TaskFlow WARNING] Tạo file .env từ .env.example và thêm API key.")
_MAX_RETRIES = 2
_RETRY_DELAY = 1.5  # seconds, doubled each retry

# ── Context Cache (tránh query DB mỗi tin) ──────────────────
_context_cache: dict = {}   # {user_id: (timestamp, context_str)}
_CACHE_TTL = 30             # seconds


def _build_context(user_id: str) -> str:
    """Xây dựng context có cấu trúc rõ ràng cho AI."""
    from core.database import Storage
    from datetime import date as _date
    all_users = Storage.get_users()
    user = next((u for u in all_users if u.id == user_id), None)
    tasks = TaskService.get_tasks(user_id)
    today_str = _date.today().isoformat()

    # ── Phân loại task ────────────────────────────────────────
    active = [t for t in tasks if t.status not in ("done", "cancelled")]
    overdue_tasks   = sorted([t for t in active if t.is_overdue],
                             key=lambda t: t.due_date or "")
    today_tasks     = [t for t in active if t.due_date == today_str and not t.is_overdue]
    upcoming_tasks  = sorted(
        [t for t in active if t.due_date and t.due_date > today_str],
        key=lambda t: (t.due_date, -t.ai_priority_score)
    )[:5]
    no_date_tasks   = [t for t in active if not t.due_date][:3]
    done_count      = sum(1 for t in tasks if t.status == "done")
    total_count     = len(tasks)
    completion_pct  = int(done_count / total_count * 100) if total_count else 0

    def _fmt_task(t) -> str:
        pri_icon = {"high": "🔴", "medium": "🟡", "low": "🟢"}.get(t.priority, "⚪")
        energy_icon = {"high": "⚡⚡", "medium": "⚡", "low": "💤"}.get(
            getattr(t, "energy_required", "medium"), "⚡")
        days = t.days_until_due
        deadline_str = ""
        if days is not None:
            if days < 0:   deadline_str = f" · ⚠️ quá hạn {abs(days)}n"
            elif days == 0: deadline_str = " · 🔔 hạn hôm nay"
            elif days == 1: deadline_str = " · hạn ngày mai"
            else:           deadline_str = f" · còn {days} ngày"
        score = getattr(t, "ai_priority_score", 50)
        est   = getattr(t, "estimated_minutes", 30)
        return (f"  • {pri_icon} **{t.title}**{deadline_str}"
                f" | {energy_icon} {est}p | score {score:.0f}")

    sections = []

    # Tổng quan
    sections.append(
        f"📊 TỔNG QUAN: {total_count} task · {done_count} xong ({completion_pct}%)"
        f" · {len(overdue_tasks)} quá hạn · {len(today_tasks)} hôm nay"
    )

    # Quá hạn
    if overdue_tasks:
        lines = [f"⚠️ QUÁ HẠN ({len(overdue_tasks)} task) — cần xử lý ngay:"]
        lines += [_fmt_task(t) for t in overdue_tasks[:4]]
        sections.append("\n".join(lines))

    # Hôm nay
    if today_tasks:
        lines = [f"📅 HÔM NAY ({len(today_tasks)} task):"]
        lines += [_fmt_task(t) for t in sorted(today_tasks, key=lambda t: -t.ai_priority_score)[:4]]
        sections.append("\n".join(lines))

    # Sắp tới
    if upcoming_tasks:
        lines = ["📌 SẮP TỚI (top 5 theo độ ưu tiên):"]
        lines += [_fmt_task(t) for t in upcoming_tasks]
        sections.append("\n".join(lines))

    # Không có deadline
    if no_date_tasks:
        lines = ["📝 CHƯA ĐẶT DEADLINE:"]
        lines += [f"  • {t.title}" for t in no_date_tasks]
        sections.append("\n".join(lines))

    # ── Trạng thái người dùng ─────────────────────────────────
    peak_hours = BehaviorService.get_peak_hours(user_id)
    productivity_score = BehaviorService.get_productivity_score(user_id)
    peak_str = ", ".join(f"{h:02d}h" for h in peak_hours) if peak_hours else "chưa học được"

    state_lines = ["👤 TRẠNG THÁI USER:"]
    state_lines.append(f"  • Năng suất tuần: **{productivity_score:.0f}/100** · Giờ vàng: {peak_str}")

    if user:
        live_energy = AIMemoryService.recall_value(user_id, "state", "estimated_energy")
        live_stress = AIMemoryService.recall_value(user_id, "state", "estimated_stress")
        live_mood   = AIMemoryService.recall_value(user_id, "state", "estimated_mood")

        energy_val = int(live_energy) if live_energy is not None else getattr(user, "energy_level", 7)
        stress_val = int(live_stress) if live_stress is not None else getattr(user, "stress_level", 5)
        energy_src = "check-in" if live_energy is not None else "mặc định"
        stress_src = "check-in" if live_stress is not None else "mặc định"

        energy_bar = "▓" * energy_val + "░" * (10 - energy_val)
        stress_bar = "▓" * stress_val  + "░" * (10 - stress_val)
        state_lines.append(f"  • Năng lượng [{energy_bar}] **{energy_val}/10** ({energy_src})")
        state_lines.append(f"  • Stress      [{stress_bar}] **{stress_val}/10** ({stress_src})")
        if live_mood is not None:
            mood_labels = {1: "rất tệ", 2: "tệ", 3: "bình thường", 4: "tốt", 5: "tuyệt vời"}
            state_lines.append(f"  • Tâm trạng: **{mood_labels.get(int(live_mood), str(live_mood))}** ({int(live_mood)}/5)")

        sleep  = getattr(user, "sleep_time", "23:00")
        wake   = getattr(user, "wake_time", "07:00")
        wstart = getattr(user, "work_start", "08:00")
        wend   = getattr(user, "work_end", "18:00")
        state_lines.append(f"  • Giờ làm: {wstart}–{wend} · Ngủ: {sleep}–{wake}")

        extras = []
        for key, label in [("role", "Vai trò"), ("main_goal", "Mục tiêu"), ("work_style", "Phong cách")]:
            val = AIMemoryService.recall_value(user_id, "preference", key)
            if val:
                extras.append(f"{label}: {val}")
        if extras:
            state_lines.append("  • " + " · ".join(extras))

    sections.append("\n".join(state_lines))

    # AI Memory summary
    memory_text = AIMemoryService.get_context_summary(user_id)
    if memory_text:
        sections.append(memory_text)

    return "\n\n".join(sections)


def _get_cached_context(user_id: str) -> str:
    """Trả về cached context nếu còn hạn, nếu không thì rebuild."""
    cached = _context_cache.get(user_id)
    if cached:
        ts, ctx = cached
        if time.time() - ts < _CACHE_TTL:
            return ctx
    ctx = _build_context(user_id)
    _context_cache[user_id] = (time.time(), ctx)
    return ctx


def invalidate_context_cache(user_id: str):
    """Gọi khi user lưu task mới — buộc rebuild context lần sau."""
    _context_cache.pop(user_id, None)


def _get_system_prompt(context: str) -> str:
    from datetime import datetime
    now = datetime.now()
    hour = now.hour
    greeting = (
        "Chào buổi sáng" if 5 <= hour < 12
        else "Chào buổi chiều" if 12 <= hour < 18
        else "Chào buổi tối" if 18 <= hour < 22
        else "Đêm khuya rồi"
    )
    return f"""Bạn là **Doumar** — trợ lý năng suất AI của TaskFlow.
Thời gian hiện tại: {now.strftime('%H:%M, %A %d/%m/%Y')} ({greeting})

━━━ DỮ LIỆU NGƯỜI DÙNG ━━━
{context}
━━━━━━━━━━━━━━━━━━━━━━━━━━

## DANH TÍNH & PHONG CÁCH

Bạn là Doumar — một người bạn đồng hành thông minh, thực tế, không vòng vo.
Giọng điệu: chuyên nghiệp nhưng gần gũi, thẳng thắn, đôi khi hài hước nhẹ.
Ngôn ngữ: Tiếng Việt tự nhiên — không cứng nhắc, không robot.

## QUY TẮC ĐỊNH DẠNG — BẮT BUỘC

**Độ dài:** Tối đa 120 từ. Chỉ viết dài hơn khi user hỏi phân tích cụ thể.

**Cấu trúc chuẩn cho mọi câu trả lời:**
```
[1 dòng tóm tắt — nêu thẳng vấn đề hoặc kết luận chính]

• [Hành động / thông tin 1]
• [Hành động / thông tin 2]
• [Hành động / thông tin 3 — nếu cần]
```

**Quy tắc bôi đậm:**
- `**tên task**` — luôn bôi đậm tên task
- `**HH:MM**` — giờ cụ thể
- `**X ngày**`, `**X%**`, `**X/10**` — con số quan trọng
- `**→ hành động**` — bước cần làm ngay

**Dấu hiệu trực quan:**
- 🔴 quá hạn / khẩn cấp  |  🟡 sắp đến  |  🟢 ổn
- ⚡ cần năng lượng cao  |  💤 nhẹ nhàng  |  🎯 focus
- ✅ đã xong  |  ⚠️ cảnh báo  |  💡 gợi ý

## LOGIC ƯU TIÊN

Khi gợi ý task, áp dụng theo thứ tự:
1. Task quá hạn → xử lý NGAY
2. Task hôm nay + AI Score cao
3. Task phù hợp với năng lượng hiện tại của user
4. Task sắp đến hạn (≤3 ngày)

## CÁC TÌNH HUỐNG ĐẶC BIỆT

**Khi user hỏi "làm gì bây giờ":**
→ Nêu đúng 2-3 task ưu tiên nhất. Không giải thích lý do trừ khi được hỏi.

**Khi năng lượng user ≤ 3/10:**
→ Chỉ gợi ý task nhẹ (💤) hoặc quick wins. Không push task khó.

**Khi stress ≥ 7/10:**
→ Thêm 1 gợi ý nghỉ ngơi/break. Không tạo áp lực thêm.

**Khi đêm khuya (01:00–04:00):**
→ Khuyên đi ngủ ngay. Tuyệt đối không gợi ý làm thêm việc.

**Khi user hỏi phân tích / báo cáo:**
→ Có thể dùng thêm headers (##) và bảng nếu cần. Tối đa 200 từ.

**Khi user hỏi câu đơn giản:**
→ Trả lời 1-2 câu. Không thêm bullet points nếu không cần thiết.

## CẤM TUYỆT ĐỐI

✗ Không mở đầu bằng "Xin chào!", "Chắc chắn rồi!", "Tuyệt vời!" hay các cụm sáo rỗng
✗ Không nhắc lại toàn bộ danh sách task — chỉ nêu những gì liên quan
✗ Không giải thích điều user đã biết
✗ Không kết thúc bằng "Hãy cho tôi biết nếu bạn cần thêm gì!"
✗ Không dùng tiếng Anh trừ tên riêng hoặc thuật ngữ kỹ thuật"""


def _is_retryable(err_str: str) -> bool:
    """Xác định lỗi có thể retry không."""
    retryable_codes = ("503", "500", "429", "unavailable", "overloaded",
                       "high demand", "temporarily", "try again")
    el = err_str.lower()
    return any(code in el for code in retryable_codes)


def _is_quota_error(err_str: str) -> bool:
    return "429" in err_str or "quota" in err_str.lower() or "rate" in err_str.lower()


def _call_gemini(client, model: str, contents, sys_prompt: str):
    """Gọi Gemini API với một model cụ thể."""
    config = types.GenerateContentConfig(
        system_instruction=sys_prompt,
        # Tắt extended thinking — giảm latency đáng kể cho gemini-2.5-flash
        thinking_config=types.ThinkingConfig(thinking_budget=0),
    )
    return client.models.generate_content(
        model=model,
        contents=contents,
        config=config,
    )


def get_ai_reply(settings: dict, message: str, user_id: str,
                 session_id: str, image_path: str = None) -> str:
    return get_gemini_reply(message, user_id, session_id, image_path)


def get_gemini_reply(message: str, user_id: str, session_id: str,
                     image_path: str = None) -> str:
    try:
        if not _API_KEY:
            return (
                "⚠️ **Chưa cấu hình API key**\n\n"
                "Để dùng AI assistant, bạn cần:\n"
                "1. Lấy API key tại Google AI Studio (miễn phí)\n"
                "2. Tạo file `.env` trong thư mục app\n"
                "3. Thêm dòng: `GEMINI_API_KEY=your_key_here`\n"
                "4. Khởi động lại app"
            )
        client = genai.Client(api_key=_API_KEY)
        context = _get_cached_context(user_id)
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
                mime = f"image/{ext}" if ext in ["jpg", "jpeg", "png", "webp"] else "image/jpeg"
                parts.append(types.Part.from_bytes(data=img_data, mime_type=mime))
                parts.append(types.Part.from_text(
                    text="Hãy phân tích hình ảnh và tạo task phù hợp. " + msg["text"]))
                contents.append(types.Content(role=role, parts=parts))
            else:
                contents.append(types.Content(
                    role=role, parts=[types.Part.from_text(text=msg["text"])]))

        if not contents:
            contents.append(types.Content(
                role="user", parts=[types.Part.from_text(text=message)]))

        # ── Retry loop với model fallback ──────────────────────────
        last_error = None
        for model in _MODEL_CHAIN:
            for attempt in range(_MAX_RETRIES):
                try:
                    response = _call_gemini(client, model, contents, sys_prompt)
                    return response.text
                except Exception as e:
                    err = str(e)
                    last_error = err

                    if _is_quota_error(err):
                        # Quota exhausted — không retry, thử model kế tiếp ngay
                        break

                    if _is_retryable(err):
                        wait = _RETRY_DELAY * (2 ** attempt)
                        time.sleep(wait)
                        continue

                    # Lỗi không thể retry (auth, bad request, ...)
                    raise

            continue

        # Tất cả models đã thất bại
        if last_error and _is_quota_error(last_error):
            return "⚠️ API đã hết lượt sử dụng. Vui lòng thử lại sau vài phút."
        return (
            "⚠️ Gemini API tạm thời quá tải. "
            "Hệ thống đã thử lại 3 lần với nhiều model nhưng không thành công. "
            "Vui lòng thử lại sau 1-2 phút."
        )

    except Exception as e:
        err = str(e)
        if _is_quota_error(err):
            return "⚠️ API đã hết lượt sử dụng. Vui lòng chờ hoặc kiểm tra Google AI Studio."
        if _is_retryable(err):
            return (
                "⚠️ Gemini API đang quá tải (503). "
                "Đây là lỗi tạm thời từ phía Google. Vui lòng thử lại sau 1-2 phút."
            )
        return f"⚠️ Lỗi Gemini API: {err}"
