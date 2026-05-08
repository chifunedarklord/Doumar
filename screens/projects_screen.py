"""
TaskFlow - Projects Screen
Quản lý dự án: danh sách, tạo mới, thêm task, xem task theo project.
"""
import flet as ft
import uuid
from datetime import datetime
from core.theme import Colors, Typography, Spacing, Radius
from core.models import Project
from core.services import ProjectService, TaskService
from components.widgets import primary_button, snack

PROJECT_COLORS = [
    "#5B4FBE", "#2563EB", "#0891B2", "#10B981",
    "#F59E0B", "#EF4444", "#8B5CF6", "#F43F5E",
]

CATEGORY_ICONS = {
    "work": "💼", "personal": "👤", "health": "❤️",
    "finance": "💰", "education": "📚",
}

STATUS_COLORS = {
    "done": Colors.SUCCESS,
    "in_progress": Colors.PRIMARY,
    "todo": Colors.TEXT_MUTED,
    "cancelled": Colors.ERROR,
}


def build_projects_screen(page: ft.Page, user, on_navigate):
    projects = ProjectService.get_projects(user.id)
    create_mode = {"v": False}
    expanded_pid = {"v": None}   # which project card is open
    main_col = ft.Column([], expand=True, scroll=ft.ScrollMode.AUTO)

    # ── Create form fields ───────────────────────────────────
    new_name_tf = ft.TextField(
        label="Tên dự án *", hint_text="VD: Đồ án tốt nghiệp, Q2 Goals...",
        bgcolor=Colors.BG_CARD, border_color=Colors.BORDER,
        focused_border_color=Colors.PRIMARY,
        text_style=ft.TextStyle(color=Colors.TEXT_PRIMARY),
        label_style=ft.TextStyle(color=Colors.TEXT_MUTED),
        border_radius=Radius.MD, cursor_color=Colors.PRIMARY,
    )
    new_desc_tf = ft.TextField(
        label="Mô tả (tuỳ chọn)", multiline=True, min_lines=2, max_lines=3,
        bgcolor=Colors.BG_CARD, border_color=Colors.BORDER,
        focused_border_color=Colors.PRIMARY,
        text_style=ft.TextStyle(color=Colors.TEXT_PRIMARY),
        label_style=ft.TextStyle(color=Colors.TEXT_MUTED),
        border_radius=Radius.MD, cursor_color=Colors.PRIMARY,
    )
    color_sel = {"v": PROJECT_COLORS[0]}
    color_row_ref = ft.Ref[ft.Row]()

    def _color_dot(c):
        sel = c == color_sel["v"]
        return ft.GestureDetector(
            content=ft.Container(
                width=28, height=28, border_radius=14, bgcolor=c,
                border=ft.border.all(3, Colors.TEXT_PRIMARY if sel else "transparent"),
            ),
            on_tap=lambda _, col=c: _pick_color(col),
        )

    def _pick_color(c):
        color_sel["v"] = c
        if color_row_ref.current:
            color_row_ref.current.controls = [_color_dot(x) for x in PROJECT_COLORS]
            page.update()

    def _create_project(_):
        name = new_name_tf.value.strip()
        if not name:
            snack(page, "Vui lòng nhập tên dự án!", success=False)
            return
        now = datetime.now().isoformat()
        p = Project(
            id=str(uuid.uuid4()), user_id=user.id, name=name,
            description=new_desc_tf.value.strip(), color=color_sel["v"],
            created_at=now, updated_at=now,
        )
        ProjectService.save_project(p)
        new_name_tf.value = ""
        new_desc_tf.value = ""
        create_mode["v"] = False
        snack(page, f"Đã tạo dự án '{name}' ✓")
        _rebuild()

    def _delete_project(project_id: str, name: str):
        ProjectService.delete_project(project_id)
        if expanded_pid["v"] == project_id:
            expanded_pid["v"] = None
        snack(page, f"Đã xoá '{name}'")
        _rebuild()

    def _remove_task_from_project(task, project_name: str):
        """Gỡ task khỏi dự án (đặt project_id = None)."""
        task.project_id = None
        task.updated_at = datetime.now().isoformat()
        TaskService.save_task(task)
        _rebuild()

    # ── Task picker dialog (2 tabs: pick existing | create new) ─
    def _open_task_picker(project: Project):
        all_tasks = TaskService.get_tasks(user.id)
        pickable = [
            t for t in all_tasks
            if t.status not in ("done", "cancelled")
            and getattr(t, "project_id", None) != project.id
        ]

        # ── Shared state ─────────────────────────────────────
        tab        = {"v": "existing"}   # "existing" | "new"
        selected   = {}                  # {task_id: bool} for existing tab
        check_refs = {}

        # New task form fields
        new_title_tf = ft.TextField(
            label="Tiêu đề *", hint_text="Tên công việc...",
            bgcolor=Colors.BG_SURFACE, border_color=Colors.BORDER,
            focused_border_color=project.color,
            text_style=ft.TextStyle(color=Colors.TEXT_PRIMARY, size=Typography.SMALL),
            label_style=ft.TextStyle(color=Colors.TEXT_MUTED, size=Typography.TINY),
            border_radius=Radius.MD, cursor_color=project.color,
            content_padding=ft.padding.symmetric(horizontal=12, vertical=10),
        )
        new_due_tf = ft.TextField(
            label="Hạn (YYYY-MM-DD, tuỳ chọn)", hint_text="2026-05-15",
            bgcolor=Colors.BG_SURFACE, border_color=Colors.BORDER,
            focused_border_color=project.color,
            text_style=ft.TextStyle(color=Colors.TEXT_PRIMARY, size=Typography.SMALL),
            label_style=ft.TextStyle(color=Colors.TEXT_MUTED, size=Typography.TINY),
            border_radius=Radius.MD, cursor_color=project.color,
            content_padding=ft.padding.symmetric(horizontal=12, vertical=10),
        )
        new_cat = {"v": "personal"}
        new_pri = {"v": "medium"}

        cat_tab_refs  = {}
        pri_tab_refs  = {}

        def _tf_chip(label, key, state, refs, accent):
            ref = ft.Ref[ft.Container]()
            refs[key] = ref

            def _select(_):
                old = state["v"]
                state["v"] = key
                if old in refs and refs[old].current:
                    refs[old].current.bgcolor = Colors.BG_SURFACE
                    refs[old].current.border = ft.Border.all(1, Colors.BORDER)
                    if refs[old].current.content:
                        refs[old].current.content.color = Colors.TEXT_MUTED
                if refs[key].current:
                    refs[key].current.bgcolor = f"#20{accent[1:]}"
                    refs[key].current.border = ft.Border.all(1, accent)
                    if refs[key].current.content:
                        refs[key].current.content.color = accent
                page.update()

            is_sel = state["v"] == key
            return ft.GestureDetector(
                on_tap=_select,
                content=ft.Container(
                    ref=ref,
                    content=ft.Text(label, size=7,
                                    color=accent if is_sel else Colors.TEXT_MUTED,
                                    weight=Typography.BOLD),
                    padding=ft.padding.symmetric(horizontal=8, vertical=4),
                    border_radius=Radius.FULL,
                    bgcolor=f"#20{accent[1:]}" if is_sel else Colors.BG_SURFACE,
                    border=ft.Border.all(1, accent if is_sel else Colors.BORDER),
                ),
            )

        cat_chips = ft.Row([
            _tf_chip("👤 Cá nhân",  "personal",  new_cat, cat_tab_refs, Colors.PRIMARY),
            _tf_chip("💼 Công việc", "work",       new_cat, cat_tab_refs, Colors.ACCENT_CYAN),
            _tf_chip("❤️ Sức khoẻ", "health",     new_cat, cat_tab_refs, Colors.ERROR),
            _tf_chip("💰 Tài chính", "finance",    new_cat, cat_tab_refs, Colors.SUCCESS),
            _tf_chip("📚 Học tập",  "education",  new_cat, cat_tab_refs, Colors.WARNING),
        ], spacing=4, wrap=True)

        pri_chips = ft.Row([
            _tf_chip("🔴 Cao",    "high",   new_pri, pri_tab_refs, Colors.ERROR),
            _tf_chip("🟡 Vừa",   "medium", new_pri, pri_tab_refs, Colors.WARNING),
            _tf_chip("🔵 Thấp",  "low",    new_pri, pri_tab_refs, Colors.PRIMARY),
        ], spacing=4)

        # ── Bodies ───────────────────────────────────────────
        def _task_row(t):
            ref = ft.Ref[ft.Container]()
            check_refs[t.id] = ref
            cat_icon = CATEGORY_ICONS.get(t.category, "📌")
            pri_color = (Colors.ERROR if t.priority == "high"
                         else Colors.WARNING if t.priority == "medium"
                         else Colors.TEXT_MUTED)
            other_proj = next(
                (p for p in projects if p.id == getattr(t, "project_id", None)), None
            )
            badge = (
                ft.Container(
                    content=ft.Text(other_proj.name[:10], size=6, color="white"),
                    padding=ft.padding.symmetric(horizontal=5, vertical=2),
                    border_radius=Radius.FULL, bgcolor=other_proj.color,
                ) if other_proj else ft.Container()
            )
            return ft.GestureDetector(
                on_tap=lambda _, tid=t.id: _toggle(tid),
                content=ft.Container(
                    ref=ref,
                    content=ft.Row([
                        ft.Text(cat_icon, size=14),
                        ft.Column([
                            ft.Text(t.title, size=Typography.SMALL,
                                    color=Colors.TEXT_PRIMARY,
                                    max_lines=1, overflow=ft.TextOverflow.ELLIPSIS),
                            ft.Row([
                                ft.Container(width=6, height=6, border_radius=3,
                                             bgcolor=pri_color),
                                ft.Text(t.due_date_display if t.due_date else "Không hạn",
                                        size=7, color=Colors.TEXT_MUTED),
                                badge,
                            ], spacing=4,
                               vertical_alignment=ft.CrossAxisAlignment.CENTER),
                        ], spacing=2, tight=True, expand=True),
                        ft.Icon(ft.Icons.CHECK_CIRCLE_ROUNDED, size=18,
                                color="transparent"),
                    ], spacing=Spacing.SM,
                       vertical_alignment=ft.CrossAxisAlignment.CENTER),
                    padding=ft.padding.symmetric(horizontal=Spacing.SM, vertical=8),
                    border_radius=Radius.MD,
                    bgcolor="transparent",
                    border=ft.Border.all(1, Colors.BORDER),
                    margin=ft.margin.only(bottom=Spacing.XS),
                ),
            )

        existing_body = (
            ft.Container(
                content=ft.Column(
                    [_task_row(t) for t in pickable],
                    spacing=0, tight=True, scroll=ft.ScrollMode.AUTO,
                ),
                height=min(280, len(pickable) * 58),
            ) if pickable else ft.Container(
                content=ft.Column([
                    ft.Text("📭", size=28, text_align=ft.TextAlign.CENTER),
                    ft.Text("Không còn task nào để thêm",
                            size=Typography.SMALL, color=Colors.TEXT_MUTED,
                            text_align=ft.TextAlign.CENTER),
                ], horizontal_alignment=ft.CrossAxisAlignment.CENTER,
                   spacing=Spacing.SM),
                padding=ft.padding.symmetric(vertical=Spacing.MD),
            )
        )

        new_body = ft.Column([
            new_title_tf,
            ft.Container(height=Spacing.SM),
            ft.Text("Danh mục", size=Typography.TINY, color=Colors.TEXT_MUTED),
            ft.Container(height=4),
            cat_chips,
            ft.Container(height=Spacing.SM),
            ft.Text("Độ ưu tiên", size=Typography.TINY, color=Colors.TEXT_MUTED),
            ft.Container(height=4),
            pri_chips,
            ft.Container(height=Spacing.SM),
            new_due_tf,
        ], spacing=0, tight=True)

        body_wrap = ft.Container(content=existing_body)

        # ── Tab bar ──────────────────────────────────────────
        tab_existing_ref = ft.Ref[ft.Container]()
        tab_new_ref      = ft.Ref[ft.Container]()

        def _switch_tab(name):
            tab["v"] = name
            body_wrap.content = existing_body if name == "existing" else new_body
            # Update tab visuals
            if tab_existing_ref.current:
                tab_existing_ref.current.bgcolor = (
                    project.color if name == "existing" else Colors.BG_SURFACE
                )
                tab_existing_ref.current.content.color = (
                    "white" if name == "existing" else Colors.TEXT_MUTED
                )
            if tab_new_ref.current:
                tab_new_ref.current.bgcolor = (
                    project.color if name == "new" else Colors.BG_SURFACE
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
                    bgcolor=project.color if is_sel else Colors.BG_SURFACE,
                    expand=True,
                ),
            )

        tab_row = ft.Container(
            content=ft.Row([
                _tab_btn("📋  Chọn có sẵn", "existing", tab_existing_ref),
                ft.Container(width=Spacing.XS),
                _tab_btn("✏️  Tạo mới",     "new",      tab_new_ref),
            ], spacing=0),
            padding=ft.padding.only(bottom=Spacing.SM),
        )

        # ── Confirm logic ────────────────────────────────────
        def _close_dlg():
            page.dialog.open = False
            page.update()

        def _toggle(task_id):
            selected[task_id] = not selected.get(task_id, False)
            ref = check_refs.get(task_id)
            if ref and ref.current:
                is_sel = selected[task_id]
                ref.current.bgcolor = f"#20{project.color[1:]}" if is_sel else "transparent"
                ref.current.border = ft.Border.all(
                    2, project.color if is_sel else Colors.BORDER
                )
                row = ref.current.content
                if isinstance(row, ft.Row) and row.controls:
                    icon = row.controls[-1]
                    if isinstance(icon, ft.Icon):
                        icon.color = project.color if is_sel else "transparent"
                page.update()

        def _confirm(_):
            if tab["v"] == "existing":
                chosen = [t for t in pickable if selected.get(t.id)]
                if not chosen:
                    snack(page, "Chưa chọn task nào!", success=False)
                    return
                for t in chosen:
                    t.project_id = project.id
                    t.updated_at = datetime.now().isoformat()
                    TaskService.save_task(t)
                _close_dlg()
                snack(page, f"Đã thêm {len(chosen)} task vào '{project.name}' ✓")
            else:
                title = new_title_tf.value.strip()
                if not title:
                    new_title_tf.error_text = "Vui lòng nhập tiêu đề"
                    page.update()
                    return
                new_title_tf.error_text = None
                due = new_due_tf.value.strip() or None
                now_str = datetime.now().isoformat()
                new_task = __import__("core.models", fromlist=["Task"]).Task(
                    id=str(uuid.uuid4()),
                    user_id=user.id,
                    title=title,
                    category=new_cat["v"],
                    priority=new_pri["v"],
                    status="todo",
                    due_date=due,
                    project_id=project.id,
                    created_at=now_str,
                    updated_at=now_str,
                )
                TaskService.save_task(new_task)
                _close_dlg()
                snack(page, f"Đã tạo và thêm '{title}' vào '{project.name}' ✓")
            _rebuild()

        dlg = ft.AlertDialog(
            modal=True,
            title=ft.Row([
                ft.Container(width=12, height=12, border_radius=6, bgcolor=project.color),
                ft.Text(f"Thêm vào {project.name}",
                        size=Typography.H4, color=Colors.TEXT_PRIMARY,
                        weight=Typography.BOLD),
            ], spacing=Spacing.SM, vertical_alignment=ft.CrossAxisAlignment.CENTER),
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

    # ── Project card (with expandable task list) ──────────────
    def _project_card(p: Project) -> ft.Container:
        stats  = ProjectService.get_project_stats(user.id, p.id)
        total  = stats["total"]
        done   = stats["done"]
        pct    = stats["completion_rate"]
        overdue = stats["overdue"]
        is_open = expanded_pid["v"] == p.id

        progress_bar = ft.Container(
            content=ft.Row([
                ft.Container(
                    bgcolor=p.color,
                    border_radius=Radius.FULL,
                    expand=pct,
                    height=4,
                ) if pct > 0 else ft.Container(),
                ft.Container(
                    bgcolor=Colors.BORDER,
                    border_radius=Radius.FULL,
                    expand=max(1, 100 - pct),
                    height=4,
                ),
            ], spacing=0),
            border_radius=Radius.FULL,
            height=4,
            clip_behavior=ft.ClipBehavior.ANTI_ALIAS,
        ) if total > 0 else ft.Container()

        # ── Task list (shown only when expanded) ──────────────
        task_section = ft.Container(height=0)
        if is_open:
            proj_tasks = ProjectService.get_project_tasks(user.id, p.id)
            if proj_tasks:
                task_rows = []
                for t in proj_tasks[:8]:   # show max 8 inline
                    s_color = STATUS_COLORS.get(t.status, Colors.TEXT_MUTED)
                    cat_icon = CATEGORY_ICONS.get(t.category, "📌")
                    task_rows.append(ft.Container(
                        content=ft.Row([
                            ft.Text(cat_icon, size=12),
                            ft.Text(t.title, size=Typography.TINY,
                                    color=Colors.TEXT_PRIMARY, expand=True,
                                    max_lines=1, overflow=ft.TextOverflow.ELLIPSIS),
                            ft.Container(
                                width=8, height=8, border_radius=4,
                                bgcolor=s_color,
                                tooltip=t.status,
                            ),
                            ft.IconButton(
                                ft.Icons.REMOVE_CIRCLE_OUTLINE_ROUNDED,
                                icon_size=14, icon_color=Colors.TEXT_MUTED,
                                tooltip="Gỡ khỏi dự án",
                                on_click=lambda _, task=t, pn=p.name: _remove_task_from_project(task, pn),
                                padding=ft.padding.all(2),
                            ),
                        ], spacing=Spacing.XS,
                           vertical_alignment=ft.CrossAxisAlignment.CENTER),
                        padding=ft.padding.symmetric(vertical=4, horizontal=2),
                        border=ft.Border(bottom=ft.BorderSide(1, Colors.BORDER + "60")),
                    ))
                if len(proj_tasks) > 8:
                    task_rows.append(
                        ft.Text(f"... và {len(proj_tasks) - 8} task khác",
                                size=Typography.TINY, color=Colors.TEXT_MUTED)
                    )
                task_list = ft.Column(task_rows, spacing=0, tight=True)
            else:
                task_list = ft.Container(
                    content=ft.Text("Chưa có task trong dự án",
                                    size=Typography.TINY, color=Colors.TEXT_MUTED,
                                    text_align=ft.TextAlign.CENTER),
                    padding=ft.padding.symmetric(vertical=8),
                    alignment=ft.Alignment(0, 0),
                )

            task_section = ft.Container(
                content=ft.Column([
                    ft.Container(height=1, bgcolor=Colors.BORDER,
                                 margin=ft.margin.symmetric(vertical=Spacing.SM)),
                    task_list,
                    ft.Container(height=Spacing.SM),
                    ft.TextButton(
                        content=ft.Row([
                            ft.Icon(ft.Icons.ADD_ROUNDED, size=14, color=Colors.PRIMARY),
                            ft.Text("Thêm công việc vào dự án", size=Typography.SMALL,
                                    color=Colors.PRIMARY, weight=Typography.MEDIUM),
                        ], spacing=4, tight=True),
                        on_click=lambda _, proj=p: _open_task_picker(proj),
                        style=ft.ButtonStyle(padding=ft.padding.symmetric(horizontal=4, vertical=0)),
                    ),
                ], spacing=0, tight=True),
            )

        def _toggle_expand(_):
            expanded_pid["v"] = None if is_open else p.id
            _rebuild()

        return ft.Container(
            content=ft.Column([
                ft.GestureDetector(
                    on_tap=_toggle_expand,
                    content=ft.Column([
                        ft.Row([
                            ft.Container(width=12, height=12, border_radius=6, bgcolor=p.color),
                            ft.Text(p.name, size=Typography.H4, color=Colors.TEXT_PRIMARY,
                                    weight=Typography.BOLD, expand=True,
                                    max_lines=1, overflow=ft.TextOverflow.ELLIPSIS),
                            ft.Icon(
                                ft.Icons.KEYBOARD_ARROW_UP_ROUNDED if is_open
                                else ft.Icons.KEYBOARD_ARROW_DOWN_ROUNDED,
                                size=18, color=Colors.TEXT_MUTED,
                            ),
                            ft.IconButton(
                                ft.Icons.DELETE_OUTLINE_ROUNDED, icon_size=16,
                                icon_color=Colors.TEXT_MUTED,
                                on_click=lambda _, pid=p.id, pn=p.name: _delete_project(pid, pn),
                                padding=ft.padding.all(4),
                            ),
                        ], spacing=Spacing.SM,
                           vertical_alignment=ft.CrossAxisAlignment.CENTER),

                        ft.Text(p.description, size=Typography.TINY, color=Colors.TEXT_MUTED,
                                max_lines=1, overflow=ft.TextOverflow.ELLIPSIS)
                        if p.description else ft.Container(height=0),

                        ft.Container(height=Spacing.SM),

                        ft.Row([
                            ft.Text(f"{done}/{total} task", size=Typography.SMALL,
                                    color=Colors.TEXT_SECONDARY),
                            ft.Container(expand=True),
                            ft.Text(f"{pct}%", size=Typography.SMALL,
                                    color=Colors.SUCCESS if pct >= 70 else Colors.WARNING,
                                    weight=Typography.BOLD),
                        ]),
                        progress_bar,

                        ft.Text(f"⚠️ {overdue} quá hạn", size=Typography.TINY, color=Colors.ERROR)
                        if overdue > 0 else ft.Container(height=0),
                    ], spacing=4, tight=True),
                ),
                task_section,
            ], spacing=0, tight=True),
            padding=Spacing.MD, border_radius=Radius.LG,
            bgcolor=Colors.BG_CARD,
            border=ft.Border.all(1, p.color + "80" if is_open else Colors.BORDER),
            shadow=ft.BoxShadow(
                blur_radius=12 if is_open else 8,
                color="#00000018" if is_open else "#00000012",
                offset=ft.Offset(0, 2),
            ),
            margin=ft.Margin.only(bottom=Spacing.SM),
            animate=ft.Animation(200, ft.AnimationCurve.EASE_OUT),
        )

    # ── Rebuild ──────────────────────────────────────────────
    def _rebuild():
        nonlocal projects
        projects = ProjectService.get_projects(user.id)

        create_form = ft.Container(
            content=ft.Column([
                ft.Text("Tạo dự án mới", size=Typography.H4, color=Colors.TEXT_PRIMARY,
                        weight=Typography.BOLD),
                ft.Container(height=Spacing.SM),
                new_name_tf,
                ft.Container(height=Spacing.XS),
                new_desc_tf,
                ft.Container(height=Spacing.SM),
                ft.Row([
                    ft.Text("Màu:", size=Typography.SMALL, color=Colors.TEXT_MUTED),
                    ft.Row([_color_dot(c) for c in PROJECT_COLORS],
                           spacing=6, ref=color_row_ref),
                ], spacing=Spacing.SM, vertical_alignment=ft.CrossAxisAlignment.CENTER),
                ft.Container(height=Spacing.MD),
                ft.Row([
                    ft.TextButton("Huỷ", on_click=lambda _: _toggle_create(),
                                  style=ft.ButtonStyle(color=Colors.TEXT_MUTED)),
                    primary_button("Tạo dự án", on_click=_create_project, height=40),
                ], alignment=ft.MainAxisAlignment.END),
            ], spacing=0, tight=True),
            padding=Spacing.MD, border_radius=Radius.LG,
            bgcolor=Colors.BG_CARD, border=ft.Border.all(1, Colors.PRIMARY_BORDER),
            margin=ft.Margin.only(bottom=Spacing.SM),
        ) if create_mode["v"] else ft.Container()

        empty_state = ft.Container(
            content=ft.Column([
                ft.Text("📁", size=48, text_align=ft.TextAlign.CENTER),
                ft.Text("Chưa có dự án nào", size=Typography.H4, color=Colors.TEXT_MUTED,
                        text_align=ft.TextAlign.CENTER),
                ft.Text("Tạo dự án để nhóm các task liên quan lại với nhau",
                        size=Typography.SMALL, color=Colors.TEXT_MUTED,
                        text_align=ft.TextAlign.CENTER),
            ], horizontal_alignment=ft.CrossAxisAlignment.CENTER, spacing=Spacing.SM),
            padding=ft.Padding.symmetric(vertical=60),
            alignment=ft.Alignment.CENTER,
        )

        main_col.controls = [
            ft.Container(
                content=ft.Row([
                    ft.IconButton(ft.Icons.ARROW_BACK_IOS_NEW_ROUNDED,
                                  on_click=lambda _: on_navigate("dashboard")),
                    ft.Text("Dự án", size=Typography.H2, color=Colors.TEXT_PRIMARY,
                            weight=Typography.BOLD, expand=True),
                    ft.IconButton(ft.Icons.ADD_ROUNDED, icon_color=Colors.PRIMARY,
                                  on_click=lambda _: _toggle_create()),
                ]),
                padding=ft.Padding.symmetric(horizontal=Spacing.MD, vertical=Spacing.MD),
            ),
            ft.Container(
                content=ft.Column([
                    create_form,
                    *(
                        [_project_card(p) for p in projects]
                        if projects else [empty_state]
                    ),
                    ft.Container(height=100),
                ], spacing=0, tight=True),
                padding=ft.Padding.symmetric(horizontal=Spacing.MD),
            ),
        ]
        page.update()

    def _toggle_create():
        create_mode["v"] = not create_mode["v"]
        _rebuild()

    _rebuild()
    return ft.Column([main_col], spacing=0, tight=True, expand=True)
