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
from core.i18n import t
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
            tasks = [tk for tk in tasks if q in tk.title.lower() or q in tk.description.lower()]
        if filter_cat["v"] != "all":
            tasks = [tk for tk in tasks if tk.category == filter_cat["v"]]
        if filter_status["v"] != "all":
            tasks = [tk for tk in tasks if tk.status == filter_status["v"]]
        if filter_pri["v"] != "all":
            tasks = [tk for tk in tasks if tk.priority == filter_pri["v"]]
        def sort_key(tk: Task):
            pri_order = {"high": 0, "medium": 1, "low": 2}
            return (0 if tk.is_overdue else 1, tk.due_date or "9999", pri_order.get(tk.priority, 1))
        return sorted(tasks, key=sort_key)

    def refresh_list():
        if tasks_ref.current:
            tasks_ref.current.controls = build_task_list()
            page.update()


    # ── Delete confirm ────────────────────────────────────────
    def delete_task(task_id: str):
        def confirm(_):
            TaskService.delete_task(task_id, user_id=user.id)
            _del_bs[0].open = False
            page.update()
            refresh_list()
            snack(page, t("task_deleted"))

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
                    ft.Text(t("delete_task_title"), size=Typography.H3,
                            color=Colors.TEXT_PRIMARY, weight=Typography.BOLD,
                            text_align=ft.TextAlign.CENTER),
                    ft.Container(height=Spacing.SM),
                    ft.Text(t("delete_warning"),
                            size=Typography.SMALL, color=Colors.TEXT_MUTED,
                            text_align=ft.TextAlign.CENTER),
                    ft.Container(height=Spacing.XL),
                    ft.Row([
                        ft.Container(
                            content=ft.Text(t("cancel"), size=Typography.BODY,
                                            color=Colors.TEXT_MUTED,
                                            weight=Typography.MEDIUM),
                            height=48, expand=True,
                            border_radius=Radius.MD,
                            bgcolor=Colors.BG_SURFACE,
                            border=ft.Border.all(1, Colors.BORDER),
                            alignment=ft.Alignment.CENTER,
                            on_click=cancel, ink=True,
                        ),
                        ft.Container(width=Spacing.SM),
                        ft.Container(
                            content=ft.Row([
                                ft.Icon(ft.Icons.DELETE_OUTLINE, size=16,
                                        color="#FFFFFF"),
                                ft.Container(width=4),
                                ft.Text(t("delete"), size=Typography.BODY,
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
                border_radius=ft.BorderRadius.only(
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

    # ── Focus Timer Bottom Sheet ──────────────────────────────
    def _open_focus_timer(task: Task):
        import time as _time
        import threading as _th
        from datetime import datetime as _dt

        timer_state = {
            "running": False,
            "start_time": None,
            "elapsed": 0,
            "session_id": str(uuid.uuid4()),
        }
        quality_state = {"v": 7}

        def _fmt(secs: int) -> str:
            m, s = divmod(secs, 60)
            h, m = divmod(m, 60)
            return f"{h:02d}:{m:02d}:{s:02d}" if h else f"{m:02d}:{s:02d}"

        # ── Direct object refs — not ft.Ref, avoids overlay ref issues ──
        timer_text = ft.Text(
            "00:00",
            size=40, color=Colors.PRIMARY,
            weight=Typography.EXTRABOLD,
            text_align=ft.TextAlign.CENTER,
        )
        quality_disp = ft.Text(
            "7", size=Typography.H3, color=Colors.PRIMARY,
            weight=Typography.BOLD, width=28,
            text_align=ft.TextAlign.CENTER,
        )
        # Single action button — swaps start ↔ stop content in-place
        action_btn = ft.Container(
            height=48, border_radius=Radius.MD,
            alignment=ft.Alignment.CENTER, ink=True,
        )

        # ── Tick loop: only updates timer_text, no full page.update() ──
        def _tick():
            while timer_state["running"]:
                _time.sleep(0.5)          # poll at 0.5 s, update display every second
                if not timer_state["running"]:
                    break
                new_elapsed = int(_time.time() - timer_state["start_time"])
                if new_elapsed == timer_state["elapsed"]:
                    continue              # no change yet
                timer_state["elapsed"] = new_elapsed
                timer_text.value = _fmt(new_elapsed)
                try:
                    timer_text.update()   # update ONLY the timer — zero lag
                except Exception:
                    pass

        def _start_session(_=None):
            if timer_state["running"]:
                return
            timer_state["running"] = True
            timer_state["start_time"] = _time.time()
            # Swap button → stop
            action_btn.content = ft.Row([
                ft.Icon(ft.Icons.STOP_ROUNDED, color="white", size=20),
                ft.Text(t("stop_btn"), size=Typography.BODY,
                        color="white", weight=Typography.SEMIBOLD),
            ], spacing=6, alignment=ft.MainAxisAlignment.CENTER)
            action_btn.bgcolor = Colors.ERROR
            action_btn.on_click = _end_session
            try:
                action_btn.update()
            except Exception:
                pass
            _th.Thread(target=_tick, daemon=True).start()

        def _end_session(_=None):
            if not timer_state["running"]:
                return
            timer_state["running"] = False          # stops _tick immediately
            elapsed_mins = max(1, timer_state["elapsed"] // 60)

            # Swap button back → start (show briefly before closing)
            action_btn.content = ft.Row([
                ft.Icon(ft.Icons.CHECK_ROUNDED, color="white", size=20),
                ft.Text(t("focus_saved", n=elapsed_mins, q=quality_state["v"]),
                        size=Typography.BODY, color="white",
                        weight=Typography.SEMIBOLD),
            ], spacing=6, alignment=ft.MainAxisAlignment.CENTER)
            action_btn.bgcolor = Colors.SUCCESS
            action_btn.on_click = None
            try:
                action_btn.update()
            except Exception:
                pass

            # Save work session
            try:
                from core.database import Storage as _Storage
                from core.models import WorkSession as _WSM
                now_str = _dt.now().isoformat()
                ws = _WSM(
                    id=timer_state["session_id"],
                    user_id=user.id,
                    task_id=task.id,
                    started_at=(_dt.fromtimestamp(timer_state["start_time"]).isoformat()
                                if timer_state["start_time"] else now_str),
                    ended_at=now_str,
                    duration_minutes=elapsed_mins,
                    focus_quality=quality_state["v"],
                    notes="",
                )
                _Storage.save_work_session(ws)
                task.actual_minutes = getattr(task, "actual_minutes", 0) + elapsed_mins
                task.updated_at = now_str
                TaskService.save_task(task)
            except Exception as _e:
                import logging
                logging.getLogger(__name__).error("Focus timer save error: %s", _e)

            # Close sheet after brief feedback
            _time.sleep(0.7)
            timer_bs[0].open = False
            try:
                page.update()
            except Exception:
                pass
            refresh_list()

        # Wire initial start state
        action_btn.content = ft.Row([
            ft.Icon(ft.Icons.PLAY_ARROW_ROUNDED, color="white", size=20),
            ft.Text(t("start_btn"), size=Typography.BODY,
                    color="white", weight=Typography.SEMIBOLD),
        ], spacing=6, alignment=ft.MainAxisAlignment.CENTER)
        action_btn.bgcolor = Colors.PRIMARY
        action_btn.on_click = _start_session

        quality_slider = ft.Slider(
            min=1, max=10, divisions=9, value=7,
            active_color=Colors.PRIMARY, thumb_color=Colors.PRIMARY,
            on_change=lambda e: [
                quality_state.update({"v": int(e.control.value)}),
                setattr(quality_disp, "value", str(quality_state["v"])),
                quality_disp.update(),
            ],
        )

        pri_info = PRIORITY_MAP.get(task.priority, PRIORITY_MAP["medium"])
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
                        ft.Icon(ft.Icons.TIMER_ROUNDED, size=22, color=Colors.PRIMARY),
                        ft.Text("Focus Timer", size=Typography.H3,
                                color=Colors.TEXT_PRIMARY, weight=Typography.BOLD),
                    ], spacing=Spacing.SM),
                    ft.Container(height=4),
                    ft.Text(task.title, size=Typography.SMALL, color=Colors.TEXT_SECONDARY,
                            max_lines=2, overflow=ft.TextOverflow.ELLIPSIS),
                    ft.Container(height=Spacing.LG),
                    # Timer display — direct object, no Ref
                    ft.Container(
                        content=timer_text,
                        alignment=ft.Alignment.CENTER,
                    ),
                    ft.Container(height=Spacing.LG),
                    # Quality slider
                    ft.Text(t("focus_quality"), size=Typography.SMALL,
                            color=Colors.TEXT_MUTED),
                    ft.Container(height=4),
                    ft.Row([
                        quality_slider,
                        quality_disp,
                    ], spacing=Spacing.SM, vertical_alignment=ft.CrossAxisAlignment.CENTER),
                    ft.Container(height=Spacing.MD),
                    action_btn,
                    ft.Container(height=Spacing.XXL),
                ], spacing=0, tight=True),
                padding=ft.padding.symmetric(horizontal=Spacing.LG),
            ),
        ], spacing=0, tight=True)

        tbs = ft.BottomSheet(
            content=ft.Container(
                content=sheet, bgcolor=Colors.BG_CARD,
                border_radius=ft.BorderRadius.only(top_left=Radius.XL, top_right=Radius.XL),
                padding=0, clip_behavior=ft.ClipBehavior.ANTI_ALIAS,
            ),
            open=True, draggable=True, use_safe_area=True,
        )
        timer_bs = [tbs]
        page.overlay.append(tbs)
        page.update()

    # ── Task Detail Bottom Sheet ──────────────────────────────
    def _open_task_detail(task: Task):
        pri_info = PRIORITY_MAP.get(task.priority, PRIORITY_MAP["medium"])
        cat_info = CATEGORY_MAP.get(task.category, CATEGORY_MAP["personal"])
        is_done  = task.status == "done"

        detail_bs = [None]

        def _close():
            if detail_bs[0]:
                detail_bs[0].open = False
                page.update()

        def _do_edit(_):
            _close()
            on_navigate("task_edit", task=task)

        def _do_delete(_):
            _close()
            delete_task(task.id)

        def _do_timer(_):
            _close()
            _open_focus_timer(task)

        def _do_toggle(_):
            toggle_done(task)
            _close()

        sheet = ft.Column([
            ft.Container(
                content=ft.Container(width=40, height=4, border_radius=Radius.FULL,
                                     bgcolor="#444444"),
                alignment=ft.Alignment.CENTER,
                padding=ft.padding.only(top=12, bottom=8),
            ),
            ft.Container(
                content=ft.Column([
                    # Title + priority bar
                    ft.Row([
                        ft.Container(
                            width=4, height=None, border_radius=Radius.FULL,
                            bgcolor=pri_info["color"], expand_loose=True,
                        ),
                        ft.Container(width=8),
                        ft.Text(task.title, size=Typography.H4,
                                color=Colors.TEXT_PRIMARY, weight=Typography.BOLD,
                                expand=True, max_lines=3,
                                overflow=ft.TextOverflow.ELLIPSIS),
                    ], vertical_alignment=ft.CrossAxisAlignment.START),
                    ft.Container(height=Spacing.SM),
                    # Meta chips row
                    ft.Row([
                        ft.Container(
                            content=ft.Text(cat_info["label"], size=10,
                                            color=Colors.TEXT_SECONDARY),
                            padding=ft.padding.symmetric(horizontal=8, vertical=4),
                            border_radius=Radius.FULL,
                            bgcolor=Colors.BG_SURFACE,
                            border=ft.Border.all(1, Colors.BORDER),
                        ),
                        ft.Container(
                            content=ft.Text(pri_info["label"], size=10,
                                            color=pri_info["color"],
                                            weight=Typography.SEMIBOLD),
                            padding=ft.padding.symmetric(horizontal=8, vertical=4),
                            border_radius=Radius.FULL,
                            bgcolor=f"#15{pri_info['color'][1:]}",
                            border=ft.Border.all(1, f"#30{pri_info['color'][1:]}"),
                        ),
                        ft.Container(
                            content=ft.Text(
                                STATUS_MAP.get(task.status, {}).get("label", task.status),
                                size=10, color=Colors.TEXT_SECONDARY,
                            ),
                            padding=ft.padding.symmetric(horizontal=8, vertical=4),
                            border_radius=Radius.FULL,
                            bgcolor=Colors.BG_SURFACE,
                            border=ft.Border.all(1, Colors.BORDER),
                        ),
                    ], spacing=Spacing.XS, wrap=True),
                    ft.Container(height=Spacing.XS),
                    # Deadline
                    ft.Row([
                        ft.Text("📅", size=13),
                        ft.Text(task.due_date_display, size=Typography.SMALL,
                                color=Colors.ERROR if task.is_overdue else Colors.TEXT_SECONDARY),
                        ft.Container(expand=True),
                        ft.Text(t("focus_time_log", n=getattr(task, 'actual_minutes', 0)),
                                size=Typography.TINY, color=Colors.TEXT_MUTED),
                    ], spacing=4, vertical_alignment=ft.CrossAxisAlignment.CENTER),
                    # Description
                    *(
                        [ft.Container(height=Spacing.SM),
                         ft.Text(task.description, size=Typography.SMALL,
                                 color=Colors.TEXT_SECONDARY, max_lines=4,
                                 overflow=ft.TextOverflow.ELLIPSIS)]
                        if task.description else []
                    ),
                    ft.Container(height=Spacing.LG),
                    # Action buttons 2x2
                    ft.Row([
                        _action_btn(ft.Icons.PLAY_CIRCLE_ROUNDED,   t("start_focus"), Colors.PRIMARY,   _do_timer),
                        ft.Container(width=Spacing.SM),
                        _action_btn(
                            ft.Icons.CHECK_CIRCLE_ROUNDED if not is_done
                            else ft.Icons.RADIO_BUTTON_UNCHECKED,
                            t("mark_done") if not is_done else t("mark_undone"),
                            Colors.SUCCESS if not is_done else Colors.TEXT_MUTED,
                            _do_toggle,
                        ),
                    ], spacing=0),
                    ft.Container(height=Spacing.SM),
                    ft.Row([
                        _action_btn(ft.Icons.EDIT_ROUNDED,           t("edit_btn"),  Colors.ACCENT_CYAN, _do_edit),
                    ], spacing=0),
                    ft.Container(height=Spacing.SM),
                    ft.Container(
                        content=ft.Row([
                            ft.Icon(ft.Icons.DELETE_OUTLINE_ROUNDED, size=16, color=Colors.ERROR),
                            ft.Text(t("delete_task_action"), size=Typography.BODY,
                                    color=Colors.ERROR, weight=Typography.MEDIUM),
                        ], spacing=6, alignment=ft.MainAxisAlignment.CENTER),
                        height=44, border_radius=Radius.MD,
                        bgcolor=f"#10{Colors.ERROR[1:]}",
                        border=ft.Border.all(1, f"#30{Colors.ERROR[1:]}"),
                        alignment=ft.Alignment.CENTER,
                        on_click=_do_delete, ink=True,
                    ),
                    ft.Container(height=Spacing.XXL),
                ], spacing=0, tight=True),
                padding=ft.padding.symmetric(horizontal=Spacing.LG),
            ),
        ], spacing=0, tight=True)

        dbs = ft.BottomSheet(
            content=ft.Container(
                content=sheet, bgcolor=Colors.BG_CARD,
                border_radius=ft.BorderRadius.only(top_left=Radius.XL, top_right=Radius.XL),
                padding=0, clip_behavior=ft.ClipBehavior.ANTI_ALIAS,
            ),
            open=True, draggable=True, use_safe_area=True,
        )
        detail_bs[0] = dbs
        page.overlay.append(dbs)
        page.update()

    def _action_btn(icon, label, color, on_tap):
        return ft.Container(
            content=ft.Column([
                ft.Icon(icon, size=22, color=color),
                ft.Text(label, size=10, color=color, text_align=ft.TextAlign.CENTER),
            ], horizontal_alignment=ft.CrossAxisAlignment.CENTER, spacing=4, tight=True),
            height=64, expand=True,
            border_radius=Radius.MD,
            bgcolor=f"#12{color[1:]}" if color.startswith("#") else Colors.BG_SURFACE,
            border=ft.Border.all(1, f"#30{color[1:]}" if color.startswith("#") else Colors.BORDER),
            alignment=ft.Alignment.CENTER,
            on_click=on_tap, ink=True,
        )

    # ── Lean Task card (tap → detail sheet) ──────────────────
    def task_card(task: Task) -> ft.Container:
        pri_info  = PRIORITY_MAP.get(task.priority, PRIORITY_MAP["medium"])
        is_done   = task.status == "done"
        status_info = STATUS_MAP.get(task.status, STATUS_MAP["todo"])

        return ft.Container(
            content=ft.Row([
                # Priority bar
                ft.Container(
                    width=4, height=None,
                    border_radius=Radius.FULL,
                    bgcolor=pri_info["color"],
                    expand_loose=True,
                ),
                ft.Container(width=8),
                # Main info
                ft.Column([
                    ft.Text(
                        task.title,
                        size=Typography.BODY,
                        color=Colors.TEXT_MUTED if is_done else Colors.TEXT_PRIMARY,
                        weight=Typography.SEMIBOLD,
                        max_lines=1,
                        overflow=ft.TextOverflow.ELLIPSIS,
                        style=ft.TextStyle(
                            decoration=ft.TextDecoration.LINE_THROUGH if is_done else None,
                        ),
                    ),
                    ft.Container(height=4),
                    ft.Row([
                        ft.Text("📅", size=11),
                        ft.Text(task.due_date_display, size=10,
                                color=Colors.ERROR if task.is_overdue else Colors.TEXT_MUTED),
                        ft.Container(
                            content=ft.Text(pri_info["label"], size=10,
                                            color=pri_info["color"],
                                            weight=Typography.SEMIBOLD),
                            padding=ft.padding.symmetric(horizontal=6, vertical=2),
                            border_radius=Radius.FULL,
                            bgcolor=f"#15{pri_info['color'][1:]}",
                        ),
                        ft.Container(
                            content=ft.Text(status_info["label"], size=10,
                                            color=Colors.TEXT_MUTED),
                            padding=ft.padding.symmetric(horizontal=6, vertical=2),
                            border_radius=Radius.FULL,
                            bgcolor=Colors.BG_SURFACE,
                            border=ft.Border.all(1, Colors.BORDER),
                        ),
                    ], spacing=4, vertical_alignment=ft.CrossAxisAlignment.CENTER, wrap=True),
                ], expand=True, spacing=0, tight=True),
                # Done toggle
                ft.GestureDetector(
                    content=ft.Container(
                        content=ft.Icon(
                            ft.Icons.CHECK_CIRCLE if is_done
                            else ft.Icons.RADIO_BUTTON_UNCHECKED,
                            size=24,
                            color=Colors.SUCCESS if is_done else Colors.TEXT_MUTED,
                        ),
                        padding=ft.padding.all(4),
                    ),
                    on_tap=lambda _, tt=task: toggle_done(tt),
                ),
            ], vertical_alignment=ft.CrossAxisAlignment.CENTER),
            padding=ft.padding.symmetric(vertical=10, horizontal=Spacing.SM),
            border_radius=Radius.MD,
            bgcolor=Colors.BG_CARD,
            border=ft.Border.all(
                1,
                f"#50{Colors.ERROR[1:]}" if task.is_overdue else Colors.BORDER,
            ),
            margin=ft.Margin.only(bottom=Spacing.SM),
            shadow=ft.BoxShadow(
                blur_radius=6 if task.is_overdue else 3,
                color="#22EF4444" if task.is_overdue else "#00000010",
                offset=ft.Offset(0, 2),
            ),
            on_click=lambda _, tt=task: _open_task_detail(tt),
            ink=True,
            animate=ft.Animation(200, ft.AnimationCurve.EASE_OUT),
        )

    def build_task_list():
        filtered = get_filtered_tasks()
        if not filtered:
            return [ft.Container(
                content=ft.Column([
                    ft.Text("📭", size=48),
                    ft.Text(t("no_tasks"), size=Typography.BODY,
                            color=Colors.TEXT_MUTED, text_align=ft.TextAlign.CENTER),
                    ft.Container(height=Spacing.MD),
                    primary_button(t("add_first_task"),
                                on_click=lambda _: on_navigate("task_edit"),
                                icon=ft.Icons.ADD, height=44, width=200),
                ], horizontal_alignment=ft.CrossAxisAlignment.CENTER,
                   spacing=Spacing.SM),
                padding=Spacing.XXL,
                alignment=ft.Alignment.CENTER,
            )]
        return [task_card(tk) for tk in filtered]

    # ── Filter chips ──────────────────────────────────────────
    def filter_row(label, options, sel_ref, update_fn):
        chips = []
        all_options = {"all": {"label": t("all_tasks"), "icon": "✦", "color": Colors.PRIMARY}}
        all_options.update(options)
        for key, info in all_options.items():
            def make_click(k, chips_list):
                def _click(_):
                    sel_ref["v"] = k
                    for i, (ck, ci) in enumerate(all_options.items()):
                        c = chips_list[i]
                        sel = (ck == k)
                        c.bgcolor = Colors.PRIMARY if sel else "transparent"
                        c.border  = ft.Border.all(1.5, Colors.PRIMARY) if sel else ft.Border.all(1, Colors.BORDER)
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

    cat_filter = filter_row(t("category_label"), CATEGORY_MAP, filter_cat, refresh_list)
    pri_filter = filter_row(t("priority_label"), PRIORITY_MAP, filter_pri, refresh_list)
    sta_filter = filter_row(t("status_label"),   STATUS_MAP,   filter_status, refresh_list)

    # ── Search & Filter Panel ─────────────────────────────────
    search_field = ft.TextField(
        hint_text=t("search_tasks"),
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
                ft.Text(t("filter_tasks"), size=Typography.H3,
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
                    content=primary_button(t("done_btn"), on_click=close_filter_sheet, width=200),
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
            border_radius=ft.BorderRadius.only(
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
            tooltip=t("filter_tooltip"),
        ),
        bgcolor=Colors.BG_INPUT,
        border_radius=Radius.FULL,
        border=ft.Border.all(1, Colors.BORDER),
        height=44,
        width=44,
        alignment=ft.Alignment.CENTER,
    )

    # ── AI Quick-Add (natural language) ──────────────────────
    def _open_ai_quick_add(_):
        _ai_input_tf = ft.TextField(
            hint_text=t("ai_task_hint"),
            hint_style=ft.TextStyle(color=Colors.TEXT_MUTED, size=Typography.SMALL),
            bgcolor=Colors.BG_CARD,
            border_color=Colors.BORDER,
            focused_border_color=Colors.PRIMARY,
            text_style=ft.TextStyle(color=Colors.TEXT_PRIMARY),
            border_radius=Radius.MD,
            cursor_color=Colors.PRIMARY,
            multiline=False,
            autofocus=True,
            content_padding=ft.padding.symmetric(horizontal=14, vertical=12),
        )
        _status_text = ft.Text("", size=Typography.TINY, color=Colors.TEXT_MUTED,
                               text_align=ft.TextAlign.CENTER)
        _parsing = {"running": False}

        def _do_parse(_):
            raw = _ai_input_tf.value.strip()
            if not raw:
                return
            if _parsing["running"]:
                return
            _parsing["running"] = True
            _status_text.value = t("ai_analyzing")
            _status_text.color = Colors.PRIMARY
            _ai_input_tf.disabled = True
            page.update()

            def _run():
                from utils.ai_helper import parse_natural_task
                data = parse_natural_task(raw, user.id)
                _parsing["running"] = False
                _ai_input_tf.disabled = False
                try:
                    page.run_task(lambda: _show_confirm(data, raw))
                except Exception:
                    _show_confirm(data, raw)

            import threading as _t
            _t.Thread(target=_run, daemon=True).start()

        def _show_confirm(data: dict, original_text: str):
            ai_bs[0].open = False
            page.update()
            _open_confirm_sheet(data)

        send_btn_ai = ft.Container(
            content=ft.Icon(ft.Icons.AUTO_AWESOME_ROUNDED, color="white", size=18),
            width=44, height=44,
            border_radius=Radius.MD,
            gradient=ft.LinearGradient(
                colors=["#A855F7", "#3B82F6"],
                begin=ft.Alignment.TOP_LEFT,
                end=ft.Alignment.BOTTOM_RIGHT,
            ),
            alignment=ft.Alignment.CENTER,
            on_click=_do_parse,
            ink=True,
        )

        sheet_content = ft.Column([
            ft.Container(
                content=ft.Container(width=40, height=4, border_radius=Radius.FULL,
                                     bgcolor="#444444"),
                alignment=ft.Alignment.CENTER,
                padding=ft.padding.only(top=12, bottom=8),
            ),
            ft.Container(
                content=ft.Column([
                    ft.Row([
                        ft.Container(
                            content=ft.Icon(ft.Icons.AUTO_AWESOME_ROUNDED, size=16, color="white"),
                            width=32, height=32, border_radius=16,
                            gradient=ft.LinearGradient(colors=["#A855F7", "#3B82F6"],
                                                       begin=ft.Alignment.TOP_LEFT,
                                                       end=ft.Alignment.BOTTOM_RIGHT),
                            alignment=ft.Alignment.CENTER,
                        ),
                        ft.Text(t("ai_quick_task"), size=Typography.H3,
                                color=Colors.TEXT_PRIMARY, weight=Typography.BOLD),
                    ], spacing=Spacing.SM),
                    ft.Text(t("ai_task_subtitle"),
                            size=Typography.TINY, color=Colors.TEXT_MUTED),
                    ft.Container(height=Spacing.MD),
                    ft.Row([_ai_input_tf, send_btn_ai], spacing=Spacing.SM),
                    ft.Container(height=6),
                    _status_text,
                    ft.Container(height=Spacing.MD),
                    ft.Row([
                        ft.Text(t("ai_task_example"),
                                size=Typography.TINY, color=Colors.TEXT_MUTED,
                                italic=True),
                    ], spacing=4),
                ], spacing=0, tight=True),
                padding=ft.padding.symmetric(horizontal=Spacing.LG),
            ),
            ft.Container(height=Spacing.XL),
        ], spacing=0, tight=True)

        bs = ft.BottomSheet(
            content=ft.Container(
                content=sheet_content,
                bgcolor=Colors.BG_CARD,
                border_radius=ft.BorderRadius.only(top_left=Radius.XL, top_right=Radius.XL),
                padding=0,
                clip_behavior=ft.ClipBehavior.ANTI_ALIAS,
            ),
            open=True, draggable=True, use_safe_area=True,
        )
        ai_bs = [bs]
        page.overlay.append(bs)
        page.update()

    def _open_confirm_sheet(data: dict):
        """Show pre-filled task fields for user to confirm before saving."""
        from core.models import Task as _Task

        cat_opts = {"personal": t("cat_personal"), "work": t("cat_work"),
                    "health": t("cat_health"), "finance": t("cat_finance"),
                    "education": t("cat_education")}
        pri_opts = {"high": t("pri_high"), "medium": t("pri_medium"), "low": t("pri_low")}
        cat_sel = {"v": data.get("category", "personal")}
        pri_sel = {"v": data.get("priority", "medium")}

        tf_title = ft.TextField(
            value=data.get("title", ""),
            label=t("title_label"),
            bgcolor=Colors.BG_SURFACE, border_color=Colors.BORDER,
            focused_border_color=Colors.PRIMARY,
            text_style=ft.TextStyle(color=Colors.TEXT_PRIMARY, size=Typography.BODY),
            label_style=ft.TextStyle(color=Colors.TEXT_MUTED, size=Typography.TINY),
            border_radius=Radius.MD, cursor_color=Colors.PRIMARY,
            content_padding=ft.padding.symmetric(horizontal=12, vertical=10),
        )
        tf_desc = ft.TextField(
            value=data.get("description", ""),
            label=t("desc_label"),
            bgcolor=Colors.BG_SURFACE, border_color=Colors.BORDER,
            focused_border_color=Colors.PRIMARY,
            text_style=ft.TextStyle(color=Colors.TEXT_PRIMARY, size=Typography.SMALL),
            label_style=ft.TextStyle(color=Colors.TEXT_MUTED, size=Typography.TINY),
            border_radius=Radius.MD, cursor_color=Colors.PRIMARY,
            content_padding=ft.padding.symmetric(horizontal=12, vertical=10),
        )

        due_str = data.get("due_date") or ""
        time_str = data.get("due_time") or ""
        tf_due  = ft.TextField(
            value=due_str, label=t("due_date_label"),
            bgcolor=Colors.BG_SURFACE, border_color=Colors.BORDER,
            focused_border_color=Colors.PRIMARY,
            text_style=ft.TextStyle(color=Colors.TEXT_PRIMARY, size=Typography.SMALL),
            label_style=ft.TextStyle(color=Colors.TEXT_MUTED, size=Typography.TINY),
            border_radius=Radius.MD, cursor_color=Colors.PRIMARY,
            content_padding=ft.padding.symmetric(horizontal=12, vertical=10),
            expand=True,
        )
        tf_time = ft.TextField(
            value=time_str, label=t("due_time_label"),
            bgcolor=Colors.BG_SURFACE, border_color=Colors.BORDER,
            focused_border_color=Colors.PRIMARY,
            text_style=ft.TextStyle(color=Colors.TEXT_PRIMARY, size=Typography.SMALL),
            label_style=ft.TextStyle(color=Colors.TEXT_MUTED, size=Typography.TINY),
            border_radius=Radius.MD, cursor_color=Colors.PRIMARY,
            content_padding=ft.padding.symmetric(horizontal=12, vertical=10),
            expand=True,
        )

        # Category chips
        cat_chip_refs = {}
        def _cat_chip(key, label):
            ref = ft.Ref[ft.Container]()
            cat_chip_refs[key] = ref
            is_sel = cat_sel["v"] == key
            def _tap(_, k=key):
                cat_sel["v"] = k
                for k2, r2 in cat_chip_refs.items():
                    if r2.current:
                        s2 = k2 == k
                        r2.current.bgcolor = Colors.PRIMARY if s2 else Colors.BG_SURFACE
                        r2.current.border = ft.Border.all(1, Colors.PRIMARY if s2 else Colors.BORDER)
                        if r2.current.content:
                            r2.current.content.color = "white" if s2 else Colors.TEXT_MUTED
                page.update()
            return ft.GestureDetector(
                on_tap=_tap,
                content=ft.Container(
                    ref=ref,
                    content=ft.Text(label, size=10,
                                    color="white" if is_sel else Colors.TEXT_MUTED),
                    padding=ft.padding.symmetric(horizontal=10, vertical=5),
                    border_radius=Radius.FULL,
                    bgcolor=Colors.PRIMARY if is_sel else Colors.BG_SURFACE,
                    border=ft.Border.all(1, Colors.PRIMARY if is_sel else Colors.BORDER),
                ),
            )

        pri_chip_refs = {}
        pri_colors = {"high": Colors.ERROR, "medium": Colors.WARNING, "low": Colors.PRIMARY}
        def _pri_chip(key, label):
            ref = ft.Ref[ft.Container]()
            pri_chip_refs[key] = ref
            is_sel = pri_sel["v"] == key
            color = pri_colors.get(key, Colors.PRIMARY)
            def _tap(_, k=key):
                pri_sel["v"] = k
                for k2, r2 in pri_chip_refs.items():
                    if r2.current:
                        s2 = k2 == k
                        c2 = pri_colors.get(k2, Colors.PRIMARY)
                        r2.current.bgcolor = f"#20{c2[1:]}" if s2 else Colors.BG_SURFACE
                        r2.current.border = ft.Border.all(1, c2 if s2 else Colors.BORDER)
                        if r2.current.content:
                            r2.current.content.color = c2 if s2 else Colors.TEXT_MUTED
                page.update()
            return ft.GestureDetector(
                on_tap=_tap,
                content=ft.Container(
                    ref=ref,
                    content=ft.Text(label, size=10,
                                    color=color if is_sel else Colors.TEXT_MUTED),
                    padding=ft.padding.symmetric(horizontal=10, vertical=5),
                    border_radius=Radius.FULL,
                    bgcolor=f"#20{color[1:]}" if is_sel else Colors.BG_SURFACE,
                    border=ft.Border.all(1, color if is_sel else Colors.BORDER),
                ),
            )

        def _save_confirmed(_):
            title = tf_title.value.strip()
            if not title:
                snack(page, t("title_required"))
                return
            now_str = datetime.now().isoformat()
            new_t = _Task(
                id=str(uuid.uuid4()),
                user_id=user.id,
                title=title,
                description=tf_desc.value.strip(),
                category=cat_sel["v"],
                priority=pri_sel["v"],
                status="todo",
                due_date=tf_due.value.strip() or None,
                due_time=tf_time.value.strip() or None,
                estimated_minutes=data.get("estimated_minutes", 30),
                reminder_minutes=data.get("reminder_minutes", 0),
                created_at=now_str,
                updated_at=now_str,
            )
            TaskService.save_task(new_t)
            confirm_bs[0].open = False
            page.update()
            refresh_list()
            snack(page, t("task_created", title=title))

        def _cancel_confirm(_):
            confirm_bs[0].open = False
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
                        ft.Icon(ft.Icons.CHECK_CIRCLE_OUTLINE, size=18, color=Colors.SUCCESS),
                        ft.Text(t("confirm_ai_task"), size=Typography.H3,
                                color=Colors.TEXT_PRIMARY, weight=Typography.BOLD),
                    ], spacing=Spacing.SM),
                    ft.Text(t("edit_if_needed"),
                            size=Typography.TINY, color=Colors.TEXT_MUTED),
                    ft.Container(height=Spacing.SM),
                    tf_title,
                    ft.Container(height=Spacing.XS),
                    tf_desc,
                    ft.Container(height=Spacing.XS),
                    ft.Row([tf_due, ft.Container(width=8), tf_time]),
                    ft.Container(height=Spacing.SM),
                    ft.Text(t("category_label"), size=Typography.TINY, color=Colors.TEXT_MUTED),
                    ft.Container(height=4),
                    ft.Row([_cat_chip(k, v) for k, v in cat_opts.items()],
                           spacing=4, wrap=True),
                    ft.Container(height=Spacing.SM),
                    ft.Text(t("priority_label"), size=Typography.TINY, color=Colors.TEXT_MUTED),
                    ft.Container(height=4),
                    ft.Row([_pri_chip(k, v) for k, v in pri_opts.items()], spacing=4),
                    ft.Container(height=Spacing.MD),
                    ft.Row([
                        ft.Container(
                            content=ft.Text(t("cancel"), size=Typography.BODY,
                                            color=Colors.TEXT_MUTED),
                            height=44, expand=True, border_radius=Radius.MD,
                            bgcolor=Colors.BG_SURFACE,
                            border=ft.Border.all(1, Colors.BORDER),
                            alignment=ft.Alignment.CENTER,
                            on_click=_cancel_confirm, ink=True,
                        ),
                        ft.Container(width=8),
                        ft.Container(
                            content=ft.Row([
                                ft.Icon(ft.Icons.SAVE_OUTLINED, size=16, color="white"),
                                ft.Text(t("save_task_btn"), size=Typography.BODY,
                                        color="white", weight=Typography.SEMIBOLD),
                            ], alignment=ft.MainAxisAlignment.CENTER, spacing=4),
                            height=44, expand=True, border_radius=Radius.MD,
                            bgcolor=Colors.PRIMARY,
                            alignment=ft.Alignment.CENTER,
                            on_click=_save_confirmed, ink=True,
                        ),
                    ]),
                    ft.Container(height=Spacing.XXL),
                ], spacing=0, tight=True),
                padding=ft.padding.symmetric(horizontal=Spacing.LG),
            ),
        ], spacing=0, tight=True)

        cbs = ft.BottomSheet(
            content=ft.Container(
                content=sheet,
                bgcolor=Colors.BG_CARD,
                border_radius=ft.BorderRadius.only(top_left=Radius.XL, top_right=Radius.XL),
                padding=0,
                clip_behavior=ft.ClipBehavior.ANTI_ALIAS,
            ),
            open=True, draggable=True, use_safe_area=True,
        )
        confirm_bs = [cbs]
        page.overlay.append(cbs)
        page.update()

    # ── AI Schedule → navigate to AI chat with pending prompt ──
    def _open_ai_schedule_sheet(_=None):
        from screens.ai_screen import set_pending_prompt as _spp
        _spp(
            "Sắp xếp lại lịch và tối ưu hóa các công việc hôm nay cho tôi. "
            "Xem xét deadline, giờ vàng tập trung và năng lượng hiện tại "
            "rồi đề xuất timeline cụ thể theo từng giờ."
        )
        on_navigate("ai")

    if False:  # dead code block — kept only for reference, never called
     def _open_ai_schedule_sheet_unused(_=None):
        import threading as _th
        from core.ai_planner_service import get_ai_schedule_today as _get_sched

        schedule_bs = [None]
        result_col = ft.Column(
            [ft.Container(
                content=ft.Row([
                    ft.ProgressRing(width=22, height=22, stroke_width=2.5,
                                    color=Colors.PRIMARY),
                    ft.Text("Doumar đang phân tích task...",
                            size=Typography.SMALL, color=Colors.TEXT_MUTED),
                ], spacing=Spacing.SM, vertical_alignment=ft.CrossAxisAlignment.CENTER),
                padding=ft.padding.all(Spacing.LG),
                alignment=ft.Alignment.CENTER,
            )],
            spacing=0, tight=True,
        )

        cat_colors = {
            "work": Colors.PRIMARY, "health": Colors.SUCCESS,
            "education": "#8B5CF6", "finance": Colors.WARNING,
            "personal": Colors.ACCENT_CYAN,
        }
        pri_dot = {"high": Colors.ERROR, "medium": Colors.WARNING, "low": Colors.SUCCESS}
        energy_label = {"high": "⚡⚡", "medium": "⚡", "low": "💤"}

        def _build_timeline(data: dict):
            slots       = data.get("slots", [])
            unscheduled = data.get("unscheduled", [])
            tips        = data.get("tips", [])
            summary     = data.get("summary", "")
            total_mins  = data.get("total_focus_minutes", 0)
            controls    = []

            h_str = f"{total_mins // 60}g{total_mins % 60:02d}" if total_mins >= 60 else f"{total_mins}p"
            controls.append(ft.Container(
                content=ft.Row([
                    ft.Text(summary, size=Typography.TINY, color=Colors.TEXT_SECONDARY,
                            expand=True, max_lines=3, overflow=ft.TextOverflow.ELLIPSIS),
                    ft.Container(
                        content=ft.Column([
                            ft.Text(h_str, size=Typography.BODY, color=Colors.PRIMARY,
                                    weight=Typography.BOLD, text_align=ft.TextAlign.CENTER),
                            ft.Text("focus", size=7, color=Colors.TEXT_MUTED,
                                    text_align=ft.TextAlign.CENTER),
                        ], spacing=0, tight=True,
                           horizontal_alignment=ft.CrossAxisAlignment.CENTER),
                        padding=ft.padding.symmetric(horizontal=10, vertical=6),
                        border_radius=Radius.MD,
                        bgcolor=Colors.PRIMARY_BG,
                        border=ft.Border.all(1, Colors.PRIMARY_BORDER),
                    ),
                ], spacing=Spacing.SM, vertical_alignment=ft.CrossAxisAlignment.START),
                padding=ft.padding.only(bottom=Spacing.SM),
            ))

            if not slots:
                controls.append(ft.Container(
                    content=ft.Text("🎉 Không có task nào — nghỉ ngơi thôi!",
                                    size=Typography.BODY, color=Colors.SUCCESS,
                                    text_align=ft.TextAlign.CENTER),
                    padding=ft.padding.symmetric(vertical=Spacing.LG),
                    alignment=ft.Alignment.CENTER,
                ))
            else:
                for slot in slots:
                    is_overdue = slot.get("is_overdue", False)
                    cat   = slot.get("category", "personal")
                    pri   = slot.get("priority", "medium")
                    enr   = slot.get("energy_required", "medium")
                    title = slot.get("task_title", "")
                    reason = slot.get("reason", "")
                    accent = cat_colors.get(cat, Colors.PRIMARY)

                    controls.append(ft.Container(
                        content=ft.Row([
                            ft.Column([
                                ft.Text(slot.get("start", ""), size=Typography.TINY,
                                        color=Colors.TEXT_PRIMARY, weight=Typography.BOLD),
                                ft.Text(slot.get("end", ""), size=8, color=Colors.TEXT_MUTED),
                            ], width=42, spacing=1, tight=True,
                               horizontal_alignment=ft.CrossAxisAlignment.END),
                            ft.Container(
                                width=3, border_radius=Radius.FULL,
                                bgcolor=Colors.ERROR if is_overdue else accent,
                                margin=ft.margin.symmetric(horizontal=6),
                                expand_loose=True,
                            ),
                            ft.Column([
                                ft.Row([
                                    ft.Text(title, size=Typography.SMALL,
                                            color=Colors.TEXT_PRIMARY, weight=Typography.SEMIBOLD,
                                            expand=True, max_lines=1,
                                            overflow=ft.TextOverflow.ELLIPSIS),
                                    ft.Container(width=7, height=7, border_radius=4,
                                                 bgcolor=pri_dot.get(pri, Colors.TEXT_MUTED)),
                                ], spacing=4, vertical_alignment=ft.CrossAxisAlignment.CENTER),
                                ft.Text(
                                    f"{energy_label.get(enr, '')}  {reason}",
                                    size=7, color=Colors.TEXT_MUTED, max_lines=1,
                                    overflow=ft.TextOverflow.ELLIPSIS,
                                ),
                            ], spacing=2, tight=True, expand=True),
                        ], spacing=0, vertical_alignment=ft.CrossAxisAlignment.CENTER),
                        padding=ft.padding.symmetric(vertical=10, horizontal=10),
                        border_radius=Radius.MD,
                        bgcolor=f"#18{Colors.ERROR[1:]}" if is_overdue else Colors.BG_CARD,
                        border=ft.Border.all(
                            1, f"#40{Colors.ERROR[1:]}" if is_overdue else Colors.BORDER),
                        margin=ft.margin.only(bottom=6),
                        on_click=lambda _: None, ink=True,
                    ))

            if unscheduled:
                controls.append(ft.Container(height=Spacing.XS))
                controls.append(ft.Container(
                    content=ft.Column([
                        ft.Text(f"Chưa sắp xếp được: {', '.join(unscheduled[:3])}",
                                size=Typography.TINY, color=Colors.TEXT_MUTED,
                                max_lines=2, overflow=ft.TextOverflow.ELLIPSIS),
                    ], spacing=2, tight=True),
                    padding=ft.padding.symmetric(horizontal=10, vertical=6),
                    border_radius=Radius.SM, bgcolor=Colors.BG_SURFACE,
                    border=ft.Border.all(1, Colors.BORDER),
                ))

            for tip in tips[:2]:
                controls.append(ft.Container(
                    content=ft.Row([
                        ft.Text("💡", size=10),
                        ft.Text(tip, size=Typography.TINY, color=Colors.TEXT_SECONDARY,
                                expand=True, max_lines=2, overflow=ft.TextOverflow.ELLIPSIS),
                    ], spacing=6, vertical_alignment=ft.CrossAxisAlignment.START),
                    padding=ft.padding.symmetric(horizontal=10, vertical=5),
                    border_radius=Radius.SM,
                    bgcolor=f"#10{Colors.WARNING[1:]}",
                    border=ft.Border.all(1, f"#28{Colors.WARNING[1:]}"),
                    margin=ft.margin.only(top=4, bottom=2),
                ))

            return controls

        def _worker():
            try:
                data = _get_sched(user.id, mode="optimize")
            except Exception as _ex:
                data = {"type": "error", "message": str(_ex)[:120]}
            new_controls = (
                [ft.Container(
                    content=ft.Text(f"❌ {data.get('message','Lỗi')}",
                                    size=Typography.SMALL, color=Colors.ERROR),
                    padding=ft.padding.all(Spacing.LG),
                )]
                if data.get("type") == "error"
                else _build_timeline(data)
            )
            result_col.controls = new_controls
            try: page.update()
            except Exception: pass

        _th.Thread(target=_worker, daemon=True).start()

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
                        ft.Container(
                            content=ft.Text("✨", size=18),
                            width=36, height=36, border_radius=Radius.SM,
                            gradient=ft.LinearGradient(
                                colors=["#A855F7", "#3B82F6"],
                                begin=ft.Alignment.TOP_LEFT,
                                end=ft.Alignment.BOTTOM_RIGHT,
                            ),
                            alignment=ft.Alignment.CENTER,
                        ),
                        ft.Column([
                            ft.Text("🗓️ AI Sắp xếp hôm nay", size=Typography.H3,
                                    color=Colors.TEXT_PRIMARY, weight=Typography.BOLD),
                            ft.Text("Doumar · AI Schedule",
                                    size=Typography.TINY, color=Colors.TEXT_MUTED),
                        ], spacing=1, tight=True, expand=True),
                        ft.Container(
                            content=ft.Icon(ft.Icons.CLOSE_ROUNDED, size=16,
                                            color=Colors.TEXT_MUTED),
                            width=30, height=30, border_radius=Radius.SM,
                            bgcolor=Colors.BG_SURFACE, alignment=ft.Alignment.CENTER,
                            on_click=lambda _: [
                                setattr(schedule_bs[0], "open", False), page.update()
                            ],
                            ink=True,
                        ),
                    ], spacing=Spacing.SM, vertical_alignment=ft.CrossAxisAlignment.CENTER),
                    ft.Container(height=Spacing.SM),
                    ft.Container(content=result_col, height=430,
                                 clip_behavior=ft.ClipBehavior.HARD_EDGE),
                    ft.Container(height=Spacing.XL),
                ], spacing=0, tight=True),
                padding=ft.padding.symmetric(horizontal=Spacing.LG),
            ),
        ], spacing=0, tight=True, scroll=ft.ScrollMode.AUTO)

        tbs = ft.BottomSheet(
            content=ft.Container(
                content=sheet, bgcolor=Colors.BG_CARD,
                border_radius=ft.BorderRadius.only(
                    top_left=Radius.XL, top_right=Radius.XL),
                padding=0, clip_behavior=ft.ClipBehavior.ANTI_ALIAS,
            ),
            open=True, draggable=True, use_safe_area=True,
        )
        schedule_bs[0] = tbs
        page.overlay.append(tbs)
        page.update()

    # ── Header ────────────────────────────────────────────────
    header = ft.Container(
        content=ft.Row([
            ft.Column([
                ft.Text(t("tasks_title"), size=Typography.H2, color=Colors.TEXT_PRIMARY,
                        weight=Typography.BOLD),
                ft.Text(t("tasks_count", n=len(TaskService.get_tasks(user.id))),
                        size=Typography.SMALL, color=Colors.TEXT_MUTED),
            ], spacing=2, tight=True),
            ft.Row([], expand=True),
            # AI Schedule button
            ft.Container(
                content=ft.Icon(ft.Icons.CALENDAR_MONTH_ROUNDED, color="white", size=16),
                width=38, height=38,
                border_radius=Radius.MD,
                gradient=ft.LinearGradient(
                    colors=["#059669", "#0D9488"],
                    begin=ft.Alignment.TOP_LEFT,
                    end=ft.Alignment.BOTTOM_RIGHT,
                ),
                alignment=ft.Alignment.CENTER,
                on_click=_open_ai_schedule_sheet,
                ink=True,
                tooltip="AI Sắp xếp hôm nay",
                margin=ft.margin.only(right=6),
            ),
            # AI Quick-add button
            ft.Container(
                content=ft.Icon(ft.Icons.AUTO_AWESOME_ROUNDED, color="white", size=16),
                width=38, height=38,
                border_radius=Radius.MD,
                gradient=ft.LinearGradient(
                    colors=["#A855F7", "#3B82F6"],
                    begin=ft.Alignment.TOP_LEFT,
                    end=ft.Alignment.BOTTOM_RIGHT,
                ),
                alignment=ft.Alignment.CENTER,
                on_click=_open_ai_quick_add,
                ink=True,
                tooltip=t("ai_create_tooltip"),
                margin=ft.margin.only(right=8),
            ),
            primary_button(t("add_btn"), on_click=lambda _: on_navigate("task_edit"),
                           height=38, width=90),
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
