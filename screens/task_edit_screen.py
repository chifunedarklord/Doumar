"""
TaskFlow - Task Edit View
"""
import flet as ft
from datetime import datetime
import uuid
import threading
from core.theme import Colors, Typography, Spacing, Radius
from core.models import Task
from core.services import TaskService, ProjectService
from core.i18n import t
from components.widgets import snack

def build_task_edit_screen(page: ft.Page, user, on_navigate, task=None):
    from core.theme import CATEGORY_MAP, PRIORITY_MAP, STATUS_MAP

    is_edit = task is not None
    _task = task or Task(
        id=str(uuid.uuid4()), user_id=user.id,
        title="", category="personal", priority="medium", status="todo",
    )

    # ── Field style helper ───────────────────────────────
    def _tf(label, value="", multiline=False, hint="", min_l=1, max_l=4, expand=None):
        return ft.TextField(
            label=label, value=value, hint_text=hint,
            multiline=multiline,
            min_lines=min_l if multiline else None,
            max_lines=max_l if multiline else None,
            bgcolor=Colors.BG_CARD,
            border_color=Colors.BORDER,
            focused_border_color=Colors.PRIMARY,
            text_style=ft.TextStyle(color=Colors.TEXT_PRIMARY, size=Typography.BODY),
            label_style=ft.TextStyle(color=Colors.TEXT_MUTED, size=Typography.SMALL),
            hint_style=ft.TextStyle(color=Colors.TEXT_MUTED),
            border_radius=Radius.MD,
            cursor_color=Colors.TEXT_PRIMARY,
            content_padding=ft.padding.symmetric(horizontal=14, vertical=12),
            expand=expand,
        )

    def _section_label(text):
        return ft.Container(
            content=ft.Text(text, size=10, color=Colors.TEXT_MUTED,
                            weight=Typography.SEMIBOLD),
            padding=ft.padding.only(left=0, bottom=8, top=2),
        )

    def _div():
        return ft.Container(
            height=1, bgcolor=Colors.BORDER,
            margin=ft.margin.symmetric(vertical=Spacing.MD),
        )

    # ── State ────────────────────────────────────────────
    _user_projects = ProjectService.get_projects(user.id)
    proj_sel = {"v": getattr(_task, "project_id", None)}

    cat_sel = {"v": _task.category}
    pri_sel = {"v": _task.priority}
    sta_sel = {"v": _task.status}
    rec_sel = {"v": _task.recur_pattern if _task.recur_pattern else "none"}
    cpl_sel = {"v": getattr(_task, "complexity", "medium")}
    dl_type_sel = {"v": getattr(_task, "deadline_type", "soft")}

    tf_est = _tf(t("est_minutes_lbl"), str(getattr(_task, "estimated_minutes", 30)), hint="30", expand=1)
    tf_est.keyboard_type = ft.KeyboardType.NUMBER

    # ── Fields ───────────────────────────────────────────
    tf_title = ft.TextField(
        label=t("task_title_field"),
        value=_task.title,
        hint_text=t("task_title_hint"),
        bgcolor=Colors.BG_CARD,
        border_color=Colors.BORDER,
        focused_border_color=Colors.PRIMARY,
        text_style=ft.TextStyle(color=Colors.TEXT_PRIMARY,
                                size=Typography.H4, weight=Typography.SEMIBOLD),
        label_style=ft.TextStyle(color=Colors.TEXT_MUTED, size=Typography.SMALL),
        hint_style=ft.TextStyle(color=Colors.TEXT_MUTED),
        border_radius=Radius.MD,
        cursor_color=Colors.TEXT_PRIMARY,
        content_padding=ft.padding.symmetric(horizontal=14, vertical=14),
    )

    tf_desc = _tf(t("desc_label"), _task.description, multiline=True,
                  hint=t("task_desc_hint"), min_l=2, max_l=3)

    # ── Date/Time pickers ────────────────────────────────
    start_val = {"v": _task.start_date or ""}
    due_val   = {"v": _task.due_date or ""}
    time_val  = {"v": _task.due_time or ""}

    start_label = ft.Text(
        _task.start_date or t("not_selected"),
        size=Typography.SMALL, color=Colors.TEXT_PRIMARY if _task.start_date else Colors.TEXT_MUTED,
    )
    due_label = ft.Text(
        _task.due_date or t("not_selected"),
        size=Typography.SMALL, color=Colors.TEXT_PRIMARY if _task.due_date else Colors.TEXT_MUTED,
    )
    time_label = ft.Text(
        _task.due_time or t("not_selected"),
        size=Typography.SMALL, color=Colors.TEXT_PRIMARY if _task.due_time else Colors.TEXT_MUTED,
    )

    def on_start_change(e):
        if e.control.value:
            d = e.control.value
            ds = f"{d.year:04d}-{d.month:02d}-{d.day:02d}"
            start_val["v"] = ds
            start_label.value = ds
            start_label.color = Colors.TEXT_PRIMARY
            page.update()

    def on_due_change(e):
        if e.control.value:
            d = e.control.value
            ds = f"{d.year:04d}-{d.month:02d}-{d.day:02d}"
            due_val["v"] = ds
            due_label.value = ds
            due_label.color = Colors.TEXT_PRIMARY
            page.update()

    def on_time_change(e):
        if e.control.value:
            t_obj = e.control.value
            ts = f"{t_obj.hour:02d}:{t_obj.minute:02d}"
            time_val["v"] = ts
            time_label.value = ts
            time_label.color = Colors.TEXT_PRIMARY
            page.update()

    start_picker = ft.DatePicker(
        first_date=datetime(2020, 1, 1),
        last_date=datetime(2030, 12, 31),
        on_change=on_start_change,
    )
    if _task.start_date:
        try:
            parts = _task.start_date.split("-")
            start_picker.value = datetime(int(parts[0]), int(parts[1]), int(parts[2]))
        except Exception: pass

    due_picker = ft.DatePicker(
        first_date=datetime(2020, 1, 1),
        last_date=datetime(2030, 12, 31),
        on_change=on_due_change,
    )
    if _task.due_date:
        try:
            parts = _task.due_date.split("-")
            due_picker.value = datetime(int(parts[0]), int(parts[1]), int(parts[2]))
        except Exception: pass

    time_picker = ft.TimePicker(
        help_text="Chọn giờ hoàn thành",
        on_change=on_time_change,
    )
    if _task.due_time:
        try:
            parts = _task.due_time.split(":")
            from datetime import time as dt_time
            time_picker.value = dt_time(int(parts[0]), int(parts[1]))
        except Exception:
            pass

    page.overlay.extend([start_picker, due_picker, time_picker])

    def _date_btn(icon, label, text_widget, picker):
        return ft.Container(
            content=ft.Row([
                ft.Icon(icon, size=16, color=Colors.TEXT_PRIMARY),
                ft.Container(width=6),
                ft.Column([
                    ft.Text(label, size=Typography.TINY, color=Colors.TEXT_MUTED),
                    text_widget,
                ], spacing=1, tight=True, expand=True),
            ], vertical_alignment=ft.CrossAxisAlignment.CENTER),
            padding=ft.padding.symmetric(horizontal=12, vertical=10),
            border_radius=Radius.MD,
            bgcolor=Colors.BG_CARD,
            border=ft.Border.all(1, Colors.BORDER),
            on_click=lambda _: setattr(picker, 'open', True) or page.update(),
            expand=True,
            ink=True,
            shadow=ft.BoxShadow(
                blur_radius=6,
                color="#00000012",
                offset=ft.Offset(0, 2),
            ),
        )

    btn_start = _date_btn(ft.Icons.PLAY_CIRCLE_OUTLINE, t("start_date_lbl"), start_label, start_picker)
    btn_due   = _date_btn(ft.Icons.EVENT_OUTLINED, t("due_date_lbl"), due_label, due_picker)
    btn_time  = _date_btn(ft.Icons.ACCESS_TIME_OUTLINED, t("time_lbl"), time_label, time_picker)

    notes_val = _task.notes if hasattr(_task, "notes") else ""
    tf_notes = _tf(t("desc_label"), notes_val, multiline=True, hint=t("task_notes_hint"), min_l=2, max_l=4)

    # ── Chip builder ─────────────────────────────────────
    def make_chips(options, sel_ref):
        chips = []
        keys_list = list(options.keys())

        def make_click(k, idx):
            def _click(_):
                sel_ref["v"] = k
                for i, c in enumerate(chips):
                    sel = (i == idx)
                    info_i = options[keys_list[i]]
                    c.bgcolor = Colors.PRIMARY if sel else "transparent"
                    c.border = ft.Border.all(1.5 if sel else 1, Colors.PRIMARY if sel else Colors.BORDER)
                    c.content.controls[0].color = info_i.get("color", Colors.TEXT_MUTED) if sel else Colors.TEXT_MUTED
                    c.content.controls[1].color = Colors.TEXT_ON_PRIMARY if sel else Colors.TEXT_MUTED
                page.update()
            return _click

        for idx, (key, info) in enumerate(options.items()):
            sel = (key == sel_ref["v"])
            chip = ft.Container(
                content=ft.Row([
                    ft.Text(info["icon"], size=12, color=info.get("color", Colors.TEXT_MUTED) if sel else Colors.TEXT_MUTED),
                    ft.Text(info["label"], size=Typography.TINY, color=Colors.TEXT_ON_PRIMARY if sel else Colors.TEXT_MUTED, weight=Typography.MEDIUM if sel else Typography.REGULAR),
                ], spacing=5, tight=True),
                padding=ft.padding.symmetric(horizontal=10, vertical=6),
                border_radius=Radius.FULL,
                bgcolor=Colors.PRIMARY if sel else "transparent",
                border=ft.Border.all(1.5 if sel else 1, Colors.PRIMARY if sel else Colors.BORDER),
                on_click=make_click(key, idx),
                animate=ft.Animation(120, ft.AnimationCurve.EASE_OUT),
            )
            chips.append(chip)
        return ft.Row(chips, scroll=ft.ScrollMode.AUTO, spacing=6)

    cat_chips = make_chips(CATEGORY_MAP, cat_sel)
    pri_chips = make_chips(PRIORITY_MAP, pri_sel)
    sta_chips = make_chips(STATUS_MAP, sta_sel)

    def make_option_chips(options_list, sel_ref):
        chips = []
        def make_click(val, idx):
            def _click(_):
                sel_ref["v"] = val
                for i, c in enumerate(chips):
                    sel = (i == idx)
                    c.bgcolor = Colors.PRIMARY if sel else "transparent"
                    c.border = ft.Border.all(1.5 if sel else 1, Colors.PRIMARY if sel else Colors.BORDER)
                    c.content.color = Colors.TEXT_ON_PRIMARY if sel else Colors.TEXT_MUTED
                page.update()
            return _click

        for idx, (val, label) in enumerate(options_list):
            sel = (val == sel_ref["v"])
            chip = ft.Container(
                content=ft.Text(label, size=Typography.TINY, color=Colors.TEXT_ON_PRIMARY if sel else Colors.TEXT_MUTED),
                padding=ft.padding.symmetric(horizontal=10, vertical=6),
                border_radius=Radius.FULL,
                bgcolor=Colors.PRIMARY if sel else "transparent",
                border=ft.Border.all(1.5 if sel else 1, Colors.PRIMARY if sel else Colors.BORDER),
                on_click=make_click(val, idx),
                animate=ft.Animation(120, ft.AnimationCurve.EASE_OUT),
            )
            chips.append(chip)
        return ft.Row(chips, scroll=ft.ScrollMode.AUTO, spacing=6)

    rem_dropdown = ft.Dropdown(
        label=t("reminder_lbl"),
        value=str(_task.reminder_minutes) if getattr(_task, "reminder_minutes", 0) > 0 else "0",
        options=[
            ft.dropdown.Option("0", t("no_reminder")),
            ft.dropdown.Option("5", f"5 {t('minutes_short')}"),
            ft.dropdown.Option("15", f"15 {t('minutes_short')}"),
            ft.dropdown.Option("30", f"30 {t('minutes_short')}"),
            ft.dropdown.Option("60", "1h"),
            ft.dropdown.Option("1440", "1d"),
        ],
        bgcolor=Colors.BG_CARD,
        border_color=Colors.BORDER,
        color=Colors.TEXT_PRIMARY,
        text_size=Typography.BODY,
        border_radius=Radius.MD,
        content_padding=ft.padding.symmetric(horizontal=12, vertical=8)
    )

    rec_chips = make_option_chips([
        ("none",    t("repeat_none")),
        ("daily",   t("repeat_daily")),
        ("weekly",  t("repeat_weekly")),
        ("monthly", t("repeat_monthly")),
    ], rec_sel)

    cpl_chips = make_option_chips([
        ("easy",   t("complexity_easy")),
        ("medium", t("complexity_medium")),
        ("hard",   t("complexity_hard")),
    ], cpl_sel)

    dl_type_chips = make_option_chips(
        [("soft", t("deadline_soft")), ("hard", t("deadline_hard")), ("estimated", t("deadline_estimated"))],
        dl_type_sel,
    )

    _proj_options = [ft.dropdown.Option(key="", text=t("no_project"))]
    _proj_options += [ft.dropdown.Option(key=p.id, text=p.name) for p in _user_projects]

    proj_dropdown = ft.Dropdown(
        label=t("project_lbl"),
        value=proj_sel["v"] or "",
        options=_proj_options,
        bgcolor=Colors.BG_CARD,
        border_color=Colors.BORDER,
        focused_border_color=Colors.PRIMARY,
        text_style=ft.TextStyle(color=Colors.TEXT_PRIMARY, size=Typography.SMALL),
        label_style=ft.TextStyle(color=Colors.TEXT_MUTED, size=Typography.SMALL),
        border_radius=Radius.MD,
        on_select=lambda e: proj_sel.update({"v": e.control.value or None}),
        visible=len(_user_projects) > 0,
    )

    # ── File Picker for OCR ──────────────────────────────
    def _apply_ocr_data(data: dict):
        """Apply AI-parsed OCR fields to the form (fill title, desc, etc.)."""
        if data.get("title") and not tf_title.value.strip():
            tf_title.value = data["title"]
        if data.get("description"):
            tf_desc.value = data["description"]
        if data.get("due_date"):
            due_val["v"] = data["due_date"]
            due_label.value = data["due_date"]
            due_label.color = Colors.TEXT_PRIMARY
        if data.get("due_time"):
            time_val["v"] = data["due_time"]
            time_label.value = data["due_time"]
            time_label.color = Colors.TEXT_PRIMARY
        if data.get("category") in ("work", "personal", "health", "finance", "education"):
            cat_sel["v"] = data["category"]
        if data.get("priority") in ("high", "medium", "low"):
            pri_sel["v"] = data["priority"]
        page.update()
        snack(page, t("ocr_fill") + " ✓")

    def _show_ocr_confirm(ocr_text: str, data: dict):
        """Show OCR result + AI-parsed fields for user to confirm."""
        tf_raw = ft.TextField(
            value=ocr_text[:500],
            label=t("ocr_recognized"),
            multiline=True, min_lines=3, max_lines=5,
            bgcolor=Colors.BG_SURFACE, border_color=Colors.BORDER,
            focused_border_color=Colors.PRIMARY,
            text_style=ft.TextStyle(color=Colors.TEXT_PRIMARY, size=Typography.TINY),
            label_style=ft.TextStyle(color=Colors.TEXT_MUTED, size=Typography.TINY),
            border_radius=Radius.MD, cursor_color=Colors.PRIMARY,
            content_padding=ft.padding.symmetric(horizontal=12, vertical=8),
            read_only=True,
        )
        info_rows = []
        if data.get("title"):
            info_rows.append(ft.Row([
                ft.Text("Tiêu đề:", size=Typography.TINY, color=Colors.TEXT_MUTED, width=70),
                ft.Text(data["title"][:50], size=Typography.TINY, color=Colors.TEXT_PRIMARY,
                        expand=True),
            ]))
        if data.get("due_date"):
            info_rows.append(ft.Row([
                ft.Text("Hạn:", size=Typography.TINY, color=Colors.TEXT_MUTED, width=70),
                ft.Text(f'{data["due_date"]} {data.get("due_time","") or ""}',
                        size=Typography.TINY, color=Colors.TEXT_PRIMARY),
            ]))
        parsed_preview = ft.Column(info_rows, spacing=4, tight=True) if info_rows else ft.Container()

        def _confirm(_):
            bs[0].open = False
            page.update()
            _apply_ocr_data(data)

        def _cancel(_):
            bs[0].open = False
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
                        ft.Icon(ft.Icons.DOCUMENT_SCANNER_OUTLINED, size=18,
                                color=Colors.PRIMARY),
                        ft.Text(t("ocr_title"), size=Typography.H3,
                                color=Colors.TEXT_PRIMARY, weight=Typography.BOLD),
                    ], spacing=Spacing.SM),
                    ft.Text(t("ocr_subtitle"),
                            size=Typography.TINY, color=Colors.TEXT_MUTED),
                    ft.Container(height=Spacing.SM),
                    tf_raw,
                    ft.Container(height=Spacing.SM),
                    parsed_preview,
                    ft.Container(height=Spacing.MD),
                    ft.Row([
                        ft.Container(
                            content=ft.Text(t("ocr_skip"), size=Typography.BODY,
                                            color=Colors.TEXT_MUTED),
                            height=44, expand=True, border_radius=Radius.MD,
                            bgcolor=Colors.BG_SURFACE,
                            border=ft.Border.all(1, Colors.BORDER),
                            alignment=ft.Alignment.CENTER,
                            on_click=_cancel, ink=True,
                        ),
                        ft.Container(width=8),
                        ft.Container(
                            content=ft.Row([
                                ft.Icon(ft.Icons.CHECK_ROUNDED, size=16, color="white"),
                                ft.Text(t("ocr_fill"), size=Typography.BODY,
                                        color="white", weight=Typography.SEMIBOLD),
                            ], alignment=ft.MainAxisAlignment.CENTER, spacing=4),
                            height=44, expand=True, border_radius=Radius.MD,
                            bgcolor=Colors.PRIMARY,
                            alignment=ft.Alignment.CENTER,
                            on_click=_confirm, ink=True,
                        ),
                    ]),
                    ft.Container(height=Spacing.XL),
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
        bs = [cbs]
        page.overlay.append(cbs)
        page.update()

    def process_ocr_click(_e):
        def _run():
            import logging
            try:
                import tkinter as tk
                from tkinter import filedialog
                root = tk.Tk()
                root.attributes('-topmost', True)
                root.withdraw()
                file_path = filedialog.askopenfilename(
                    title="Chọn ảnh",
                    filetypes=[("Image files", "*.jpg;*.jpeg;*.png;*.bmp")]
                )
                root.destroy()
            except Exception:
                file_path = None

            if not file_path:
                return

            try:
                page.run_task(lambda: snack(page, "Đang xử lý ảnh (OCR + AI)…"))
            except Exception:
                pass

            try:
                import pytesseract
                from PIL import Image
                ocr_text = pytesseract.image_to_string(Image.open(file_path), lang="eng+vie")
            except Exception as ex:
                logging.exception("OCR failed")
                try:
                    page.run_task(lambda: snack(page,
                        "Lỗi OCR. Kiểm tra Tesseract-OCR đã được cài đặt chưa?"))
                except Exception:
                    pass
                return

            if not ocr_text.strip():
                try:
                    page.run_task(lambda: snack(page, "Không tìm thấy chữ trong ảnh"))
                except Exception:
                    pass
                return

            # Pipe OCR text through AI
            try:
                from utils.ai_helper import parse_ocr_to_task
                data = parse_ocr_to_task(ocr_text)
            except Exception:
                logging.exception("parse_ocr_to_task failed")
                data = {"title": "", "description": ocr_text[:300]}

            try:
                page.run_task(lambda: _show_ocr_confirm(ocr_text, data))
            except Exception:
                pass

        threading.Thread(target=_run, daemon=True).start()

    # ── Save ─────────────────────────────────────────────
    err_ref = ft.Ref[ft.Text]()

    def save_task(_):
        title = tf_title.value.strip()
        if not title:
            err_ref.current.value = t("task_not_saved")
            page.update()
            return
            
        # Check if task is postponed (due date changed to later date)
        old_due_date = _task.due_date
        new_due_date = due_val["v"] or None
        if is_edit and old_due_date and new_due_date:
            try:
                old_d = datetime.strptime(old_due_date, "%Y-%m-%d")
                new_d = datetime.strptime(new_due_date, "%Y-%m-%d")
                if new_d > old_d:
                    _task.postpone_count = getattr(_task, "postpone_count", 0) + 1
                    TaskService.mark_delayed(_task, reason="User changed due date")
            except Exception:
                pass
                
        _task.title            = title
        _task.description      = tf_desc.value.strip()
        _task.start_date       = start_val["v"] or None
        _task.due_date         = new_due_date
        _task.due_time         = time_val["v"] or None
        _task.category         = cat_sel["v"]
        _task.priority         = pri_sel["v"]
        _task.status           = sta_sel["v"]
        _task.is_recurring     = rec_sel["v"] != "none"
        _task.recur_pattern    = "" if rec_sel["v"] == "none" else rec_sel["v"]
        _task.reminder_minutes = int(rem_dropdown.value) if rem_dropdown.value else 0
        _task.complexity       = cpl_sel["v"]
        _task.deadline_type    = dl_type_sel["v"]
        _task.project_id       = proj_sel["v"] or None
        _task.estimated_minutes= int(tf_est.value) if tf_est.value and tf_est.value.isdigit() else 30
        _task.notes            = tf_notes.value.strip()
        if _task.status == "done" and not _task.completed_at:
            _task.completed_at = datetime.now().isoformat()
        TaskService.save_task(_task)
        snack(page, t("save_success_task"))
        on_navigate("tasks")
        

    def cancel_task(_):
        on_navigate("tasks")

    # HEADER
    header = ft.Container(
        content=ft.Row([
            ft.IconButton(ft.Icons.ARROW_BACK_IOS_NEW_ROUNDED, on_click=cancel_task),
            ft.Text(t("edit_task_title") if is_edit else t("new_task_title"), size=Typography.H2, color=Colors.TEXT_PRIMARY, weight=Typography.BOLD),
        ]),
        padding=ft.Padding.symmetric(horizontal=Spacing.MD, vertical=Spacing.MD),
    )

    # Scrollable form body
    form_body = ft.Container(
        content=ft.Column([
            ft.Row([
                _section_label(t("section_content")),
                ft.Container(expand=True),
                ft.IconButton(ft.Icons.DOCUMENT_SCANNER_OUTLINED, icon_color=Colors.PRIMARY, icon_size=18, tooltip=t("scan_img_tooltip"), on_click=process_ocr_click)
            ]),
            tf_title, ft.Container(height=Spacing.SM), tf_desc, _div(),

            _section_label(t("section_time")),
            ft.Row([btn_start, ft.Container(width=Spacing.SM), btn_due]), ft.Container(height=Spacing.SM), ft.Row([btn_time]), _div(),

            _section_label(t("section_classify")),
            ft.Container(content=proj_dropdown, padding=ft.padding.symmetric(vertical=4)) if len(_user_projects) > 0 else ft.Container(),
            ft.Container(content=ft.Column([ft.Row([ft.Icon(ft.Icons.FOLDER_OUTLINED, size=13, color=Colors.TEXT_MUTED), ft.Container(width=4), ft.Text(t("category_label"), size=Typography.TINY, color=Colors.TEXT_MUTED)]), ft.Container(height=6), cat_chips], spacing=0, tight=True), padding=ft.padding.symmetric(vertical=4)),
            ft.Container(content=ft.Column([ft.Row([ft.Icon(ft.Icons.FLAG_OUTLINED, size=13, color=Colors.TEXT_MUTED), ft.Container(width=4), ft.Text(t("priority_label"), size=Typography.TINY, color=Colors.TEXT_MUTED)]), ft.Container(height=6), pri_chips], spacing=0, tight=True), padding=ft.padding.symmetric(vertical=4)),
            ft.Container(content=ft.Column([ft.Row([ft.Icon(ft.Icons.TERRAIN_ROUNDED, size=13, color=Colors.TEXT_MUTED), ft.Container(width=4), ft.Text(t("complexity_lbl"), size=Typography.TINY, color=Colors.TEXT_MUTED)]), ft.Container(height=6), cpl_chips], spacing=0, tight=True), padding=ft.padding.symmetric(vertical=4)),
            ft.Container(content=ft.Column([ft.Row([ft.Icon(ft.Icons.LOCK_CLOCK_OUTLINED, size=13, color=Colors.TEXT_MUTED), ft.Container(width=4), ft.Text(t("deadline_type_lbl"), size=Typography.TINY, color=Colors.TEXT_MUTED)]), ft.Container(height=6), dl_type_chips], spacing=0, tight=True), padding=ft.padding.symmetric(vertical=4)),
            ft.Container(content=tf_est, padding=ft.padding.symmetric(vertical=6)),
            _div(),

            _section_label(t("section_settings")),
            ft.Container(content=rem_dropdown, padding=ft.padding.symmetric(vertical=4)),
            ft.Container(height=Spacing.SM),
            ft.Container(content=ft.Column([ft.Row([ft.Icon(ft.Icons.REPEAT_ROUNDED, size=13, color=Colors.TEXT_MUTED), ft.Container(width=4), ft.Text(t("repeat_lbl"), size=Typography.TINY, color=Colors.TEXT_MUTED)]), ft.Container(height=6), rec_chips], spacing=0, tight=True), padding=ft.padding.symmetric(vertical=4)),
            _div(),

            _section_label(t("section_notes")),
            tf_notes, ft.Container(height=Spacing.MD),

            ft.Text("", ref=err_ref, color=Colors.ERROR, size=Typography.SMALL, text_align=ft.TextAlign.CENTER),
            ft.Container(height=Spacing.SM),

            ft.Row([
                ft.Container(content=ft.Text(t("cancel"), size=Typography.BODY, color=Colors.TEXT_MUTED, weight=Typography.MEDIUM), height=48, expand=1, border_radius=Radius.MD, bgcolor=Colors.BG_SURFACE, border=ft.Border.all(1, Colors.BORDER), alignment=ft.Alignment.CENTER, on_click=cancel_task, ink=True),
                ft.Container(width=Spacing.SM),
                ft.Container(content=ft.Row([ft.Icon(ft.Icons.CHECK_ROUNDED, size=16, color=Colors.TEXT_ON_PRIMARY), ft.Container(width=4), ft.Text(t("save"), size=Typography.BODY, color=Colors.TEXT_ON_PRIMARY, weight=Typography.SEMIBOLD)], alignment=ft.MainAxisAlignment.CENTER, spacing=0), height=48, expand=2, border_radius=Radius.MD, bgcolor=Colors.PRIMARY, alignment=ft.Alignment.CENTER, on_click=save_task, ink=True),
            ]),
            ft.Container(height=Spacing.XXXL),
            ft.Container(height=Spacing.XXXL),
        ], spacing=0, tight=True),
        padding=ft.padding.symmetric(horizontal=Spacing.MD, vertical=Spacing.SM),
        expand=True,
    )

    return ft.Column([
        header,
        ft.Column([form_body], scroll=ft.ScrollMode.AUTO, expand=True)
    ], expand=True, spacing=0)
