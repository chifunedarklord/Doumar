"""Transactional server persistence for MySQL/MariaDB and isolated SQLite tests."""
import hashlib
import os
import re
from contextlib import contextmanager
from pathlib import Path
from sqlalchemy import create_engine, event, text
from sqlalchemy.engine import make_url, URL
from sqlalchemy.exc import IntegrityError
from server.schema import metadata


def digest(value):
    return hashlib.sha256(value.encode()).hexdigest()


class Connection:
    def __init__(self, connection):
        self.raw = connection

    def execute(self, statement, parameters=()):
        # Existing application statements use qmark positional binds. Convert
        # binds, never values, and let SQLAlchemy quote reserved MySQL names.
        if not isinstance(statement, str):
            result = self.raw.execute(statement, parameters or {})
        else:
            quote = self.raw.dialect.identifier_preparer.quote
            statement = re.sub(r'\b(key|usage)\b', lambda match: quote(match.group(0)), statement)
            pieces = statement.split('?')
            if len(pieces) - 1 != len(parameters):
                raise ValueError('Số tham số SQL không khớp.')
            sql = ''.join(piece + (':p' + str(i) if i < len(parameters) else '') for i, piece in enumerate(pieces))
            result = self.raw.execute(text(sql), {'p' + str(i): value for i, value in enumerate(parameters)})
        return result.mappings() if result.returns_rows else result

    def upsert(self, name, keys, values, increment=None):
        table = metadata.tables[name]
        if self.raw.dialect.name == 'mysql':
            from sqlalchemy.dialects.mysql import insert
        else:
            from sqlalchemy.dialects.sqlite import insert
        statement = insert(table).values(**values)
        changes = {key: value for key, value in values.items() if key not in keys}
        changes.update({key: table.c[key] + value for key, value in (increment or {}).items()})
        if self.raw.dialect.name == 'mysql':
            statement = statement.on_duplicate_key_update(**changes)
        else:
            statement = statement.on_conflict_do_update(index_elements=list(keys), set_=changes)
        return self.raw.execute(statement)


class Store:
    def __init__(self, location):
        location = str(location)
        self.path = location  # Compatibility for local test/recovery tooling.
        if '://' not in location:
            path = Path(location).resolve()
            path.parent.mkdir(parents=True, exist_ok=True, mode=0o700)
            fd = os.open(path, os.O_CREAT | os.O_RDWR, 0o600)
            os.close(fd)
            location = URL.create('sqlite', database=str(path))
        url = make_url(location) if isinstance(location, str) else location
        if url.get_backend_name() not in ('mysql', 'sqlite'):
            raise ValueError('Máy chủ hỗ trợ mysql+pymysql hoặc SQLite cho phát triển.')
        options = {'pool_pre_ping': True, 'hide_parameters': True}
        if url.get_backend_name() == 'mysql':
            options.update(pool_recycle=1800, isolation_level='READ COMMITTED', connect_args={'connect_timeout': 10, 'read_timeout': 30, 'write_timeout': 30})
        else:
            from sqlalchemy.pool import NullPool
            options['connect_args'] = {'check_same_thread': False, 'timeout': 30}
            options['poolclass'] = NullPool
            self.path = str(Path(url.database).resolve())
        self.engine = create_engine(url, **options)
        if self.engine.dialect.name == 'sqlite':
            @event.listens_for(self.engine, 'connect')
            def sqlite_setup(db, _):
                db.execute('PRAGMA foreign_keys=ON')
                db.execute('PRAGMA journal_mode=WAL')
        metadata.create_all(self.engine)
        if self.engine.dialect.name == 'sqlite' and os.name != 'nt':
            for name in (self.path, self.path + '-wal', self.path + '-shm'):
                if Path(name).exists():
                    os.chmod(name, 0o600)

    @contextmanager
    def connect(self, lock=None):
        with self.engine.connect() as raw:
            try:
                if raw.dialect.name == 'sqlite':
                    raw.exec_driver_sql('BEGIN IMMEDIATE')
                else:
                    raw.begin()
                    if lock:
                        from sqlalchemy.dialects.mysql import insert
                        table = metadata.tables['transaction_locks']
                        for item in sorted(lock if isinstance(lock, (list, tuple)) else [lock]):
                            key = digest(item)
                            # The update acquires an InnoDB row lock until commit.
                            raw.execute(insert(table).values(key=key).on_duplicate_key_update(key=key))
                yield Connection(raw)
                raw.commit()
            except Exception:
                raw.rollback()
                raise
