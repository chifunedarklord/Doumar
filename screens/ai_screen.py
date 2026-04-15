"""
TaskFlow - AI Assistant Screen
Trợ lý ảo tích hợp AI - giao diện chat thông minh
"""
import flet as ft
import threading
import time
from core.theme import Colors, Typography, Spacing, Radius

# ── Demo reply pool (rotates, no API needed) ───────────────────────────────
_DEMO_REPLIES = [
    "Dựa trên dữ liệu công việc của bạn, tôi thấy bạn có xu hướng "
    "hoàn thành tốt nhất vào buổi sáng. Hãy ưu tiên các task khó vào "
    "khung giờ 8–11h để đạt hiệu suất cao nhất! ☀️",

    "Tôi nhận thấy bạn có nhiều task thuộc danh mục **Công việc**. "
    "Hãy thử chia nhỏ mỗi task lớn thành các bước nhỏ 30 phút để "
    "tránh bị quá tải và dễ theo dõi tiến độ hơn. 🎯",

    "Mẹo năng suất: Áp dụng kỹ thuật Pomodoro –\n"
    "• 25 phút tập trung làm việc\n"
    "• 5 phút nghỉ ngơi\n"
    "• Cứ 4 vòng nghỉ dài 15–20 phút\n"
    "Não bộ sẽ hoạt động hiệu quả hơn rất nhiều! 🍅",

    "Theo nghiên cứu, việc đặt deadline cụ thể (giờ + ngày) thay vì "
    "chỉ ghi ngày giúp tỷ lệ hoàn thành task tăng 40%. Hãy thử với "
    "các task tiếp theo của bạn nhé! ⏰",

    "Nếu bạn đang bị overwhelmed, hãy dùng ma trận Eisenhower:\n"
    "• 🔴 Khẩn + Quan trọng → Làm ngay\n"
    "• 🟡 Quan trọng + Không khẩn → Lên lịch\n"
    "• 🟠 Khẩn + Không quan trọng → Uỷ thác\n"
    "• ⚪ Không khẩn + Không quan trọng → Bỏ qua",

    "Great job making progress! Consistency beats perfection — "
    "hoàn thành các task nhỏ đều đặn mỗi ngày sẽ tạo ra kết quả lớn "
    "theo thời gian. Bạn đang đi đúng hướng! 💪",
]

_QUICK_PROMPTS = [
    ("📊", "Phân tích", "Phân tích tình trạng công việc của tôi"),
    ("💡", "Mẹo",       "Cho tôi mẹo tăng năng suất làm việc"),
    ("🎯", "Ưu tiên",   "Task nào tôi nên tập trung làm trước?"),
    ("🗓️", "Kế hoạch",  "Giúp tôi lên kế hoạch làm việc hiệu quả"),
]


def build_ai_screen(page: ft.Page, user, on_navigate):
    from core.models import Storage

    tasks   = Storage.get_tasks(user.id)
    total   = len(tasks)
    done    = sum(1 for t in tasks if t.status == "done")
    pending = sum(1 for t in tasks if t.status == "todo")
    pct     = int(done / total * 100) if total else 0

    _idx = {"i": 0}   # rotating demo reply index

    # ── Chat list ──────────────────────────────────────────────────────────
    chat_lv = ft.ListView(
        expand=True,
        spacing=12,
        padding=ft.Padding.symmetric(horizontal=Spacing.MD, vertical=Spacing.MD),
        auto_scroll=True,
    )

    def _bubble(text: str = None, is_user: bool = False, audio: bool = False, image_src: str = None) -> ft.Row:
        if image_src:
            content = ft.Image(src=image_src, height=200, fit="contain", border_radius=8)
        elif audio:
            content = ft.Row([
                ft.Icon(ft.Icons.MIC_ROUNDED, color="white" if is_user else Colors.TEXT_PRIMARY, size=20),
                ft.Text("Tin nhắn thoại (0:04)", color="white" if is_user else Colors.TEXT_PRIMARY, size=Typography.BODY)
            ], tight=True)
        else:
            content = ft.Text(
                text,
                size=Typography.BODY,
                color="white" if is_user else Colors.TEXT_PRIMARY,
                selectable=True,
            )

        bubble = ft.Container(
            content=content,
            padding=ft.Padding.symmetric(horizontal=14, vertical=10),
            border_radius=ft.BorderRadius(
                top_left=16, top_right=16,
                bottom_right=4 if is_user else 16,
                bottom_left=16 if is_user else 4,
            ),
            bgcolor=Colors.SECONDARY if is_user else Colors.BG_CARD,
            border=ft.border.all(1, Colors.BORDER) if not is_user else None,
            shadow=ft.BoxShadow(
                blur_radius=8, color="#00000033", offset=ft.Offset(0, 2)
            ),
            animate=ft.Animation(300, ft.AnimationCurve.EASE_OUT),
        )

        if is_user:
            return ft.Row(
                [
                    ft.Container(expand=1),
                    ft.Column([bubble], expand=4, horizontal_alignment=ft.CrossAxisAlignment.END)
                ],
                spacing=0,
            )

        ai_avatar = ft.Container(
            content=ft.Image(src="avtdoumar.png", fit="cover"),
            width=30, height=30,
            border_radius=15,
            clip_behavior=ft.ClipBehavior.ANTI_ALIAS,
            bgcolor="#7C3AED",
            alignment=ft.Alignment.CENTER,
            shadow=ft.BoxShadow(blur_radius=8, color="#7C3AED55", offset=ft.Offset(0, 2))
        )
        return ft.Row(
            [
                ai_avatar,
                ft.Column([bubble], expand=True, horizontal_alignment=ft.CrossAxisAlignment.START)
            ],
            spacing=Spacing.SM,
            vertical_alignment=ft.CrossAxisAlignment.START,
        )

    def _scroll_down():
        async def _scroll():
            try:
                await chat_lv.scroll_to(offset=99999, duration=300)
            except Exception:
                pass
        try:
            page.run_task(_scroll)
        except Exception:
            pass

    def _add_bubble(text: str = None, is_user: bool = False, audio: bool = False, image_src: str = None):
        bubble = _bubble(text, is_user, audio, image_src)
        has_typing = _typing in chat_lv.controls
        
        if has_typing:
            chat_lv.controls.remove(_typing)
            
        chat_lv.controls.append(bubble)
        
        if has_typing:
            chat_lv.controls.append(_typing)
            
        page.update()
        _scroll_down()

    # ── Typing indicator ───────────────────────────────────────────────────
    _typing = ft.Container(
        content=ft.Row([
            ft.Container(
                content=ft.Image(src="avtdoumar.png", fit="cover"),
                width=26, height=26, border_radius=13,
                clip_behavior=ft.ClipBehavior.ANTI_ALIAS,
                bgcolor="#7C3AED",
                alignment=ft.Alignment.CENTER,
                shadow=ft.BoxShadow(blur_radius=4, color="#7C3AED55", offset=ft.Offset(0, 2))
            ),
            ft.Container(
                content=ft.Row([
                    ft.Container(
                        width=7, height=7, border_radius=4,
                        bgcolor=Colors.TEXT_MUTED,
                        animate=ft.Animation(600, ft.AnimationCurve.EASE_IN_OUT),
                    ),
                    ft.Container(
                        width=7, height=7, border_radius=4,
                        bgcolor=Colors.TEXT_MUTED,
                        animate=ft.Animation(600, ft.AnimationCurve.EASE_IN_OUT),
                    ),
                    ft.Container(
                        width=7, height=7, border_radius=4,
                        bgcolor=Colors.TEXT_MUTED,
                        animate=ft.Animation(600, ft.AnimationCurve.EASE_IN_OUT),
                    ),
                ], spacing=4),
                padding=ft.Padding.symmetric(horizontal=14, vertical=10),
                border_radius=ft.BorderRadius(16, 16, 16, 4),
                bgcolor=Colors.BG_CARD,
                border=ft.border.all(1, Colors.BORDER),
            ),
            ft.Container(expand=True),
        ], spacing=Spacing.SM, vertical_alignment=ft.CrossAxisAlignment.END),
        visible=False,
    )

    # ── Welcome message ────────────────────────────────────────────────────
    name = user.full_name or user.username
    _add_bubble(
        f"Xin chào {name}! 👋\n\n"
        f"Tôi là Doumar trợ lý của bạn. Hiện bạn có:\n"
        f"• {total} công việc tổng cộng\n"
        f"• ✅ {done} hoàn thành ({pct}%)\n"
        f"• 📋 {pending} đang chờ\n\n"
        "Hỏi tôi bất cứ điều gì về quản lý công việc và năng suất!",
        is_user=False,
    )
    chat_lv.controls.append(_typing)

    # ── Input & send ───────────────────────────────────────────────────────
    tf = ft.TextField(
        hint_text="Nhắn gì đó cho AI…",
        hint_style=ft.TextStyle(color=Colors.TEXT_MUTED),
        bgcolor=Colors.BG_INPUT,
        border_color=Colors.BORDER,
        focused_border_color=Colors.SECONDARY,
        text_style=ft.TextStyle(color=Colors.TEXT_PRIMARY),
        border_radius=Radius.LG,
        cursor_color=Colors.PRIMARY,
        expand=True,
        on_submit=lambda e: _send(e),
    )

    # ── Upload Image (Giả lập để không phụ thuộc phiên bản Flet Native) ──
    def _pick(e):
        tf.hint_text = "Đang tải ảnh lên..."
        tf.disabled = True
        page.update()
        
        def _simulate_pick():
            time.sleep(1)
            tf.hint_text = "Nhắn gì đó cho AI…"
            tf.disabled = False
            _add_bubble(is_user=True, image_src="doumar1.png")
            page.update()
            _simulate_reply()
            
        threading.Thread(target=_simulate_pick, daemon=True).start()

    # ── State for recording ──
    _record_state = {"is_recording": False}

    def _toggle_record(_):
        if not _record_state["is_recording"]:
            _record_state["is_recording"] = True
            btn_mic.icon = ft.Icons.STOP_CIRCLE_ROUNDED
            btn_mic.icon_color = Colors.ERROR
            tf.hint_text = "Đang thu âm..."
            tf.disabled = True
        else:
            _record_state["is_recording"] = False
            btn_mic.icon = ft.Icons.MIC_ROUNDED
            btn_mic.icon_color = Colors.TEXT_MUTED
            tf.hint_text = "Nhắn gì đó cho AI…"
            tf.disabled = False
            _add_bubble(is_user=True, audio=True)
            _simulate_reply()
        page.update()

    btn_attach = ft.IconButton(
        icon=ft.Icons.IMAGE_ROUNDED,
        icon_color=Colors.TEXT_MUTED,
        on_click=_pick
    )

    btn_mic = ft.IconButton(
        icon=ft.Icons.MIC_ROUNDED,
        icon_color=Colors.TEXT_MUTED,
        on_click=_toggle_record
    )

    def _simulate_reply():
        _typing.visible = True
        page.update()
        _scroll_down()

        def _reply():
            time.sleep(0.9)
            reply = _DEMO_REPLIES[_idx["i"] % len(_DEMO_REPLIES)]
            _idx["i"] += 1
            _typing.visible = False
            _add_bubble(text=reply, is_user=False)
            page.update()

        threading.Thread(target=_reply, daemon=True).start()

    def _send(_):
        text = tf.value.strip()
        if not text:
            return
        tf.value = ""
        _add_bubble(text=text, is_user=True)
        _simulate_reply()

    send_btn = ft.Container(
        content=ft.Icon(ft.Icons.SEND_ROUNDED, color="white", size=20),
        width=46, height=46,
        border_radius=Radius.LG,
        gradient=ft.LinearGradient(
            colors=["#7C3AED", "#2563EB"],
            begin=ft.Alignment.TOP_LEFT,
            end=ft.Alignment.BOTTOM_RIGHT,
        ),
        alignment=ft.Alignment.CENTER,
        on_click=_send,
        ink=True,
        shadow=ft.BoxShadow(
            blur_radius=12, color="#7C3AED55", offset=ft.Offset(0, 3)
        ),
        animate=ft.Animation(150, ft.AnimationCurve.EASE_OUT),
    )

    # ── Quick-prompt chips ─────────────────────────────────────────────────
    def _chip(emoji: str, label: str, prompt: str):
        def _tap(_):
            tf.value = prompt
            _send(None)

        return ft.GestureDetector(
            content=ft.Container(
                content=ft.Row([
                    ft.Text(emoji, size=12),
                    ft.Text(label, size=Typography.TINY,
                            color=Colors.TEXT_SECONDARY),
                ], spacing=4, tight=True),
                padding=ft.Padding.symmetric(horizontal=10, vertical=6),
                border_radius=Radius.FULL,
                border=ft.border.all(1, Colors.BORDER),
                bgcolor=Colors.BG_SURFACE,
            ),
            on_tap=_tap,
        )

    chips_row = ft.Row(
        [_chip(e, l, p) for e, l, p in _QUICK_PROMPTS],
        scroll=ft.ScrollMode.AUTO,
        spacing=Spacing.SM,
    )

    # ── History Panel ──────────────────────────────────────────────────────
    history_lv = ft.ListView(
        expand=True,
        spacing=8,
        controls=[
            ft.Text("Hôm nay", color=Colors.TEXT_MUTED, size=Typography.SMALL),
            ft.Container(content=ft.Text("Báo cáo tiến độ"), padding=10, border_radius=8, bgcolor=Colors.BG_SURFACE),
            ft.Container(content=ft.Text("Lên lịch trình"), padding=10, border_radius=8, bgcolor=Colors.BG_SURFACE),
            ft.Text("Hôm qua", color=Colors.TEXT_MUTED, size=Typography.SMALL),
            ft.Container(content=ft.Text("Tóm tắt lỗi UI"), padding=10, border_radius=8, bgcolor=Colors.BG_SURFACE),
        ]
    )
    
    history_panel = ft.Container(
        content=ft.Column([
            ft.Text("Lịch sử trò chuyện", size=Typography.H4, weight=ft.FontWeight.BOLD),
            ft.Divider(color=Colors.BORDER),
            history_lv
        ]),
        width=0,
        bgcolor=Colors.BG_DARK,
        padding=0,
        border=ft.Border(left=ft.BorderSide(1, Colors.BORDER)),
        animate=ft.Animation(300, ft.AnimationCurve.EASE_OUT_CUBIC),
        clip_behavior=ft.ClipBehavior.HARD_EDGE
    )

    _history_state = {"open": False}
    def toggle_history(e):
        _history_state["open"] = not _history_state["open"]
        if _history_state["open"]:
            history_panel.width = 250
            history_panel.padding = 16
        else:
            history_panel.width = 0
            history_panel.padding = 0
        page.update()

    btn_menu = ft.IconButton(
        icon=ft.Icons.MENU_ROUNDED,
        icon_color=Colors.TEXT_PRIMARY,
        on_click=toggle_history
    )

    # ── Header ─────────────────────────────────────────────────────────────
    header = ft.Container(
        content=ft.Row([
            ft.Container(
                content=ft.Image(src="avtdoumar.png", fit="cover"),
                width=44, height=44,
                border_radius=22,
                clip_behavior=ft.ClipBehavior.ANTI_ALIAS,
                bgcolor="#7C3AED",
                alignment=ft.Alignment.CENTER,
                shadow=ft.BoxShadow(blur_radius=16, color="#7C3AED55", offset=ft.Offset(0, 4))
            ),
            ft.Column([
                ft.Text("Doumar", size=Typography.H3,
                        color=Colors.TEXT_PRIMARY, weight=Typography.BOLD),
                ft.Row([
                    ft.Container(
                        width=7, height=7, border_radius=4,
                        bgcolor=Colors.SUCCESS,
                    ),
                    ft.Text("Đang hoạt động", size=Typography.TINY,
                            color=Colors.SUCCESS),
                ], spacing=4,
                   vertical_alignment=ft.CrossAxisAlignment.CENTER),
            ], spacing=2, tight=True),
            ft.Container(expand=True),
            ft.Container(
                content=ft.Text("AI", size=Typography.TINY,
                                color="white", weight=Typography.BOLD),
                padding=ft.Padding.symmetric(horizontal=8, vertical=3),
                border_radius=Radius.FULL,
                gradient=ft.LinearGradient(
                    colors=["#7C3AED", "#2563EB"],
                    begin=ft.Alignment.CENTER_LEFT,
                    end=ft.Alignment.CENTER_RIGHT,
                ),
            ),
        ], spacing=Spacing.SM,
           vertical_alignment=ft.CrossAxisAlignment.CENTER),
        padding=ft.Padding.symmetric(horizontal=Spacing.MD, vertical=Spacing.MD),
        border=ft.Border(bottom=ft.BorderSide(1, Colors.BORDER)),
        bgcolor=Colors.BG_DARKEST,
    )

    # ── Assemble ───────────────────────────────────────────────────────────
    main_chat = ft.Column([
        header,
        chat_lv,
        # Quick prompts
        ft.Container(
            content=chips_row,
            padding=ft.Padding.symmetric(horizontal=Spacing.MD, vertical=Spacing.XS),
            border=ft.Border(top=ft.BorderSide(1, Colors.BORDER)),
        ),
        # Input bar
        ft.Container(
            content=ft.Row([btn_menu, btn_attach, btn_mic, tf, send_btn], spacing=Spacing.SM),
            padding=ft.Padding.symmetric(horizontal=Spacing.MD, vertical=Spacing.SM),
            bgcolor=Colors.BG_DARKEST,
        ),
    ], spacing=0, tight=True, expand=True)

    return ft.Row([
        main_chat,
        history_panel
    ], expand=True, spacing=0)
