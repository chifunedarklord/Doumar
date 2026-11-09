"""Desktop reminder agent and opt-in per-user startup registration."""
import logging
import os
from pathlib import Path
import subprocess
import sys
import time
from datetime import datetime

log = logging.getLogger(__name__)


def send_notification(title, message):
    try:
        from plyer import notification
        notification.notify(title=title, message=message, app_name='TaskFlow', timeout=10)
        return True
    except Exception:
        log.exception('OS notification delivery failed')
        return False


def command():
    return [sys.executable, str(Path(__file__).resolve().parents[1] / 'main.py'), '--background']


def start_agent():
    kwargs = {'stdin': subprocess.DEVNULL, 'stdout': subprocess.DEVNULL, 'stderr': subprocess.DEVNULL,
              'cwd': str(Path(__file__).resolve().parents[1])}
    if os.name == 'nt':
        kwargs['creationflags'] = subprocess.CREATE_NO_WINDOW | subprocess.DETACHED_PROCESS
    else:
        kwargs['start_new_session'] = True
    subprocess.Popen(command(), **kwargs)


def set_autostart(enabled):
    """Called only from the explicit startup switch in Settings."""
    if sys.platform == 'win32':
        import winreg
        with winreg.CreateKey(winreg.HKEY_CURRENT_USER, r'Software\Microsoft\Windows\CurrentVersion\Run') as key:
            if enabled:
                winreg.SetValueEx(key, 'TaskFlow', 0, winreg.REG_SZ, subprocess.list2cmdline(command()))
            else:
                try:
                    winreg.DeleteValue(key, 'TaskFlow')
                except FileNotFoundError:
                    pass
    elif sys.platform.startswith('linux'):
        folder = Path(os.getenv('XDG_CONFIG_HOME', str(Path.home() / '.config'))) / 'autostart'
        target = folder / 'taskflow-reminders.desktop'
        if enabled:
            folder.mkdir(parents=True, exist_ok=True)
            def escape(value):
                return '"' + value.replace('\\', '\\\\').replace('"', '\\"').replace('`', '\\`').replace('$', '\\$').replace('%', '%%') + '"'
            target.write_text('[Desktop Entry]\nType=Application\nName=TaskFlow reminders\nExec=' +
                              ' '.join(escape(v) for v in command()) + '\nTerminal=false\n', encoding='utf-8')
        else:
            target.unlink(missing_ok=True)
    else:
        raise ValueError('Tự khởi động hiện hỗ trợ Windows và Linux.')


def autostart_enabled():
    if sys.platform == 'win32':
        import winreg
        try:
            with winreg.OpenKey(winreg.HKEY_CURRENT_USER, r'Software\Microsoft\Windows\CurrentVersion\Run') as key:
                winreg.QueryValueEx(key, 'TaskFlow')
            return True
        except FileNotFoundError:
            return False
    return (Path(os.getenv('XDG_CONFIG_HOME', str(Path.home() / '.config'))) / 'autostart/taskflow-reminders.desktop').exists()


def deliver(user_id, now=None):
    from core.workspace import Workspace
    from core.repositories import Storage
    user = next((u for u in Storage.get_users() if u.id == user_id), None)
    if not user or not user.settings.get('desktop_reminders', True):
        return 0
    pending = Workspace.pending_reminders(user_id, now=now, catchup_seconds=86400)
    if not pending:
        return 0
    # One summary after suspend/reboot avoids a burst of old notifications.
    if len(pending) > 3:
        sent = send_notification('TaskFlow · Nhắc việc', f'{len(pending)} lịch nhắc đang chờ. Mở TaskFlow để xem công việc và lịch hôm nay.')
        if sent:
            for item in pending:
                Workspace.mark_reminded(user_id, item['key'])
        return len(pending) if sent else 0
    count = 0
    for item in pending:
        if Storage.get_session() != user_id:
            break
        if send_notification('TaskFlow · Nhắc việc', item['title']):
            Workspace.mark_reminded(user_id, item['key'])
            count += 1
    return count


def run_agent():
    from core.orm import engine
    from core.repositories import Storage
    root = Path(engine.url.database).resolve().parent if engine.url.get_backend_name() == 'sqlite' else Path.home() / '.taskflow'
    root.mkdir(parents=True, exist_ok=True)
    # OS-held lock is released on crash; never rely on stale PID files.
    with (root / 'reminders.lock').open('a+b') as lock:
        try:
            if os.name == 'nt':
                import msvcrt
                lock.write(b'0')
                lock.flush()
                lock.seek(0)
                msvcrt.locking(lock.fileno(), msvcrt.LK_NBLCK, 1)
            else:
                import fcntl
                fcntl.flock(lock, fcntl.LOCK_EX | fcntl.LOCK_NB)
        except OSError:
            return
        import threading
        stop = threading.Event()
        syncing = threading.Event()
        def sync_account(uid):
            try:
                from core.cloud import restore_session
                from core.sync import synchronize
                if restore_session(uid):
                    synchronize(uid)
            except Exception:
                log.warning('Background sync deferred; local reminders remain active')
            finally:
                syncing.clear()
        def poll():
            tick = 0
            while not stop.is_set():
                try:
                    uid = Storage.get_session()
                    user = next((u for u in Storage.get_users() if u.id == uid), None) if uid else None
                    if user and user.settings.get('background_reminders', False):
                        deliver(uid)
                        if tick % 4 == 0 and not syncing.is_set():
                            syncing.set()
                            threading.Thread(target=sync_account, args=(uid,), daemon=True).start()
                    elif user:
                        stop.set()
                        break
                except Exception:
                    log.exception('Background reminder check failed')
                tick += 1
                stop.wait(15)
        threading.Thread(target=poll, daemon=True).start()
        try:
            from core.tray import run_tray
            run_tray(stop)
        except Exception:
            log.warning('System tray unavailable; reminder agent remains active', exc_info=True)
            stop.wait()
