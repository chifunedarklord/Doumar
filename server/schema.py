"""Portable account schema: InnoDB + utf8mb4 on MySQL/MariaDB."""
from sqlalchemy import MetaData, Table, Column, String, Text, Float, Integer, ForeignKey, UniqueConstraint
from sqlalchemy.dialects.mysql import LONGTEXT

metadata = MetaData()
large_text = Text().with_variant(LONGTEXT(), 'mysql')


def table(name, *columns):
    return Table(name, metadata, *columns, mysql_engine='InnoDB', mysql_charset='utf8mb4', mysql_collate='utf8mb4_bin')


def account():
    return Column('account', String(36), ForeignKey('accounts.id'), nullable=False)


accounts = table('accounts', Column('id', String(36), primary_key=True),
    Column('username', String(40), unique=True, nullable=False), Column('email', String(254), unique=True, nullable=False),
    Column('password', String(255), nullable=False), Column('name', String(200), nullable=False), Column('created', Float(53), nullable=False))
tokens = table('tokens', Column('hash', String(64), primary_key=True), account(), Column('expires', Float(53), nullable=False))
resets = table('resets', Column('hash', String(64), primary_key=True), account(), Column('expires', Float(53), nullable=False))
workspaces = table('workspaces', Column('account', String(36), ForeignKey('accounts.id'), primary_key=True),
    Column('revision', Integer, nullable=False), Column('payload', large_text, nullable=False))
entitlements = table('entitlements', Column('account', String(36), ForeignKey('accounts.id'), primary_key=True),
    Column('plan', String(20), nullable=False), Column('expires', Float(53), nullable=False))
orders = table('orders', Column('id', String(36), primary_key=True), account(), Column('request_id', String(100), nullable=False),
    Column('plan', String(20), nullable=False), Column('cycle', String(20), nullable=False), Column('method', String(20), nullable=False),
    Column('amount', Integer, nullable=False), Column('status', String(20), nullable=False), Column('created', Float(53), nullable=False),
    Column('provider', String(255)), Column('details', large_text), UniqueConstraint('account', 'request_id'))
usage = table('usage', Column('account', String(36), ForeignKey('accounts.id'), primary_key=True),
    Column('period', String(7), primary_key=True), Column('count', Integer, nullable=False))
limits = table('limits', Column('key', String(191), primary_key=True), Column('starts', Float(53), nullable=False), Column('count', Integer, nullable=False))
locks = table('transaction_locks', Column('key', String(64), primary_key=True))

# A link stores only encrypted OAuth credentials, never Google passwords.
google_links = table('google_links', Column('account', String(36), ForeignKey('accounts.id'), primary_key=True),
    Column('calendar_id', String(255), nullable=False), Column('credentials', large_text, nullable=False),
    Column('sync_token', large_text), Column('last_sync', Float(53), nullable=False), Column('error', Text))
google_states = table('google_states', Column('hash', String(64), primary_key=True), account(), Column('expires', Float(53), nullable=False))
google_maps = table('google_maps', Column('account', String(36), ForeignKey('accounts.id'), primary_key=True),
    Column('local_id', String(128), primary_key=True), Column('event_id', String(1024), nullable=False),
    Column('local_hash', String(64), nullable=False), Column('remote_hash', String(64), nullable=False),
    Column('etag', String(255)), Column('conflict', large_text))
google_jobs = table('google_jobs', Column('account', String(36), ForeignKey('accounts.id'), primary_key=True),
    Column('owner', String(36), nullable=False), Column('expires', Float(53), nullable=False))

social_identities = table('social_identities', Column('provider', String(20), primary_key=True),
    Column('subject', String(191), primary_key=True), account())
social_requests = table('social_requests', Column('ticket_hash', String(64), primary_key=True),
    Column('state_hash', String(64), unique=True, nullable=False), Column('provider', String(20), nullable=False),
    Column('verifier', String(128), nullable=False), Column('expires', Float(53), nullable=False),
    Column('status', String(20), nullable=False), Column('account', String(36), ForeignKey('accounts.id')),
    Column('error', Text))
