"""
TaskFlow - AI Assistant Screen
AI chat + AI Planner (Notion-like): lập kế hoạch, tạo task, refine plan.
"""
import flet as ft
import threading
import uuid
import logging
from datetime import datetime

from core.theme import Colors, Typography, Spacing, Radius
from components.widgets import snack

logger = logging.getLogger(__name__)

_QUICK_PROMPTS = [
    ("📊", "Phân tích",   "Phân tích tình trạng công việc của tôi"),
    ("📋", "Kế hoạch",   "Lên kế hoạch làm đồ án OpenGL trong 5 ngày"),
    ("🎯", "Ưu tiên",    "Task nào tôi nên tập trung làm trước?"),
    ("✈️", "Đi chơi",    "Lên kế hoạch ngày mai đi chơi"),
]


# ── Plan card renderer ────────────────────────────────────────────────────────

def _render_plan_card(plan: dict, on_save_tasks, on_refine) -> ft.Container:
    """Render a plan_result dict as a rich Flet card."""
    from core.ai_planner_service import get_intent_label, get_refine_options

    intent              = plan.get("intent", "unknown")
    intent_label        = get_intent_label(intent)
    title               = plan.get("title", "Kế hoạch")
    summary             = plan.get("summary", "")
    assumptions         = plan.get("assumptions", [])
    personalization_used = plan.get("personalization_used", [])
    steps               = plan.get("plan", [])
    tasks               = plan.get("suggested_tasks", [])
    follow_up           = plan.get("follow_up_question", "Bạn muốn chỉnh theo phần nào?")
    refine_opts         = plan.get("refine_options", get_refine_options(intent))

    # ── Intent badge ───────────────────────────────────────────
    intent_badge = ft.Container(
        content=ft.Text(intent_label, size=9, color="white", weight=Typography.BOLD),
        padding=ft.padding.symmetric(horizontal=8, vertical=3),
        border_radius=Radius.FULL,
        gradient=ft.LinearGradient(
            colors=["#A855F7", "#3B82F6"],
            begin=ft.Alignment.CENTER_LEFT,
            end=ft.Alignment.CENTER_RIGHT,
        ),
    )

    # ── Header ─────────────────────────────────────────────────
    header = ft.Column([
        ft.Row([
            ft.Text("📌", size=16),
            ft.Text(title, size=Typography.BODY, color=Colors.TEXT_PRIMARY,
                    weight=Typography.BOLD, expand=True,
                    max_lines=2, overflow=ft.TextOverflow.ELLIPSIS),
        ], spacing=6, vertical_alignment=ft.CrossAxisAlignment.START),
        ft.Row([intent_badge], spacing=0),
        ft.Container(height=4),
        ft.Text(summary, size=Typography.TINY, color=Colors.TEXT_MUTED,
                max_lines=3, overflow=ft.TextOverflow.ELLIPSIS),
    ], spacing=4, tight=True)

    # ── Assumptions ────────────────────────────────────────────
    assume_rows = []
    if assumptions:
        assume_rows = [
            ft.Container(
                content=ft.Column([
                    ft.Row([
                        ft.Icon(ft.Icons.LIGHTBULB_OUTLINE_ROUNDED, size=12, color=Colors.WARNING),
                        ft.Text("Giả định:", size=Typography.TINY,
                                color=Colors.WARNING, weight=Typography.SEMIBOLD),
                    ], spacing=4),
                    *[ft.Text(f"• {a}", size=Typography.TINY, color=Colors.TEXT_MUTED)
                      for a in assumptions[:3]],
                ], spacing=3, tight=True),
                padding=ft.padding.symmetric(horizontal=10, vertical=6),
                border_radius=Radius.SM,
                bgcolor=f"#15{Colors.WARNING[1:]}",
                border=ft.Border.all(1, f"#30{Colors.WARNING[1:]}"),
            )
        ]

    # ── Plan steps ──────────────────────────────────────────────
    def _step_row(step: dict) -> ft.Container:
        time_label = step.get("time_or_step", "")
        step_title = step.get("title", "")
        details    = step.get("details", [])
        return ft.Container(
            content=ft.Column([
                ft.Row([
                    ft.Container(
                        content=ft.Text(time_label, size=8,
                                        color=Colors.PRIMARY, weight=Typography.BOLD),
                        padding=ft.padding.symmetric(horizontal=7, vertical=3),
                        border_radius=Radius.FULL,
                        bgcolor=Colors.PRIMARY_BG,
                        border=ft.Border.all(1, Colors.PRIMARY_BORDER),
                    ),
                    ft.Text(step_title, size=Typography.SMALL,
                            color=Colors.TEXT_PRIMARY, weight=Typography.SEMIBOLD,
                            expand=True, max_lines=1,
                            overflow=ft.TextOverflow.ELLIPSIS),
                ], spacing=6, vertical_alignment=ft.CrossAxisAlignment.CENTER),
                ft.Column([
                    ft.Text(f"  • {d}", size=Typography.TINY, color=Colors.TEXT_MUTED)
                    for d in details[:4]
                ], spacing=1, tight=True),
            ], spacing=3, tight=True),
            padding=ft.padding.symmetric(vertical=5, horizontal=8),
            border_radius=Radius.SM,
            bgcolor=Colors.BG_SURFACE,
            border=ft.Border(left=ft.BorderSide(2, Colors.PRIMARY)),
            margin=ft.margin.only(bottom=4),
        )

    plan_section = ft.Column([
        ft.Row([
            ft.Icon(ft.Icons.CALENDAR_TODAY_ROUNDED, size=13, color=Colors.PRIMARY),
            ft.Text("Kế hoạch chi tiết:", size=Typography.SMALL,
                    color=Colors.TEXT_PRIMARY, weight=Typography.SEMIBOLD),
        ], spacing=4),
        ft.Column([_step_row(s) for s in steps[:6]], spacing=0, tight=True),
    ], spacing=6, tight=True) if steps else ft.Container(height=0)

    # ── Suggested tasks ─────────────────────────────────────────
    task_checks = {t.get("title", ""): {"v": True} for t in tasks}

    def _task_row(t: dict) -> ft.Row:
        title_t = t.get("title", "")
        pri     = t.get("priority", "medium")
        pri_color = {"high": Colors.ERROR, "medium": Colors.WARNING,
                     "low": Colors.PRIMARY}.get(pri, Colors.PRIMARY)
        est     = t.get("estimated_minutes", 30)
        check_ref = ft.Ref[ft.Container]()
        state = task_checks.get(title_t, {"v": True})

        def _toggle(_, title=title_t, s=state, ref=check_ref):
            s["v"] = not s["v"]
            if ref.current:
                ref.current.bgcolor = Colors.SUCCESS if s["v"] else "transparent"
                ref.current.border = ft.Border.all(
                    1, Colors.SUCCESS if s["v"] else Colors.TEXT_MUTED)
                if ref.current.content:
                    ref.current.content.color = "white" if s["v"] else Colors.TEXT_MUTED

        return ft.GestureDetector(
            on_tap=_toggle,
            content=ft.Row([
                ft.Container(
                    ref=check_ref,
                    content=ft.Icon(ft.Icons.CHECK, size=10, color="white"),
                    width=18, height=18, border_radius=4,
                    bgcolor=Colors.SUCCESS,
                    border=ft.Border.all(1, Colors.SUCCESS),
                    alignment=ft.Alignment.CENTER,
                ),
                ft.Column([
                    ft.Text(title_t, size=Typography.TINY, color=Colors.TEXT_PRIMARY,
                            max_lines=1, overflow=ft.TextOverflow.ELLIPSIS, expand=True),
                    ft.Text(f"{est} phút", size=8, color=Colors.TEXT_MUTED),
                ], spacing=0, tight=True, expand=True),
                ft.Container(
                    width=5, height=5, border_radius=3, bgcolor=pri_color,
                ),
            ], spacing=8, vertical_alignment=ft.CrossAxisAlignment.CENTER),
        )

    def _save_tasks(_):
        from core.models import Task as _Task
        from core.services import TaskService as _TS, BehaviorService as _BS
        saved = 0
        for t in tasks:
            title_t = t.get("title", "")
            if task_checks.get(title_t, {"v": True})["v"]:
                try:
                    now_str = datetime.now().isoformat()
                    new_t = _Task(
                        id=str(uuid.uuid4()),
                        user_id="",  # filled below
                        title=title_t,
                        description=t.get("description", ""),
                        category=t.get("category", "personal"),
                        priority=t.get("priority", "medium"),
                        status="todo",
                        due_date=t.get("due_date"),
                        due_time=t.get("due_time"),
                        estimated_minutes=int(t.get("estimated_minutes") or 30),
                        created_at=now_str,
                        updated_at=now_str,
                    )
                    new_t.user_id = _current_user_id[0]
                    _TS.save_task(new_t)
                    saved += 1
                except Exception:
                    logger.exception("Failed to save task: %s", title_t)
        snack(_current_page[0], f"✓ Đã lưu {saved} task vào danh sách!")
        try:
            _BS.log(_current_user_id[0], "plan_save_tasks", {"task_count": saved})
        except Exception:
            pass

    tasks_section = ft.Container(height=0)
    if tasks:
        save_btn = ft.Container(
            content=ft.Row([
                ft.Icon(ft.Icons.SAVE_OUTLINED, size=14, color="white"),
                ft.Text(f"Lưu {len(tasks)} task được chọn", size=Typography.TINY,
                        color="white", weight=Typography.SEMIBOLD),
            ], spacing=6, alignment=ft.MainAxisAlignment.CENTER),
            height=36, border_radius=Radius.MD,
            bgcolor=Colors.SUCCESS,
            alignment=ft.Alignment.CENTER,
            on_click=_save_tasks, ink=True,
            margin=ft.margin.only(top=6),
        )
        tasks_section = ft.Column([
            ft.Row([
                ft.Icon(ft.Icons.CHECKLIST_ROUNDED, size=13, color=Colors.SUCCESS),
                ft.Text(f"{len(tasks)} task đề xuất:", size=Typography.SMALL,
                        color=Colors.TEXT_PRIMARY, weight=Typography.SEMIBOLD),
            ], spacing=4),
            ft.Column([_task_row(t) for t in tasks[:6]], spacing=4, tight=True),
            save_btn,
        ], spacing=6, tight=True)

    # ── Refine section ──────────────────────────────────────────
    def _refine_chip(opt: str) -> ft.GestureDetector:
        return ft.GestureDetector(
            on_tap=lambda _, o=opt: on_refine(o),
            content=ft.Container(
                content=ft.Text(opt, size=8, color=Colors.PRIMARY),
                padding=ft.padding.symmetric(horizontal=10, vertical=5),
                border_radius=Radius.FULL,
                bgcolor=Colors.PRIMARY_BG,
                border=ft.Border.all(1, Colors.PRIMARY_BORDER),
            ),
        )

    refine_section = ft.Column([
        ft.Container(height=4),
        ft.Text(follow_up, size=Typography.TINY, color=Colors.TEXT_MUTED),
        ft.Container(height=4),
        ft.Row([_refine_chip(o) for o in refine_opts[:4]], spacing=4, wrap=True),
        ft.Row([_refine_chip(o) for o in refine_opts[4:]], spacing=4, wrap=True),
    ], spacing=2, tight=True)

    # ── Divider helper ──────────────────────────────────────────
    def _div():
        return ft.Container(height=1, bgcolor=Colors.BORDER,
                             margin=ft.margin.symmetric(vertical=6))

    # ── Personalization badge ───────────────────────────────────
    personalization_row = []
    if personalization_used:
        items = personalization_used[:3]
        chips = [
            ft.Container(
                content=ft.Text(p, size=7, color=Colors.PRIMARY),
                padding=ft.padding.symmetric(horizontal=6, vertical=2),
                border_radius=Radius.FULL,
                bgcolor=Colors.PRIMARY_BG,
                border=ft.Border.all(1, Colors.PRIMARY_BORDER),
            )
            for p in items
        ]
        personalization_row = [
            ft.Container(
                content=ft.Column([
                    ft.Row([
                        ft.Icon(ft.Icons.AUTO_AWESOME_ROUNDED, size=10, color=Colors.PRIMARY),
                        ft.Text("Đã cá nhân hóa theo:", size=Typography.TINY,
                                color=Colors.PRIMARY, weight=Typography.SEMIBOLD),
                    ], spacing=3),
                    ft.Row(chips, spacing=4, wrap=True),
                ], spacing=3, tight=True),
                padding=ft.padding.symmetric(horizontal=10, vertical=6),
                border_radius=Radius.SM,
                bgcolor=Colors.PRIMARY_BG,
                border=ft.Border.all(1, Colors.PRIMARY_BORDER),
            )
        ]

    # ── Assemble card ───────────────────────────────────────────
    sections = [header]
    if personalization_row:
        sections += [_div()] + personalization_row
    if assume_rows:
        sections += [_div()] + assume_rows
    if steps:
        sections += [_div(), plan_section]
    if tasks:
        sections += [_div(), tasks_section]
    sections += [_div(), refine_section]

    return ft.Container(
        content=ft.Column(sections, spacing=0, tight=True),
        padding=ft.padding.all(14),
        border_radius=ft.BorderRadius(4, 16, 16, 16),
        bgcolor=Colors.BG_CARD,
        border=ft.Border.all(1, Colors.PRIMARY_BORDER),
        shadow=ft.BoxShadow(blur_radius=10, color=Colors.PRIMARY_SHADOW,
                            offset=ft.Offset(0, 2)),
        width=290,
    )


# ── Main screen builder ───────────────────────────────────────────────────────

_current_page    = [None]   # module-level refs for save task callbacks
_current_user_id = [""]


def build_ai_screen(page: ft.Page, user, on_navigate):
    from core.services import TaskService, ChatService

    _current_page[0]    = page
    _current_user_id[0] = user.id

    tasks   = TaskService.get_tasks(user.id)
    total   = len(tasks)
    done    = sum(1 for t in tasks if t.status == "done")
    pending = sum(1 for t in tasks if t.status == "todo")
    pct     = int(done / total * 100) if total else 0

    # ── State ──────────────────────────────────────────────────
    _state = {
        "session_id": None,
        "last_plan": None,      # stores last plan_result for refine
    }

    # ── Chat ListView ──────────────────────────────────────────
    chat_lv = ft.ListView(
        expand=True,
        spacing=12,
        padding=ft.Padding.symmetric(horizontal=Spacing.MD, vertical=Spacing.MD),
        auto_scroll=True,
    )

    # ── Bubble helper ──────────────────────────────────────────
    def _bubble(text: str, is_user: bool = False, animate: bool = True) -> ft.Row:
        content = ft.Text(
            text,
            size=Typography.BODY,
            color="white" if is_user else Colors.TEXT_PRIMARY,
            selectable=True,
        )
        bubble = ft.Container(
            content=content,
            padding=ft.Padding.symmetric(horizontal=14, vertical=10),
            border_radius=ft.BorderRadius(
                top_left=16, top_right=16,
                bottom_right=4 if is_user else 16,
                bottom_left=16 if is_user else 4,
            ),
            bgcolor=Colors.PRIMARY if is_user else Colors.BG_CARD,
            border=ft.Border.all(1, Colors.BORDER) if not is_user else None,
            shadow=ft.BoxShadow(blur_radius=8, color="#00000018", offset=ft.Offset(0, 2)),
            animate=ft.Animation(300, ft.AnimationCurve.EASE_OUT) if animate else None,
        )
        ai_avatar = ft.Container(
            content=ft.Image(src="avtdoumar.png", fit="cover"),
            width=30, height=30, border_radius=15,
            clip_behavior=ft.ClipBehavior.ANTI_ALIAS,
        )
        if is_user:
            return ft.Row([ft.Container(expand=1),
                           ft.Column([bubble], expand=4,
                                     horizontal_alignment=ft.CrossAxisAlignment.END)],
                          spacing=0)
        return ft.Row([ai_avatar,
                       ft.Column([bubble], expand=True,
                                 horizontal_alignment=ft.CrossAxisAlignment.START)],
                      spacing=Spacing.SM, vertical_alignment=ft.CrossAxisAlignment.START)

    def _plan_row(plan_data: dict) -> ft.Row:
        """Wrap plan card in the AI-side row layout."""
        ai_avatar = ft.Container(
            content=ft.Image(src="avtdoumar.png", fit="cover"),
            width=30, height=30, border_radius=15,
            clip_behavior=ft.ClipBehavior.ANTI_ALIAS,
        )

        def _on_save(evt=None):
            # save_tasks already wired in the card via _save_tasks closure
            pass

        def _on_refine(option: str):
            _do_refine(option)

        card = _render_plan_card(plan_data, _on_save, _on_refine)
        return ft.Row(
            [ai_avatar,
             ft.Column([card], expand=True,
                       horizontal_alignment=ft.CrossAxisAlignment.START)],
            spacing=Spacing.SM,
            vertical_alignment=ft.CrossAxisAlignment.START,
        )

    def _scroll_down():
        async def _s():
            try:
                await chat_lv.scroll_to(offset=99999, duration=300)
            except Exception:
                pass
        try:
            page.run_task(_s)
        except Exception:
            pass

    def _add_to_chat(control, scroll=True):
        if _typing in chat_lv.controls:
            idx = chat_lv.controls.index(_typing)
            chat_lv.controls.insert(idx, control)
        else:
            chat_lv.controls.append(control)
        page.update()
        if scroll:
            _scroll_down()

    # ── Typing indicator ───────────────────────────────────────
    _typing = ft.Container(
        content=ft.Row([
            ft.Container(
                content=ft.Image(src="avtdoumar.png", fit="cover"),
                width=26, height=26, border_radius=13,
                clip_behavior=ft.ClipBehavior.ANTI_ALIAS,
            ),
            ft.Container(
                content=ft.Row([
                    ft.Container(width=7, height=7, border_radius=4,
                                 bgcolor=Colors.TEXT_MUTED,
                                 animate=ft.Animation(600, ft.AnimationCurve.EASE_IN_OUT)),
                    ft.Container(width=7, height=7, border_radius=4,
                                 bgcolor=Colors.TEXT_MUTED,
                                 animate=ft.Animation(600, ft.AnimationCurve.EASE_IN_OUT)),
                    ft.Container(width=7, height=7, border_radius=4,
                                 bgcolor=Colors.TEXT_MUTED,
                                 animate=ft.Animation(600, ft.AnimationCurve.EASE_IN_OUT)),
                ], spacing=4),
                padding=ft.Padding.symmetric(horizontal=14, vertical=10),
                border_radius=ft.BorderRadius(16, 16, 16, 4),
                bgcolor=Colors.BG_CARD,
                border=ft.Border.all(1, Colors.BORDER),
            ),
            ft.Container(expand=True),
        ], spacing=Spacing.SM, vertical_alignment=ft.CrossAxisAlignment.END),
        visible=False,
    )

    # ── Input bar ──────────────────────────────────────────────
    tf = ft.TextField(
        hint_text="Nhắn gì đó, hoặc 'Lên kế hoạch...'",
        hint_style=ft.TextStyle(color=Colors.TEXT_MUTED),
        bgcolor=Colors.BG_INPUT,
        border_color=Colors.BORDER,
        focused_border_color=Colors.PRIMARY,
        text_style=ft.TextStyle(color=Colors.TEXT_PRIMARY),
        border_radius=Radius.LG,
        cursor_color=Colors.PRIMARY,
        expand=True,
        on_submit=lambda e: _send(e),
    )

    # ── Image picker ───────────────────────────────────────────
    def _pick(e):
        tf.hint_text = "Đang chọn Ảnh..."
        tf.disabled = True
        page.update()

        def _run():
            try:
                import tkinter as tk
                from tkinter import filedialog
                root = tk.Tk()
                root.attributes('-topmost', True)
                root.withdraw()
                file_path = filedialog.askopenfilename(
                    title="Chọn ảnh",
                    filetypes=[("Image files", "*.jpg;*.jpeg;*.png;*.bmp")]
                )
                root.destroy()
            except Exception:
                file_path = None
            tf.hint_text = "Nhắn gì đó, hoặc 'Lên kế hoạch...'"
            tf.disabled = False
            page.update()
            if file_path:
                _add_to_chat(_bubble(is_user=True, text="[Đã gửi ảnh]"))
                tf.value = "Hãy phân tích hình ảnh này và tạo task giúp tôi."
                _send(None, image_path=file_path)

        threading.Thread(target=_run, daemon=True).start()

    btn_attach = ft.IconButton(icon=ft.Icons.IMAGE_ROUNDED,
                                icon_color=Colors.TEXT_MUTED, on_click=_pick)

    # ── Reply logic ────────────────────────────────────────────
    def _do_refine(option: str):
        """User clicked a refine option — update the plan."""
        tf.value = ""
        _add_to_chat(_bubble(option, is_user=True))
        if _state["session_id"]:
            ChatService.add_message(user.id, _state["session_id"], "user", option)
        try:
            from core.services import BehaviorService as _BS
            _BS.log(user.id, "plan_refine", {"option": option})
        except Exception:
            pass
        _run_plan_reply(option, last_plan=_state.get("last_plan"))

    def _run_plan_reply(message: str, last_plan: dict = None):
        _typing.visible = True
        page.update()
        _scroll_down()

        def _worker():
            from core.ai_planner_service import get_plan_response
            result = get_plan_response(message, user.id, last_plan=last_plan)
            _typing.visible = False

            if result.get("type") == "plan_result":
                _state["last_plan"] = result
                row = _plan_row(result)
                _add_to_chat(row)
                # Also save a text summary to chat history
                summary = f"[Kế hoạch] {result.get('title', '')}\n{result.get('summary', '')}"
                if _state["session_id"]:
                    ChatService.add_message(user.id, _state["session_id"], "model", summary)

            elif result.get("type") == "task_create":
                # Show as a quick-create task bubble
                msg = (f"📋 Task gợi ý:\n"
                       f"**{result.get('title', '')}**\n"
                       f"Ưu tiên: {result.get('priority', 'medium')} | "
                       f"Hạn: {result.get('due_date') or 'chưa đặt'}")
                _add_to_chat(_bubble(msg, is_user=False))
                _show_task_create_confirm(result)
                if _state["session_id"]:
                    ChatService.add_message(user.id, _state["session_id"], "model", msg)

            else:
                # normal_chat fallback
                msg = result.get("message", "Mình sẽ hỗ trợ bạn lập kế hoạch và quản lý task.")
                _add_to_chat(_bubble(msg, is_user=False))
                if _state["session_id"]:
                    ChatService.add_message(user.id, _state["session_id"], "model", msg)

            _load_sessions_ui()
            try:
                page.update()
            except RuntimeError:
                pass

        threading.Thread(target=_worker, daemon=True).start()

    def _run_text_reply(message: str, image_path: str = None):
        _typing.visible = True
        page.update()
        _scroll_down()

        def _worker():
            from utils.ai_helper import get_ai_reply, extract_task_from_reply
            reply = get_ai_reply(user.settings, message, user.id,
                                 _state["session_id"], image_path)
            _typing.visible = False
            _add_to_chat(_bubble(reply, is_user=False))
            if _state["session_id"]:
                ChatService.add_message(user.id, _state["session_id"], "model", reply)

            # Check for inline task suggestion
            try:
                task_data = extract_task_from_reply(reply, user.id)
                if task_data:
                    _show_inline_task_btn(task_data)
            except Exception:
                logger.exception("extract_task_from_reply failed")

            _load_sessions_ui()
            try:
                page.update()
            except RuntimeError:
                pass

        threading.Thread(target=_worker, daemon=True).start()

    def _send(_, image_path=None):
        text = tf.value.strip()
        if not text and not image_path:
            return
        tf.value = ""
        if text and not image_path:
            _add_to_chat(_bubble(text, is_user=True))
            if _state["session_id"]:
                ChatService.add_message(user.id, _state["session_id"], "user", text)
            # Log behavior + extract memory in background
            def _bg_process(msg=text, uid=user.id):
                try:
                    from core.services import BehaviorService as _BS
                    from core.ai_planner_service import detect_plan_intent as _dpi
                    _BS.log(uid, "chat_sent", {
                        "length": len(msg),
                        "has_plan_intent": bool(_dpi(msg)),
                    })
                    from utils.ai_helper import extract_memory_from_user_message
                    extract_memory_from_user_message(uid, msg)
                except Exception:
                    pass
            threading.Thread(target=_bg_process, daemon=True).start()
        elif image_path:
            if _state["session_id"]:
                ChatService.add_message(user.id, _state["session_id"], "user",
                                        f"[Đã gửi hình ảnh] {text}")
        _load_sessions_ui()
        page.update()

        # Route to planner or normal chat
        from core.ai_planner_service import detect_plan_intent
        if not image_path and text:
            intent = detect_plan_intent(text)
            if intent:
                _run_plan_reply(text, last_plan=_state.get("last_plan"))
                return
        _run_text_reply(text, image_path)

    # ── Inline task creation button ─────────────────────────────
    def _show_inline_task_btn(task_data: dict):
        from core.models import Task as _Task
        from core.services import TaskService as _TS

        def _do_create(_):
            try:
                now_str = datetime.now().isoformat()
                new_t = _Task(
                    id=str(uuid.uuid4()),
                    user_id=user.id,
                    title=task_data.get("title", "Task mới"),
                    description=task_data.get("description", ""),
                    category=task_data.get("category", "personal"),
                    priority=task_data.get("priority", "medium"),
                    status="todo",
                    due_date=task_data.get("due_date"),
                    due_time=task_data.get("due_time"),
                    estimated_minutes=int(task_data.get("estimated_minutes") or 30),
                    reminder_minutes=int(task_data.get("reminder_minutes") or 0),
                    created_at=now_str,
                    updated_at=now_str,
                )
                _TS.save_task(new_t)
                snack(page, f"✓ Đã tạo: {new_t.title}")
                if btn_row in chat_lv.controls:
                    chat_lv.controls.remove(btn_row)
                page.update()
            except Exception:
                logger.exception("Inline task creation failed")

        btn_row = ft.Row([
            ft.Container(expand=True),
            ft.Container(
                content=ft.Row([
                    ft.Icon(ft.Icons.ADD_TASK_ROUNDED, size=13, color="white"),
                    ft.Text(f'Tạo: "{task_data.get("title", "")[:28]}"',
                            size=Typography.TINY, color="white",
                            weight=Typography.SEMIBOLD),
                ], spacing=5, tight=True),
                padding=ft.padding.symmetric(horizontal=12, vertical=7),
                border_radius=Radius.FULL,
                gradient=ft.LinearGradient(
                    colors=["#A855F7", "#3B82F6"],
                    begin=ft.Alignment.CENTER_LEFT,
                    end=ft.Alignment.CENTER_RIGHT,
                ),
                on_click=_do_create, ink=True,
                shadow=ft.BoxShadow(blur_radius=8, color="#40A855F7",
                                    offset=ft.Offset(0, 2)),
            ),
        ], spacing=0)
        _add_to_chat(btn_row)

    # ── Task create confirm sheet ───────────────────────────────
    def _show_task_create_confirm(data: dict):
        from core.models import Task as _Task
        from core.services import TaskService as _TS

        tf_title = ft.TextField(
            value=data.get("title", ""),
            label="Tiêu đề",
            bgcolor=Colors.BG_SURFACE, border_color=Colors.BORDER,
            focused_border_color=Colors.PRIMARY,
            text_style=ft.TextStyle(color=Colors.TEXT_PRIMARY, size=Typography.SMALL),
            label_style=ft.TextStyle(color=Colors.TEXT_MUTED, size=Typography.TINY),
            border_radius=Radius.MD, cursor_color=Colors.PRIMARY,
            content_padding=ft.padding.symmetric(horizontal=12, vertical=10),
        )
        tf_due = ft.TextField(
            value=data.get("due_date") or "",
            label="Hạn (YYYY-MM-DD)",
            bgcolor=Colors.BG_SURFACE, border_color=Colors.BORDER,
            focused_border_color=Colors.PRIMARY,
            text_style=ft.TextStyle(color=Colors.TEXT_PRIMARY, size=Typography.SMALL),
            label_style=ft.TextStyle(color=Colors.TEXT_MUTED, size=Typography.TINY),
            border_radius=Radius.MD, cursor_color=Colors.PRIMARY,
            content_padding=ft.padding.symmetric(horizontal=12, vertical=10),
            expand=True,
        )
        tf_time = ft.TextField(
            value=data.get("due_time") or "",
            label="Giờ (HH:MM)",
            bgcolor=Colors.BG_SURFACE, border_color=Colors.BORDER,
            focused_border_color=Colors.PRIMARY,
            text_style=ft.TextStyle(color=Colors.TEXT_PRIMARY, size=Typography.SMALL),
            label_style=ft.TextStyle(color=Colors.TEXT_MUTED, size=Typography.TINY),
            border_radius=Radius.MD, cursor_color=Colors.PRIMARY,
            content_padding=ft.padding.symmetric(horizontal=12, vertical=10),
            expand=True,
        )

        def _save(_):
            title = tf_title.value.strip()
            if not title:
                snack(page, "⚠️ Vui lòng nhập tiêu đề!")
                return
            now_str = datetime.now().isoformat()
            new_t = _Task(
                id=str(uuid.uuid4()),
                user_id=user.id,
                title=title,
                description=data.get("description", ""),
                category=data.get("category", "personal"),
                priority=data.get("priority", "medium"),
                status="todo",
                due_date=tf_due.value.strip() or None,
                due_time=tf_time.value.strip() or None,
                estimated_minutes=int(data.get("estimated_minutes") or 30),
                reminder_minutes=int(data.get("reminder_minutes") or 0),
                created_at=now_str,
                updated_at=now_str,
            )
            _TS.save_task(new_t)
            bs[0].open = False
            page.update()
            snack(page, f"✓ Đã tạo: {title}")

        def _cancel(_):
            bs[0].open = False
            page.update()

        sheet = ft.Column([
            ft.Container(
                content=ft.Container(width=40, height=4, border_radius=Radius.FULL,
                                     bgcolor="#444444"),
                alignment=ft.Alignment.CENTER,
                padding=ft.padding.only(top=12, bottom=8),
            ),
            ft.Container(
                content=ft.Column([
                    ft.Row([
                        ft.Icon(ft.Icons.ADD_TASK_ROUNDED, size=18, color=Colors.PRIMARY),
                        ft.Text("Xác nhận tạo Task", size=Typography.H3,
                                color=Colors.TEXT_PRIMARY, weight=Typography.BOLD),
                    ], spacing=Spacing.SM),
                    ft.Container(height=Spacing.SM),
                    tf_title,
                    ft.Container(height=Spacing.XS),
                    ft.Row([tf_due, ft.Container(width=8), tf_time]),
                    ft.Container(height=Spacing.MD),
                    ft.Row([
                        ft.Container(
                            content=ft.Text("Hủy", size=Typography.BODY,
                                            color=Colors.TEXT_MUTED),
                            height=44, expand=True, border_radius=Radius.MD,
                            bgcolor=Colors.BG_SURFACE,
                            border=ft.Border.all(1, Colors.BORDER),
                            alignment=ft.Alignment.CENTER,
                            on_click=_cancel, ink=True,
                        ),
                        ft.Container(width=8),
                        ft.Container(
                            content=ft.Row([
                                ft.Icon(ft.Icons.CHECK_ROUNDED, size=16, color="white"),
                                ft.Text("Lưu Task", size=Typography.BODY, color="white",
                                        weight=Typography.SEMIBOLD),
                            ], alignment=ft.MainAxisAlignment.CENTER, spacing=4),
                            height=44, expand=True, border_radius=Radius.MD,
                            bgcolor=Colors.PRIMARY,
                            alignment=ft.Alignment.CENTER,
                            on_click=_save, ink=True,
                        ),
                    ]),
                    ft.Container(height=Spacing.XL),
                ], spacing=0, tight=True),
                padding=ft.padding.symmetric(horizontal=Spacing.LG),
            ),
        ], spacing=0, tight=True)

        cbs = ft.BottomSheet(
            content=ft.Container(
                content=sheet, bgcolor=Colors.BG_CARD,
                border_radius=ft.BorderRadius.only(top_left=Radius.XL, top_right=Radius.XL),
                padding=0, clip_behavior=ft.ClipBehavior.ANTI_ALIAS,
            ),
            open=True, draggable=True, use_safe_area=True,
        )
        bs = [cbs]
        page.overlay.append(cbs)
        page.update()

    # ── Send button ────────────────────────────────────────────
    send_btn = ft.Container(
        content=ft.Icon(ft.Icons.SEND_ROUNDED, color="white", size=20),
        width=46, height=46,
        border_radius=Radius.LG,
        gradient=ft.LinearGradient(
            colors=[Colors.PRIMARY_LIGHT, Colors.PRIMARY],
            begin=ft.Alignment.TOP_LEFT,
            end=ft.Alignment.BOTTOM_RIGHT,
        ),
        alignment=ft.Alignment.CENTER,
        on_click=_send, ink=True,
        shadow=ft.BoxShadow(blur_radius=12, color=Colors.PRIMARY_SHADOW,
                            offset=ft.Offset(0, 3)),
    )

    # ── Quick prompt chips ─────────────────────────────────────
    def _chip(emoji: str, label: str, prompt: str):
        def _tap(_):
            tf.value = prompt
            _send(None)
        return ft.GestureDetector(
            content=ft.Container(
                content=ft.Row([
                    ft.Text(emoji, size=12),
                    ft.Text(label, size=Typography.TINY, color=Colors.TEXT_SECONDARY),
                ], spacing=4, tight=True),
                padding=ft.Padding.symmetric(horizontal=10, vertical=6),
                border_radius=Radius.FULL,
                border=ft.Border.all(1, Colors.BORDER),
                bgcolor=Colors.BG_SURFACE,
            ),
            on_tap=_tap,
        )

    chips_row = ft.Row(
        [_chip(e, l, p) for e, l, p in _QUICK_PROMPTS],
        scroll=ft.ScrollMode.AUTO, spacing=Spacing.SM,
    )

    # ── History panel ──────────────────────────────────────────
    _history_state = {"open": False}

    def toggle_history(e):
        _history_state["open"] = not _history_state["open"]
        if _history_state["open"]:
            history_panel.width = 250
            history_panel.padding = 16
        else:
            history_panel.width = 0
            history_panel.padding = 0
        page.update()

    def _start_new_chat(_):
        _state["session_id"] = ChatService.create_session(user.id, "Chat mới")
        _state["last_plan"] = None
        _load_active_session()
        if _history_state["open"]:
            toggle_history(None)

    history_lv = ft.ListView(expand=True, spacing=8, controls=[])
    history_panel = ft.Container(
        content=ft.Column([
            ft.Text("Lịch sử", size=Typography.H4, weight=ft.FontWeight.BOLD),
            ft.Divider(color=Colors.BORDER),
            history_lv,
        ]),
        width=0, bgcolor=Colors.BG_DARK, padding=0,
        border=ft.Border(left=ft.BorderSide(1, Colors.BORDER)),
        animate=ft.Animation(300, ft.AnimationCurve.EASE_OUT_CUBIC),
        clip_behavior=ft.ClipBehavior.HARD_EDGE,
    )

    btn_menu = ft.IconButton(icon=ft.Icons.MENU_ROUNDED,
                              icon_color=Colors.TEXT_PRIMARY, on_click=toggle_history)

    def _load_sessions_ui():
        sessions = ChatService.get_sessions(user.id)
        controls = []
        for s in sessions:
            is_active = (s["id"] == _state["session_id"])

            def make_select(sid):
                return lambda e: _switch_session(sid)

            def make_delete(sid):
                return lambda e: _delete_session(sid)

            item = ft.Container(
                content=ft.Row([
                    ft.Icon(ft.Icons.CHAT_BUBBLE_OUTLINE, size=16,
                            color=Colors.PRIMARY if is_active else Colors.TEXT_MUTED),
                    ft.Text(s.get("title", "Chat"), expand=True,
                            color=Colors.TEXT_PRIMARY if is_active else Colors.TEXT_SECONDARY,
                            size=Typography.BODY, no_wrap=True),
                    ft.IconButton(ft.Icons.CLOSE, icon_size=16,
                                  icon_color=Colors.TEXT_MUTED,
                                  on_click=make_delete(s["id"]), padding=0),
                ], alignment=ft.MainAxisAlignment.SPACE_BETWEEN),
                padding=10, border_radius=8,
                bgcolor=Colors.BG_SURFACE if is_active else "transparent",
                on_click=make_select(s["id"]), ink=True,
            )
            controls.append(item)

        btn_clear = ft.Container(
            content=ft.Row([
                ft.Icon(ft.Icons.DELETE_OUTLINE_ROUNDED, color=Colors.ERROR, size=18),
                ft.Text("Xóa tất cả", color=Colors.ERROR, size=Typography.BODY),
            ]),
            padding=10, border_radius=8, bgcolor=Colors.BG_SURFACE,
            on_click=lambda _: _clear_all_sessions(), ink=True,
        )
        if controls:
            controls.append(ft.Divider(color=Colors.BORDER))
        controls.append(btn_clear)
        history_lv.controls = controls
        try:
            page.update()
        except Exception:
            pass

    def _switch_session(sid):
        _state["session_id"] = sid
        _state["last_plan"] = None
        _load_active_session()
        if _history_state["open"]:
            toggle_history(None)

    def _delete_session(sid):
        ChatService.delete_session(user.id, sid)
        if _state["session_id"] == sid:
            _state["session_id"] = None
            _load_active_session()
        else:
            _load_sessions_ui()

    def _clear_all_sessions():
        ChatService.clear_all(user.id)
        _state["session_id"] = None
        _state["last_plan"] = None
        _load_active_session()

    def _load_active_session():
        chat_lv.controls.clear()
        sessions = ChatService.get_sessions(user.id)
        if not _state["session_id"]:
            if sessions:
                _state["session_id"] = sessions[0]["id"]
            else:
                _state["session_id"] = ChatService.create_session(user.id, "Chat mới")
        session = ChatService.get_session(user.id, _state["session_id"])
        if not session:
            _state["session_id"] = ChatService.create_session(user.id, "Chat mới")
            session = ChatService.get_session(user.id, _state["session_id"])

        history = session.get("messages", [])
        if not history:
            name = user.full_name or user.username
            welcome_text = (
                f"Xin chào {name}! 👋\n\n"
                f"Tôi là **Doumar** — trợ lý AI lập kế hoạch của bạn.\n"
                f"Hiện bạn có {total} công việc · ✅ {done} xong ({pct}%) · 📋 {pending} chờ\n\n"
                f"Thử nhập:\n"
                f'• "Lên kế hoạch làm đồ án OpenGL trong 5 ngày"\n'
                f'• "Mai 8h nhắc tôi nộp báo cáo"\n'
                f'• "Task nào cần làm trước?"'
            )
            chat_lv.controls.append(_bubble(welcome_text, is_user=False, animate=False))
            ChatService.add_message(user.id, _state["session_id"], "model", welcome_text)
        else:
            for msg in history:
                chat_lv.controls.append(
                    _bubble(msg["text"], is_user=(msg["role"] == "user"), animate=False)
                )

        chat_lv.controls.append(_typing)
        _load_sessions_ui()
        try:
            page.update()
            _scroll_down()
        except Exception:
            pass

    # ── Header ─────────────────────────────────────────────────
    header = ft.Container(
        content=ft.Row([
            ft.Container(
                content=ft.Image(src="avtdoumar.png", fit="cover"),
                width=44, height=44, border_radius=22,
                clip_behavior=ft.ClipBehavior.ANTI_ALIAS,
                shadow=ft.BoxShadow(blur_radius=10, color=Colors.PRIMARY_SHADOW,
                                    offset=ft.Offset(0, 3)),
            ),
            ft.Column([
                ft.Text("Doumar", size=Typography.H3,
                        color=Colors.TEXT_PRIMARY, weight=Typography.BOLD),
                ft.Row([
                    ft.Container(width=7, height=7, border_radius=4,
                                 bgcolor=Colors.SUCCESS),
                    ft.Text("AI Planner · Đang hoạt động", size=Typography.TINY,
                            color=Colors.SUCCESS),
                ], spacing=4, vertical_alignment=ft.CrossAxisAlignment.CENTER),
            ], spacing=2, tight=True),
            ft.Container(expand=True),
            ft.IconButton(
                icon=ft.Icons.ADD_COMMENT_ROUNDED,
                icon_color=Colors.TEXT_MUTED,
                tooltip="Chat mới",
                on_click=_start_new_chat,
            ),
            ft.Container(
                content=ft.Text("AI", size=Typography.TINY, color="white",
                                weight=Typography.BOLD),
                padding=ft.Padding.symmetric(horizontal=8, vertical=3),
                border_radius=Radius.FULL,
                gradient=ft.LinearGradient(
                    colors=[Colors.PRIMARY_LIGHT, Colors.PRIMARY],
                    begin=ft.Alignment.CENTER_LEFT,
                    end=ft.Alignment.CENTER_RIGHT,
                ),
            ),
        ], spacing=Spacing.SM, vertical_alignment=ft.CrossAxisAlignment.CENTER),
        padding=ft.Padding.symmetric(horizontal=Spacing.MD, vertical=Spacing.MD),
        border=ft.Border(bottom=ft.BorderSide(1, Colors.BORDER)),
        bgcolor=Colors.BG_DARKEST,
        shadow=ft.BoxShadow(blur_radius=8, color="#00000012", offset=ft.Offset(0, 2)),
    )

    # ── Assemble ───────────────────────────────────────────────
    main_chat = ft.Column([
        header,
        chat_lv,
        ft.Container(
            content=chips_row,
            padding=ft.Padding.symmetric(horizontal=Spacing.MD, vertical=Spacing.XS),
            border=ft.Border(top=ft.BorderSide(1, Colors.BORDER)),
        ),
        ft.Container(
            content=ft.Row([btn_menu, btn_attach, tf, send_btn], spacing=Spacing.SM),
            padding=ft.Padding.symmetric(horizontal=Spacing.MD, vertical=Spacing.SM),
            bgcolor=Colors.BG_DARKEST,
        ),
    ], spacing=0, tight=True, expand=True)

    _load_active_session()

    return ft.Row([main_chat, history_panel], expand=True, spacing=0)
