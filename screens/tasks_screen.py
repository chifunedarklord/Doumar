"""
TaskFlow - Tasks Management Screen
Quản lý công việc với filter, search, add/edit/delete.
"""
import flet as ft
import uuid
from datetime import datetime, date
from core.theme import Colors, Typography, Spacing, Radius, CATEGORY_MAP, PRIORITY_MAP, STATUS_MAP
from core.models import Task
from core.services import TaskService
from components.widgets import (
    glow_text, primary_divider, glass_card, primary_button,
    text_input, snack, avatar_circle, priority_badge,
    category_badge, status_chip, section_header
)


def build_tasks_screen(page: ft.Page, user, on_navigate):
    tasks_ref = ft.Ref[ft.Column]()
    search_val    = {"v": ""}
    filter_cat    = {"v": "all"}
    filter_status = {"v": "all"}
    filter_pri    = {"v": "all"}

    def get_filtered_tasks():
        tasks = TaskService.get_tasks(user.id)
        q = search_val["v"].lower()
        if q:
            tasks = [t for t in tasks if q in t.title.lower() or q in t.description.lower()]
        if filter_cat["v"] != "all":
            tasks = [t for t in tasks if t.category == filter_cat["v"]]
        if filter_status["v"] != "all":
            tasks = [t for t in tasks if t.status == filter_status["v"]]
        if filter_pri["v"] != "all":
            tasks = [t for t in tasks if t.priority == filter_pri["v"]]
        def sort_key(t: Task):
            pri_order = {"high": 0, "medium": 1, "low": 2}
            return (0 if t.is_overdue else 1, t.due_date or "9999", pri_order.get(t.priority, 1))
        return sorted(tasks, key=sort_key)

    def refresh_list():
        if tasks_ref.current:
            tasks_ref.current.controls = build_task_list()
            page.update()


    # ── Delete confirm ────────────────────────────────────────
    def delete_task(task_id: str):
        def confirm(_):
            TaskService.delete_task(task_id)
            _del_bs[0].open = False
            page.update()
            refresh_list()
            snack(page, "Đã xóa công việc")

        def cancel(_):
            _del_bs[0].open = False
            page.update()

        del_sheet = ft.Column([
            ft.Container(
                content=ft.Container(width=40, height=4, border_radius=Radius.FULL,
                                     bgcolor="#444444"),
                alignment=ft.Alignment.CENTER,
                padding=ft.padding.only(top=12, bottom=8),
            ),
            ft.Container(
                content=ft.Column([
                    ft.Container(
                        content=ft.Text("🗑️", size=36),
                        alignment=ft.Alignment.CENTER,
                        padding=ft.padding.only(bottom=Spacing.SM),
                    ),
                    ft.Text("Xóa công việc?", size=Typography.H3,
                            color=Colors.TEXT_PRIMARY, weight=Typography.BOLD,
                            text_align=ft.TextAlign.CENTER),
                    ft.Container(height=Spacing.SM),
                    ft.Text("Hành động này không thể hoàn tác.",
                            size=Typography.SMALL, color=Colors.TEXT_MUTED,
                            text_align=ft.TextAlign.CENTER),
                    ft.Container(height=Spacing.XL),
                    ft.Row([
                        ft.Container(
                            content=ft.Text("Hủy", size=Typography.BODY,
                                            color=Colors.TEXT_MUTED,
                                            weight=Typography.MEDIUM),
                            height=48, expand=True,
                            border_radius=Radius.MD,
                            bgcolor=Colors.BG_SURFACE,
                            border=ft.border.all(1, Colors.BORDER),
                            alignment=ft.Alignment.CENTER,
                            on_click=cancel, ink=True,
                        ),
                        ft.Container(width=Spacing.SM),
                        ft.Container(
                            content=ft.Row([
                                ft.Icon(ft.Icons.DELETE_OUTLINE, size=16,
                                        color="#FFFFFF"),
                                ft.Container(width=4),
                                ft.Text("Xóa", size=Typography.BODY,
                                        color="#FFFFFF",
                                        weight=Typography.SEMIBOLD),
                            ], alignment=ft.MainAxisAlignment.CENTER, spacing=0),
                            height=48, expand=True,
                            border_radius=Radius.MD,
                            bgcolor=Colors.ERROR,
                            alignment=ft.Alignment.CENTER,
                            on_click=confirm, ink=True,
                        ),
                    ]),
                    ft.Container(height=Spacing.XXL),
                ], horizontal_alignment=ft.CrossAxisAlignment.CENTER,
                   spacing=0, tight=True),
                padding=ft.padding.symmetric(horizontal=Spacing.LG),
            ),
        ], spacing=0, tight=True)

        del_bs = ft.BottomSheet(
            content=ft.Container(
                content=del_sheet,
                bgcolor=Colors.BG_CARD,
                border_radius=ft.border_radius.only(
                    top_left=Radius.XL, top_right=Radius.XL,
                ),
                padding=0,
                clip_behavior=ft.ClipBehavior.ANTI_ALIAS,
            ),
            open=True,
            draggable=True,
            use_safe_area=True,
        )
        _del_bs = [del_bs]
        page.overlay.append(del_bs)
        page.update()

    def toggle_done(task: Task):
        TaskService.toggle_done(task)
        refresh_list()

    # ── Task card ─────────────────────────────────────────────
    def task_card(task: Task) -> ft.Container:
        cat_info = CATEGORY_MAP.get(task.category, CATEGORY_MAP["personal"])
        pri_info = PRIORITY_MAP.get(task.priority, PRIORITY_MAP["medium"])
        is_done  = task.status == "done"

        return ft.Container(
            content=ft.Column([
                ft.Row([
                    ft.Container(
                        width=4, height=None,
                        border_radius=Radius.FULL,
                        bgcolor=pri_info["color"],
                        expand_loose=True,
                    ),
                    ft.Container(width=Spacing.SM),
                    ft.Column([
                        ft.Row([
                            ft.Text(
                                task.title,
                                size=Typography.BODY,
                                color=Colors.TEXT_MUTED if is_done else Colors.TEXT_PRIMARY,
                                weight=Typography.BOLD,
                                expand=True,
                                max_lines=2,
                                overflow=ft.TextOverflow.ELLIPSIS,
                                style=ft.TextStyle(
                                    decoration=ft.TextDecoration.LINE_THROUGH if is_done else None,
                                ),
                            ),
                        ]),
                        ft.Container(height=4),
                        ft.Row([
                            category_badge(task.category),
                            priority_badge(task.priority),
                            status_chip(task.status),
                        ], spacing=Spacing.XS, wrap=True),
                        ft.Container(height=4),
                        ft.Row([
                            ft.Text("📅", size=11),
                            ft.Text(task.due_date_display, size=Typography.TINY,
                                    color=Colors.ERROR if task.is_overdue else Colors.TEXT_MUTED),
                            ft.Row([], expand=True),
                            ft.Text(f"🔁" if task.is_recurring else "",
                                    size=Typography.TINY, color=Colors.TEXT_MUTED),
                        ], spacing=4),
                        ft.Text(task.description[:80] + ("…" if len(task.description) > 80 else ""),
                                size=Typography.TINY, color=Colors.TEXT_MUTED,
                                max_lines=1, overflow=ft.TextOverflow.ELLIPSIS)
                        if task.description else ft.Container(),
                    ], expand=True, spacing=0, tight=True),
                    ft.Column([
                        ft.IconButton(
                            icon=ft.Icons.CHECK_CIRCLE if is_done else ft.Icons.RADIO_BUTTON_UNCHECKED,
                            icon_color=Colors.SUCCESS if is_done else Colors.TEXT_MUTED,
                            icon_size=22,
                            on_click=lambda _, tt=task: toggle_done(tt),
                            tooltip="Đánh dấu hoàn thành",
                        ),
                        ft.IconButton(
                            icon=ft.Icons.EDIT_OUTLINED,
                            icon_color=Colors.TEXT_MUTED,
                            icon_size=18,
                            on_click=lambda _, tt=task: on_navigate("task_edit", task=tt),
                            tooltip="Chỉnh sửa",
                        ),
                        ft.IconButton(
                            icon=ft.Icons.DELETE_OUTLINE,
                            icon_color=Colors.ERROR + "AA",
                            icon_size=18,
                            on_click=lambda _, tid=task.id: delete_task(tid),
                            tooltip="Xóa",
                        ),
                    ], spacing=0, tight=True),
                ], vertical_alignment=ft.CrossAxisAlignment.START),
            ], spacing=0, tight=True),
            padding=ft.padding.symmetric(vertical=Spacing.SM, horizontal=Spacing.MD),
            border_radius=Radius.MD,
            bgcolor=Colors.BG_CARD,
            border=ft.Border.all(1, Colors.BORDER_GLOW if task.is_overdue else Colors.BORDER),
            margin=ft.Margin.only(bottom=Spacing.SM),
            animate=ft.Animation(200, ft.AnimationCurve.EASE_OUT),
            shadow=ft.BoxShadow(
                blur_radius=8 if task.is_overdue else 4,
                color="#22EF4444" if task.is_overdue else "#00000015",
                offset=ft.Offset(0, 2),
            ),
        )

    def build_task_list():
        filtered = get_filtered_tasks()
        if not filtered:
            return [ft.Container(
                content=ft.Column([
                    ft.Text("📭", size=48),
                    ft.Text("Không có công việc nào", size=Typography.BODY,
                            color=Colors.TEXT_MUTED, text_align=ft.TextAlign.CENTER),
                    ft.Container(height=Spacing.MD),
                    primary_button("Thêm công việc đầu tiên",
                                on_click=lambda _: on_navigate("task_edit"),
                                icon=ft.Icons.ADD, height=44, width=200),
                ], horizontal_alignment=ft.CrossAxisAlignment.CENTER,
                   spacing=Spacing.SM),
                padding=Spacing.XXL,
                alignment=ft.Alignment.CENTER,
            )]
        return [task_card(t) for t in filtered]

    # ── Filter chips ──────────────────────────────────────────
    def filter_row(label, options, sel_ref, update_fn):
        chips = []
        all_options = {"all": {"label": "Tất cả", "icon": "✦", "color": Colors.PRIMARY}}
        all_options.update(options)
        for key, info in all_options.items():
            def make_click(k, chips_list):
                def _click(_):
                    sel_ref["v"] = k
                    for i, (ck, ci) in enumerate(all_options.items()):
                        c = chips_list[i]
                        sel = (ck == k)
                        c.bgcolor = Colors.PRIMARY if sel else "transparent"
                        c.border  = ft.border.all(1.5, Colors.PRIMARY) if sel else ft.border.all(1, Colors.BORDER)
                        c.content.controls[1].color = Colors.TEXT_ON_PRIMARY if sel else Colors.TEXT_MUTED
                    update_fn()
                return _click
            selected = (key == sel_ref["v"])
            chip = ft.Container(
                content=ft.Row([
                    ft.Text(info["icon"], size=10),
                    ft.Text(info["label"], size=Typography.TINY,
                            color=Colors.TEXT_ON_PRIMARY if selected else Colors.TEXT_MUTED),
                ], spacing=4, tight=True),
                padding=ft.Padding.symmetric(horizontal=10, vertical=5),
                border_radius=Radius.FULL,
                bgcolor=Colors.PRIMARY if selected else "transparent",
                border=ft.Border.all(1.5 if selected else 1,
                                      Colors.PRIMARY if selected else Colors.BORDER),
            )
            chip.on_click = make_click(key, chips)
            chips.append(chip)
        return ft.Row([
            ft.Text(label, size=Typography.TINY, color=Colors.TEXT_MUTED, width=60),
            ft.Row(chips, scroll=ft.ScrollMode.AUTO, spacing=Spacing.XS, expand=True),
        ], vertical_alignment=ft.CrossAxisAlignment.CENTER)

    cat_filter = filter_row("Danh mục",   CATEGORY_MAP, filter_cat, refresh_list)
    pri_filter = filter_row("Ưu tiên",    PRIORITY_MAP, filter_pri, refresh_list)
    sta_filter = filter_row("Trạng thái", STATUS_MAP,   filter_status, refresh_list)

    # ── Search bar ────────────────────────────────────────────
    search_field = ft.TextField(
        hint_text="🔍  Tìm kiếm công việc...",
        bgcolor=Colors.BG_INPUT,
        border_color=Colors.BORDER,
        focused_border_color=Colors.PRIMARY,
        text_style=ft.TextStyle(color=Colors.TEXT_PRIMARY, size=Typography.BODY),
        hint_style=ft.TextStyle(color=Colors.TEXT_MUTED),
        border_radius=Radius.FULL,
        height=44,
        cursor_color=Colors.TEXT_PRIMARY,
        on_change=lambda e: [search_val.update({"v": e.control.value}), refresh_list()],
    )

    # ── Header ────────────────────────────────────────────────
    header = ft.Container(
        content=ft.Row([
            ft.Column([
                ft.Text("Công việc", size=Typography.H2, color=Colors.TEXT_PRIMARY,
                        weight=Typography.BOLD),
                ft.Text(f"{len(TaskService.get_tasks(user.id))} công việc",
                        size=Typography.SMALL, color=Colors.TEXT_MUTED),
            ], spacing=2, tight=True),
            ft.Row([], expand=True),
            ft.Container(
                content=primary_button("+ Thêm", on_click=lambda _: on_navigate("task_edit"),
                                    height=38, width=100),
            ),
        ], alignment=ft.MainAxisAlignment.SPACE_BETWEEN,
           vertical_alignment=ft.CrossAxisAlignment.CENTER),
        padding=ft.padding.symmetric(horizontal=Spacing.MD, vertical=Spacing.MD),
    )

    filter_panel = ft.Container(
        content=ft.Column([
            search_field,
            ft.Container(height=Spacing.SM),
            cat_filter,
            ft.Container(height=Spacing.XS),
            pri_filter,
            ft.Container(height=Spacing.XS),
            sta_filter,
        ], spacing=0, tight=True),
        padding=ft.Padding.symmetric(horizontal=Spacing.MD, vertical=Spacing.SM),
        bgcolor=Colors.BG_CARD,
        border=ft.Border.only(bottom=ft.BorderSide(1, Colors.BORDER)),
        shadow=ft.BoxShadow(
            blur_radius=6,
            color="#00000015",
            offset=ft.Offset(0, 2),
        ),
    )

    task_list_col = ft.Column(build_task_list(), spacing=0, tight=True, ref=tasks_ref)

    body = ft.Column([
        header,
        filter_panel,
        ft.Container(
            content=task_list_col,
            padding=ft.padding.symmetric(horizontal=Spacing.MD, vertical=Spacing.MD),
            expand=True,
        ),
    ], spacing=0, tight=True, scroll=ft.ScrollMode.AUTO, expand=True)

    return body
