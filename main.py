"""
TaskFlow - Main Application Entry Point
"""
import sys
import os
sys.path.insert(0, os.path.dirname(__file__))

import flet as ft
from core.theme import Colors, Typography, Spacing, Radius
from core.services import AuthService


def main(page: ft.Page):
    page.title        = "TaskFlow"
    page.bgcolor      = "transparent"
    page.window.frameless = True
    page.window.bgcolor = "transparent"
    page.theme_mode   = ft.ThemeMode.DARK
    page.window.width = 420
    page.window.height = 820
    page.window.min_width = 360
    page.window.min_height = 600
    page.window.maximizable = False
    page.window.max_width  = 420
    page.window.max_height = 900
    page.window_resizable  = False
    page.padding      = 0
    page.fonts        = {}
    page.spacing      = 0

    # ── App state ─────────────────────────────────────────────
    current_user = {"u": AuthService.get_current_user()}
    active_tab   = {"t": "dashboard"}

    # ── Navigation bar ────────────────────────────────────────
    # 4 regular tabs — report is merged into Profile
    NAV_ITEMS = [
        ("dashboard", ft.Icons.HOME_ROUNDED,           ft.Icons.HOME_OUTLINED,           "Home"),
        ("tasks",     ft.Icons.CHECK_CIRCLE_ROUNDED,   ft.Icons.CHECK_CIRCLE_OUTLINE,    "Tasks"),
        ("calendar",  ft.Icons.CALENDAR_MONTH_ROUNDED, ft.Icons.CALENDAR_MONTH_OUTLINED, "Lịch"),
        ("profile",   ft.Icons.PERSON_ROUNDED,         ft.Icons.PERSON_OUTLINED,         "Profile"),
    ]

    def build_nav_item(tab_id, icon_active, icon_idle, label):
        is_sel = (active_tab["t"] == tab_id)
        return ft.Container(
            content=ft.Column([
                ft.Container(
                    content=ft.Icon(
                        icon_active if is_sel else icon_idle,
                        color=Colors.BG_DARKEST if is_sel else Colors.TEXT_MUTED,
                        size=22,
                    ),
                    width=44, height=32,
                    border_radius=Radius.LG,
                    bgcolor=Colors.PRIMARY if is_sel else "transparent",
                    alignment=ft.Alignment.CENTER,
                    animate=ft.Animation(200, ft.AnimationCurve.EASE_OUT),
                ),
                ft.Text(label, size=Typography.TINY,
                        color=Colors.PRIMARY if is_sel else Colors.TEXT_MUTED,
                        weight=Typography.SEMIBOLD if is_sel else Typography.REGULAR),
            ], horizontal_alignment=ft.CrossAxisAlignment.CENTER,
               spacing=3, tight=True),
            on_click=lambda _, t=tab_id: navigate(t),
            expand=True,
            ink=True,
            padding=ft.Padding.symmetric(vertical=4),
        )

    def build_nav_bar():
        ai_is_sel = active_tab["t"] == "ai"

        # ── Floating circular AI button (lives IN the row, floats via margin) ──
        ai_btn = ft.Container(
            content=ft.Column([
                ft.Icon(ft.Icons.AUTO_AWESOME_ROUNDED, color="white", size=22),
                ft.Text("AI", size=8, color="white", weight=Typography.BOLD),
            ], horizontal_alignment=ft.CrossAxisAlignment.CENTER, spacing=1, tight=True),
            width=60, height=60,
            border_radius=30,
            gradient=ft.LinearGradient(
                colors=["#A855F7", "#3B82F6"] if ai_is_sel else ["#7C3AED", "#1D4ED8"],
                begin=ft.Alignment.TOP_LEFT,
                end=ft.Alignment.BOTTOM_RIGHT,
            ),
            alignment=ft.Alignment.CENTER,
            on_click=lambda _: navigate("ai"),
            ink=True,
            animate=ft.Animation(200, ft.AnimationCurve.EASE_OUT),
            # Float 16px above bar bottom — overflows bar top via clip_behavior=NONE
            margin=ft.Margin.only(bottom=16),
        )

        # AI slot: same expand ratio as nav items but centers the circle
        ai_slot = ft.Container(
            content=ai_btn,
            expand=True,
            alignment=ft.Alignment.CENTER,
        )

        # Single Row — no Stack, no blocking layers
        return ft.Container(
            content=ft.Row([
                build_nav_item(*NAV_ITEMS[0]),
                build_nav_item(*NAV_ITEMS[1]),
                ai_slot,
                build_nav_item(*NAV_ITEMS[2]),
                build_nav_item(*NAV_ITEMS[3]),
            ], spacing=0,
               vertical_alignment=ft.CrossAxisAlignment.END),
            height=64,
            bgcolor="#FFFFFF",
            border=ft.Border(top=ft.BorderSide(1, Colors.BORDER)),
            shadow=ft.BoxShadow(blur_radius=16, color="#20000000",
                                offset=ft.Offset(0, -4)),
            clip_behavior=ft.ClipBehavior.NONE,
        )

    # ── Screen router ─────────────────────────────────────────
    screen_area = ft.Container(expand=True, padding=0)
    nav_bar_ref = ft.Ref[ft.Container]()
    app_bar_ref = ft.Ref[ft.Container]()

    def navigate(route: str, **kwargs):
        active_tab["t"] = route
        user = current_user["u"]
        if not user:
            show_auth()
            return

        from screens.dashboard_screen import build_dashboard
        from screens.tasks_screen     import build_tasks_screen
        from screens.calendar_screen  import build_calendar_screen
        from screens.report_screen    import build_report_screen
        from screens.profile_screen   import build_profile_screen
        from screens.ai_screen        import build_ai_screen
        
        try:
            from screens.settings_screen  import build_settings_screen
        except ImportError:
            build_settings_screen = None
            
        try:
            from screens.task_edit_screen import build_task_edit_screen
        except ImportError:
            build_task_edit_screen = None

        builders = {
            "dashboard": lambda: build_dashboard(page, user, navigate),
            "tasks":     lambda: build_tasks_screen(page, user, navigate),
            "calendar":  lambda: build_calendar_screen(page, user, navigate),
            "report":    lambda: build_report_screen(page, user, navigate),
            "profile":   lambda: build_profile_screen(page, user, navigate, on_logout=logout_user),
            "ai":        lambda: build_ai_screen(page, user, navigate),
            "settings":  lambda: build_settings_screen(page, user, navigate, on_logout=logout_user) if build_settings_screen else build_dashboard(page, user, navigate),
            "task_edit": lambda: build_task_edit_screen(page, user, navigate, kwargs.get("task")) if build_task_edit_screen else build_dashboard(page, user, navigate),
        }

        builder = builders.get(route, builders["dashboard"])
        screen_area.content = builder()
        
        # Hide navbar on sub-screens
        if route in ["settings", "task_edit"]:
            nav_bar_ref.current.visible = False
        else:
            nav_bar_ref.current.visible = True
            nav_bar_ref.current.content = build_nav_bar()
            
        page.update()

    # ── Auth ──────────────────────────────────────────────────
    def show_auth():
        from screens.auth_screen import build_auth_screen

        def on_login(user):
            current_user["u"] = user
            active_tab["t"] = "dashboard"
            show_main_app()

        page.controls.clear()
        page.controls.append(wrap_in_phone(build_auth_screen(page, on_login), include_navbar=False))
        page.update()

    def logout_user():
        current_user["u"] = None
        active_tab["t"] = "dashboard"
        show_auth()

    def build_status_bar():
        from datetime import datetime
        current_time = datetime.now().strftime("%H:%M")
        return ft.WindowDragArea(
            content=ft.Container(
                content=ft.Row([
                    ft.Text(current_time, size=12, weight=ft.FontWeight.BOLD, color=Colors.TEXT_PRIMARY),
                    ft.Row([
                        ft.Icon(ft.Icons.WIFI, size=14, color=Colors.TEXT_PRIMARY),
                        ft.Icon(ft.Icons.BATTERY_FULL, size=14, color=Colors.TEXT_PRIMARY),
                    ], spacing=4),
                ], alignment=ft.MainAxisAlignment.SPACE_BETWEEN, vertical_alignment=ft.CrossAxisAlignment.CENTER),
                padding=ft.padding.only(left=24, right=20, top=14, bottom=8),
                bgcolor="transparent",
            )
        )

    def wrap_in_phone(content_control, include_navbar=False):
        status_bar = build_status_bar()
        home_indicator = ft.Container(
            content=ft.Container(width=120, height=4, border_radius=2, bgcolor=Colors.BORDER),
            alignment=ft.Alignment.CENTER,
            padding=ft.padding.only(bottom=8, top=4),
            bgcolor="transparent",
        )
        
        controls = [
            status_bar, 
            ft.Container(content=content_control, expand=True)
        ]
        if include_navbar:
            controls.append(ft.Container(ref=nav_bar_ref, content=build_nav_bar()))
            
        controls.append(home_indicator)
        
        return ft.Container(
            content=ft.Column(controls, spacing=0, tight=True, expand=True),
            expand=True,
            bgcolor="#FFFFFF",
            border_radius=36,
            border=ft.border.all(8, "#1F2937"),
            clip_behavior=ft.ClipBehavior.ANTI_ALIAS,
            shadow=ft.BoxShadow(blur_radius=24, color="#30000000", offset=ft.Offset(0, 10))
        )

    def show_main_app():
        page.controls.clear()
        page.controls.append(
            wrap_in_phone(screen_area, include_navbar=True)
        )
        navigate("dashboard")

    # ── Notification Loop ─────────────────────────────────────
    import threading, time
    from datetime import datetime
    _notified = set()
    
    def _notification_worker():
        while True:
            time.sleep(10)
            if current_user["u"]:
                try:
                    from core.services import TaskService
                    due_tasks = TaskService.check_reminders(current_user["u"].id, _notified)
                    for t in due_tasks:
                        try:
                            from plyer import notification
                            notification.notify(
                                title="TaskFlow Nhắc Việc",
                                message=f"Đến giờ làm: {t.title}",
                                app_name="TaskFlow",
                                timeout=5
                            )
                        except Exception as e:
                            print("Plyer Error:", e)
                        try:
                            def show_snack(task_title):
                                sb = ft.SnackBar(
                                    content=ft.Text(f"🔔 Nhắc nhở tới hạn: {task_title}", color="white"),
                                    bgcolor="#F59E0B"
                                )
                                page.overlay.append(sb)
                                sb.open = True
                                page.update()
                            page.run_task(lambda t_title=t.title: show_snack(t_title))
                        except Exception:
                            pass
                except Exception:
                    pass

    threading.Thread(target=_notification_worker, daemon=True).start()

    # ── Bootstrap ─────────────────────────────────────────────
    if current_user["u"]:
        show_main_app()
    else:
        show_auth()


if __name__ == "__main__":
    ft.run(main, assets_dir="assets")