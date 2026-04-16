"""
TaskFlow - Dashboard / Home Screen
Màn hình chính với tổng quan công việc, lịch trình hôm nay.
"""
import flet as ft
from datetime import datetime, date, timedelta
from core.theme import Colors, Typography, Spacing, Radius, CATEGORY_MAP, PRIORITY_MAP, STATUS_MAP
from core.models import Task
from core.services import TaskService
from components.widgets import (
    glow_text, primary_divider, glass_card, primary_button,
    text_input, snack, avatar_circle, priority_badge,
    category_badge, status_chip, section_header, stat_card
)


WEEKDAYS_VI = ["T2", "T3", "T4", "T5", "T6", "T7", "CN"]
MONTHS_VI   = ["Tháng 1","Tháng 2","Tháng 3","Tháng 4","Tháng 5","Tháng 6",
               "Tháng 7","Tháng 8","Tháng 9","Tháng 10","Tháng 11","Tháng 12"]


def build_dashboard(page: ft.Page, user, on_navigate):
    """
    Tham số:
      page        - ft.Page
      user        - User object
      on_navigate - callback(route_name)  # "tasks" | "calendar" | "report" | "profile"
    """
    tasks = TaskService.get_tasks(user.id)
    today_str = date.today().isoformat()

    # ── Stats ────────────────────────────────────────────────
    total     = len(tasks)
    done      = sum(1 for t in tasks if t.status == "done")
    in_prog   = sum(1 for t in tasks if t.status == "in_progress")
    overdue   = sum(1 for t in tasks if t.is_overdue)
    today_tasks = [t for t in tasks if t.due_date == today_str and t.status != "done"]

    completion_pct = int(done / total * 100) if total else 0

    # ── Header ───────────────────────────────────────────────
    now  = datetime.now()
    hour = now.hour
    greeting = ("Chào buổi sáng" if hour < 12 else
                "Chào buổi chiều" if hour < 18 else "Chào buổi tối")

    header = ft.Container(
        content=ft.Row([
            ft.Column([
                ft.Text(f"{greeting},", size=Typography.BODY,
                        color=Colors.TEXT_MUTED),
                ft.Text(user.full_name or user.username,
                        size=Typography.H2, color=Colors.TEXT_PRIMARY,
                        weight=Typography.BOLD),
                ft.Text(now.strftime("%A, %d %B %Y").replace(
                    "Monday","Thứ Hai").replace("Tuesday","Thứ Ba")
                    .replace("Wednesday","Thứ Tư").replace("Thursday","Thứ Năm")
                    .replace("Friday","Thứ Sáu").replace("Saturday","Thứ Bảy")
                    .replace("Sunday","Chủ Nhật")
                    .replace("January","tháng 1").replace("February","tháng 2")
                    .replace("March","tháng 3").replace("April","tháng 4")
                    .replace("May","tháng 5").replace("June","tháng 6")
                    .replace("July","tháng 7").replace("August","tháng 8")
                    .replace("September","tháng 9").replace("October","tháng 10")
                    .replace("November","tháng 11").replace("December","tháng 12"),
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

    # ── Progress ring ────────────────────────────────────────
    progress_ring = ft.Container(
        content=ft.Stack([
            ft.Container(
                content=ft.ProgressRing(
                    value=completion_pct / 100,
                    width=60, height=60,
                    stroke_width=5,
                    color=Colors.PRIMARY,
                    bgcolor=Colors.BG_SURFACE,
                ),
                alignment=ft.Alignment.CENTER,
            ),
            ft.Container(
                content=ft.Column([
                    ft.Text(f"{completion_pct}%", size=Typography.BODY,
                            color=Colors.PRIMARY, weight=Typography.BOLD),
                    ft.Text("done", size=Typography.TINY, color=Colors.TEXT_MUTED),
                ], horizontal_alignment=ft.CrossAxisAlignment.CENTER,
                   spacing=0, tight=True),
                alignment=ft.Alignment.CENTER,
            ),
        ]),
        width=60, height=60,
    )

    overview_card = ft.Container(
        content=ft.Row([
            ft.Column([
                ft.Text("Tổng quan hôm nay", size=Typography.H4,
                        color=Colors.TEXT_PRIMARY, weight=Typography.BOLD),
                ft.Container(height=2),
                ft.Row([
                    _mini_stat(str(total), "Tổng", Colors.PRIMARY),
                    _mini_stat(str(done), "Xong", Colors.PRIMARY),
                    _mini_stat(str(in_prog), "Đang làm", Colors.PRIMARY),
                    _mini_stat(str(overdue), "Quá hạn", Colors.PRIMARY),
                ], spacing=Spacing.SM),
            ], spacing=0, expand=True),
            progress_ring,
        ], alignment=ft.MainAxisAlignment.SPACE_BETWEEN,
           vertical_alignment=ft.CrossAxisAlignment.CENTER),
        padding=Spacing.SM,
        border_radius=Radius.LG,
        gradient=ft.LinearGradient(
            colors=[Colors.BG_CARD, Colors.BG_SURFACE],
            begin=ft.Alignment.TOP_LEFT,
            end=ft.Alignment.BOTTOM_RIGHT,
        ),
        border=ft.Border.all(1, Colors.BORDER),
        shadow=ft.BoxShadow(blur_radius=16, color="#00000066",
                            offset=ft.Offset(0, 4)),
    )

    # ── Quick action buttons ──────────────────────────────────
    def quick_action(icon, label, color, route):
        return ft.GestureDetector(
            content=ft.Container(
                content=ft.Column([
                    ft.Container(
                        content=ft.Text(icon, size=22),
                        width=48, height=48,
                        border_radius=Radius.MD,
                        bgcolor=Colors.PRIMARY_BG,
                        alignment=ft.Alignment.CENTER,
                        border=ft.Border.all(1, Colors.PRIMARY_BORDER),
                        shadow=ft.BoxShadow(
                            blur_radius=10,
                            color=Colors.PRIMARY_SHADOW,
                            offset=ft.Offset(0, 3),
                        ),
                    ),
                    ft.Text(label, size=Typography.TINY, color=Colors.TEXT_SECONDARY,
                            text_align=ft.TextAlign.CENTER),
                ], horizontal_alignment=ft.CrossAxisAlignment.CENTER,
                   spacing=Spacing.XS),
                padding=Spacing.SM,
            ),
            on_tap=lambda _: on_navigate(route),
        )

    quick_actions = ft.Row([
        quick_action("📋", "Công việc",  Colors.PRIMARY, "tasks"),
        quick_action("📅", "Lịch biểu",  Colors.PRIMARY,   "calendar"),
        quick_action("📊", "Báo cáo",    Colors.PRIMARY, "report"),
        quick_action("👤", "Tài khoản",  Colors.PRIMARY, "profile"),
    ], alignment=ft.MainAxisAlignment.SPACE_AROUND)

    # ── Today tasks list ─────────────────────────────────────
    def task_item(task: Task) -> ft.Container:
        cat_info = CATEGORY_MAP.get(task.category, CATEGORY_MAP["personal"])
        pri_info = PRIORITY_MAP.get(task.priority, PRIORITY_MAP["medium"])

        return ft.Container(
            content=ft.Row([
                ft.Container(
                    width=4, height=52,
                    border_radius=Radius.FULL,
                    bgcolor=pri_info["color"],
                ),
                ft.Container(width=Spacing.SM),
                ft.Column([
                    ft.Text(task.title, size=Typography.BODY,
                            color=Colors.TEXT_PRIMARY, weight=Typography.MEDIUM,
                            max_lines=1, overflow=ft.TextOverflow.ELLIPSIS),
                    ft.Row([
                        ft.Text(cat_info["icon"], size=11),
                        ft.Text(cat_info["label"], size=Typography.TINY,
                                color=Colors.TEXT_MUTED),
                        ft.Text("·", size=Typography.TINY, color=Colors.TEXT_MUTED),
                        ft.Text(task.due_date_display, size=Typography.TINY,
                                color=Colors.ERROR if task.is_overdue else Colors.TEXT_MUTED),
                    ], spacing=4, tight=True),
                ], spacing=2, expand=True, tight=True),
                status_chip(task.status),
            ], vertical_alignment=ft.CrossAxisAlignment.CENTER, spacing=0),
            padding=ft.Padding.symmetric(vertical=Spacing.SM, horizontal=Spacing.MD),
            border_radius=Radius.MD,
            bgcolor=Colors.BG_CARD,
            border=ft.Border.all(1, Colors.BORDER),
            margin=ft.Margin.only(bottom=Spacing.SM),
            on_click=lambda _: on_navigate("tasks"),
            ink=True,
        )

    today_list_content = ft.Column(
        [task_item(t) for t in today_tasks[:5]] if today_tasks
        else [ft.Container(
            content=ft.Column([
                ft.Text("🎉", size=40),
                ft.Text("Không có công việc hôm nay!",
                        size=Typography.BODY, color=Colors.TEXT_MUTED,
                        text_align=ft.TextAlign.CENTER),
            ], horizontal_alignment=ft.CrossAxisAlignment.CENTER, spacing=Spacing.SM),
            padding=Spacing.XL,
            alignment=ft.Alignment.CENTER,
        )],
        spacing=0, tight=True,
    )

    # ── Mini week calendar ───────────────────────────────────
    def week_day_chip(d: date) -> ft.Container:
        is_today = (d == date.today())
        has_task = any(t.due_date == d.isoformat() for t in tasks)
        wd = d.weekday()  # 0=Mon
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
                    width=34, height=34,
                    border_radius=Radius.FULL,
                    bgcolor=Colors.PRIMARY if is_today else "transparent",
                    alignment=ft.Alignment.CENTER,
                ),
                ft.Container(
                    width=5, height=5,
                    border_radius=Radius.FULL,
                    bgcolor=Colors.PRIMARY if has_task else "transparent",
                ),
            ], horizontal_alignment=ft.CrossAxisAlignment.CENTER,
               spacing=3, tight=True),
            padding=ft.Padding.symmetric(horizontal=Spacing.SM, vertical=Spacing.XS),
        )

    today = date.today()
    start_of_week = today - timedelta(days=today.weekday())
    week_dates = [start_of_week + timedelta(days=i) for i in range(7)]
    week_row = ft.Row([week_day_chip(d) for d in week_dates],
                      alignment=ft.MainAxisAlignment.SPACE_AROUND)

    week_card = ft.Container(
        content=ft.Column([
            ft.Row([
                ft.Text(f"{MONTHS_VI[today.month-1]} {today.year}",
                        size=Typography.H4, color=Colors.TEXT_PRIMARY,
                        weight=Typography.SEMIBOLD),
                ft.Row([], expand=True),
                ft.TextButton("Xem lịch", on_click=lambda _: on_navigate("calendar"),
                              style=ft.ButtonStyle(color=Colors.PRIMARY,
                                                   padding=ft.Padding.all(0))),
            ]),
            ft.Container(height=Spacing.SM),
            week_row,
        ], spacing=0, tight=True),
        padding=Spacing.MD,
        border_radius=Radius.LG,
        bgcolor=Colors.BG_CARD,
        border=ft.border.all(1, Colors.BORDER),
        shadow=ft.BoxShadow(
            blur_radius=12,
            color="#00000018",
            offset=ft.Offset(0, 3),
        ),
    )

    # ── Upcoming high priority tasks ─────────────────────────
    upcoming = sorted(
        [t for t in tasks if t.status not in ("done","cancelled") and t.priority == "high"],
        key=lambda t: t.due_date or "9999"
    )[:3]

    def upcoming_chip(t: Task) -> ft.Container:
        cat = CATEGORY_MAP.get(t.category, CATEGORY_MAP["personal"])
        return ft.Container(
            content=ft.Column([
                ft.Container(
                    content=ft.Text(cat["icon"], size=20),
                    width=44, height=44,
                    border_radius=Radius.MD,
                    bgcolor=Colors.PRIMARY_BG,
                    alignment=ft.Alignment.CENTER,
                    border=ft.Border.all(1, Colors.PRIMARY_BORDER),
                    shadow=ft.BoxShadow(
                        blur_radius=8,
                        color=Colors.PRIMARY_SHADOW,
                        offset=ft.Offset(0, 2),
                    ),
                ),
                ft.Container(
                    content=ft.Text(t.title, size=Typography.TINY,
                                    color=Colors.TEXT_PRIMARY, weight=Typography.MEDIUM,
                                    max_lines=2, overflow=ft.TextOverflow.ELLIPSIS,
                                    text_align=ft.TextAlign.CENTER),
                    width=80,
                ),
                ft.Text(t.due_date_display, size=Typography.TINY,
                        color=Colors.PRIMARY if t.is_overdue else Colors.TEXT_MUTED),
            ], horizontal_alignment=ft.CrossAxisAlignment.CENTER, spacing=4, tight=True),
            padding=Spacing.SM,
            on_click=lambda _: on_navigate("tasks"),
        )

    urgent_section = ft.Column([
        section_header("🔥 Ưu tiên cao", f"{len(upcoming)} công việc cần chú ý",
                       "Xem tất cả", lambda _: on_navigate("tasks")),
        ft.Container(height=Spacing.SM),
        ft.Row([upcoming_chip(t) for t in upcoming], spacing=0,
               scroll=ft.ScrollMode.AUTO) if upcoming
        else ft.Text("Không có công việc ưu tiên cao.",
                     size=Typography.SMALL, color=Colors.TEXT_MUTED),
    ], spacing=0, tight=True)

    # ── Assemble body ────────────────────────────────────────
    body = ft.Column([
        header,
        ft.Container(
            content=ft.Column([
                overview_card,
                ft.Container(height=Spacing.LG),
                quick_actions,
                ft.Container(height=Spacing.LG),
                week_card,
                ft.Container(height=Spacing.LG),
                section_header("📋 Hôm nay cần làm",
                               f"{len(today_tasks)} công việc",
                               "Tất cả", lambda _: on_navigate("tasks")),
                ft.Container(height=Spacing.SM),
                today_list_content,
                ft.Container(height=Spacing.LG),
                urgent_section,
                ft.Container(height=Spacing.XXXL),
            ], spacing=0, tight=True),
            padding=ft.Padding.symmetric(horizontal=Spacing.MD),
        ),
    ], spacing=0, tight=True, scroll=ft.ScrollMode.AUTO, expand=True)

    return body


def _mini_stat(value: str, label: str, color: str) -> ft.Column:
    return ft.Column([
        ft.Text(value, size=Typography.BODY, color=color, weight=Typography.BOLD),
        ft.Text(label, size=Typography.TINY, color=Colors.TEXT_MUTED),
    ], horizontal_alignment=ft.CrossAxisAlignment.CENTER, spacing=0, tight=True)
