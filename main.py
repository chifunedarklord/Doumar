"""
TaskFlow - Main Application Entry Point
"""
import sys
import os

# ── Tự động chuyển vào môi trường ảo .venv nếu chạy từ Python hệ thống ──
def _ensure_venv():
    here = os.path.dirname(os.path.abspath(__file__)) if "__file__" in globals() else os.getcwd()
    for venv_name in [".venv", "venv"]:
        venv_path = os.path.join(here, venv_name)
        if sys.platform == "win32":
            py_bin = os.path.join(venv_path, "Scripts", "python.exe")
        else:
            py_bin = os.path.join(venv_path, "bin", "python")

        if os.path.isfile(py_bin):
            if os.path.abspath(sys.prefix) != os.path.abspath(venv_path):
                os.environ["VIRTUAL_ENV"] = venv_path
                bin_dir = os.path.dirname(py_bin)
                os.environ["PATH"] = bin_dir + os.path.pathsep + os.environ.get("PATH", "")
                try:
                    os.execv(py_bin, [py_bin] + sys.argv)
                except Exception as e:
                    print(f"[TaskFlow] Cảnh báo: Không thể tự động chuyển sang venv: {e}")

_ensure_venv()

import logging
logging.basicConfig(
    level=logging.WARNING,
    format="%(asctime)s %(levelname)s %(name)s: %(message)s",
)
sys.path.insert(0, os.path.dirname(__file__))

import flet as ft
import core.compat  # noqa: F401 - Cross-version compatibility shim
from core.theme import Colors, Typography, Spacing, Radius
from core.services import AuthService
from core.i18n import t, set_lang
from components.desktop_style import desktop_theme, monochrome, readable

try:
    from core.orm import DB_BACKEND
    print(f"[TaskFlow] DB Backend: {DB_BACKEND.upper()}")
except Exception:
    pass


def main(page: ft.Page):
    page.title        = "TaskFlow"
    page.bgcolor      = ft.Colors.SURFACE
    try:
        page.window.frameless = False
        page.window.bgcolor = ft.Colors.SURFACE
        page.window.width = 1280
        page.window.height = 820
        page.window.min_width = 1040
        page.window.min_height = 600
        page.window.maximizable = True
        page.window.resizable = True
    except Exception:
        page.window_resizable = True
    page.theme_mode = ft.ThemeMode.LIGHT
    page.theme = desktop_theme()
    page.padding      = 0
    page.fonts        = {}
    page.spacing      = 0

    # ── App state ─────────────────────────────────────────────
    current_user = {"u": AuthService.get_current_user()}
    if current_user['u']:
        from core.cloud import restore_session
        restore_session(current_user['u'].id)
    active_tab   = {"t": "tasks"}
    chat_cache = {"content": None}
    tasks_refresh = {"callback": None}
    navigation_guard = {'callback': None}
    cloud_message = ft.Text('Lưu trên máy', size=11, color='#666666')
    page.window.prevent_close = True
    async def close_window():
        await page.window.destroy()
    async def window_event(event):
        if event.type == ft.WindowEventType.CLOSE:
            if navigation_guard['callback']:
                navigation_guard['callback'](lambda: page.run_task(close_window))
            else:
                await close_window()
    page.window.on_event = window_event

    def refresh_tasks():
        if active_tab["t"] == "tasks" and tasks_refresh["callback"]:
            tasks_refresh["callback"]()

    def build_chat_page():
        if chat_cache["content"] is None:
            from screens.ai_screen import build_ai_screen
            chat_cache["content"] = build_ai_screen(
                page, current_user["u"], navigate, compact=True,
                standalone=True, on_tasks_changed=refresh_tasks,
            )
        return chat_cache["content"]


    # ── Screen router ─────────────────────────────────────────
    screen_area = ft.Container(expand=True, padding=0)
    nav_bar_ref = ft.Ref[ft.Container]()
    app_bar_ref = ft.Ref[ft.Container]()

    def navigate(route: str, **kwargs):
        guard = navigation_guard['callback']
        if guard:
            def proceed():
                navigation_guard['callback'] = None
                navigate(route, **kwargs)
            guard(proceed)
            return
        page.on_keyboard_event = None
        if route in ("dashboard", "insights"):
            route = "tasks" if route == "dashboard" else "report"
        active_tab["t"] = route
        user = current_user["u"]
        if not user:
            show_auth()
            return


        from screens.desktop_screen import build_tasks, build_editor, build_report
        from screens.workspace_screen import build_schedule, build_plans, build_data, build_trash, build_projects, build_account_settings
        from screens.upgrade_screen import build_upgrade, build_checkout, build_locked
        from core.access import access_for
        builders = {
            "tasks":     lambda: build_tasks(page, user, navigate, register_refresh=lambda callback: tasks_refresh.update(callback=callback), project_id=kwargs.get("project_id")),
            "calendar":  lambda: build_schedule(page, user, navigate),
            "report":    lambda: build_report(page, user, navigate),
            "profile":   lambda: build_account_settings(page, user, navigate, logout_user),
            "ai":        build_chat_page,
            "settings":  lambda: build_account_settings(page, user, navigate, logout_user),
            "task_edit": lambda: build_editor(page, user, navigate, kwargs.get("task"), register_guard=lambda callback: navigation_guard.update(callback=callback)),
            "projects":  lambda: build_projects(page, user, navigate),
            "plans":     lambda: build_upgrade(page, user, navigate),
            "checkout":  lambda: build_checkout(page, user, navigate, kwargs.get("plan"), kwargs.get("cycle", "monthly"), request_id=kwargs.get('request_id'), payment_method=kwargs.get('payment_method')),
            "data":      lambda: build_data(page, user, navigate, on_restored=lambda: chat_cache.update(content=None)),
            "trash":     lambda: build_trash(page, user, navigate),
        }

        builder = builders.get(route, builders["tasks"])
        required_feature = {"ai": "ai_chat", "projects": "projects"}.get(route)
        screen_area.content = build_locked(page, user, navigate, required_feature) if required_feature and not access_for(user.id).allows(required_feature) else builder()
        readable(screen_area.content)
        
        # Hide navbar on sub-screens
        if nav_bar_ref.current:
            nav_bar_ref.current.visible = True
            nav_bar_ref.current.content = build_sidebar()
            
        page.update()

    # ── Auth ──────────────────────────────────────────────────
    def show_auth():
        from screens.auth_screen import build_auth_screen

        def on_login(user):
            current_user["u"] = user
            active_tab["t"] = "dashboard"
            from core.services import AIMemoryService
            # Restore saved language preference
            try:
                saved_lang = AIMemoryService.recall_value(user.id, "system", "app_language")
                if saved_lang:
                    set_lang(saved_lang)
            except Exception:
                pass
            show_main_app()

        page.controls.clear()
        page.controls.append(wrap_desktop(build_auth_screen(page, on_login), include_navbar=False))
        page.update()

    def show_onboarding(user):
        from screens.onboarding_screen import build_onboarding_screen

        def on_complete():
            show_main_app()

        page.controls.clear()
        page.controls.append(
            wrap_desktop(
                readable(monochrome(build_onboarding_screen(page, user, on_complete))),
                include_navbar=False,
            )
        )
        page.update()

    def logout_user():
        AuthService.logout()
        page.overlay.clear()
        current_user["u"] = None
        active_tab["t"] = "tasks"
        chat_cache["content"] = None
        tasks_refresh["callback"] = None
        navigation_guard['callback'] = None
        show_auth()


    def build_sidebar():
        from screens.desktop_screen import palette
        c = palette(page)
        def item(label, icon, route):
            selected = active_tab["t"] == route or (route == "tasks" and active_tab["t"] in ("projects", "task_edit", "trash")) or (route == "plans" and active_tab["t"] == "checkout")
            return ft.Container(
                content=ft.Row([ft.Icon(icon, size=18, color=c["text"]), ft.Text(label, size=16, color=c["text"], weight=ft.FontWeight.W_600 if selected else ft.FontWeight.W_400, max_lines=1, overflow=ft.TextOverflow.ELLIPSIS, expand=True)], spacing=10),
                padding=ft.Padding.symmetric(horizontal=12, vertical=10), border_radius=5,
                bgcolor=c["selected"] if selected else None,
                on_click=lambda e: navigate(route), ink=True,
            )
        user = current_user["u"]
        return ft.Column([
            ft.Container(ft.Row([ft.Icon(ft.Icons.CHECK_BOX_OUTLINED, size=20, color=c["text"]), ft.Text("TaskFlow", size=16, weight=ft.FontWeight.W_600, color=c["text"])], spacing=9), padding=12),
            ft.Container(height=20),
            item("Công việc", ft.Icons.CHECK_BOX_OUTLINED, "tasks"),
            item("Lịch làm việc", ft.Icons.CALENDAR_TODAY_OUTLINED, "calendar"),
            item("Chat AI", ft.Icons.CHAT_BUBBLE_OUTLINE, "ai"),
            item("Báo cáo", ft.Icons.BAR_CHART, "report"),
            ft.Container(expand=True),
            item("Nâng cấp", ft.Icons.WORKSPACE_PREMIUM_OUTLINED, "plans"),
            item("Dữ liệu", ft.Icons.SAVE_ALT, "data"),
            ft.Container(cloud_message, padding=ft.Padding.symmetric(horizontal=12, vertical=6), on_click=lambda e: navigate('data')),
            item("Cài đặt", ft.Icons.SETTINGS_OUTLINED, "settings"),
            item(user.full_name or user.username, ft.Icons.PERSON_OUTLINE, "profile"),
        ], spacing=3, expand=True)

    def wrap_desktop(content_control, include_navbar=False):
        from screens.desktop_screen import palette
        c = palette(page)
        page.bgcolor = c["bg"]
        if not include_navbar:
            return ft.Container(
                content=ft.Container(content_control, width=460, padding=28),
                alignment=ft.Alignment.CENTER, expand=True, bgcolor=c["bg"],
            )
        return ft.Row([
            ft.Container(ref=nav_bar_ref, content=build_sidebar(), width=190, padding=12, bgcolor=c["side"], border=ft.Border(right=ft.BorderSide(1, c["line"]))),
            ft.Container(content=content_control, expand=True, padding=ft.Padding.symmetric(horizontal=32, vertical=36), bgcolor=c["bg"]),
        ], spacing=0, expand=True, vertical_alignment=ft.CrossAxisAlignment.STRETCH)

    def show_main_app():
        if current_user['u'].settings.get('background_reminders', False):
            from core.reminders import start_agent
            start_agent()
        page.controls.clear()
        page.controls.append(
            wrap_desktop(screen_area, include_navbar=True)
        )
        navigate("tasks")

    def appearance_changed(_):
        # Semantic colors follow the host theme without discarding draft inputs.
        page.update()

    page.on_platform_brightness_change = appearance_changed

    # ── Background Workers ────────────────────────────────────
    import threading, time
    from datetime import datetime
    _notified = set()

    # ── Setup EventBus handlers ───────────────────────────────
    try:
        from core.intelligence.event_bus import EventBus, Events

        def _on_task_completed(event):
            uid = event["data"].get("user_id")
            if uid:
                try:
                    from core.services import AIMemoryService
                    AIMemoryService.update_from_behavior(uid)
                except Exception:
                    pass

        def _on_session_ended(event):
            uid = event["data"].get("user_id")
            if uid:
                try:
                    from core.services import AIMemoryService
                    AIMemoryService.update_from_behavior(uid)
                except Exception:
                    pass

        bus = EventBus.get_instance()
        bus.subscribe(Events.TASK_COMPLETED, _on_task_completed)
        bus.subscribe(Events.SESSION_ENDED, _on_session_ended)
    except Exception as e:
        print(f"[EventBus] Setup error: {e}")

    _sync_running = threading.Event()

    def _sync_account(uid):
        try:
            from core.sync import synchronize
            from core.repositories import Storage
            result = synchronize(uid, can_download=lambda: bool(current_user['u'] and current_user['u'].id == uid and active_tab['t'] not in ('task_edit', 'ai')))
            async def finished(account_id, info):
                if current_user['u'] and current_user['u'].id == account_id:
                    cloud_message.value = info['message']
                    if info['state'] in ('downloaded', 'merged'):
                        chat_cache['content'] = None
                        fresh = next((u for u in Storage.get_users() if u.id == account_id), None)
                        if fresh:
                            current_user['u'] = fresh
                        refresh_tasks()
                    page.update()
            page.run_task(finished, uid, result)
        except Exception:
            async def failed(account_id):
                if current_user['u'] and current_user['u'].id == account_id:
                    cloud_message.value = 'Chưa đồng bộ · Mở Dữ liệu'
                    page.update()
            try:
                page.run_task(failed, uid)
            except Exception:
                pass
        finally:
            _sync_running.clear()

    def _notification_worker():
        tick = 0
        while True:
            time.sleep(10)
            tick += 1
            if current_user["u"]:
                uid = current_user["u"].id

                # Persist delivery markers so restarting the app does not repeat reminders.
                try:
                    from core.workspace import Workspace
                    from core.repositories import Storage
                    saved_user = next((u for u in Storage.get_users() if u.id == uid), None)
                    background = bool(saved_user and saved_user.settings.get('background_reminders', False))
                    enabled = bool(saved_user and saved_user.settings.get('desktop_reminders', True))
                    reminders = Workspace.pending_reminders(uid, catchup_seconds=86400) if enabled and not background else []
                    if len(reminders) > 3:
                        from core.reminders import deliver
                        if deliver(uid):
                            reminders = []
                        else:
                            reminders = reminders[:3]
                    for reminder in reminders:
                        if current_user["u"] is None or current_user["u"].id != uid:
                            break
                        key = (uid, reminder["key"])
                        if key in _notified:
                            continue
                        _notified.add(key)
                        native_sent = False
                        try:
                            from plyer import notification
                            notification.notify(title="TaskFlow — Nhắc việc", message=reminder["title"], app_name="TaskFlow", timeout=10)
                            native_sent = True
                            Workspace.mark_reminded(uid, reminder["key"])
                        except Exception:
                            pass
                        async def show_snack(account_id, item, marker, delivered):
                            try:
                                if current_user["u"] is not None and current_user["u"].id == account_id:
                                    sb = ft.SnackBar(content=ft.Text("Nhắc việc: " + item["title"], color="#111111"), bgcolor="#F5F5F5", duration=5000)
                                    page.overlay.append(sb)
                                    sb.open = True
                                    page.update()
                                    if not delivered:
                                        Workspace.mark_reminded(account_id, item["key"])
                            finally:
                                _notified.discard(marker)
                        try:
                            page.run_task(show_snack, uid, reminder, key, native_sent)
                        except Exception:
                            _notified.discard(key)
                except Exception:
                    logging.getLogger(__name__).exception("Reminder delivery failed")

                if tick % 6 == 1 and active_tab['t'] not in ('task_edit', 'ai'):
                    from core.cloud import session_for
                    if session_for(uid) and not _sync_running.is_set():
                        _sync_running.set()
                        threading.Thread(target=_sync_account, args=(uid,), daemon=True).start()

                # AI Memory update every 5 minutes (30 ticks)
                if tick % 30 == 0:
                    try:
                        from core.services import AIMemoryService
                        AIMemoryService.update_from_behavior(uid)
                    except Exception:
                        pass

    threading.Thread(target=_notification_worker, daemon=True).start()

    # ── Bootstrap ─────────────────────────────────────────────
    if current_user["u"]:
        show_main_app()
    else:
        show_auth()


if __name__ == "__main__":
    if '--background' in sys.argv:
        from core.reminders import run_agent
        run_agent()
    elif '--quick-add' in sys.argv:
        from screens.quick_add_screen import quick_add_main
        ft.run(quick_add_main)
    else:
        ft.run(main, assets_dir="assets")
