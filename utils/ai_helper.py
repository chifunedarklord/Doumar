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
    "gemini-3.1-flash-lite",
]
_API_KEY = '' if os.getenv('TASKFLOW_API_URL') else os.getenv("GEMINI_API_KEY", "")
if not _API_KEY and not os.getenv('TASKFLOW_API_URL'):
    print("[TaskFlow WARNING] GEMINI_API_KEY chưa được cấu hình.")
    print("[TaskFlow WARNING] Tạo file .env từ .env.example và thêm API key.")
_MAX_RETRIES = 2
_RETRY_DELAY = 1.5  # seconds, doubled each retry

# ── Context Cache (tránh query DB mỗi tin) ──────────────────
_context_cache: dict = {}   # {user_id: (timestamp, context_str)}
_CACHE_TTL = 30             # seconds


def _build_context(user_id: str) -> str:
    """Build structured AI context with labeled sections from SQL Server tables."""
    from core.database import Storage
    from datetime import date as _date

    today_str = _date.today().isoformat()
    all_users = Storage.get_users()
    user = next((u for u in all_users if u.id == user_id), None)
    tasks = TaskService.get_tasks(user_id)
    events = Storage.get_behavior_events(user_id, limit=100)
    sessions = Storage.get_work_sessions(user_id, limit=30)

    sections = []

    from zoneinfo import ZoneInfo
    from datetime import datetime
    import json
    zone = getattr(user, "timezone", None) or "Asia/Ho_Chi_Minh"
    now = datetime.now(ZoneInfo(zone))
    today_str = now.date().isoformat()
    sections.append(f"[ACCOUNT TIME] {now.isoformat()} | múi giờ: {zone}")
    profile = AIMemoryService.recall_value(user_id, 'preference', 'planning_profile')
    if not isinstance(profile, dict):
        profile = (user.settings or {}).get("planning_profile", {}) if user else {}
    sections.append("[USER PROFILE — tự khai, đã xác nhận]\n" + json.dumps(profile, ensure_ascii=False))
    sections.append("Các câu chưa có trong hồ sơ là chưa biết. Các bộ nhớ khác có thể là suy luận cũ; không coi là sở thích đã xác nhận.")
    from core.workspace import Workspace
    from core.task_focus import TaskFocus
    sections.append("[CURRENT FOCUS TARGET — người dùng chủ động chọn]\n" + json.dumps(TaskFocus.current(user_id), ensure_ascii=False))
    sections.append("[SAVED CALENDAR — lịch đã lưu, không tự dời]\n" + json.dumps(Workspace.blocks(user_id), ensure_ascii=False))

    # ── [CURRENT STATE] — từ ai_memory (check-in) + user_behavior ─
    state_lines = ["[CURRENT STATE]"]
    peak_hours = BehaviorService.get_peak_hours(user_id) if sessions else []
    productivity_score = BehaviorService.get_productivity_score(user_id)
    peak_str = ", ".join(f"{h:02d}h" for h in peak_hours) if peak_hours else "chưa xác định"

    live_energy = AIMemoryService.recall_value(user_id, "state", "estimated_energy")
    live_stress = AIMemoryService.recall_value(user_id, "state", "estimated_stress")
    live_mood   = AIMemoryService.recall_value(user_id, "state", "estimated_mood")

    energy_val = int(live_energy) if live_energy is not None else (
        getattr(user, "energy_level", 7) if user else 7)
    stress_val = int(live_stress) if live_stress is not None else (
        getattr(user, "stress_level", 5) if user else 5)
    energy_src = "ước tính chưa xác nhận"
    stress_src = "ước tính chưa xác nhận"

    energy_bar = "▓" * energy_val + "░" * (10 - energy_val)
    stress_bar = "▓" * stress_val  + "░" * (10 - stress_val)
    state_lines.append(f"Năng lượng: {energy_val}/10 ({energy_src})" if live_energy is not None else "Năng lượng: chưa biết")
    state_lines.append(f"Áp lực: {stress_val}/10 ({stress_src})" if live_stress is not None else "Mức áp lực: chưa biết")
    if live_mood is not None:
        mood_labels = {1: "rất tệ", 2: "tệ", 3: "bình thường", 4: "tốt", 5: "tuyệt vời"}
        state_lines.append(f"Tâm trạng: {mood_labels.get(int(live_mood), str(live_mood))}")
    state_lines.append(f"Năng suất tuần: {productivity_score:.0f}/100")
    state_lines.append(f"Khung giờ quan sát chưa xác nhận: {peak_str}")
    # AI rule hints based on live state
    if energy_val <= 3:
        state_lines.append("⚠ NĂNG LƯỢNG THẤP → chỉ gợi ý task nhẹ, không push việc khó")
    if stress_val >= 7:
        state_lines.append("⚠ STRESS CAO → thêm nghỉ ngắn giữa các task, giảm áp lực")
    sections.append("\n".join(state_lines))

    # ── [TASK SUMMARY] — từ bảng tasks ───────────────────────────
    active        = [t for t in tasks if t.status not in ("done", "cancelled")]
    overdue_tasks = sorted([t for t in active if t.is_overdue],
                           key=lambda t: t.due_date or "")
    today_tasks   = [t for t in active if t.due_date == today_str and not t.is_overdue]
    upcoming_tasks = sorted(
        [t for t in active if t.due_date and t.due_date > today_str],
        key=lambda t: (t.due_date, -t.ai_priority_score)
    )[:5]
    no_date_tasks = [t for t in active if not t.due_date][:3]
    done_count    = sum(1 for t in tasks if t.status == "done")
    total_count   = len(tasks)
    completion_pct = int(done_count / total_count * 100) if total_count else 0

    def _fmt_task(t) -> str:
        pri_icon = {"high": "🔴", "medium": "🟡", "low": "🟢"}.get(t.priority, "⚪")
        energy_icon = {"high": "⚡⚡", "medium": "⚡", "low": "💤"}.get(
            getattr(t, "energy_required", "medium"), "⚡")
        days = t.days_until_due
        deadline_str = ""
        if days is not None:
            if days < 0:    deadline_str = f" · ⚠️ quá hạn {abs(days)}n"
            elif days == 0: deadline_str = " · 🔔 hạn hôm nay"
            elif days == 1: deadline_str = " · hạn ngày mai"
            else:           deadline_str = f" · còn {days} ngày"
        score = getattr(t, "ai_priority_score", 50)
        est   = getattr(t, "estimated_minutes", 30)
        return (f"  • {pri_icon} {t.title}{deadline_str} | {energy_icon} {est}p | score {score:.0f}")

    task_lines = ["[TASK SUMMARY]"]
    task_lines.append(
        f"Tổng quan: {total_count} task · {done_count} xong ({completion_pct}%)"
        f" · {len(overdue_tasks)} quá hạn · {len(today_tasks)} hôm nay"
    )
    if overdue_tasks:
        task_lines.append(f"\n⚠️ QUÁ HẠN ({len(overdue_tasks)} task) — cần xử lý ngay:")
        task_lines += [_fmt_task(t) for t in overdue_tasks[:4]]
    if today_tasks:
        task_lines.append(f"\n📅 HÔM NAY ({len(today_tasks)} task):")
        task_lines += [_fmt_task(t) for t in sorted(
            today_tasks, key=lambda t: -t.ai_priority_score)[:4]]
    if upcoming_tasks:
        task_lines.append("\n📌 SẮP TỚI (top 5 theo độ ưu tiên):")
        task_lines += [_fmt_task(t) for t in upcoming_tasks]
    if no_date_tasks:
        task_lines.append("\n📝 CHƯA ĐẶT DEADLINE:")
        task_lines += [f"  • {t.title}" for t in no_date_tasks]
    sections.append("\n".join(task_lines))

    # ── [LEARNED HABITS] — từ user_behavior + work_sessions ──────
    habits_lines = ["[LEARNED HABITS]"]
    try:
        from core.intelligence.behavior_learner import BehaviorLearner

        if peak_hours:
            hours_str = ", ".join(f"{h}:00" for h in sorted(peak_hours)[:4])
            habits_lines.append(f"Xu hướng giờ hoạt động (chưa xác nhận): {hours_str}")

        delay_patterns = BehaviorLearner.learn_delay_patterns(events)
        if delay_patterns:
            sorted_delays = sorted(delay_patterns.items(), key=lambda x: -x[1])
            worst_cats = [c for c, v in sorted_delays[:2] if v > 0]
            if worst_cats:
                habits_lines.append(
                    f"Category hay trì hoãn: {', '.join(worst_cats)} → có thể đề xuất chia nhỏ, chờ xác nhận")

        completed_sessions = [s for s in sessions
                               if isinstance(s, dict) and s.get("duration_minutes", 0) > 0]
        if completed_sessions:
            avg_focus = sum(s.get("duration_minutes", 0)
                            for s in completed_sessions) / len(completed_sessions)
            avg_quality = sum(s.get("focus_quality", 5)
                              for s in completed_sessions) / len(completed_sessions)
            habits_lines.append(f"Focus trung bình: {avg_focus:.0f} phút/phiên, chất lượng {avg_quality:.1f}/10")

        done_cats: dict = {}
        for t in tasks:
            if t.status == "done" and t.category:
                done_cats[t.category] = done_cats.get(t.category, 0) + 1
        if done_cats:
            best_cat = max(done_cats.items(), key=lambda x: x[1])[0]
            habits_lines.append(f"Category hoàn thành nhiều nhất: {best_cat}")
    except Exception:
        pass
    if len(habits_lines) == 1:
        habits_lines.append("Chưa đủ dữ liệu (cần thêm hoạt động để học thói quen)")
    sections.append("\n".join(habits_lines))

    # ── [RECENT BEHAVIOR] — từ user_behavior ─────────────────────
    recent_lines = ["[RECENT BEHAVIOR]"]
    _ev_labels = {
        "task_complete":   "✅ Hoàn thành task",
        "task_delay":      "⏰ Trì hoãn task",
        "session_start":   "🎯 Bắt đầu focus",
        "session_end":     "⏹ Kết thúc focus",
        "chat_sent":       "💬 Gửi tin nhắn AI",
        "plan_save_tasks": "📋 Lưu task từ kế hoạch",
        "plan_refine":     "🔧 Tinh chỉnh kế hoạch",
        "task_create":     "➕ Tạo task mới",
    }
    if events:
        for ev in events[:8]:
            ev_type = ev.get("event_type", "")
            ts_str  = (ev.get("timestamp", "") or "")[:16]
            ev_data = ev.get("event_data", {}) or {}
            label   = _ev_labels.get(ev_type, f"· {ev_type}")
            if ev_type == "task_complete":
                title = ev_data.get("title", ev_data.get("task_id", "")[:12])
                if title:
                    label += f": {title}"
            elif ev_type == "session_end":
                dur  = ev_data.get("duration_minutes", 0)
                qual = ev_data.get("focus_quality", 5)
                label += f" ({dur} phút, chất lượng {qual}/10)"
            elif ev_type == "plan_refine":
                opt = ev_data.get("option", "")
                if opt:
                    label += f": {opt}"
            recent_lines.append(f"  {ts_str}  {label}" if ts_str else f"  {label}")
    else:
        recent_lines.append("  Chưa có hoạt động nào được ghi lại")
    sections.append("\n".join(recent_lines))

    # ── [AI MEMORY] — từ bảng ai_memory ──────────────────────────
    memory_text = AIMemoryService.get_context_summary(user_id)
    sections.append(f"[AI MEMORY — có thể chứa suy luận chưa xác nhận]\n{memory_text}" if memory_text
                    else "[AI MEMORY]\nChưa có bộ nhớ AI nào được lưu")
    memories = Storage.get_memory(user_id)
    sections.append("[ACCOUNT MEMORIES — loại, độ tin cậy và nguồn cần được phân biệt]\n" +
                    json.dumps([{k: m.get(k) for k in ('memory_type', 'key', 'value', 'confidence', 'updated_at')}
                                for m in memories if m.get('memory_type') in ('preference', 'habit', 'pattern', 'goal', 'constraint', 'profile', 'state', 'performance', 'project')][:80], ensure_ascii=False))

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
    from core.ai_policy import chat_instruction
    return chat_instruction(context)


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
    from core.ai_policy import DOUMAR_POLICY
    if not sys_prompt.startswith(DOUMAR_POLICY):
        sys_prompt = DOUMAR_POLICY + '\n\n' + sys_prompt
    config = types.GenerateContentConfig(
        system_instruction=sys_prompt,
        # Keep interactive requests responsive with a supported Gemini 3 setting.
        thinking_config=types.ThinkingConfig(thinking_level=types.ThinkingLevel.LOW),
    )
    return client.models.generate_content(
        model=model,
        contents=contents,
        config=config,
    )


def parse_natural_task(text: str, user_id: str) -> dict:
    """Parse natural language (Vietnamese) into task JSON fields.
    Returns dict with keys: title, description, category, priority,
    due_date, due_time, estimated_minutes, reminder_minutes.
    Falls back to basic heuristics if API unavailable."""
    from datetime import date, timedelta
    import re, json as _json

    today = date.today()

    def _fallback() -> dict:
        lower = text.lower()
        # due_date heuristics
        due_date = None
        due_time = None
        if "hôm nay" in lower:
            due_date = today.isoformat()
        elif "ngày mai" in lower or "mai" in lower:
            due_date = (today + timedelta(days=1)).isoformat()
        elif "tuần sau" in lower:
            due_date = (today + timedelta(days=7)).isoformat()
        # time heuristic  e.g. "8h", "14h30", "8:30"
        m = re.search(r"(\d{1,2})[h:](\d{0,2})", lower)
        if m:
            h = int(m.group(1))
            mi = int(m.group(2)) if m.group(2) else 0
            if 0 <= h <= 23:
                due_time = f"{h:02d}:{mi:02d}"
        # priority heuristics
        priority = "medium"
        if any(w in lower for w in ("gấp", "khẩn", "urgent", "ngay", "quan trọng")):
            priority = "high"
        elif any(w in lower for w in ("thư giãn", "rảnh", "thoải mái")):
            priority = "low"
        # category heuristics
        category = "personal"
        if any(w in lower for w in ("họp", "báo cáo", "công ty", "sếp", "khách", "dự án")):
            category = "work"
        elif any(w in lower for w in ("tập", "gym", "chạy", "sức khỏe", "ăn", "ngủ")):
            category = "health"
        elif any(w in lower for w in ("tiền", "lương", "chi tiêu", "mua", "thanh toán")):
            category = "finance"
        # reminder
        reminder = 15 if due_time else 0
        return {
            "title": text[:80],
            "description": "",
            "category": category,
            "priority": priority,
            "due_date": due_date,
            "due_time": due_time,
            "estimated_minutes": 30,
            "reminder_minutes": reminder,
        }

    if not _API_KEY:
        return _fallback()

    try:
        client = genai.Client(api_key=_API_KEY)
        prompt = f"""Hôm nay là {today.isoformat()} ({today.strftime('%A')}).
Người dùng nhập: "{text}"

Phân tích và trả về JSON (chỉ JSON, không markdown, không giải thích):
{{
  "title": "tiêu đề ngắn gọn",
  "description": "mô tả nếu cần, để trống nếu không có",
  "category": "work|personal|health|finance|education",
  "priority": "high|medium|low",
  "due_date": "YYYY-MM-DD hoặc null",
  "due_time": "HH:MM hoặc null",
  "estimated_minutes": 30,
  "reminder_minutes": 15
}}

Quy tắc:
- "mai", "ngày mai" → due_date là {(today + timedelta(days=1)).isoformat()}
- "hôm nay" → due_date là {today.isoformat()}
- "tuần sau" → {(today + timedelta(days=7)).isoformat()}
- "8h", "14h30" → due_time là "08:00", "14:30"
- Nếu có due_time → reminder_minutes = 15, không thì 0
- Chọn category phù hợp nhất với nội dung"""

        resp = client.models.generate_content(
            model="gemini-3.1-flash-lite",
            contents=[types.Content(role="user", parts=[types.Part.from_text(text=prompt)])],
            config=types.GenerateContentConfig(thinking_config=types.ThinkingConfig(thinking_level=types.ThinkingLevel.LOW)),
        )
        raw = resp.text.strip()
        # Strip markdown code fences if present
        raw = re.sub(r"^```[a-z]*\n?", "", raw).rstrip("`").strip()
        data = _json.loads(raw)
        # Ensure required keys exist
        return {
            "title": data.get("title", text[:80]),
            "description": data.get("description", ""),
            "category": data.get("category", "personal"),
            "priority": data.get("priority", "medium"),
            "due_date": data.get("due_date"),
            "due_time": data.get("due_time"),
            "estimated_minutes": int(data.get("estimated_minutes") or 30),
            "reminder_minutes": int(data.get("reminder_minutes") or 0),
        }
    except Exception:
        return _fallback()


def extract_task_from_reply(reply_text: str, user_id: str) -> dict | None:
    """Check if an AI reply contains a clear task suggestion.
    Returns task dict if found, None otherwise."""
    import re, json as _json
    from datetime import date, timedelta
    today = date.today()

    # Quick disqualify: too short or no task-like keywords
    lower = reply_text.lower()
    task_signals = ("tạo task", "thêm task", "tạo công việc", "đề xuất task",
                    "task:", "công việc:", "nhắc nhở", "nên làm", "gợi ý task")
    if not any(sig in lower for sig in task_signals):
        return None

    if not _API_KEY:
        return None

    try:
        client = genai.Client(api_key=_API_KEY)
        prompt = f"""Từ câu trả lời AI dưới đây, kiểm tra xem có ĐỀ XUẤT TẠO TASK cụ thể không.
Nếu có, trả về JSON. Nếu không, trả về {{"found": false}}.

Câu trả lời AI:
"{reply_text[:500]}"

Hôm nay: {today.isoformat()}

JSON nếu có task:
{{
  "found": true,
  "title": "tiêu đề task",
  "description": "",
  "category": "work|personal|health|finance|education",
  "priority": "high|medium|low",
  "due_date": "YYYY-MM-DD hoặc null",
  "due_time": "HH:MM hoặc null",
  "estimated_minutes": 30,
  "reminder_minutes": 0
}}"""
        resp = client.models.generate_content(
            model="gemini-3.1-flash-lite",
            contents=[types.Content(role="user", parts=[types.Part.from_text(text=prompt)])],
            config=types.GenerateContentConfig(thinking_config=types.ThinkingConfig(thinking_level=types.ThinkingLevel.LOW)),
        )
        raw = resp.text.strip()
        raw = re.sub(r"^```[a-z]*\n?", "", raw).rstrip("`").strip()
        data = _json.loads(raw)
        if not data.get("found"):
            return None
        return {
            "title": data.get("title", "Task mới"),
            "description": data.get("description", ""),
            "category": data.get("category", "personal"),
            "priority": data.get("priority", "medium"),
            "due_date": data.get("due_date"),
            "due_time": data.get("due_time"),
            "estimated_minutes": int(data.get("estimated_minutes") or 30),
            "reminder_minutes": int(data.get("reminder_minutes") or 0),
        }
    except Exception:
        return None


def parse_ocr_to_task(ocr_text: str) -> dict:
    """Parse OCR-extracted text into task fields using AI."""
    import re, json as _json
    from datetime import date, timedelta
    today = date.today()

    def _fallback():
        lines = [l.strip() for l in ocr_text.split("\n") if l.strip()]
        return {
            "title": lines[0][:80] if lines else "Task từ ảnh",
            "description": "\n".join(lines[1:])[:300] if len(lines) > 1 else "",
            "category": "personal",
            "priority": "medium",
            "due_date": None,
            "due_time": None,
            "estimated_minutes": 30,
            "reminder_minutes": 0,
        }

    if not _API_KEY or not ocr_text.strip():
        return _fallback()

    try:
        client = genai.Client(api_key=_API_KEY)
        prompt = f"""Hôm nay: {today.isoformat()}.
Đây là văn bản trích xuất từ ảnh bằng OCR:

\"\"\"{ocr_text[:1000]}\"\"\"

Phân tích và tạo task từ nội dung trên. Trả về JSON (chỉ JSON):
{{
  "title": "tiêu đề task ngắn gọn",
  "description": "mô tả chi tiết nếu có",
  "category": "work|personal|health|finance|education",
  "priority": "high|medium|low",
  "due_date": "YYYY-MM-DD hoặc null",
  "due_time": "HH:MM hoặc null",
  "estimated_minutes": 30,
  "reminder_minutes": 0
}}"""
        resp = client.models.generate_content(
            model="gemini-3.1-flash-lite",
            contents=[types.Content(role="user", parts=[types.Part.from_text(text=prompt)])],
            config=types.GenerateContentConfig(thinking_config=types.ThinkingConfig(thinking_level=types.ThinkingLevel.LOW)),
        )
        raw = resp.text.strip()
        raw = re.sub(r"^```[a-z]*\n?", "", raw).rstrip("`").strip()
        data = _json.loads(raw)
        return {
            "title": data.get("title", "Task từ ảnh")[:80],
            "description": data.get("description", ""),
            "category": data.get("category", "personal"),
            "priority": data.get("priority", "medium"),
            "due_date": data.get("due_date"),
            "due_time": data.get("due_time"),
            "estimated_minutes": int(data.get("estimated_minutes") or 30),
            "reminder_minutes": int(data.get("reminder_minutes") or 0),
        }
    except Exception:
        return _fallback()


def get_ai_reply(settings: dict, message: str, user_id: str,
                 session_id: str, image_path: str = None) -> str:
    return get_gemini_reply(message, user_id, session_id, image_path)


def get_gemini_reply(message: str, user_id: str, session_id: str,
                     image_path: str = None) -> str:
    from core.cloud import CloudClient, CloudError, generate_ai
    if CloudClient(user_id).configured:
        try:
            session = ChatService.get_session(user_id, session_id)
            history = '\n'.join(item['role'] + ': ' + item['text'] for item in (session or {}).get('messages', [])[-20:])
            return generate_ai(user_id, (history + '\n' + message)[-60000:], _get_system_prompt(_get_cached_context(user_id)), image_path=image_path)
        except CloudError as exc:
            return str(exc)
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


def extract_memory_from_user_message(user_id: str, message: str) -> None:
    """Dùng Gemini trích xuất thói quen/sở thích/mục tiêu từ tin nhắn user và lưu vào ai_memory.
    Chạy trong background thread — không block UI."""
    from core.cloud import CloudClient
    if CloudClient(user_id).configured or not _API_KEY or len(message.strip()) < 15:
        return
    try:
        import json as _json
        import re as _re

        client = genai.Client(api_key=_API_KEY)
        prompt = f"""Phân tích tin nhắn người dùng và trích xuất thói quen/sở thích/mục tiêu/trạng thái nếu có.

Tin nhắn: "{message[:500]}"

Chỉ trích xuất khi thông tin RÕ RÀNG và ĐÁNG LƯU lâu dài.
KHÔNG trích xuất: tên riêng, email, mật khẩu, câu hỏi đơn giản, yêu cầu một lần, thông tin nhạy cảm.

Trả về JSON thuần túy (không markdown):
{{
  "should_save": true/false,
  "memories": [
    {{
      "memory_type": "preference|habit|pattern|goal|state|constraint",
      "key": "key_ngan_gon",
      "value": "gia tri cu the",
      "confidence": 0.0-1.0
    }}
  ]
}}

Ví dụ trích xuất hợp lệ:
- "Tôi thường học tốt nhất buổi tối" → habit: peak_study_time="buổi tối", confidence=0.8
- "Tôi muốn hoàn thành đồ án trước 30/6" → goal: main_goal="hoàn thành đồ án trước 30/6", confidence=0.9
- "Tôi hay bị mất tập trung khi làm nhóm" → preference: work_style="solo hiệu quả hơn", confidence=0.75
- "Tôi đang stress vì thi cử" → state: stress_cause="thi cử", confidence=0.85
- "Tôi không thích task hành chính" → preference: dislike_category="administrative", confidence=0.7"""

        resp = client.models.generate_content(
            model="gemini-3.1-flash-lite",
            contents=[types.Content(role="user", parts=[types.Part.from_text(text=prompt)])],
            config=types.GenerateContentConfig(
                thinking_config=types.ThinkingConfig(thinking_level=types.ThinkingLevel.LOW)
            ),
        )
        raw = resp.text.strip()
        raw = _re.sub(r"^```[a-z]*\n?", "", raw).rstrip("`").strip()
        data = _json.loads(raw)

        if data.get("should_save") and data.get("memories"):
            for mem in data["memories"]:
                mem_type   = mem.get("memory_type", "preference")
                key        = str(mem.get("key", "")).strip()
                value      = str(mem.get("value", "")).strip()
                confidence = float(mem.get("confidence", 0.6))
                if key and value and confidence >= 0.5:
                    AIMemoryService.remember(user_id, mem_type, key, value, confidence)
                    invalidate_context_cache(user_id)
    except Exception:
        pass  # non-critical — silently ignore
