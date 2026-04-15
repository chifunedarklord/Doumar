"""
TaskFlow - Task Edit View
"""
import flet as ft
from datetime import datetime
import uuid
from core.theme import Colors, Typography, Spacing, Radius
from core.models import Storage, Task
from components.widgets import snack

def build_task_edit_screen(page: ft.Page, user, on_navigate, task=None):
    from screens.tasks_screen import CATEGORY_MAP, PRIORITY_MAP, STATUS_MAP

    is_edit = task is not None
    t = task or Task(
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
            bgcolor="#1A1A1A",
            border_color=Colors.BORDER,
            focused_border_color="#888888",
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
    cat_sel = {"v": t.category}
    pri_sel = {"v": t.priority}
    sta_sel = {"v": t.status}
    rec_sel = {"v": t.recur_pattern if t.recur_pattern else "none"}

    # ── Fields ───────────────────────────────────────────
    tf_title = ft.TextField(
        label="Tiêu đề *",
        value=t.title,
        hint_text="Nhập tiêu đề công việc...",
        bgcolor="#1A1A1A",
        border_color=Colors.BORDER,
        focused_border_color="#BBBBBB",
        text_style=ft.TextStyle(color=Colors.TEXT_PRIMARY,
                                size=Typography.H4, weight=Typography.SEMIBOLD),
        label_style=ft.TextStyle(color=Colors.TEXT_MUTED, size=Typography.SMALL),
        hint_style=ft.TextStyle(color=Colors.TEXT_MUTED),
        border_radius=Radius.MD,
        cursor_color=Colors.TEXT_PRIMARY,
        content_padding=ft.padding.symmetric(horizontal=14, vertical=14),
    )

    tf_desc = _tf("Mô tả", t.description, multiline=True,
                  hint="Thêm mô tả chi tiết...", min_l=2, max_l=3)

    # ── Date/Time pickers ────────────────────────────────
    start_val = {"v": t.start_date or ""}
    due_val   = {"v": t.due_date or ""}
    time_val  = {"v": t.due_time or ""}

    start_label = ft.Text(
        t.start_date or "Chưa chọn",
        size=Typography.SMALL, color=Colors.TEXT_PRIMARY if t.start_date else Colors.TEXT_MUTED,
    )
    due_label = ft.Text(
        t.due_date or "Chưa chọn",
        size=Typography.SMALL, color=Colors.TEXT_PRIMARY if t.due_date else Colors.TEXT_MUTED,
    )
    time_label = ft.Text(
        t.due_time or "Chưa chọn",
        size=Typography.SMALL, color=Colors.TEXT_PRIMARY if t.due_time else Colors.TEXT_MUTED,
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
    if t.start_date:
        try:
            parts = t.start_date.split("-")
            start_picker.value = datetime(int(parts[0]), int(parts[1]), int(parts[2]))
        except Exception: pass

    due_picker = ft.DatePicker(
        first_date=datetime(2020, 1, 1),
        last_date=datetime(2030, 12, 31),
        on_change=on_due_change,
    )
    if t.due_date:
        try:
            parts = t.due_date.split("-")
            due_picker.value = datetime(int(parts[0]), int(parts[1]), int(parts[2]))
        except Exception: pass

    time_picker = ft.TimePicker(
        help_text="Chọn giờ hoàn thành",
        on_change=on_time_change,
    )
    if t.due_time:
        try:
            parts = t.due_time.split(":")
            from datetime import time as dt_time
            time_picker.value = dt_time(int(parts[0]), int(parts[1]))
        except Exception:
            pass

    page.overlay.extend([start_picker, due_picker, time_picker])

    def _date_btn(icon, label, text_widget, picker):
        return ft.Container(
            content=ft.Row([
                ft.Icon(icon, size=16, color=Colors.TEXT_MUTED),
                ft.Container(width=6),
                ft.Column([
                    ft.Text(label, size=Typography.TINY, color=Colors.TEXT_MUTED),
                    text_widget,
                ], spacing=1, tight=True, expand=True),
            ], vertical_alignment=ft.CrossAxisAlignment.CENTER),
            padding=ft.padding.symmetric(horizontal=12, vertical=10),
            border_radius=Radius.MD,
            bgcolor="#1A1A1A",
            border=ft.border.all(1, Colors.BORDER),
            on_click=lambda _: setattr(picker, 'open', True) or page.update(),
            expand=True,
            ink=True,
        )

    btn_start = _date_btn(ft.Icons.PLAY_CIRCLE_OUTLINE, "Ngày bắt đầu", start_label, start_picker)
    btn_due   = _date_btn(ft.Icons.EVENT_OUTLINED, "Hạn hoàn thành", due_label, due_picker)
    btn_time  = _date_btn(ft.Icons.ACCESS_TIME_OUTLINED, "Giờ", time_label, time_picker)

    notes_val = t.notes if hasattr(t, "notes") else ""
    tf_notes = _tf("Ghi chú", notes_val, multiline=True, hint="Ghi chú thêm...", min_l=2, max_l=4)

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
                    c.bgcolor = "#2E2E2E" if sel else "transparent"
                    c.border = ft.border.all(1.5 if sel else 1, "#888888" if sel else Colors.BORDER)
                    c.content.controls[0].color = info_i.get("color", Colors.TEXT_MUTED) if sel else Colors.TEXT_MUTED
                    c.content.controls[1].color = Colors.TEXT_PRIMARY if sel else Colors.TEXT_MUTED
                page.update()
            return _click

        for idx, (key, info) in enumerate(options.items()):
            sel = (key == sel_ref["v"])
            chip = ft.Container(
                content=ft.Row([
                    ft.Text(info["icon"], size=12, color=info.get("color", Colors.TEXT_MUTED) if sel else Colors.TEXT_MUTED),
                    ft.Text(info["label"], size=Typography.TINY, color=Colors.TEXT_PRIMARY if sel else Colors.TEXT_MUTED, weight=Typography.MEDIUM if sel else Typography.REGULAR),
                ], spacing=5, tight=True),
                padding=ft.padding.symmetric(horizontal=10, vertical=6),
                border_radius=Radius.FULL,
                bgcolor="#2E2E2E" if sel else "transparent",
                border=ft.border.all(1.5 if sel else 1, "#888888" if sel else Colors.BORDER),
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
                    c.bgcolor = "#2E2E2E" if sel else "transparent"
                    c.border = ft.border.all(1.5 if sel else 1, "#888888" if sel else Colors.BORDER)
                    c.content.color = Colors.TEXT_PRIMARY if sel else Colors.TEXT_MUTED
                page.update()
            return _click

        for idx, (val, label) in enumerate(options_list):
            sel = (val == sel_ref["v"])
            chip = ft.Container(
                content=ft.Text(label, size=Typography.TINY, color=Colors.TEXT_PRIMARY if sel else Colors.TEXT_MUTED),
                padding=ft.padding.symmetric(horizontal=10, vertical=6),
                border_radius=Radius.FULL,
                bgcolor="#2E2E2E" if sel else "transparent",
                border=ft.border.all(1.5 if sel else 1, "#888888" if sel else Colors.BORDER),
                on_click=make_click(val, idx),
                animate=ft.Animation(120, ft.AnimationCurve.EASE_OUT),
            )
            chips.append(chip)
        return ft.Row(chips, scroll=ft.ScrollMode.AUTO, spacing=6)

    rem_checkbox = ft.Checkbox(
        label="Bật thông báo nhắc nhở khi đến giờ",
        value=(t.reminder_minutes > 0),
        active_color=Colors.PRIMARY,
        check_color="white",
        label_style=ft.TextStyle(size=Typography.SMALL, color=Colors.TEXT_PRIMARY)
    )

    rec_chips = make_option_chips([
        ("none",    "Không"),
        ("daily",   "Hàng ngày"),
        ("weekly",  "Hàng tuần"),
        ("monthly", "Hàng tháng"),
    ], rec_sel)

    # ── Save ─────────────────────────────────────────────
    err_ref = ft.Ref[ft.Text]()

    def save_task(_):
        title = tf_title.value.strip()
        if not title:
            err_ref.current.value = "⚠️  Vui lòng nhập tiêu đề!"
            page.update()
            return
        t.title            = title
        t.description      = tf_desc.value.strip()
        t.start_date       = start_val["v"] or None
        t.due_date         = due_val["v"] or None
        t.due_time         = time_val["v"] or None
        t.category         = cat_sel["v"]
        t.priority         = pri_sel["v"]
        t.status           = sta_sel["v"]
        t.is_recurring     = rec_sel["v"] != "none"
        t.recur_pattern    = "" if rec_sel["v"] == "none" else rec_sel["v"]
        t.reminder_minutes = 1 if rem_checkbox.value else 0
        t.notes            = tf_notes.value.strip()
        if t.status == "done" and not t.completed_at:
            t.completed_at = datetime.now().isoformat()
        Storage.save_task(t)
        snack(page, "Đã lưu công việc ✓")
        on_navigate("tasks")
        

    def cancel_task(_):
        on_navigate("tasks")

    # HEADER
    header = ft.Container(
        content=ft.Row([
            ft.IconButton(ft.Icons.ARROW_BACK_IOS_NEW_ROUNDED, on_click=cancel_task),
            ft.Text("Sửa công việc" if is_edit else "Công việc mới", size=Typography.H2, color=Colors.TEXT_PRIMARY, weight=Typography.BOLD),
        ]),
        padding=ft.Padding.symmetric(horizontal=Spacing.MD, vertical=Spacing.MD),
    )

    # Scrollable form body
    form_body = ft.Container(
        content=ft.Column([
            _section_label("📝  NỘI DUNG"),
            tf_title, ft.Container(height=Spacing.SM), tf_desc, _div(),
            
            _section_label("📅  THỜI GIAN"),
            ft.Row([btn_start, ft.Container(width=Spacing.SM), btn_due]), ft.Container(height=Spacing.SM), ft.Row([btn_time]), _div(),
            
            _section_label("🏷️  PHÂN LOẠI"),
            ft.Container(content=ft.Column([ft.Row([ft.Icon(ft.Icons.FOLDER_OUTLINED, size=13, color=Colors.TEXT_MUTED), ft.Container(width=4), ft.Text("Danh mục", size=Typography.TINY, color=Colors.TEXT_MUTED)]), ft.Container(height=6), cat_chips], spacing=0, tight=True), padding=ft.padding.symmetric(vertical=4)),
            ft.Container(content=ft.Column([ft.Row([ft.Icon(ft.Icons.FLAG_OUTLINED, size=13, color=Colors.TEXT_MUTED), ft.Container(width=4), ft.Text("Độ ưu tiên", size=Typography.TINY, color=Colors.TEXT_MUTED)]), ft.Container(height=6), pri_chips], spacing=0, tight=True), padding=ft.padding.symmetric(vertical=4)),
            ft.Container(content=ft.Column([ft.Row([ft.Icon(ft.Icons.CIRCLE_OUTLINED, size=13, color=Colors.TEXT_MUTED), ft.Container(width=4), ft.Text("Trạng thái", size=Typography.TINY, color=Colors.TEXT_MUTED)]), ft.Container(height=6), sta_chips], spacing=0, tight=True), padding=ft.padding.symmetric(vertical=4)),
            _div(),
            
            _section_label("⚙️  CÀI ĐẶT"),
            ft.Container(content=rem_checkbox, padding=ft.padding.symmetric(vertical=4)),
            ft.Container(height=Spacing.SM),
            ft.Container(content=ft.Column([ft.Row([ft.Icon(ft.Icons.REPEAT_ROUNDED, size=13, color=Colors.TEXT_MUTED), ft.Container(width=4), ft.Text("Lặp lại", size=Typography.TINY, color=Colors.TEXT_MUTED)]), ft.Container(height=6), rec_chips], spacing=0, tight=True), padding=ft.padding.symmetric(vertical=4)),
            _div(),
            
            _section_label("📌  GHI CHÚ"),
            tf_notes, ft.Container(height=Spacing.MD),
            
            ft.Text("", ref=err_ref, color=Colors.ERROR, size=Typography.SMALL, text_align=ft.TextAlign.CENTER),
            ft.Container(height=Spacing.SM),
            
            ft.Row([
                ft.Container(content=ft.Text("Hủy", size=Typography.BODY, color=Colors.TEXT_MUTED, weight=Typography.MEDIUM), height=48, expand=1, border_radius=Radius.MD, bgcolor=Colors.BG_SURFACE, border=ft.border.all(1, Colors.BORDER), alignment=ft.Alignment.CENTER, on_click=cancel_task, ink=True),
                ft.Container(width=Spacing.SM),
                ft.Container(content=ft.Row([ft.Icon(ft.Icons.CHECK_ROUNDED, size=16, color=Colors.TEXT_ON_PRIMARY), ft.Container(width=4), ft.Text("Lưu", size=Typography.BODY, color=Colors.TEXT_ON_PRIMARY, weight=Typography.SEMIBOLD)], alignment=ft.MainAxisAlignment.CENTER, spacing=0), height=48, expand=2, border_radius=Radius.MD, bgcolor=Colors.PRIMARY, alignment=ft.Alignment.CENTER, on_click=save_task, ink=True),
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
