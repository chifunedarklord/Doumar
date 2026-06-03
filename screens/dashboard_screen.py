"""
TaskFlow - Dashboard / Home Screen
Màn hình chính với AI insights, burnout detection, smart schedule.
"""
import flet as ft
from datetime import datetime, date, timedelta
from core.theme import Colors, Typography, Spacing, Radius, CATEGORY_MAP, PRIORITY_MAP, STATUS_MAP
from core.models import Task
from core.services import TaskService, BehaviorService, AnalyticsService
from core.i18n import t, weekdays, months, greeting as i18n_greeting
from components.widgets import (
    glow_text, primary_divider, glass_card, primary_button,
    text_input, snack, avatar_circle, priority_badge,
    category_badge, status_chip, section_header, stat_card
)



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

    # ── Today focus time ─────────────────────────────────────
    try:
        from core.database import Storage as _Storage
        all_sessions = _Storage.get_work_sessions(user.id, limit=100)
        focus_today_mins = sum(
            s.get("duration_minutes", 0) if isinstance(s, dict)
            else getattr(s, "duration_minutes", 0)
            for s in all_sessions
            if (s.get("started_at", "") if isinstance(s, dict)
                else getattr(s, "started_at", "")).startswith(today_str)
        )
    except Exception:
        focus_today_mins = 0

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
    _greeting = i18n_greeting(hour)

    header = ft.Container(
        content=ft.Row([
            ft.Column([
                ft.Text(f"{_greeting},", size=Typography.BODY, color=Colors.TEXT_MUTED),
                ft.Text(user.full_name or user.username, size=Typography.H2,
                        color=Colors.TEXT_PRIMARY, weight=Typography.BOLD),
                ft.Text(now.strftime("%d/%m/%Y ") + weekdays()[now.weekday()],
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

    focus_h   = focus_today_mins // 60
    focus_m   = focus_today_mins % 60
    focus_str = f"{focus_h}h{focus_m:02d}" if focus_h else f"{focus_today_mins}p"

    overview_card = ft.Container(
        content=ft.Column([
            ft.Row([
                ft.Column([
                    ft.Text(t("overview"), size=Typography.H4,
                            color=Colors.TEXT_PRIMARY, weight=Typography.BOLD),
                    ft.Container(height=2),
                    ft.Row([
                        _mini_stat(str(total),           t("total_stat"),       Colors.PRIMARY),
                        _mini_stat(str(done),            t("done_stat"),        Colors.SUCCESS),
                        _mini_stat(str(in_prog),         t("in_progress_stat"), Colors.ACCENT_CYAN),
                        _mini_stat(str(overdue),         t("overdue_stat"),     Colors.ERROR),
                        _mini_stat(str(len(today_tasks)),t("today_stat"),       Colors.WARNING),
                    ], spacing=Spacing.SM),
                ], spacing=0, expand=True),
                progress_ring,
            ], alignment=ft.MainAxisAlignment.SPACE_BETWEEN,
               vertical_alignment=ft.CrossAxisAlignment.CENTER),
            ft.Container(height=Spacing.XS),
            ft.Container(
                content=ft.Row([
                    ft.Icon(ft.Icons.TIMER_OUTLINED, size=13, color=Colors.PRIMARY),
                    ft.Text(f"{t('focus_today')}: ", size=Typography.TINY, color=Colors.TEXT_MUTED),
                    ft.Text(focus_str, size=Typography.TINY, color=Colors.PRIMARY,
                            weight=Typography.SEMIBOLD),
                    ft.Container(width=8),
                    ft.Text(f"{completion_pct}% {t('pct_done')}", size=Typography.TINY,
                            color=Colors.SUCCESS if completion_pct >= 50 else Colors.TEXT_MUTED),
                ], spacing=4, vertical_alignment=ft.CrossAxisAlignment.CENTER),
                padding=ft.padding.symmetric(horizontal=6, vertical=4),
                border_radius=Radius.SM,
                bgcolor=Colors.PRIMARY_BG,
                border=ft.Border.all(1, Colors.PRIMARY_BORDER),
            ),
        ], spacing=0, tight=True),
        padding=Spacing.SM, border_radius=Radius.LG,
        gradient=ft.LinearGradient(colors=[Colors.BG_CARD, Colors.BG_SURFACE],
                                   begin=ft.Alignment.TOP_LEFT, end=ft.Alignment.BOTTOM_RIGHT),
        border=ft.Border.all(1, Colors.BORDER),
        shadow=ft.BoxShadow(blur_radius=16, color="#00000066", offset=ft.Offset(0, 4)),
    )

    # ── AI Insights card ─────────────────────────────────────
    burnout_color = burnout["color"]
    peak_str = ", ".join(f"{h:02d}h" for h in peak_hours) if peak_hours else t("no_data")
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
                    content=ft.Text(t("details"), size=Typography.TINY, color=Colors.PRIMARY),
                    on_tap=lambda _: on_navigate("report"),
                ),
            ], spacing=Spacing.SM, vertical_alignment=ft.CrossAxisAlignment.CENTER),
            ft.Container(height=Spacing.SM),
            ft.Row([
                _insight_chip("⚡", "Peak hours", peak_str, Colors.PRIMARY),
                _insight_chip("📊", t("weekly_score"), f"{productivity_score:.0f}/100", prod_color),
                _insight_chip("🔥", t("burnout_risk"), burnout["label"], burnout_color),
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
        quick_action("📋", t("qa_tasks"),    Colors.PRIMARY,     "tasks"),
        quick_action("📅", t("qa_calendar"), Colors.ACCENT_CYAN, "calendar"),
        quick_action("📊", t("qa_report"),   Colors.SUCCESS,     "report"),
        quick_action("🤖", t("qa_ai"),       Colors.PRIMARY,     "ai"),
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
                        ft.Text(f"{slot['duration_minutes']} {t('minutes_short')}", size=Typography.TINY, color=Colors.TEXT_MUTED),
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
                       t("schedule_subtitle"),
                       t("see_all"), lambda _: on_navigate("tasks")),
        ft.Container(height=Spacing.SM),
        ft.Column(
            [schedule_item(slot) for slot in schedule_slots if slot.get("task")] if schedule_slots
            else [ft.Text(t("no_schedule"), size=Typography.BODY,
                          color=Colors.TEXT_MUTED, text_align=ft.TextAlign.CENTER)],
            spacing=0, tight=True,
        ),
    ], spacing=0, tight=True)

    # ── Mini week calendar ────────────────────────────────────
    def week_day_chip(d: date) -> ft.Container:
        is_today = (d == date.today())
        has_task = any(t.due_date == d.isoformat() for t in tasks)
        wd = d.weekday()
        label = weekdays()[wd]
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
                ft.Text(f"{months()[today.month-1]} {today.year}", size=Typography.H4,
                        color=Colors.TEXT_PRIMARY, weight=Typography.SEMIBOLD),
                ft.Row([], expand=True),
                ft.TextButton(t("view_calendar"), on_click=lambda _: on_navigate("calendar"),
                              style=ft.ButtonStyle(color=Colors.PRIMARY, padding=ft.Padding.all(0))),
            ]),
            ft.Container(height=Spacing.SM),
            ft.Row([week_day_chip(d) for d in week_dates],
                   alignment=ft.MainAxisAlignment.SPACE_AROUND),
        ], spacing=0, tight=True),
        padding=Spacing.MD, border_radius=Radius.LG, bgcolor=Colors.BG_CARD,
        border=ft.Border.all(1, Colors.BORDER),
        shadow=ft.BoxShadow(blur_radius=12, color="#00000018", offset=ft.Offset(0, 3)),
    )

    # ── Priority Tasks Section ────────────────────────────────
    active_tasks = [t for t in tasks if t.status not in ("done", "cancelled")]
    overdue_t = [t for t in active_tasks if t.is_overdue]
    today_task_list = [t for t in active_tasks
                       if t.due_date == today_str and not t.is_overdue]
    upcoming_t = sorted(
        [t for t in active_tasks if t.due_date and t.due_date > today_str],
        key=lambda t: (t.due_date, {"high": 0, "medium": 1, "low": 2}.get(t.priority, 1))
    )
    priority_tasks = (overdue_t + today_task_list + upcoming_t)[:6]

    def _pri_task_row(t: Task):
        is_overdue = t.is_overdue
        pri_color = {"high": Colors.ERROR, "medium": Colors.WARNING, "low": Colors.PRIMARY}.get(
            t.priority, Colors.PRIMARY)
        date_color = Colors.ERROR if is_overdue else Colors.TEXT_MUTED
        return ft.Container(
            content=ft.Row([
                ft.Container(
                    width=3, height=None,
                    border_radius=Radius.FULL,
                    bgcolor=Colors.ERROR if is_overdue else pri_color,
                    expand_loose=True,
                ),
                ft.Container(width=8),
                ft.Column([
                    ft.Text(t.title, size=Typography.SMALL, color=Colors.TEXT_PRIMARY,
                            weight=Typography.MEDIUM, max_lines=1,
                            overflow=ft.TextOverflow.ELLIPSIS),
                    ft.Row([
                        ft.Text("⚠️" if is_overdue else "📅", size=10),
                        ft.Text(t.due_date_display, size=Typography.TINY, color=date_color),
                        ft.Text("·", size=Typography.TINY, color=Colors.TEXT_MUTED),
                        ft.Text(t.category, size=Typography.TINY, color=Colors.TEXT_MUTED),
                    ], spacing=4, tight=True),
                ], expand=True, spacing=2, tight=True),
                ft.GestureDetector(
                    content=ft.Icon(
                        ft.Icons.CHECK_CIRCLE if t.status == "done"
                        else ft.Icons.RADIO_BUTTON_UNCHECKED,
                        size=20,
                        color=Colors.SUCCESS if t.status == "done" else Colors.TEXT_MUTED,
                    ),
                    on_tap=lambda _, tt=t: [
                        TaskService.toggle_done(tt), on_navigate("dashboard")
                    ],
                ),
            ], vertical_alignment=ft.CrossAxisAlignment.CENTER),
            padding=ft.padding.symmetric(vertical=8, horizontal=10),
            border_radius=Radius.MD,
            bgcolor=f"#10{Colors.ERROR[1:]}" if is_overdue else Colors.BG_CARD,
            border=ft.Border.all(1, f"#30{Colors.ERROR[1:]}" if is_overdue else Colors.BORDER),
            margin=ft.margin.only(bottom=Spacing.XS),
            on_click=lambda _, tt=t: on_navigate("task_edit", task=tt),
            ink=True,
        )

    priority_section = ft.Column([
        section_header("🎯 " + t("priority_today"),
                       t("overdue_today_subtitle", o=len(overdue_t), d=len(today_task_list)),
                       t("see_all"), lambda _: on_navigate("tasks")),
        ft.Container(height=Spacing.SM),
        *(([_pri_task_row(tk) for tk in priority_tasks]) if priority_tasks else
          [ft.Container(
              content=ft.Text(t("no_priority_tasks"), size=Typography.BODY,
                              color=Colors.TEXT_MUTED, text_align=ft.TextAlign.CENTER),
              padding=ft.padding.symmetric(vertical=Spacing.MD),
          )]),
    ], spacing=0, tight=True)

    # ── AI Schedule Today card ────────────────────────────────
    # Bấm chip → set pending prompt → navigate sang AI chat → tự gửi
    _SCHED_PROMPTS = {
        "optimize":
            "Sắp xếp lại lịch và tối ưu hóa các công việc hôm nay cho tôi. "
            "Hãy xem xét deadline, giờ vàng tập trung và năng lượng hiện tại của tôi "
            "rồi đề xuất timeline cụ thể theo từng giờ.",
        "priority":
            "Ưu tiên và sắp xếp kế hoạch các task hôm nay theo tầm quan trọng và deadline. "
            "Việc nào khẩn cấp nhất? Lên lịch cụ thể cho từng task.",
        "what_first":
            "Việc nào tôi nên làm trước tiên trong hôm nay? "
            "Phân tích toàn bộ task và lập kế hoạch chi tiết theo thứ tự ưu tiên.",
    }

    def _go_to_ai(mode: str):
        from screens.ai_screen import set_pending_prompt as _spp
        _spp(_SCHED_PROMPTS.get(mode, _SCHED_PROMPTS["optimize"]))
        on_navigate("ai")

    def _sched_chip(label: str, mode: str, primary: bool = False):
        return ft.GestureDetector(
            on_tap=lambda _: _go_to_ai(mode),
            content=ft.Container(
                content=ft.Text(label, size=Typography.TINY,
                                color="white" if primary else Colors.PRIMARY,
                                weight=Typography.SEMIBOLD),
                padding=ft.padding.symmetric(horizontal=12, vertical=7),
                border_radius=Radius.FULL,
                gradient=ft.LinearGradient(
                    colors=["#A855F7", "#3B82F6"],
                    begin=ft.Alignment.CENTER_LEFT,
                    end=ft.Alignment.CENTER_RIGHT,
                ) if primary else None,
                bgcolor=None if primary else Colors.PRIMARY_BG,
                border=ft.Border.all(1, Colors.PRIMARY_BORDER) if not primary else None,
                shadow=ft.BoxShadow(blur_radius=8, color="#40A855F7",
                                    offset=ft.Offset(0, 2)) if primary else None,
            ),
        )

    ai_schedule_card = ft.Container(
        content=ft.Column([
            ft.Row([
                ft.Container(
                    content=ft.Row([
                        ft.Text("✨", size=14),
                        ft.Text("AI Sắp xếp hôm nay", size=Typography.BODY,
                                color="white", weight=Typography.BOLD),
                    ], spacing=6, tight=True),
                    padding=ft.padding.symmetric(horizontal=0),
                    expand=True,
                ),
                ft.Icon(ft.Icons.AUTO_AWESOME_ROUNDED, size=16,
                        color="rgba(255,255,255,0.6)"),
            ], spacing=Spacing.SM, vertical_alignment=ft.CrossAxisAlignment.CENTER),
            ft.Container(height=4),
            ft.Text(
                "Doumar phân tích deadline, năng lượng & giờ vàng của bạn → đề xuất timeline tối ưu",
                size=Typography.TINY, color="rgba(255,255,255,0.75)",
                max_lines=2, overflow=ft.TextOverflow.ELLIPSIS,
            ),
            ft.Container(height=Spacing.SM),
            ft.Row([
                _sched_chip("🗓️ Sắp xếp hôm nay",       "optimize",   primary=True),
                _sched_chip("🎯 Ưu tiên task",           "priority"),
                _sched_chip("❓ Làm gì trước?",           "what_first"),
            ], spacing=6, wrap=True),
        ], spacing=0, tight=True),
        padding=ft.padding.symmetric(horizontal=Spacing.MD, vertical=Spacing.MD),
        border_radius=Radius.LG,
        gradient=ft.LinearGradient(
            colors=["#1E1B4B", "#312E81", "#1E1B4B"],
            begin=ft.Alignment.TOP_LEFT,
            end=ft.Alignment.BOTTOM_RIGHT,
        ),
        border=ft.Border.all(1, "#5B21B6"),
        shadow=ft.BoxShadow(blur_radius=16, color="#40A855F7", offset=ft.Offset(0, 4)),
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
                ft.Container(height=Spacing.SM),
                ai_schedule_card,
                ft.Container(height=Spacing.LG),
                priority_section,
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
    from core.i18n import t
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
                ft.Text(t("checkin_title"), size=Typography.H4,
                        color=Colors.TEXT_PRIMARY, weight=Typography.BOLD, expand=True),
                ft.TextButton(
                    t("skip"),
                    on_click=_submit,
                    style=ft.ButtonStyle(color=Colors.TEXT_MUTED,
                                         padding=ft.Padding.all(0)),
                ),
            ], spacing=Spacing.SM, vertical_alignment=ft.CrossAxisAlignment.CENTER),
            ft.Text(t("checkin_subtitle"), size=Typography.TINY, color=Colors.TEXT_MUTED),
            ft.Container(height=Spacing.SM),
            ft.Row([
                ft.Text(t("checkin_energy_label"), size=Typography.SMALL, color=Colors.TEXT_SECONDARY,
                        width=100),
                energy_slider,
                energy_display,
            ], spacing=Spacing.SM, vertical_alignment=ft.CrossAxisAlignment.CENTER),
            ft.Row([
                ft.Text(t("checkin_mood_label"), size=Typography.SMALL, color=Colors.TEXT_SECONDARY,
                        width=100),
                mood_slider,
                mood_display,
            ], spacing=Spacing.SM, vertical_alignment=ft.CrossAxisAlignment.CENTER),
            ft.Container(height=Spacing.XS),
            primary_button(t("start_day"), on_click=_submit, height=44),
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
