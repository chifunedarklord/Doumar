"""
TaskFlow - Calendar Screen
Lịch tháng với hiển thị công việc theo ngày.
"""
import flet as ft
import uuid
from datetime import date, timedelta, datetime
import calendar
from core.theme import Colors, Typography, Spacing, Radius, CATEGORY_MAP, PRIORITY_MAP
from core.models import Task
from core.services import TaskService
from core.i18n import t, weekdays, months
from components.widgets import primary_divider, priority_badge, category_badge, status_chip


def _make_empty_task_for(user_id: str, due_date_str: str) -> Task:
    now_str = datetime.now().isoformat()
    return Task(
        id=str(uuid.uuid4()),
        user_id=user_id,
        title="",
        due_date=due_date_str,
        created_at=now_str,
        updated_at=now_str,
    )


def build_calendar_screen(page: ft.Page, user, on_navigate):
    today = date.today()
    view_date = {"y": today.year, "m": today.month}
    selected_date = {"d": today}
    tasks_all = TaskService.get_tasks(user.id)

    # task lookup by date
    def tasks_for_date(d: date):
        ds = d.isoformat()
        return [tk for tk in tasks_all if tk.due_date == ds]

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
            ft.Text(f"{months()[m-1]} {y}", size=Typography.H3,
                    color=Colors.TEXT_PRIMARY, weight=Typography.BOLD, expand=True,
                    text_align=ft.TextAlign.CENTER),
            ft.IconButton(ft.Icons.CHEVRON_RIGHT, icon_color=Colors.PRIMARY,
                          icon_size=22, on_click=next_m),
        ], alignment=ft.MainAxisAlignment.SPACE_BETWEEN,
           vertical_alignment=ft.CrossAxisAlignment.CENTER)

        # ── Weekday headers ───────────────────────────────────
        wd_row = ft.Row([
            ft.Container(
                content=ft.Text(wd, size=Typography.TINY,
                                color=Colors.ERROR if wd_i == 6 else Colors.TEXT_MUTED,
                                weight=Typography.SEMIBOLD, text_align=ft.TextAlign.CENTER),
                expand=True,
            )
            for wd_i, wd in enumerate(weekdays())
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
                for tk in day_tasks[:3]:
                    pri = PRIORITY_MAP.get(tk.priority, {})
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
            is_overdue = task.is_overdue
            is_today_task = (task.due_date == today.isoformat())
            # Color coding: overdue=red, today=blue, else default
            card_bg     = (f"#10{Colors.ERROR[1:]}" if is_overdue
                           else f"#10{Colors.PRIMARY[1:]}" if is_today_task
                           else Colors.BG_CARD)
            card_border = (f"#40{Colors.ERROR[1:]}" if is_overdue
                           else Colors.PRIMARY_BORDER if is_today_task
                           else Colors.BORDER)
            title_color = (Colors.ERROR if is_overdue
                           else Colors.PRIMARY if is_today_task
                           else Colors.TEXT_PRIMARY)

            def _toggle_done(_, tt=task):
                from core.services import TaskService as _TS
                _TS.toggle_done(tt)
                refresh()

            return ft.Container(
                content=ft.Row([
                    ft.Container(
                        width=4, height=44,
                        border_radius=Radius.FULL,
                        bgcolor=Colors.ERROR if is_overdue else (
                            Colors.PRIMARY if is_today_task else pri["color"]),
                    ),
                    ft.Container(width=Spacing.SM),
                    ft.Text(cat["icon"], size=16),
                    ft.Container(width=Spacing.XS),
                    ft.Column([
                        ft.Text(task.title, size=Typography.BODY,
                                color=title_color, weight=Typography.MEDIUM,
                                max_lines=1, overflow=ft.TextOverflow.ELLIPSIS),
                        ft.Text(
                            ("⚠️ " + t("overdue_label") + "  " if is_overdue else "") +
                            (task.due_time or "") + ("  " if task.due_time else "") +
                            cat["label"],
                            size=Typography.TINY,
                            color=Colors.ERROR if is_overdue else Colors.TEXT_MUTED),
                    ], spacing=0, tight=True, expand=True),
                    status_chip(task.status),
                    ft.GestureDetector(
                        on_tap=_toggle_done,
                        content=ft.Container(
                            content=ft.Icon(
                                ft.Icons.CHECK_CIRCLE if task.status == "done"
                                else ft.Icons.RADIO_BUTTON_UNCHECKED,
                                size=20,
                                color=Colors.SUCCESS if task.status == "done"
                                      else Colors.TEXT_MUTED,
                            ),
                            padding=ft.padding.all(4),
                        ),
                    ),
                ], vertical_alignment=ft.CrossAxisAlignment.CENTER, spacing=0),
                padding=ft.Padding.symmetric(vertical=Spacing.SM, horizontal=Spacing.SM),
                border_radius=Radius.MD,
                bgcolor=card_bg,
                border=ft.Border.all(1, card_border),
                margin=ft.Margin.only(bottom=Spacing.SM),
                shadow=ft.BoxShadow(
                    blur_radius=8 if is_overdue else 4,
                    color="#22EF4444" if is_overdue else "#00000010",
                    offset=ft.Offset(0, 2),
                ),
            )

        # "Add task for selected day" button
        sel_date_str = sel.isoformat()
        add_for_day_btn = ft.Container(
            content=ft.Row([
                ft.Icon(ft.Icons.ADD_ROUNDED, size=16, color=Colors.PRIMARY),
                ft.Text(t("add_for_date", date=sel.strftime('%d/%m')),
                        size=Typography.SMALL, color=Colors.PRIMARY,
                        weight=Typography.MEDIUM),
            ], spacing=4, tight=True, alignment=ft.MainAxisAlignment.CENTER),
            height=40,
            border_radius=Radius.MD,
            bgcolor=Colors.PRIMARY_BG,
            border=ft.Border.all(1, Colors.PRIMARY_BORDER),
            alignment=ft.Alignment.CENTER,
            ink=True,
            on_click=lambda _: on_navigate("task_edit",
                                           task=_make_empty_task_for(user.id, sel_date_str)),
        )

        sel_header = ft.Row([
            ft.Text(
                f"{t('today') if sel == today else sel.strftime('%d/%m/%Y')} — {t('tasks_count', n=len(sel_tasks))}",
                size=Typography.H4, color=Colors.TEXT_PRIMARY, weight=Typography.SEMIBOLD,
                expand=True,
            ),
        ])

        sel_list = ft.Column(
            [sel_task_item(tk) for tk in sel_tasks] + [add_for_day_btn]
            if sel_tasks else [
                ft.Container(
                    content=ft.Column([
                        ft.Text("📭", size=32),
                        ft.Text(t("no_tasks_day"),
                                size=Typography.SMALL, color=Colors.TEXT_MUTED,
                                text_align=ft.TextAlign.CENTER),
                    ], horizontal_alignment=ft.CrossAxisAlignment.CENTER, spacing=Spacing.SM),
                    padding=Spacing.LG,
                    alignment=ft.Alignment.CENTER,
                ),
                add_for_day_btn,
            ],
            spacing=0, tight=True,
        )

        return ft.Column([
            # Header
            ft.Container(
                content=ft.Text(t("calendar_title"), size=Typography.H2,
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
                border=ft.Border.all(1, Colors.BORDER),
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
