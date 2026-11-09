"""Optional native system tray: no main window is needed for quick entry."""
import subprocess
import sys
from pathlib import Path


def open_window(quick=False):
    args = [sys.executable, str(Path(__file__).resolve().parents[1] / 'main.py')]
    if quick:
        args.append('--quick-add')
    options = {'cwd': str(Path(__file__).resolve().parents[1]), 'stdin': subprocess.DEVNULL,
               'stdout': subprocess.DEVNULL, 'stderr': subprocess.DEVNULL}
    if sys.platform == 'win32':
        options['creationflags'] = subprocess.CREATE_NO_WINDOW
    subprocess.Popen(args, **options)


def run_tray(stop):
    import pystray
    from PIL import Image, ImageDraw
    image = Image.new('RGBA', (64, 64), (0, 0, 0, 0))
    draw = ImageDraw.Draw(image)
    draw.rounded_rectangle((5, 5, 59, 59), radius=10, fill='#111111')
    draw.line([(17, 32), (27, 43), (48, 22)], fill='white', width=6)
    def quit_agent(icon, item):
        stop.set()
        icon.stop()
    icon = pystray.Icon('TaskFlow', image, 'TaskFlow — Nhắc việc', menu=pystray.Menu(
        pystray.MenuItem('Thêm lịch nhanh', lambda icon, item: open_window(True), default=True),
        pystray.MenuItem('Mở TaskFlow', lambda icon, item: open_window()),
        pystray.Menu.SEPARATOR,
        pystray.MenuItem('Thoát tiến trình nền', quit_agent)))
    import threading
    def watch():
        stop.wait()
        icon.stop()
    def setup(icon):
        try:
            if not stop.is_set():
                icon.visible = True
        finally:
            # Setup runs after the native loop is ready, so a stop requested
            # during startup cannot be lost before Icon.run begins.
            threading.Thread(target=watch, daemon=True).start()
    icon.run(setup=setup)
