"""
TaskFlow - Dashboard / Home Screen
Màn hình chính với AI insights, burnout detection, smart schedule.
"""
import flet as ft
from datetime import datetime, date, timedelta
from core.theme import Colors, Typography, Spacing, Radius, CATEGORY_MAP, PRIORITY_MAP, STATUS_MAP
from core.models import Task
from core.services import TaskService, BehaviorService, AnalyticsService
from components.widgets import (
    glow_text, primary_divider, glass_card, primary_button,
    text_input, snack, avatar_circle, priority_badge,
    category_badge, status_chip, section_header, stat_card
)

WEEKDAYS_VI = ["T2", "T3", "T4", "T5", "T6", "T7", "CN"]
MONTHS_VI   = ["Tháng 1","Tháng 2","Tháng 3","Tháng 4","Tháng 5","Tháng 6",
               "Tháng 7","Tháng 8","Tháng 9","Tháng 10","Tháng 11","Tháng 12"]


def build_dashboard(page: ft.Page, user, on_navigate):
    tasks = TaskService.get_tasks(user.id)
    today_str = date.today().isoformat()

    # ── Daily Check-in ──────────────────────────────────────
    checkin_card = _build_checkin_card(page, user)

    # ── Stats ───────────────────────────────────────────────
    total     = len(tasks)
    done      = sum(1 for t in tasks if t.status == "done")
    in_prog   = sum(1 for t in tasks if t.status == "in_progress")
    overdue   = sum(1 for t in tasks if t.is_overdue)
    today_tasks = [t for t in tasks if t.due_date == today_str and t.status != "done"]
    completion_pct = int(done / total * 100) if total else 0

    # ── AI Data (Cached) ─────────────────────────────────────
    try:
        report = AnalyticsService.get_full_report(user.id)
        peak_hours = report.get("peak_hours", [9, 10, 11])
        productivity_score = report.get("weekly_score", 0.0)
        burnout = report.get("burnout", {
            "level": "low", "label": "Thấp", "color": Colors.SUCCESS,
            "score": 0, "reasons": [], "suggestions": []
        })
    except Exception:
        peak_hours = [9, 10, 11]
        productivity_score = 0.0
        burnout = {"level": "low", "label": "Thấp", "color": Colors.SUCCESS,
                   "score": 0, "reasons": [], "suggestions": []}

    # ── Smart Schedule ─────────────────────────────
    try:
        from core.intelligence.scheduling_engine import SchedulingEngine
        from core.services import AIMemoryService
        current_hour = datetime.now().hour

        checkin_energy = AIMemoryService.recall_value(user.id, "state", "estimated_energy")
        checkin_stress = AIMemoryService.recall_value(user.id, "state", "estimated_stress")
        energy_level = int(checkin_energy) if checkin_energy is not None else getattr(user, "energy_level", 7)
        stress_level = int(checkin_stress) if checkin_stress is not None else getattr(user, "stress_level", 5)

        work_start_raw = getattr(user, "work_start", "08:00")
        work_end_raw   = getattr(user, "work_end",   "18:00")
        try:
            work_start_hour = int(work_start_raw.split(":")[0])
        except Exception:
            work_start_hour = 8
        try:
            work_end_hour = int(work_end_raw.split(":")[0])
        except Exception:
            work_end_hour = 20

        ctx = {
            "peak_hours":             peak_hours,
            "current_hour":           current_hour,
            "energy_level":           energy_level,
            "stress_level":           stress_level,
            "daily_workload_minutes": sum(
                getattr(t, "estimated_minutes", 30)
                for t in tasks
                if t.status not in ("done", "cancelled")
                and getattr(t, "due_date", None) == today_str
            ),
            "work_start_hour": work_start_hour,
            "work_end_hour":   work_end_hour,
            "user_id":         user.id,
        }
        schedule_slots = SchedulingEngine.suggest_today(tasks, peak_hours, ctx)
    except Exception:
        schedule_slots = []

    # ── Header ───────────────────────────────────────────────
    now = datetime.now()
    hour = now.hour
    greeting = ("Chào buổi sáng" if hour < 12 else
                "Chào buổi chiều" if hour < 18 else "Chào buổi tối")

    header = ft.Container(
        content=ft.Row([
            ft.Column([
                ft.Text(f"{greeting},", size=Typography.BODY, color=Colors.TEXT_MUTED),
                ft.Text(user.full_name or user.username, size=Typography.H2,
                        color=Colors.TEXT_PRIMARY, weight=Typography.BOLD),
                ft.Text(now.strftime("%A, %d/%m/%Y").replace(
                    "Monday","Thứ Hai").replace("Tuesday","Thứ Ba")
                    .replace("Wednesday","Thứ Tư").replace("Thursday","Thứ Năm")
                    .replace("Friday","Thứ Sáu").replace("Saturday","Thứ Bảy")
                    .replace("Sunday","Chủ Nhật"),
                        size=Typography.SMALL, color=Colors.TEXT_MUTED),
            ], spacing=2, tight=True),
            ft.Row([], expand=True),
            ft.GestureDetector(
                content=avatar_circle(user.full_name or user.username,
                                      color=user.avatar_color, size=48),
                on_tap=lambda _: on_navigate("profile"),
            )
        ], alignment=ft.MainAxisAlignment.SPACE_BETWEEN,
           vertical_alignment=ft.CrossAxisAlignment.CENTER),
        padding=ft.Padding.symmetric(horizontal=Spacing.MD, vertical=Spacing.MD),
    )

    # ── Overview card ────────────────────────────────────────
    progress_ring = ft.Container(
        content=ft.Stack([
            ft.Container(
                content=ft.ProgressRing(value=completion_pct / 100, width=60, height=60,
                                        stroke_width=5, color=Colors.PRIMARY,
                                        bgcolor=Colors.BG_SURFACE),
                alignment=ft.Alignment.CENTER,
            ),
            ft.Container(
                content=ft.Column([
                    ft.Text(f"{completion_pct}%", size=Typography.BODY,
                            color=Colors.PRIMARY, weight=Typography.BOLD),
                    ft.Text("done", size=Typography.TINY, color=Colors.TEXT_MUTED),
                ], horizontal_alignment=ft.CrossAxisAlignment.CENTER, spacing=0, tight=True),
                alignment=ft.Alignment.CENTER,
            ),
        ]),
        width=60, height=60,
    )

    overview_card = ft.Container(
        content=ft.Row([
            ft.Column([
                ft.Text("Tổng quan công việc", size=Typography.H4,
                        color=Colors.TEXT_PRIMARY, weight=Typography.BOLD),
                ft.Container(height=2),
                ft.Row([
                    _mini_stat(str(total),   "Tổng",       Colors.PRIMARY),
                    _mini_stat(str(done),    "Hoàn thành", Colors.SUCCESS),
                    _mini_stat(str(in_prog), "Đang làm",   Colors.ACCENT_CYAN),
                    _mini_stat(str(overdue), "Quá hạn",    Colors.ERROR),
                ], spacing=Spacing.SM),
            ], spacing=0, expand=True),
            progress_ring,
        ], alignment=ft.MainAxisAlignment.SPACE_BETWEEN,
           vertical_alignment=ft.CrossAxisAlignment.CENTER),
        padding=Spacing.SM, border_radius=Radius.LG,
        gradient=ft.LinearGradient(colors=[Colors.BG_CARD, Colors.BG_SURFACE],
                                   begin=ft.Alignment.TOP_LEFT, end=ft.Alignment.BOTTOM_RIGHT),
        border=ft.Border.all(1, Colors.BORDER),
        shadow=ft.BoxShadow(blur_radius=16, color="#00000066", offset=ft.Offset(0, 4)),
    )

    # ── AI Insights card ─────────────────────────────────────
    burnout_color = burnout["color"]
    peak_str = ", ".join(f"{h:02d}h" for h in peak_hours) if peak_hours else "Chưa có dữ liệu"
    prod_color = Colors.SUCCESS if productivity_score >= 70 else Colors.WARNING if productivity_score >= 40 else Colors.ERROR

    ai_insights_card = ft.Container(
        content=ft.Column([
            ft.Row([
                ft.Container(
                    content=ft.Text("🤖", size=16),
                    width=32, height=32, border_radius=Radius.SM,
                    bgcolor="#EFF6FF", alignment=ft.Alignment.CENTER,
                ),
                ft.Text("AI Insights", size=Typography.H4,
                        color=Colors.TEXT_PRIMARY, weight=Typography.BOLD),
                ft.Row([], expand=True),
                ft.GestureDetector(
                    content=ft.Text("Chi tiết", size=Typography.TINY, color=Colors.PRIMARY),
                    on_tap=lambda _: on_navigate("report"),
                ),
            ], spacing=Spacing.SM, vertical_alignment=ft.CrossAxisAlignment.CENTER),
            ft.Container(height=Spacing.SM),
            ft.Row([
                _insight_chip("⚡", "Peak hours", peak_str, Colors.PRIMARY),
                _insight_chip("📊", "Năng suất tuần", f"{productivity_score:.0f}/100", prod_color),
                _insight_chip("🔥", "Burnout risk", burnout["label"], burnout_color),
            ], spacing=Spacing.SM),
        ], spacing=0, tight=True),
        padding=Spacing.MD, border_radius=Radius.LG,
        bgcolor=Colors.BG_CARD, border=ft.Border.all(1, Colors.BORDER),
        shadow=ft.BoxShadow(blur_radius=12, color="#00000018", offset=ft.Offset(0, 3)),
    )

    # ── Actionable Advice Banner ───────────────────────────
    try:
        suggestions = report.get("recommendations", [])
    except Exception:
        suggestions = []

    advice_banner = None
    if suggestions:
        sug = suggestions[0]
        pri = sug.get("priority", "low")
        if pri == "critical":
            banner_bg     = f"#20{Colors.ERROR[1:]}"
            banner_border = f"#50{Colors.ERROR[1:]}"
            title_color   = Colors.ERROR
        elif pri == "high":
            banner_bg     = f"#20{Colors.WARNING[1:]}"
            banner_border = f"#50{Colors.WARNING[1:]}"
            title_color   = Colors.WARNING
        else:
            banner_bg     = f"#20{Colors.PRIMARY[1:]}"
            banner_border = Colors.PRIMARY_BORDER
            title_color   = Colors.PRIMARY

        advice_banner = ft.Container(
            content=ft.Row([
                ft.Text(sug.get("icon", "💡"), size=18),
                ft.Column([
                    ft.Text(sug.get("title", ""), size=Typography.SMALL,
                            color=title_color, weight=Typography.BOLD),
                    ft.Text(sug.get("message", ""), size=Typography.TINY,
                            color=Colors.TEXT_SECONDARY),
                ], spacing=1, tight=True, expand=True),
            ], spacing=Spacing.SM, vertical_alignment=ft.CrossAxisAlignment.CENTER),
            padding=ft.Padding.symmetric(horizontal=Spacing.MD, vertical=Spacing.SM),
            border_radius=Radius.MD,
            bgcolor=banner_bg,
            border=ft.Border.all(1, banner_border),
        )

    # ── Quick actions ────────────────────────────────────────
    def quick_action(icon, label, color, route):
        return ft.GestureDetector(
            content=ft.Container(
                content=ft.Column([
                    ft.Container(
                        content=ft.Text(icon, size=22),
                        width=48, height=48, border_radius=Radius.MD,
                        bgcolor=Colors.PRIMARY_BG, alignment=ft.Alignment.CENTER,
                        border=ft.Border.all(1, Colors.PRIMARY_BORDER),
                        shadow=ft.BoxShadow(blur_radius=10, color=Colors.PRIMARY_SHADOW,
                                            offset=ft.Offset(0, 3)),
                    ),
                    ft.Text(label, size=Typography.TINY, color=Colors.TEXT_SECONDARY,
                            text_align=ft.TextAlign.CENTER),
                ], horizontal_alignment=ft.CrossAxisAlignment.CENTER, spacing=Spacing.XS),
                padding=Spacing.SM,
            ),
            on_tap=lambda _: on_navigate(route),
        )

    quick_actions = ft.Row([
        quick_action("📋", "Công việc",  Colors.PRIMARY, "tasks"),
        quick_action("📁", "Dự án",      Colors.PRIMARY, "projects"),
        quick_action("📅", "Lịch biểu", Colors.PRIMARY, "calendar"),
        quick_action("📊", "Analytics",  Colors.PRIMARY, "report"),
    ], alignment=ft.MainAxisAlignment.SPACE_AROUND)

    # ── Smart Schedule Timeline ──────────────────────────────
    def schedule_item(slot: dict) -> ft.Container:
        task = slot["task"]
        cat_info = CATEGORY_MAP.get(task.category, CATEGORY_MAP["personal"])
        _block_colors = {"deep_work": Colors.PRIMARY, "quick_win": Colors.ACCENT_TEAL, "regular": Colors.SUCCESS}
        score_color = _block_colors.get(slot["block_type"], Colors.SUCCESS)
        start_h = slot["suggested_hour"]
        end_h = start_h + max(1, slot["duration_minutes"] // 60)

        return ft.Container(
            content=ft.Row([
                ft.Column([
                    ft.Text(f"{start_h:02d}:00", size=Typography.SMALL, color=Colors.TEXT_PRIMARY, weight=Typography.BOLD),
                    ft.Text(f"{end_h:02d}:00", size=Typography.TINY, color=Colors.TEXT_MUTED),
                ], alignment=ft.MainAxisAlignment.CENTER, horizontal_alignment=ft.CrossAxisAlignment.END, width=45, spacing=2),
                ft.Container(width=2, height=40, bgcolor=score_color, border_radius=Radius.FULL),
                ft.Column([
                    ft.Text(task.title, size=Typography.BODY, color=Colors.TEXT_PRIMARY,
                            weight=Typography.MEDIUM, max_lines=1,
                            overflow=ft.TextOverflow.ELLIPSIS),
                    ft.Row([
                        ft.Text(cat_info["icon"], size=11),
                        ft.Text(f"{slot['duration_minutes']} phút", size=Typography.TINY, color=Colors.TEXT_MUTED),
                        ft.Text("·", size=Typography.TINY, color=Colors.TEXT_MUTED),
                        ft.Text({"deep_work": "Deep Work", "quick_win": "Quick Win", "regular": "Regular"}.get(
                            slot["block_type"], "Regular"), size=Typography.TINY, color=score_color),
                    ], spacing=4, tight=True),
                ], spacing=2, expand=True, tight=True),
            ], vertical_alignment=ft.CrossAxisAlignment.CENTER, spacing=Spacing.SM),
            padding=ft.Padding.symmetric(vertical=Spacing.SM, horizontal=Spacing.SM),
            border_radius=Radius.MD, bgcolor=Colors.BG_CARD,
            border=ft.Border.all(1, Colors.BORDER),
            margin=ft.Margin.only(bottom=Spacing.SM),
            on_click=lambda _: on_navigate("tasks"),
            ink=True,
        )

    ai_tasks_section = ft.Column([
        section_header("✨ AI Smart Schedule",
                       "Lịch làm việc tối ưu năng lượng hôm nay",
                       "Tất cả", lambda _: on_navigate("tasks")),
        ft.Container(height=Spacing.SM),
        ft.Column(
            [schedule_item(slot) for slot in schedule_slots] if schedule_slots
            else [ft.Text("🎉 Không có việc cần làm!", size=Typography.BODY,
                          color=Colors.TEXT_MUTED, text_align=ft.TextAlign.CENTER)],
            spacing=0, tight=True,
        ),
    ], spacing=0, tight=True)

    # ── Mini week calendar ────────────────────────────────────
    def week_day_chip(d: date) -> ft.Container:
        is_today = (d == date.today())
        has_task = any(t.due_date == d.isoformat() for t in tasks)
        wd = d.weekday()
        label = WEEKDAYS_VI[wd] if wd < 7 else "CN"
        return ft.Container(
            content=ft.Column([
                ft.Text(label, size=Typography.TINY,
                        color=Colors.PRIMARY if is_today else Colors.TEXT_MUTED,
                        weight=Typography.SEMIBOLD if is_today else Typography.REGULAR),
                ft.Container(
                    content=ft.Text(str(d.day), size=Typography.BODY,
                                    color=Colors.BG_DARKEST if is_today else Colors.TEXT_PRIMARY,
                                    weight=Typography.BOLD if is_today else Typography.REGULAR),
                    width=34, height=34, border_radius=Radius.FULL,
                    bgcolor=Colors.PRIMARY if is_today else "transparent",
                    alignment=ft.Alignment.CENTER,
                ),
                ft.Container(width=5, height=5, border_radius=Radius.FULL,
                             bgcolor=Colors.PRIMARY if has_task else "transparent"),
            ], horizontal_alignment=ft.CrossAxisAlignment.CENTER, spacing=3, tight=True),
            padding=ft.Padding.symmetric(horizontal=Spacing.SM, vertical=Spacing.XS),
        )

    today = date.today()
    start_of_week = today - timedelta(days=today.weekday())
    week_dates = [start_of_week + timedelta(days=i) for i in range(7)]
    week_card = ft.Container(
        content=ft.Column([
            ft.Row([
                ft.Text(f"{MONTHS_VI[today.month-1]} {today.year}", size=Typography.H4,
                        color=Colors.TEXT_PRIMARY, weight=Typography.SEMIBOLD),
                ft.Row([], expand=True),
                ft.TextButton("Xem lịch", on_click=lambda _: on_navigate("calendar"),
                              style=ft.ButtonStyle(color=Colors.PRIMARY, padding=ft.Padding.all(0))),
            ]),
            ft.Container(height=Spacing.SM),
            ft.Row([week_day_chip(d) for d in week_dates],
                   alignment=ft.MainAxisAlignment.SPACE_AROUND),
        ], spacing=0, tight=True),
        padding=Spacing.MD, border_radius=Radius.LG, bgcolor=Colors.BG_CARD,
        border=ft.border.all(1, Colors.BORDER),
        shadow=ft.BoxShadow(blur_radius=12, color="#00000018", offset=ft.Offset(0, 3)),
    )

    # ── Assemble ──────────────────────────────────────────────
    main_items = [
        header,
        ft.Container(
            content=ft.Column([
                *([] if checkin_card is None else [checkin_card, ft.Container(height=Spacing.SM)]),
                overview_card,
                ft.Container(height=Spacing.SM),
                ai_insights_card,
                *([] if not advice_banner else [ft.Container(height=Spacing.SM), advice_banner]),
                ft.Container(height=Spacing.LG),
                quick_actions,
                ft.Container(height=Spacing.LG),
                week_card,
                ft.Container(height=Spacing.LG),
                ai_tasks_section,
                ft.Container(height=Spacing.XXXL),
            ], spacing=0, tight=True),
            padding=ft.Padding.symmetric(horizontal=Spacing.MD),
        ),
    ]

    return ft.Column(main_items, spacing=0, tight=True,
                     scroll=ft.ScrollMode.AUTO, expand=True)


# ─── Helpers ──────────────────────────────────────────────────────────────────

def _mini_stat(value: str, label: str, color: str) -> ft.Column:
    return ft.Column([
        ft.Text(value, size=Typography.BODY, color=color, weight=Typography.BOLD),
        ft.Text(label, size=Typography.TINY, color=Colors.TEXT_MUTED),
    ], horizontal_alignment=ft.CrossAxisAlignment.CENTER, spacing=0, tight=True)


def _build_checkin_card(page: ft.Page, user) -> ft.Container | None:
    """Returns check-in card if not yet done today, otherwise None."""
    from core.services import AIMemoryService, BehaviorService
    today_str = date.today().isoformat()
    last_checkin = AIMemoryService.recall_value(user.id, "state", "last_checkin_date")
    if last_checkin == today_str:
        return None

    state = {"energy": 7, "mood": 3, "submitted": False}
    card_ref = ft.Ref[ft.Container]()

    energy_display = ft.Text("7", size=Typography.H4, color=Colors.PRIMARY,
                             weight=Typography.BOLD, width=24,
                             text_align=ft.TextAlign.CENTER)
    mood_display   = ft.Text("3", size=Typography.H4, color=Colors.SUCCESS,
                             weight=Typography.BOLD, width=24,
                             text_align=ft.TextAlign.CENTER)

    energy_slider = ft.Slider(
        min=1, max=10, divisions=9, value=7,
        active_color=Colors.PRIMARY, thumb_color=Colors.PRIMARY,
        on_change=lambda e: _on_energy(e),
    )
    mood_slider = ft.Slider(
        min=1, max=5, divisions=4, value=3,
        active_color=Colors.SUCCESS, thumb_color=Colors.SUCCESS,
        on_change=lambda e: _on_mood(e),
    )

    def _on_energy(e):
        state["energy"] = int(e.control.value)
        energy_display.value = str(state["energy"])
        page.update()

    def _on_mood(e):
        state["mood"] = int(e.control.value)
        mood_display.value = str(state["mood"])
        page.update()

    def _submit(_):
        if state["submitted"]:
            return
        state["submitted"] = True
        energy = state["energy"]
        mood   = state["mood"]
        AIMemoryService.remember(user.id, "state", "estimated_energy", energy, 0.9)
        AIMemoryService.remember(user.id, "state", "estimated_mood",   mood,   0.9)
        AIMemoryService.remember(user.id, "state", "last_checkin_date", today_str, 1.0)
        BehaviorService.log(user.id, "daily_checkin", {"energy": energy, "mood": mood})
        if card_ref.current:
            card_ref.current.visible = False
            page.update()

    return ft.Container(
        ref=card_ref,
        content=ft.Column([
            ft.Row([
                ft.Text("☀️", size=18),
                ft.Text("Check-in buổi sáng", size=Typography.H4,
                        color=Colors.TEXT_PRIMARY, weight=Typography.BOLD, expand=True),
                ft.TextButton(
                    "Bỏ qua",
                    on_click=_submit,
                    style=ft.ButtonStyle(color=Colors.TEXT_MUTED,
                                         padding=ft.Padding.all(0)),
                ),
            ], spacing=Spacing.SM, vertical_alignment=ft.CrossAxisAlignment.CENTER),
            ft.Text("Hôm nay bạn thế nào?", size=Typography.TINY, color=Colors.TEXT_MUTED),
            ft.Container(height=Spacing.SM),
            ft.Row([
                ft.Text("⚡ Năng lượng", size=Typography.SMALL, color=Colors.TEXT_SECONDARY,
                        width=100),
                energy_slider,
                energy_display,
            ], spacing=Spacing.SM, vertical_alignment=ft.CrossAxisAlignment.CENTER),
            ft.Row([
                ft.Text("😊 Tâm trạng", size=Typography.SMALL, color=Colors.TEXT_SECONDARY,
                        width=100),
                mood_slider,
                mood_display,
            ], spacing=Spacing.SM, vertical_alignment=ft.CrossAxisAlignment.CENTER),
            ft.Container(height=Spacing.XS),
            primary_button("Bắt đầu ngày mới 🚀", on_click=_submit, height=44),
        ], spacing=4, tight=True),
        padding=Spacing.MD,
        border_radius=Radius.LG,
        bgcolor=Colors.BG_CARD,
        border=ft.Border.all(1, Colors.PRIMARY_BORDER),
        shadow=ft.BoxShadow(blur_radius=12, color=Colors.PRIMARY_SHADOW,
                            offset=ft.Offset(0, 3)),
    )


def _insight_chip(icon: str, label: str, value: str, color: str) -> ft.Container:
    # Flet uses ARGB (#AARRGGBB).
    # Convert "#RRGGBB" to "#15RRGGBB" (15 hex is ~8% opacity, 20 is ~12%)
    bg_color = f"#20{color[1:]}" if color.startswith("#") else color
    border_color = f"#40{color[1:]}" if color.startswith("#") else color
    
    return ft.Container(
        content=ft.Column([
            ft.Text(icon, size=18, text_align=ft.TextAlign.CENTER),
            ft.Text(value, size=Typography.TINY, color=color,
                    weight=Typography.BOLD, text_align=ft.TextAlign.CENTER),
            ft.Text(label, size=10, color=Colors.TEXT_MUTED, text_align=ft.TextAlign.CENTER),
        ], horizontal_alignment=ft.CrossAxisAlignment.CENTER, spacing=2, tight=True),
        padding=ft.Padding.symmetric(horizontal=Spacing.SM, vertical=Spacing.SM),
        border_radius=Radius.MD, bgcolor=bg_color,
        border=ft.Border.all(1, border_color),
        expand=True,
    )
