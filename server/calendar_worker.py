"""Run continuously on the server so Google sync continues with desktop closed."""
import logging
import signal
import threading
from server.app import Application
from server.google_calendar import GoogleError


def main():
    app = Application()
    stop = threading.Event()
    for name in ('SIGINT', 'SIGTERM'):
        if hasattr(signal, name):
            signal.signal(getattr(signal, name), lambda *_: stop.set())
    try:
        while not stop.is_set():
            with app.store.connect() as db:
                accounts = [row['account'] for row in db.execute('SELECT account FROM google_links').fetchall()]
            for uid in accounts:
                if stop.is_set():
                    break
                try:
                    app.google.sync(uid)
                except GoogleError:
                    logging.warning('Google sync deferred for one linked account; check account status in TaskFlow')
            stop.wait(60)
    finally:
        app.store.engine.dispose()


if __name__ == '__main__':
    main()
