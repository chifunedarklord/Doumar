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

    # ── Stats ───────────────────────────────────────────────
    total     = len(tasks)
    done      = sum(1 for t in tasks if t.status == "done")
    in_prog   = sum(1 for t in tasks if t.status == "in_progress")
    overdue   = sum(1 for t in tasks if t.is_overdue)
    today_tasks = [t for t in tasks if t.due_date == today_str and t.status != "done"]
    completion_pct = int(done / total * 100) if total else 0

    # ── AI Data ──────────────────────────────────────────────
    try:
        peak_hours = BehaviorService.get_peak_hours(user.id)
        productivity_score = BehaviorService.get_productivity_score(user.id)
    except Exception:
        peak_hours = [9, 10, 11]
        productivity_score = 0.0

    # ── Burnout detection ────────────────────────────────────
    try:
        from core.ai_engine import BurnoutDetector
        from core.database import Storage
        sessions = Storage.get_work_sessions(user.id, 50)
        events = Storage.get_behavior_events(user.id, limit=100)
        burnout = BurnoutDetector.get_risk(tasks, sessions, events)
    except Exception:
        burnout = {"level": "low", "label": "Thấp", "color": Colors.SUCCESS,
                   "score": 0, "reasons": [], "suggestions": []}

    # ── AI Priority Ranked tasks ─────────────────────────────
    try:
        from core.ai_engine import PriorityEngine
        current_hour = datetime.now().hour
        ctx = {"peak_hours": peak_hours, "current_hour": current_hour}
        ai_ranked = PriorityEngine.rank_tasks(tasks, ctx)[:3]
    except Exception:
        ai_ranked = [t for t in tasks if t.status not in ("done","cancelled")][:3]

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

    # ── Burnout warning banner (chỉ hiện nếu cao) ───────────
    burnout_banner = None
    if burnout["level"] in ("high", "critical") and burnout["suggestions"]:
        burnout_banner = ft.Container(
            content=ft.Row([
                ft.Text("⚠️", size=18),
                ft.Column([
                    ft.Text("Cảnh báo kiệt sức", size=Typography.SMALL,
                            color="#92400E", weight=Typography.BOLD),
                    ft.Text(burnout["suggestions"][0], size=Typography.TINY,
                            color="#92400E"),
                ], spacing=1, tight=True, expand=True),
            ], spacing=Spacing.SM, vertical_alignment=ft.CrossAxisAlignment.CENTER),
            padding=ft.Padding.symmetric(horizontal=Spacing.MD, vertical=Spacing.SM),
            border_radius=Radius.MD,
            bgcolor="#FEF3C7",
            border=ft.Border.all(1, "#FDE68A"),
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
        quick_action("📅", "Lịch biểu", Colors.PRIMARY, "calendar"),
        quick_action("📊", "Analytics",  Colors.PRIMARY, "report"),
        quick_action("👤", "Tài khoản",  Colors.PRIMARY, "profile"),
    ], alignment=ft.MainAxisAlignment.SPACE_AROUND)

    # ── AI Priority Tasks ────────────────────────────────────
    def ai_task_item(task: Task, rank: int) -> ft.Container:
        cat_info = CATEGORY_MAP.get(task.category, CATEGORY_MAP["personal"])
        pri_info = PRIORITY_MAP.get(task.priority, PRIORITY_MAP["medium"])
        score = getattr(task, "ai_priority_score", task.ai_priority_score)
        score_color = Colors.ERROR if score >= 75 else Colors.WARNING if score >= 50 else Colors.SUCCESS

        return ft.Container(
            content=ft.Row([
                ft.Container(
                    content=ft.Text(f"#{rank}", size=Typography.TINY,
                                    color="white", weight=Typography.BOLD),
                    width=28, height=28, border_radius=Radius.FULL,
                    bgcolor=score_color, alignment=ft.Alignment.CENTER,
                ),
                ft.Container(width=Spacing.SM),
                ft.Column([
                    ft.Text(task.title, size=Typography.BODY, color=Colors.TEXT_PRIMARY,
                            weight=Typography.MEDIUM, max_lines=1,
                            overflow=ft.TextOverflow.ELLIPSIS),
                    ft.Row([
                        ft.Text(cat_info["icon"], size=11),
                        ft.Text(cat_info["label"], size=Typography.TINY, color=Colors.TEXT_MUTED),
                        ft.Text("·", size=Typography.TINY, color=Colors.TEXT_MUTED),
                        ft.Text(task.due_date_display, size=Typography.TINY,
                                color=Colors.ERROR if task.is_overdue else Colors.TEXT_MUTED),
                    ], spacing=4, tight=True),
                ], spacing=2, expand=True, tight=True),
                ft.Column([
                    ft.Text(f"{score:.0f}", size=Typography.SMALL,
                            color=score_color, weight=Typography.BOLD),
                    ft.Text("AI score", size=8, color=Colors.TEXT_MUTED),
                ], horizontal_alignment=ft.CrossAxisAlignment.CENTER, spacing=0, tight=True),
            ], vertical_alignment=ft.CrossAxisAlignment.CENTER, spacing=0),
            padding=ft.Padding.symmetric(vertical=Spacing.SM, horizontal=Spacing.MD),
            border_radius=Radius.MD, bgcolor=Colors.BG_CARD,
            border=ft.Border.all(1, Colors.BORDER),
            margin=ft.Margin.only(bottom=Spacing.SM),
            on_click=lambda _: on_navigate("tasks"),
            ink=True,
        )

    ai_tasks_section = ft.Column([
        section_header("🤖 AI Ưu tiên hôm nay",
                       "Xếp hạng thông minh theo AI score",
                       "Tất cả", lambda _: on_navigate("tasks")),
        ft.Container(height=Spacing.SM),
        ft.Column(
            [ai_task_item(t, i+1) for i, t in enumerate(ai_ranked)] if ai_ranked
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
                overview_card,
                ft.Container(height=Spacing.SM),
                ai_insights_card,
                *([] if not burnout_banner else [ft.Container(height=Spacing.SM), burnout_banner]),
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


def _insight_chip(icon: str, label: str, value: str, color: str) -> ft.Container:
    return ft.Container(
        content=ft.Column([
            ft.Text(icon, size=18, text_align=ft.TextAlign.CENTER),
            ft.Text(value, size=Typography.TINY, color=color,
                    weight=Typography.BOLD, text_align=ft.TextAlign.CENTER),
            ft.Text(label, size=8, color=Colors.TEXT_MUTED, text_align=ft.TextAlign.CENTER),
        ], horizontal_alignment=ft.CrossAxisAlignment.CENTER, spacing=2, tight=True),
        padding=ft.Padding.symmetric(horizontal=Spacing.SM, vertical=Spacing.SM),
        border_radius=Radius.MD, bgcolor=color + "15",
        border=ft.Border.all(1, color + "40"),
        expand=True,
    )
