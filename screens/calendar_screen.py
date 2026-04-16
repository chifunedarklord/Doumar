"""
TaskFlow - Calendar Screen
Lịch tháng với hiển thị công việc theo ngày.
"""
import flet as ft
from datetime import date, timedelta
import calendar
from core.theme import Colors, Typography, Spacing, Radius, CATEGORY_MAP, PRIORITY_MAP
from core.services import TaskService
from components.widgets import primary_divider, priority_badge, category_badge, status_chip


MONTHS_VI = ["","Tháng 1","Tháng 2","Tháng 3","Tháng 4","Tháng 5",
             "Tháng 6","Tháng 7","Tháng 8","Tháng 9","Tháng 10","Tháng 11","Tháng 12"]
WEEKDAY_VI = ["T2","T3","T4","T5","T6","T7","CN"]


def build_calendar_screen(page: ft.Page, user, on_navigate):
    today = date.today()
    view_date = {"y": today.year, "m": today.month}
    selected_date = {"d": today}
    tasks_all = TaskService.get_tasks(user.id)

    # task lookup by date
    def tasks_for_date(d: date):
        ds = d.isoformat()
        return [t for t in tasks_all if t.due_date == ds]

    main_col = ft.Column([], expand=True)

    def build():
        y, m = view_date["y"], view_date["m"]
        sel  = selected_date["d"]

        # ── Month navigation ──────────────────────────────────
        def prev_m(_):
            if view_date["m"] == 1: view_date["m"] = 12; view_date["y"] -= 1
            else: view_date["m"] -= 1
            refresh()
        def next_m(_):
            if view_date["m"] == 12: view_date["m"] = 1; view_date["y"] += 1
            else: view_date["m"] += 1
            refresh()

        nav = ft.Row([
            ft.IconButton(ft.Icons.CHEVRON_LEFT, icon_color=Colors.PRIMARY,
                          icon_size=22, on_click=prev_m),
            ft.Text(f"{MONTHS_VI[m]} {y}", size=Typography.H3,
                    color=Colors.TEXT_PRIMARY, weight=Typography.BOLD, expand=True,
                    text_align=ft.TextAlign.CENTER),
            ft.IconButton(ft.Icons.CHEVRON_RIGHT, icon_color=Colors.PRIMARY,
                          icon_size=22, on_click=next_m),
        ], alignment=ft.MainAxisAlignment.SPACE_BETWEEN,
           vertical_alignment=ft.CrossAxisAlignment.CENTER)

        # ── Weekday headers ───────────────────────────────────
        wd_row = ft.Row([
            ft.Container(
                content=ft.Text(d, size=Typography.TINY,
                                color=Colors.PRIMARY if d == "CN" else Colors.TEXT_MUTED,
                                weight=Typography.SEMIBOLD, text_align=ft.TextAlign.CENTER),
                expand=True,
            )
            for d in WEEKDAY_VI
        ])

        # ── Calendar grid ─────────────────────────────────────
        cal = calendar.monthcalendar(y, m)
        rows = []
        for week in cal:
            cells = []
            for wd_idx, day in enumerate(week):
                if day == 0:
                    cells.append(ft.Container(expand=True))
                    continue
                d = date(y, m, day)
                day_tasks = tasks_for_date(d)
                is_today  = (d == today)
                is_sel    = (d == sel)
                is_sun    = (wd_idx == 6)

                # dot indicators (up to 3)
                dot_colors = []
                for t in day_tasks[:3]:
                    pri = PRIORITY_MAP.get(t.priority, {})
                    dot_colors.append(pri.get("color", Colors.TEXT_MUTED))

                dots = ft.Row([
                    ft.Container(width=4, height=4, border_radius=Radius.FULL, bgcolor=c)
                    for c in dot_colors
                ] + [ft.Container(expand=True)],
                    spacing=2, tight=True)

                def make_tap(dd):
                    def _tap(_):
                        selected_date["d"] = dd
                        refresh()
                    return _tap

                cell = ft.Container(
                    content=ft.Column([
                        ft.Container(
                            content=ft.Text(
                                str(day),
                                size=Typography.SMALL,
                                color=(Colors.TEXT_ON_PRIMARY if is_sel else
                                       Colors.PRIMARY if is_today else
                                       Colors.ERROR if is_sun else
                                       Colors.TEXT_PRIMARY),
                                weight=Typography.BOLD if (is_today or is_sel) else Typography.REGULAR,
                                text_align=ft.TextAlign.CENTER,
                            ),
                            width=30, height=30,
                            border_radius=Radius.FULL,
                            bgcolor=(Colors.PRIMARY if is_sel else
                                     "#222563EB" if is_today else "transparent"),
                            alignment=ft.Alignment.CENTER,
                            border=ft.Border.all(1.5, Colors.PRIMARY) if is_today and not is_sel else None,
                        ),
                        dots if day_tasks else ft.Container(height=6),
                    ], horizontal_alignment=ft.CrossAxisAlignment.CENTER,
                       spacing=2, tight=True),
                    expand=True,
                    on_click=make_tap(d),
                    padding=ft.Padding.symmetric(vertical=4),
                    border_radius=Radius.SM,
                    ink=True,
                )
                cells.append(cell)
            rows.append(ft.Row(cells, spacing=0))

        grid = ft.Column(rows, spacing=4, tight=True)

        # ── Selected day task list ────────────────────────────
        sel_tasks = tasks_for_date(sel)

        def sel_task_item(task):
            cat  = CATEGORY_MAP.get(task.category, CATEGORY_MAP["personal"])
            pri  = PRIORITY_MAP.get(task.priority, PRIORITY_MAP["medium"])
            return ft.Container(
                content=ft.Row([
                    ft.Container(
                        width=4, height=44,
                        border_radius=Radius.FULL,
                        bgcolor=pri["color"],
                    ),
                    ft.Container(width=Spacing.SM),
                    ft.Text(cat["icon"], size=16),
                    ft.Container(width=Spacing.XS),
                    ft.Column([
                        ft.Text(task.title, size=Typography.BODY,
                                color=Colors.TEXT_PRIMARY, weight=Typography.MEDIUM,
                                max_lines=1, overflow=ft.TextOverflow.ELLIPSIS),
                        ft.Text(
                            (task.due_time or "") + ("  " if task.due_time else "") +
                            cat["label"],
                            size=Typography.TINY, color=Colors.TEXT_MUTED),
                    ], spacing=0, tight=True, expand=True),
                    status_chip(task.status),
                ], vertical_alignment=ft.CrossAxisAlignment.CENTER, spacing=0),
                padding=ft.Padding.symmetric(vertical=Spacing.SM, horizontal=Spacing.SM),
                border_radius=Radius.MD,
                bgcolor=Colors.BG_CARD,
                border=ft.border.all(1, Colors.BORDER),
                margin=ft.Margin.only(bottom=Spacing.SM),
                shadow=ft.BoxShadow(
                    blur_radius=8,
                    color="#00000015",
                    offset=ft.Offset(0, 2),
                ),
            )

        sel_header = ft.Row([
            ft.Text(
                f"{'Hôm nay' if sel == today else sel.strftime('%d/%m/%Y')} — {len(sel_tasks)} công việc",
                size=Typography.H4, color=Colors.TEXT_PRIMARY, weight=Typography.SEMIBOLD,
            ),
        ])

        sel_list = ft.Column(
            [sel_task_item(t) for t in sel_tasks] if sel_tasks else [
                ft.Container(
                    content=ft.Column([
                        ft.Text("📭", size=32),
                        ft.Text("Không có công việc ngày này",
                                size=Typography.SMALL, color=Colors.TEXT_MUTED,
                                text_align=ft.TextAlign.CENTER),
                    ], horizontal_alignment=ft.CrossAxisAlignment.CENTER, spacing=Spacing.SM),
                    padding=Spacing.LG,
                    alignment=ft.Alignment.CENTER,
                )
            ],
            spacing=0, tight=True,
        )

        return ft.Column([
            # Header
            ft.Container(
                content=ft.Text("Lịch biểu", size=Typography.H2,
                                color=Colors.TEXT_PRIMARY, weight=Typography.BOLD),
                padding=ft.Padding.symmetric(horizontal=Spacing.MD, vertical=Spacing.MD),
            ),
            # Calendar card
            ft.Container(
                content=ft.Column([
                    nav,
                    ft.Container(height=Spacing.SM),
                    wd_row,
                    primary_divider(0.15),
                    ft.Container(height=Spacing.SM),
                    grid,
                ], spacing=Spacing.SM, tight=True),
                padding=Spacing.MD,
                margin=ft.margin.symmetric(horizontal=Spacing.MD),
                border_radius=Radius.LG,
                bgcolor=Colors.BG_CARD,
                border=ft.border.all(1, Colors.BORDER),
                shadow=ft.BoxShadow(blur_radius=12, color="#00000015",
                                    offset=ft.Offset(0, 4)),
            ),
            ft.Container(height=Spacing.MD),
            # Selected day panel
            ft.Container(
                content=ft.Column([
                    sel_header,
                    ft.Container(height=Spacing.SM),
                    sel_list,
                ], spacing=0, tight=True),
                padding=ft.Padding.symmetric(horizontal=Spacing.MD),
            ),
            ft.Container(height=Spacing.XXXL),
        ], spacing=0, tight=True, scroll=ft.ScrollMode.AUTO, expand=True)

    def refresh():
        tasks_all.clear()
        tasks_all.extend(TaskService.get_tasks(user.id))
        main_col.controls = [build()]
        page.update()

    refresh()
    return main_col
