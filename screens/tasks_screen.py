"""
TaskFlow - Tasks Management Screen
Quản lý công việc với filter, search, add/edit/delete.
"""
import flet as ft
import uuid
from datetime import datetime, date
from core.theme import Colors, Typography, Spacing, Radius, CATEGORY_MAP, PRIORITY_MAP, STATUS_MAP
from core.models import Task
from core.services import TaskService, ProjectService
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

    # ── Assign task to project dialog ─────────────────────────
    def _open_assign_project(task: Task):
        all_projects = ProjectService.get_projects(user.id)
        tab = {"v": "assign"}          # "assign" | "new"
        new_cat = {"v": "personal"}
        new_pri = {"v": "medium"}
        proj_item_refs = {}

        new_title_tf = ft.TextField(
            label="Tiêu đề *", hint_text="Tên công việc mới...",
            bgcolor=Colors.BG_SURFACE, border_color=Colors.BORDER,
            focused_border_color=Colors.PRIMARY,
            text_style=ft.TextStyle(color=Colors.TEXT_PRIMARY, size=Typography.SMALL),
            label_style=ft.TextStyle(color=Colors.TEXT_MUTED, size=Typography.TINY),
            border_radius=Radius.MD, cursor_color=Colors.PRIMARY,
            content_padding=ft.padding.symmetric(horizontal=12, vertical=10),
        )
        new_proj_sel = {"v": all_projects[0].id if all_projects else None}
        new_due_tf = ft.TextField(
            label="Hạn (YYYY-MM-DD, tuỳ chọn)",
            bgcolor=Colors.BG_SURFACE, border_color=Colors.BORDER,
            focused_border_color=Colors.PRIMARY,
            text_style=ft.TextStyle(color=Colors.TEXT_PRIMARY, size=Typography.SMALL),
            label_style=ft.TextStyle(color=Colors.TEXT_MUTED, size=Typography.TINY),
            border_radius=Radius.MD, cursor_color=Colors.PRIMARY,
            content_padding=ft.padding.symmetric(horizontal=12, vertical=10),
        )
        new_proj_ref_map = {}

        def _close_dlg():
            page.dialog.open = False
            page.update()

        # ── Project list for assign tab ───────────────────────
        selected_pid = {"v": getattr(task, "project_id", None)}

        def _proj_item(p):
            ref = ft.Ref[ft.Container]()
            proj_item_refs[p.id] = ref
            is_sel = selected_pid["v"] == p.id

            def _tap(_, pid=p.id):
                old = selected_pid["v"]
                selected_pid["v"] = None if old == pid else pid
                for pid2, r in proj_item_refs.items():
                    if r.current:
                        sel2 = selected_pid["v"] == pid2
                        r.current.bgcolor = f"#20{all_projects[0].color[1:]}" if sel2 else "transparent"
                        # Update border
                        proj2 = next((x for x in all_projects if x.id == pid2), None)
                        if proj2:
                            r.current.bgcolor = f"#20{proj2.color[1:]}" if sel2 else "transparent"
                            r.current.border = ft.Border.all(2, proj2.color if sel2 else Colors.BORDER)
                        # Checkmark
                        row = r.current.content
                        if isinstance(row, ft.Row) and len(row.controls) >= 3:
                            row.controls[-1].color = (
                                proj2.color if sel2 else "transparent"
                            ) if proj2 else "transparent"
                page.update()

            return ft.GestureDetector(
                on_tap=_tap,
                content=ft.Container(
                    ref=ref,
                    content=ft.Row([
                        ft.Container(width=14, height=14, border_radius=7, bgcolor=p.color),
                        ft.Text(p.name, size=Typography.SMALL, color=Colors.TEXT_PRIMARY,
                                expand=True,
                                max_lines=1, overflow=ft.TextOverflow.ELLIPSIS),
                        ft.Icon(ft.Icons.CHECK_CIRCLE_ROUNDED, size=18,
                                color=p.color if is_sel else "transparent"),
                    ], spacing=Spacing.SM,
                       vertical_alignment=ft.CrossAxisAlignment.CENTER),
                    padding=ft.padding.symmetric(horizontal=Spacing.SM, vertical=10),
                    border_radius=Radius.MD,
                    bgcolor=f"#20{p.color[1:]}" if is_sel else "transparent",
                    border=ft.Border.all(2 if is_sel else 1,
                                         p.color if is_sel else Colors.BORDER),
                    margin=ft.margin.only(bottom=Spacing.XS),
                ),
            )

        # "remove from project" row
        remove_ref = ft.Ref[ft.Container]()

        def _tap_remove(_):
            selected_pid["v"] = None
            if remove_ref.current:
                remove_ref.current.bgcolor = "#20FF0000"
                remove_ref.current.border = ft.Border.all(2, Colors.ERROR)
            for _, r in proj_item_refs.items():
                if r.current:
                    r.current.bgcolor = "transparent"
                    proj2 = next((x for x in all_projects
                                  if x.id == next(
                                      (pid for pid, rr in proj_item_refs.items() if rr is r), None
                                  )), None)
                    r.current.border = ft.Border.all(1, Colors.BORDER)
                    row = r.current.content
                    if isinstance(row, ft.Row) and len(row.controls) >= 3:
                        row.controls[-1].color = "transparent"
            page.update()

        remove_item = ft.GestureDetector(
            on_tap=_tap_remove,
            content=ft.Container(
                ref=remove_ref,
                content=ft.Row([
                    ft.Icon(ft.Icons.REMOVE_CIRCLE_OUTLINE_ROUNDED, size=14,
                            color=Colors.TEXT_MUTED),
                    ft.Text("Bỏ khỏi dự án", size=Typography.SMALL,
                            color=Colors.TEXT_MUTED, expand=True),
                ], spacing=Spacing.SM,
                   vertical_alignment=ft.CrossAxisAlignment.CENTER),
                padding=ft.padding.symmetric(horizontal=Spacing.SM, vertical=10),
                border_radius=Radius.MD, bgcolor="transparent",
                border=ft.Border.all(1, Colors.BORDER),
                margin=ft.margin.only(bottom=Spacing.XS),
            ),
        ) if getattr(task, "project_id", None) else ft.Container(height=0)

        assign_body = (
            ft.Container(
                content=ft.Column(
                    ([remove_item] if getattr(task, "project_id", None) else []) +
                    [_proj_item(p) for p in all_projects],
                    spacing=0, tight=True, scroll=ft.ScrollMode.AUTO,
                ),
                height=min(260, (len(all_projects) + 1) * 54),
            ) if all_projects else ft.Container(
                content=ft.Column([
                    ft.Text("📁", size=28, text_align=ft.TextAlign.CENTER),
                    ft.Text("Chưa có dự án nào", size=Typography.SMALL,
                            color=Colors.TEXT_MUTED, text_align=ft.TextAlign.CENTER),
                    ft.Text("Tạo dự án trước trong màn hình Dự án.",
                            size=Typography.TINY, color=Colors.TEXT_MUTED,
                            text_align=ft.TextAlign.CENTER),
                ], horizontal_alignment=ft.CrossAxisAlignment.CENTER,
                   spacing=Spacing.SM),
                padding=ft.padding.symmetric(vertical=Spacing.MD),
            )
        )

        # ── New task mini-form ────────────────────────────────
        cat_chip_refs = {}
        pri_chip_refs = {}

        def _mini_chip(label, key, state, refs, accent):
            ref = ft.Ref[ft.Container]()
            refs[key] = ref

            def _sel(_):
                old = state["v"]
                state["v"] = key
                for k2, r2 in refs.items():
                    if r2.current:
                        is2 = k2 == key
                        r2.current.bgcolor = f"#20{accent[1:]}" if is2 else Colors.BG_SURFACE
                        r2.current.border = ft.Border.all(1, accent if is2 else Colors.BORDER)
                        if r2.current.content:
                            r2.current.content.color = accent if is2 else Colors.TEXT_MUTED
                page.update()

            is_sel = state["v"] == key
            return ft.GestureDetector(
                on_tap=_sel,
                content=ft.Container(
                    ref=ref,
                    content=ft.Text(label, size=7,
                                    color=accent if is_sel else Colors.TEXT_MUTED,
                                    weight=Typography.BOLD),
                    padding=ft.padding.symmetric(horizontal=8, vertical=5),
                    border_radius=Radius.FULL,
                    bgcolor=f"#20{accent[1:]}" if is_sel else Colors.BG_SURFACE,
                    border=ft.Border.all(1, accent if is_sel else Colors.BORDER),
                ),
            )

        # Project selector for new task
        np_chip_refs = {}
        def _np_chip(p):
            ref = ft.Ref[ft.Container]()
            np_chip_refs[p.id] = ref
            is_sel = new_proj_sel["v"] == p.id

            def _tap_np(_, pid=p.id, pc=p.color):
                new_proj_sel["v"] = pid
                for pid2, r2 in np_chip_refs.items():
                    if r2.current:
                        is2 = pid2 == pid
                        proj2 = next((x for x in all_projects if x.id == pid2), None)
                        c2 = proj2.color if proj2 else Colors.PRIMARY
                        r2.current.bgcolor = f"#20{c2[1:]}" if is2 else Colors.BG_SURFACE
                        r2.current.border = ft.Border.all(1, c2 if is2 else Colors.BORDER)
                        if r2.current.content and isinstance(r2.current.content, ft.Row):
                            txt = r2.current.content.controls[-1] if r2.current.content.controls else None
                            if txt and isinstance(txt, ft.Text):
                                txt.color = c2 if is2 else Colors.TEXT_MUTED
                page.update()

            return ft.GestureDetector(
                on_tap=_tap_np,
                content=ft.Container(
                    ref=ref,
                    content=ft.Row([
                        ft.Container(width=8, height=8, border_radius=4, bgcolor=p.color),
                        ft.Text(p.name[:10], size=7,
                                color=p.color if is_sel else Colors.TEXT_MUTED),
                    ], spacing=4, tight=True),
                    padding=ft.padding.symmetric(horizontal=8, vertical=5),
                    border_radius=Radius.FULL,
                    bgcolor=f"#20{p.color[1:]}" if is_sel else Colors.BG_SURFACE,
                    border=ft.Border.all(1, p.color if is_sel else Colors.BORDER),
                ),
            )

        new_body = ft.Column([
            new_title_tf,
            ft.Container(height=Spacing.SM),
            ft.Text("Danh mục", size=Typography.TINY, color=Colors.TEXT_MUTED),
            ft.Container(height=4),
            ft.Row([
                _mini_chip("👤 Cá nhân",  "personal",  new_cat, cat_chip_refs, Colors.PRIMARY),
                _mini_chip("💼 Công việc", "work",       new_cat, cat_chip_refs, Colors.ACCENT_CYAN),
                _mini_chip("❤️ Sức khoẻ", "health",     new_cat, cat_chip_refs, Colors.ERROR),
                _mini_chip("💰 Tài chính", "finance",    new_cat, cat_chip_refs, Colors.SUCCESS),
            ], spacing=4, wrap=True),
            ft.Container(height=Spacing.SM),
            ft.Text("Độ ưu tiên", size=Typography.TINY, color=Colors.TEXT_MUTED),
            ft.Container(height=4),
            ft.Row([
                _mini_chip("🔴 Cao",   "high",   new_pri, pri_chip_refs, Colors.ERROR),
                _mini_chip("🟡 Vừa",  "medium", new_pri, pri_chip_refs, Colors.WARNING),
                _mini_chip("🔵 Thấp", "low",    new_pri, pri_chip_refs, Colors.PRIMARY),
            ], spacing=4),
            *(
                [
                    ft.Container(height=Spacing.SM),
                    ft.Text("Dự án", size=Typography.TINY, color=Colors.TEXT_MUTED),
                    ft.Container(height=4),
                    ft.Row([_np_chip(p) for p in all_projects], spacing=4, wrap=True),
                ] if all_projects else []
            ),
            ft.Container(height=Spacing.SM),
            new_due_tf,
        ], spacing=0, tight=True)

        # ── Tab switching ─────────────────────────────────────
        body_wrap = ft.Container(content=assign_body)
        tab_assign_ref = ft.Ref[ft.Container]()
        tab_new_ref    = ft.Ref[ft.Container]()

        def _switch_tab(name):
            tab["v"] = name
            body_wrap.content = assign_body if name == "assign" else new_body
            if tab_assign_ref.current:
                tab_assign_ref.current.bgcolor = (
                    Colors.PRIMARY if name == "assign" else Colors.BG_SURFACE
                )
                tab_assign_ref.current.content.color = (
                    "white" if name == "assign" else Colors.TEXT_MUTED
                )
            if tab_new_ref.current:
                tab_new_ref.current.bgcolor = (
                    Colors.PRIMARY if name == "new" else Colors.BG_SURFACE
                )
                tab_new_ref.current.content.color = (
                    "white" if name == "new" else Colors.TEXT_MUTED
                )
            page.update()

        def _tab_btn(label, name, ref):
            is_sel = tab["v"] == name
            return ft.GestureDetector(
                on_tap=lambda _, n=name: _switch_tab(n),
                content=ft.Container(
                    ref=ref,
                    content=ft.Text(label, size=Typography.TINY, weight=Typography.SEMIBOLD,
                                    color="white" if is_sel else Colors.TEXT_MUTED),
                    padding=ft.padding.symmetric(horizontal=14, vertical=7),
                    border_radius=Radius.MD,
                    bgcolor=Colors.PRIMARY if is_sel else Colors.BG_SURFACE,
                    expand=True,
                ),
            )

        tab_row = ft.Container(
            content=ft.Row([
                _tab_btn("📁  Gán dự án", "assign", tab_assign_ref),
                ft.Container(width=Spacing.XS),
                _tab_btn("✏️  Tạo mới",   "new",    tab_new_ref),
            ], spacing=0),
            padding=ft.padding.only(bottom=Spacing.SM),
        )

        # ── Confirm ───────────────────────────────────────────
        def _confirm(_):
            if tab["v"] == "assign":
                task.project_id = selected_pid["v"]
                task.updated_at = datetime.now().isoformat()
                TaskService.save_task(task)
                _close_dlg()
                if selected_pid["v"]:
                    proj = next((p for p in all_projects if p.id == selected_pid["v"]), None)
                    snack(page, f"Đã gán '{task.title[:20]}' vào '{proj.name if proj else ''}' ✓")
                else:
                    snack(page, "Đã bỏ task khỏi dự án")
                refresh_list()
            else:
                title = new_title_tf.value.strip()
                if not title:
                    new_title_tf.error_text = "Vui lòng nhập tiêu đề"
                    page.update()
                    return
                new_title_tf.error_text = None
                now_str = datetime.now().isoformat()
                new_t = Task(
                    id=str(uuid.uuid4()),
                    user_id=user.id,
                    title=title,
                    category=new_cat["v"],
                    priority=new_pri["v"],
                    status="todo",
                    due_date=new_due_tf.value.strip() or None,
                    project_id=new_proj_sel["v"],
                    created_at=now_str,
                    updated_at=now_str,
                )
                TaskService.save_task(new_t)
                _close_dlg()
                proj = next((p for p in all_projects if p.id == new_proj_sel["v"]), None)
                proj_name = f" vào '{proj.name}'" if proj else ""
                snack(page, f"Đã tạo '{title}'{proj_name} ✓")
                refresh_list()

        curr_proj = next(
            (p for p in all_projects if p.id == getattr(task, "project_id", None)), None
        )
        title_text = (
            f"'{task.title[:20]}' — {curr_proj.name}" if curr_proj
            else f"Gán dự án cho '{task.title[:22]}'"
        )

        dlg = ft.AlertDialog(
            modal=True,
            title=ft.Text(title_text, size=Typography.H4,
                          color=Colors.TEXT_PRIMARY, weight=Typography.BOLD),
            content=ft.Column([
                tab_row,
                body_wrap,
            ], spacing=0, tight=True, width=340),
            actions=[
                ft.TextButton("Huỷ", on_click=lambda _: _close_dlg(),
                              style=ft.ButtonStyle(color=Colors.TEXT_MUTED)),
                primary_button("Xác nhận", on_click=_confirm, height=38),
            ],
            actions_alignment=ft.MainAxisAlignment.END,
            bgcolor=Colors.BG_CARD,
        )
        page.dialog = dlg
        dlg.open = True
        page.update()

    # ── Task card ─────────────────────────────────────────────
    def task_card(task: Task) -> ft.Container:
        cat_info  = CATEGORY_MAP.get(task.category, CATEGORY_MAP["personal"])
        pri_info  = PRIORITY_MAP.get(task.priority, PRIORITY_MAP["medium"])
        is_done   = task.status == "done"
        all_projs = ProjectService.get_projects(user.id)
        task_proj = next(
            (p for p in all_projs if p.id == getattr(task, "project_id", None)), None
        )

        proj_badge = (
            ft.GestureDetector(
                on_tap=lambda _, tt=task: _open_assign_project(tt),
                content=ft.Container(
                    content=ft.Row([
                        ft.Container(width=8, height=8, border_radius=4,
                                     bgcolor=task_proj.color),
                        ft.Text(task_proj.name[:16], size=7,
                                color=task_proj.color, weight=Typography.MEDIUM),
                    ], spacing=4, tight=True),
                    padding=ft.padding.symmetric(horizontal=6, vertical=3),
                    border_radius=Radius.FULL,
                    bgcolor=f"#15{task_proj.color[1:]}",
                    border=ft.Border.all(1, f"#40{task_proj.color[1:]}"),
                ),
            ) if task_proj else ft.GestureDetector(
                on_tap=lambda _, tt=task: _open_assign_project(tt),
                content=ft.Container(
                    content=ft.Row([
                        ft.Icon(ft.Icons.FOLDER_OUTLINED, size=10,
                                color=Colors.TEXT_MUTED),
                        ft.Text("Gán dự án", size=7, color=Colors.TEXT_MUTED),
                    ], spacing=3, tight=True),
                    padding=ft.padding.symmetric(horizontal=6, vertical=3),
                    border_radius=Radius.FULL,
                    bgcolor="transparent",
                    border=ft.Border.all(1, Colors.BORDER),
                ),
            )
        )

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
                            proj_badge,
                            ft.Text("🔁" if task.is_recurring else "",
                                    size=Typography.TINY, color=Colors.TEXT_MUTED),
                        ], spacing=4, vertical_alignment=ft.CrossAxisAlignment.CENTER),
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

    # ── Search & Filter Panel ─────────────────────────────────
    search_field = ft.TextField(
        hint_text="🔍  Tìm kiếm công việc...",
        bgcolor=Colors.BG_INPUT,
        border_color=Colors.BORDER,
        focused_border_color=Colors.PRIMARY,
        text_style=ft.TextStyle(color=Colors.TEXT_PRIMARY, size=Typography.BODY),
        hint_style=ft.TextStyle(color=Colors.TEXT_MUTED),
        border_radius=Radius.FULL,
        height=44,
        expand=True,
        cursor_color=Colors.TEXT_PRIMARY,
        on_change=lambda e: [search_val.update({"v": e.control.value}), refresh_list()],
    )

    def close_filter_sheet(_):
        filter_bs.open = False
        page.update()

    filter_sheet_content = ft.Column([
        ft.Container(
            content=ft.Container(width=40, height=4, border_radius=Radius.FULL,
                                 bgcolor="#444444"),
            alignment=ft.Alignment.CENTER,
            padding=ft.padding.only(top=12, bottom=8),
        ),
        ft.Container(
            content=ft.Column([
                ft.Text("Lọc công việc", size=Typography.H3,
                        color=Colors.TEXT_PRIMARY, weight=Typography.BOLD,
                        text_align=ft.TextAlign.CENTER),
                ft.Container(height=Spacing.MD),
                cat_filter,
                ft.Container(height=Spacing.SM),
                pri_filter,
                ft.Container(height=Spacing.SM),
                sta_filter,
                ft.Container(height=Spacing.XL),
                ft.Container(
                    content=primary_button("Xong", on_click=close_filter_sheet, width=200),
                    alignment=ft.Alignment.CENTER
                )
            ], horizontal_alignment=ft.CrossAxisAlignment.STRETCH,
               spacing=0, tight=True),
            padding=ft.padding.only(left=Spacing.LG, right=Spacing.LG, bottom=Spacing.LG),
        ),
    ], spacing=0, tight=True)

    filter_bs = ft.BottomSheet(
        content=ft.Container(
            content=filter_sheet_content,
            bgcolor=Colors.BG_CARD,
            border_radius=ft.border_radius.only(
                top_left=Radius.XL, top_right=Radius.XL,
            ),
            padding=0,
            clip_behavior=ft.ClipBehavior.ANTI_ALIAS,
        ),
        open=False,
        draggable=True,
        use_safe_area=True,
    )
    page.overlay.append(filter_bs)

    def open_filter_sheet(e):
        filter_bs.open = True
        page.update()

    filter_btn = ft.Container(
        content=ft.IconButton(
            icon=ft.Icons.TUNE,
            icon_color=Colors.TEXT_PRIMARY,
            icon_size=20,
            on_click=open_filter_sheet,
            tooltip="Bộ lọc",
        ),
        bgcolor=Colors.BG_INPUT,
        border_radius=Radius.FULL,
        border=ft.Border.all(1, Colors.BORDER),
        height=44,
        width=44,
        alignment=ft.Alignment.CENTER,
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
        content=ft.Row([
            search_field,
            filter_btn,
        ], spacing=Spacing.SM),
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
