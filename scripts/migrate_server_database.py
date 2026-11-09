"""Non-destructive SQLite server → MySQL migration. Dry run by default."""
import argparse
import json
import os
from pathlib import Path
import sqlite3
import sys
from contextlib import closing
from urllib.parse import quote
sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
from server.store import Store
from server.schema import metadata

SKIP = {'transaction_locks', 'google_jobs', 'google_states', 'social_requests'}


def migrate(source, target, apply=False):
    source = Path(source).resolve()
    if not source.is_file():
        raise ValueError('Không tìm thấy file SQLite máy chủ. Không tạo file rỗng thay thế.')
    with closing(sqlite3.connect('file:' + quote(str(source)) + '?mode=ro', uri=True)) as db:
        db.row_factory = sqlite3.Row
        db.execute('BEGIN')
        names = {row[0] for row in db.execute("SELECT name FROM sqlite_master WHERE type='table'")}
        if 'accounts' not in names:
            raise ValueError('Đây không phải SQLite của API server. Dữ liệu desktop cần xuất JSON rồi nhập vào tài khoản đồng bộ.')
        data = {table.name: [dict(row) for row in db.execute('SELECT * FROM "' + table.name + '"')]
                for table in metadata.sorted_tables if table.name not in SKIP and table.name in names}
    counts = {name: len(rows) for name, rows in data.items()}
    if not apply:
        return {'applied': False, 'counts': counts, 'message': 'Chưa ghi dữ liệu. Dừng API/worker và sao lưu trước khi dùng --apply.'}
    if not target:
        raise ValueError('Thiếu TASKFLOW_SERVER_DATABASE_URL cho cơ sở dữ liệu đích.')
    store = Store(target)
    try:
        if store.engine.dialect.name == 'sqlite' and Path(store.path).resolve() == source:
            raise ValueError('Nguồn và đích phải khác nhau.')
        with store.connect(lock='migration') as db:
            for table in metadata.sorted_tables:
                if table.name not in SKIP:
                    if db.raw.execute(table.select().limit(1)).first():
                        raise ValueError('Cơ sở dữ liệu đích phải trống; không ghi đè dữ liệu hiện có.')
            for table in metadata.sorted_tables:
                if data.get(table.name):
                    db.raw.execute(table.insert(), data[table.name])
        return {'applied': True, 'counts': counts, 'message': 'Đã chép dữ liệu, giữ nguyên ID và bản băm. Nguồn được giữ nguyên.'}
    finally:
        store.engine.dispose()


if __name__ == '__main__':
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--source', required=True)
    parser.add_argument('--apply', action='store_true')
    args = parser.parse_args()
    from dotenv import load_dotenv
    load_dotenv(Path(__file__).resolve().parents[1] / 'server/.env')
    print(json.dumps(migrate(args.source, os.getenv('TASKFLOW_SERVER_DATABASE_URL'), args.apply), ensure_ascii=False, indent=2))
