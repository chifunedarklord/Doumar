"""WSGI account/sync/billing/AI API. Desktop data and test users are never imported.

Local: python -m server.app (loopback only). Production: HTTPS reverse proxy +
gunicorn server.app:application; set TASKFLOW_SERVER_DB to persistent storage.
"""
import base64
import calendar
import json
import logging
import os
import re
import secrets
import smtplib
import ssl
import time
import uuid
from datetime import datetime, timezone
from email.message import EmailMessage
from http import HTTPStatus
from pathlib import Path

import bcrypt
from core.plans import quote
from server.store import Store, digest, IntegrityError

log = logging.getLogger(__name__)
try:
    from dotenv import load_dotenv
    load_dotenv(Path(__file__).parent / '.env')
except ImportError:
    pass
AI_LIMITS = {'free': 0, 'plus': 300, 'pro': 1500}


class APIError(ValueError):
    def __init__(self, status, message, **extra):
        self.status, self.message, self.extra = status, message, extra
        super().__init__(message)


def password_hash(value):
    if not isinstance(value, str) or not 10 <= len(value) or len(value.encode()) > 72:
        raise APIError(400, 'Mật khẩu cần ít nhất 10 ký tự và tối đa 72 byte.')
    return bcrypt.hashpw(value.encode(), bcrypt.gensalt()).decode()


def public_account(row):
    result = {key: row[key] for key in ('id', 'username', 'email', 'name')}
    if result['email'].endswith('@social.taskflow.invalid'):
        result['email'] = ''
    return result


def empty_workspace():
    return {'format': 'taskflow-workspace', 'version': 1,
            **{key: [] for key in ('tasks', 'memories', 'sessions', 'messages', 'blocks', 'trash')}}


def validate_workspace(payload):
    from core.snapshot import validate_snapshot
    try:
        return validate_snapshot(payload)
    except (ValueError, TypeError, KeyError) as exc:
        raise APIError(400, str(exc)) from exc


class Application:
    def __init__(self, path=None, mailer=None, ai=None, payment=None):
        self.store = Store(path or os.getenv('TASKFLOW_SERVER_DATABASE_URL') or os.getenv('TASKFLOW_SERVER_DB', 'server-data/taskflow.sqlite'))
        self.mailer = mailer or self.send_reset_email
        from server.ai import generate
        from server.payments import create
        self.ai = ai or generate
        self.payment = payment or create
        self.payment_override = payment is not None
        from server.google_calendar import GoogleCalendar
        self.google = GoogleCalendar(self.store)
        from server.social_auth import SocialAuth
        self.social = SocialAuth(self.store)
        # Equal-cost negative password check helps avoid username enumeration.
        self.dummy_hash = bcrypt.hashpw(secrets.token_bytes(24), bcrypt.gensalt())

    def __call__(self, environ, start_response):
        try:
            length = int(environ.get('CONTENT_LENGTH') or 0)
            if not 0 <= length <= 8 * 1024 * 1024:
                raise APIError(413, 'Yêu cầu vượt giới hạn 8 MB.')
            raw = environ['wsgi.input'].read(length) if length else b''
            if len(raw) != length:
                raise APIError(400, 'Yêu cầu chưa đầy đủ.')
            path, method = environ.get('PATH_INFO', '/'), environ['REQUEST_METHOD']
            if method == 'POST' and path == '/v1/webhooks/stripe':
                from server.payments import verified_stripe_event
                result = self.stripe_event(verified_stripe_event(raw, environ.get('HTTP_STRIPE_SIGNATURE', '')))
            elif method == 'POST' and path == '/v1/webhooks/payos':
                from server.payments import verified_payos_event
                result = self.payos_event(verified_payos_event(raw))
            elif method == 'GET' and path == '/v1/google/callback':
                from urllib.parse import parse_qs
                params = parse_qs(environ.get('QUERY_STRING', ''))
                result = self.google.callback(params.get('state', [''])[0], params.get('code', [''])[0])
            elif method == 'GET' and path in ('/v1/auth/social/google/callback', '/v1/auth/social/facebook/callback'):
                from urllib.parse import parse_qs
                params = parse_qs(environ.get('QUERY_STRING', ''))
                from server.social_auth import SocialError
                try:
                    result = self.social.callback(path.split('/')[-2], params.get('state', [''])[0],
                        params.get('code', [''])[0], bool(params.get('error')))
                except SocialError as exc:
                    raise APIError(400, str(exc)) from exc
            else:
                data = json.loads(raw) if raw else {}
                if not isinstance(data, dict):
                    raise APIError(400, 'Yêu cầu phải là một đối tượng JSON.')
                ip = environ.get('REMOTE_ADDR', 'unknown')
                trusted = {item.strip() for item in os.getenv('TASKFLOW_TRUSTED_PROXIES', '').split(',') if item.strip()}
                if ip in trusted and environ.get('HTTP_X_REAL_IP'):
                    import ipaddress
                    ip = str(ipaddress.ip_address(environ['HTTP_X_REAL_IP']))
                result = self.dispatch(method, path, data, environ.get('HTTP_AUTHORIZATION', ''), ip)
            status = 200
        except APIError as exc:
            status, result = exc.status, {'error': exc.message, **exc.extra}
        except (ValueError, KeyError, TypeError, UnicodeError):
            status, result = 400, {'error': 'Yêu cầu không hợp lệ.'}
        except Exception:
            log.exception('TaskFlow API request failed')
            status, result = 503, {'error': 'Dịch vụ tạm thời chưa sẵn sàng. Hãy thử lại.'}
        body = json.dumps(result, ensure_ascii=False).encode()
        start_response(f'{status} {HTTPStatus(status).phrase}', [('Content-Type', 'application/json; charset=utf-8'),
            ('Content-Length', str(len(body))), ('Cache-Control', 'no-store'), ('X-Content-Type-Options', 'nosniff')])
        return [body]

    def throttle(self, key, maximum=10, window=900):
        now = time.time()
        with self.store.connect(lock='limit:' + key) as db:
            db.execute('DELETE FROM limits WHERE starts < ?', (now - 86400,))
            row = db.execute('SELECT * FROM limits WHERE key=?', (key,)).fetchone()
            if row and now - row['starts'] < window:
                if row['count'] >= maximum:
                    raise APIError(429, 'Bạn thao tác quá nhiều lần. Hãy chờ rồi thử lại.')
                db.execute('UPDATE limits SET count=count+1 WHERE key=?', (key,))
            else:
                db.upsert('limits', ('key',), {'key': key, 'starts': now, 'count': 1})

    def account(self, authorization):
        token = authorization.removeprefix('Bearer ') if authorization.startswith('Bearer ') else ''
        with self.store.connect() as db:
            row = db.execute('SELECT a.* FROM accounts a JOIN tokens t ON a.id=t.account WHERE t.hash=? AND t.expires>?',
                             (digest(token), time.time())).fetchone()
        if not row:
            raise APIError(401, 'Phiên đăng nhập hết hạn. Hãy đăng nhập lại.')
        return row

    def entitlement(self, account_id):
        with self.store.connect() as db:
            row = db.execute('SELECT * FROM entitlements WHERE account=?', (account_id,)).fetchone()
        active = bool(row and row['expires'] > time.time())
        return {'account_id': account_id, 'plan': row['plan'] if active else 'free',
                'valid_until': datetime.fromtimestamp(row['expires'], timezone.utc).isoformat() if active else '',
                'auto_renew': False}

    def dispatch(self, method, path, data, authorization='', ip='local'):
        if method == 'POST' and path.startswith('/v1/auth/social/'):
            from server.social_auth import SocialError
            try:
                if path == '/v1/auth/social/start':
                    self.throttle('social-start:' + ip, 10)
                    return self.social.start(data.get('provider'))
                if path in ('/v1/auth/social/status', '/v1/auth/social/finish', '/v1/auth/social/cancel'):
                    ticket = data.get('ticket', '')
                    self.throttle('social-poll:' + digest(str(ticket)), 60, 60)
                    return self.social.poll(ticket, finish=path.endswith('/finish'), cancel=path.endswith('/cancel'))
            except SocialError as exc:
                raise APIError(400, str(exc)) from exc
        if method == 'GET' and path == '/health':
            return {'status': 'ok'}
        if method == 'GET' and path == '/payment-return':
            return {'message': 'Quay lại TaskFlow và chọn Kiểm tra thanh toán. Trang này không kích hoạt gói.'}
        if path.startswith('/v1/auth/') and method == 'POST':
            return self.auth(path, data, authorization, ip)
        user = self.account(authorization)
        uid = user['id']
        if path.startswith('/v1/google/'):
            from server.google_calendar import GoogleError
            try:
                if method == 'GET' and path == '/v1/google/status':
                    return self.google.status(uid)
                if method == 'POST' and path == '/v1/google/connect':
                    return self.google.start(uid)
                if method == 'POST' and path == '/v1/google/disconnect':
                    return self.google.disconnect(uid)
                if method == 'POST' and path == '/v1/google/sync':
                    self.throttle('google-sync:' + uid, 4, 60)
                    return self.google.sync(uid)
                if method == 'POST' and path == '/v1/google/resolve':
                    return self.google.resolve(uid, str(data.get('local_id', '')), data.get('choice'))
            except GoogleError as exc:
                raise APIError(503, str(exc)) from exc
        if method == 'GET' and path == '/v1/account':
            return {'account': public_account(user)}
        if path == '/v1/sync' and method in ('GET', 'PUT'):
            return self.sync(uid, method, data)
        if method == 'GET' and path == '/v1/billing/entitlement':
            return self.entitlement(uid)
        if method == 'GET' and path == '/v1/billing/orders':
            with self.store.connect() as db:
                rows = db.execute('SELECT * FROM orders WHERE account=? ORDER BY created DESC LIMIT 100', (uid,)).fetchall()
            return {'orders': [self.order_public(row) for row in rows]}
        if method == 'POST' and path == '/v1/billing/checkouts':
            return self.checkout(uid, data)
        if method == 'GET' and path.startswith('/v1/billing/checkouts/'):
            with self.store.connect() as db:
                row = db.execute('SELECT * FROM orders WHERE account=? AND id=?', (uid, path.rsplit('/', 1)[-1])).fetchone()
            if not row:
                raise APIError(404, 'Không tìm thấy đơn hàng.')
            if row['status'] == 'pending' and row['provider'] and not self.payment_override:
                self.throttle('verify-order:' + uid, 20, 60)
                from server.payments import status as payment_status
                try:
                    verified = payment_status(dict(row))
                    if verified == 'paid':
                        self.settle(row['id'], row['provider'], row['amount'], 'VND')
                    elif verified in ('expired', 'cancelled', 'failed'):
                        with self.store.connect() as db:
                            db.execute("UPDATE orders SET status=? WHERE id=? AND status='pending'", (verified, row['id']))
                    with self.store.connect() as db:
                        row = db.execute('SELECT * FROM orders WHERE id=?', (row['id'],)).fetchone()
                except Exception as exc:
                    raise APIError(503, 'Chưa kiểm tra được với cổng thanh toán. Đơn và dữ liệu vẫn được giữ; hãy thử lại.') from exc
            return self.order_public(row)
        if method == 'GET' and path == '/v1/ai/usage':
            return self.usage(uid)
        if method == 'POST' and path == '/v1/ai/generate':
            return self.generate(uid, data)
        raise APIError(404, 'Không tìm thấy chức năng.')

    def auth(self, path, data, authorization, ip):
        self.throttle('auth-ip:' + ip, 60)
        if path == '/v1/auth/register':
            username = str(data.get('username', '')).strip().casefold()
            email = str(data.get('email', '')).strip().casefold()
            name = str(data.get('name', username)).strip()[:200]
            if not re.fullmatch(r'[a-z0-9_]{3,40}', username) or len(email) > 254 or not re.fullmatch(r'[^\s@]+@[^\s@]+\.[^\s@]+', email):
                raise APIError(400, 'Tên đăng nhập cần 3–40 chữ thường, số hoặc dấu gạch dưới; email cần hợp lệ.')
            hashed = password_hash(data.get('password'))
            try:
                with self.store.connect() as db:
                    db.execute('INSERT INTO accounts VALUES (?,?,?,?,?,?)',
                               (str(uuid.uuid4()), username, email, hashed, name or username, time.time()))
            except IntegrityError:
                raise APIError(409, 'Không thể tạo tài khoản với thông tin này. Hãy đăng nhập hoặc khôi phục mật khẩu.')
            return {'message': 'Đã tạo tài khoản. Bạn có thể đăng nhập.'}
        if path == '/v1/auth/login':
            username = str(data.get('username', '')).strip().casefold()
            self.throttle('login:' + digest(username), 10)
            password = data.get('password', '')
            if not isinstance(password, str) or len(password.encode()) > 72:
                raise APIError(401, 'Tên đăng nhập hoặc mật khẩu chưa đúng.')
            with self.store.connect() as db:
                row = db.execute('SELECT * FROM accounts WHERE username=?', (username,)).fetchone()
            correct = bcrypt.checkpw(password.encode(), row['password'].encode() if row else self.dummy_hash)
            if not row or not correct:
                raise APIError(401, 'Tên đăng nhập hoặc mật khẩu chưa đúng.')
            token = secrets.token_urlsafe(32)
            with self.store.connect(lock='auth') as db:
                latest = db.execute('SELECT password FROM accounts WHERE id=?', (row['id'],)).fetchone()
                if not latest or latest['password'] != row['password']:
                    raise APIError(401, 'Mật khẩu vừa thay đổi. Hãy đăng nhập lại.')
                db.execute('DELETE FROM tokens WHERE expires < ?', (time.time(),))
                db.execute('INSERT INTO tokens VALUES (?,?,?)', (digest(token), row['id'], time.time() + 30 * 86400))
            return {'access_token': token, 'account': public_account(row)}
        if path == '/v1/auth/logout':
            self.account(authorization)
            with self.store.connect() as db:
                db.execute('DELETE FROM tokens WHERE hash=?', (digest(authorization.removeprefix('Bearer ')),))
            return {'message': 'Đã đăng xuất.'}
        if path == '/v1/auth/forgot-password':
            email = str(data.get('email', '')).strip().casefold()
            self.throttle('reset:' + digest(email), 3, 3600)
            if not os.getenv('SMTP_HOST') and self.mailer == self.send_reset_email:
                raise APIError(503, 'Chưa kết nối email khôi phục. Hãy liên hệ nhà phát hành.')
            with self.store.connect(lock='auth') as db:
                row = db.execute('SELECT * FROM accounts WHERE email=?', (email,)).fetchone()
                if row and row['email'].endswith('@social.taskflow.invalid'):
                    row = None
                token = secrets.token_urlsafe(32)
                if row:
                    db.execute('DELETE FROM resets WHERE account=?', (row['id'],))
                    db.execute('INSERT INTO resets VALUES (?,?,?)', (digest(token), row['id'], time.time() + 900))
            if row:
                self.mailer(email, token)
            return {'message': 'Nếu email thuộc một tài khoản, mã khôi phục có hiệu lực 15 phút sẽ được gửi.'}
        if path == '/v1/auth/reset-password':
            hashed = password_hash(data.get('password'))
            with self.store.connect(lock='auth') as db:
                row = db.execute('SELECT * FROM resets WHERE hash=? AND expires>?', (digest(str(data.get('token', ''))), time.time())).fetchone()
                if not row:
                    raise APIError(400, 'Mã khôi phục hết hạn hoặc đã sử dụng.')
                db.execute('UPDATE accounts SET password=? WHERE id=?', (hashed, row['account']))
                db.execute('DELETE FROM resets WHERE account=?', (row['account'],))
                db.execute('DELETE FROM tokens WHERE account=?', (row['account'],))
            return {'message': 'Đã đặt lại mật khẩu. Hãy đăng nhập lại trên các thiết bị.'}
        if path == '/v1/auth/change-password':
            user = self.account(authorization)
            old = data.get('old_password', '')
            if not isinstance(old, str) or len(old.encode()) > 72 or not bcrypt.checkpw(old.encode(), user['password'].encode()):
                raise APIError(400, 'Mật khẩu hiện tại chưa đúng.')
            hashed = password_hash(data.get('password'))
            with self.store.connect(lock='auth') as db:
                db.execute('UPDATE accounts SET password=? WHERE id=?', (hashed, user['id']))
                db.execute('DELETE FROM tokens WHERE account=? AND hash<>?', (user['id'], digest(authorization.removeprefix('Bearer '))))
                db.execute('DELETE FROM resets WHERE account=?', (user['id'],))
            return {'message': 'Đã đổi mật khẩu và đăng xuất các thiết bị khác.'}
        raise APIError(404, 'Không tìm thấy chức năng tài khoản.')

    @staticmethod
    def send_reset_email(email, token):
        message = EmailMessage()
        message['Subject'], message['From'], message['To'] = 'Khôi phục tài khoản TaskFlow', os.environ['SMTP_FROM'], email
        message.set_content('Mã khôi phục TaskFlow (hết hạn sau 15 phút):\n\n' + token + '\n\nNếu bạn không yêu cầu, hãy bỏ qua email này.')
        with smtplib.SMTP(os.environ['SMTP_HOST'], int(os.getenv('SMTP_PORT', '587')), timeout=15) as smtp:
            smtp.starttls(context=ssl.create_default_context())
            if os.getenv('SMTP_USERNAME'):
                smtp.login(os.environ['SMTP_USERNAME'], os.environ['SMTP_PASSWORD'])
            smtp.send_message(message)

    def sync(self, uid, method, data):
        with self.store.connect(lock='workspace:' + uid) as db:
            row = db.execute('SELECT * FROM workspaces WHERE account=?', (uid,)).fetchone()
            revision = row['revision'] if row else 0
            if method == 'PUT':
                if type(data.get('revision')) is not int or data['revision'] != revision:
                    raise APIError(409, 'Dữ liệu trên thiết bị khác đã thay đổi. Chọn bản cần giữ trước khi đồng bộ.', revision=revision)
                payload = validate_workspace(data.get('workspace'))
                revision += 1
                db.upsert('workspaces', ('account',), {'account': uid, 'revision': revision, 'payload': json.dumps(payload, ensure_ascii=False)})
            else:
                payload = json.loads(row['payload']) if row else empty_workspace()
        return {'account_id': uid, 'revision': revision, 'workspace': payload}

    def usage(self, uid):
        plan = self.entitlement(uid)['plan']
        period = datetime.now(timezone.utc).strftime('%Y-%m')
        with self.store.connect(lock='usage:' + uid + ':' + period) as db:
            row = db.execute('SELECT count FROM usage WHERE account=? AND period=?', (uid, period)).fetchone()
        return {'period': period, 'used': row['count'] if row else 0, 'limit': AI_LIMITS[plan], 'plan': plan}

    def generate(self, uid, data):
        self.throttle('ai:' + uid, 10, 60)
        plan = self.entitlement(uid)['plan']
        if plan == 'free':
            raise APIError(403, 'AI thuộc gói Plus và Pro.')
        if not isinstance(data.get('message'), str) or not 1 <= len(data['message']) <= 60000 or not isinstance(data.get('instruction', ''), str):
            raise APIError(400, 'Nội dung AI cần từ 1 đến 60.000 ký tự.')
        feature = data.get('feature', 'ai_chat')
        if feature not in ('ai_chat', 'ai_images', 'ai_documents', 'ai_voice') or (feature != 'ai_chat' and plan != 'pro'):
            raise APIError(403, 'Tính năng AI này thuộc gói Pro.')
        if data.get('image'):
            if plan != 'pro' or feature != 'ai_images' or data.get('mime') not in ('image/png', 'image/jpeg', 'image/webp'):
                raise APIError(403, 'Phân tích ảnh cần gói Pro và ảnh PNG/JPEG/WebP.')
            raw_image = base64.b64decode(data['image'], validate=True)
            if len(raw_image) > 4 * 1024 * 1024:
                raise APIError(413, 'Ảnh vượt giới hạn 4 MB.')
            from server.ai import validate_image
            try:
                validate_image(raw_image, data['mime'])
            except ValueError as exc:
                raise APIError(400, str(exc)) from exc
        period = datetime.now(timezone.utc).strftime('%Y-%m')
        with self.store.connect(lock='usage:' + uid + ':' + period) as db:
            row = db.execute('SELECT count FROM usage WHERE account=? AND period=?', (uid, period)).fetchone()
            if row and row['count'] >= AI_LIMITS[plan]:
                raise APIError(429, 'Đã dùng hết hạn mức AI tháng này. Hạn mức làm mới đầu tháng UTC.')
            db.upsert('usage', ('account', 'period'), {'account': uid, 'period': period, 'count': 1}, increment={'count': 1})
        try:
            reply = self.ai(data)
        except Exception as exc:
            with self.store.connect(lock='usage:' + uid + ':' + period) as db:
                db.execute('UPDATE usage SET count=CASE WHEN count>0 THEN count-1 ELSE 0 END WHERE account=? AND period=?', (uid, period))
            raise APIError(503, 'Dịch vụ AI chưa sẵn sàng. Lượt lỗi không bị tính phí hạn mức.') from exc
        return {'text': reply, 'usage': self.usage(uid)}

    @staticmethod
    def order_public(row):
        data = {key: row[key] for key in ('id', 'plan', 'cycle', 'amount', 'status', 'created')}
        data.update(order_id=data.pop('id'), account_id=row['account'], payment_method=row['method'], currency='VND')
        data['request_id'] = row['request_id']
        if row['details']:
            data.update({k: v for k, v in json.loads(row['details']).items() if k != 'provider'})
        return data

    def checkout(self, uid, data):
        self.throttle('checkout:' + uid, 10, 60)
        if data.get('payment_method') not in ('visa', 'bank_qr') or not isinstance(data.get('request_id'), str) or not 1 <= len(data['request_id']) <= 100:
            raise APIError(400, 'Phương thức hoặc mã yêu cầu không hợp lệ.')
        quote(data.get('plan'), data.get('cycle'))
        from server.payments import configured
        if not self.payment_override and not configured(data['payment_method']):
            raise APIError(503, 'Phương thức thanh toán chưa được nhà phát hành kết nối. Chưa tạo đơn hoặc thu tiền.')
        if self.entitlement(uid)['plan'] == 'pro' and data['plan'] == 'plus':
            raise APIError(409, 'Gói Pro còn hiệu lực. Bạn có thể chọn Plus sau khi Pro hết hạn.')
        with self.store.connect(lock='billing') as db:
            row = db.execute('SELECT * FROM orders WHERE account=? AND request_id=?', (uid, data['request_id'])).fetchone()
            if row and (row['plan'], row['cycle'], row['method']) != (data['plan'], data['cycle'], data['payment_method']):
                raise APIError(409, 'Mã yêu cầu đã được dùng cho một gói khác.')
            if row and row['details']:
                return self.order_public(row)
            if not row:
                pending = db.execute("SELECT 1 FROM orders WHERE account=? AND status='pending'", (uid,)).fetchone()
                if pending:
                    raise APIError(409, 'Bạn có một đơn đang chờ. Mở Lịch sử giao dịch để hoàn tất hoặc kiểm tra đơn đó trước.')
                # Reserve the introduction while an order is pending; simultaneous
                # purchases cannot obtain multiple first-month promotions.
                first = db.execute("SELECT 1 FROM orders WHERE account=? AND status IN ('pending','paid')", (uid,)).fetchone() is None
                price = quote(data['plan'], data['cycle'], first)
                oid = str(uuid.uuid4())
                db.execute('INSERT INTO orders VALUES (?,?,?,?,?,?,?,?,?,?,?)',
                           (oid, uid, data['request_id'], data['plan'], data['cycle'], data['payment_method'], price['amount'], 'pending', time.time(), None, None))
                row = db.execute('SELECT * FROM orders WHERE id=?', (oid,)).fetchone()
        try:
            details = self.payment(dict(row))
        except Exception as exc:
            # Retain reserved order: retry uses the same provider idempotency key.
            raise APIError(503, 'Chưa kết nối được cổng thanh toán. Chưa xác nhận thu tiền; hãy thử lại cùng đơn.') from exc
        with self.store.connect() as db:
            db.execute('UPDATE orders SET provider=?, details=? WHERE id=?', (details['provider'], json.dumps(details), row['id']))
            row = db.execute('SELECT * FROM orders WHERE id=?', (row['id'],)).fetchone()
        return self.order_public(row)

    def settle(self, order_id, provider, amount, currency):
        with self.store.connect(lock='billing') as db:
            row = db.execute('SELECT * FROM orders WHERE id=?', (order_id,)).fetchone()
            if not row or row['provider'] != provider or row['amount'] != amount or currency.upper() != 'VND':
                raise APIError(400, 'Giao dịch không khớp đơn hàng.')
            if row['status'] == 'paid':
                return {'received': True}
            if row['status'] != 'pending':
                raise APIError(409, 'Đơn hàng không còn chờ thanh toán.')
            current = db.execute('SELECT * FROM entitlements WHERE account=?', (row['account'],)).fetchone()
            if current and current['expires'] > time.time() and current['plan'] != row['plan']:
                # Upgrade replaces the plan from now; no downgrade checkout while
                # a higher plan is active (guarded at checkout below).
                begin = time.time()
            else:
                begin = max(time.time(), current['expires'] if current else 0)
            day = datetime.fromtimestamp(begin, timezone.utc)
            months = 12 if row['cycle'] == 'annual' else 1
            year, month = divmod(day.year * 12 + day.month - 1 + months, 12)
            expires = day.replace(year=year, month=month + 1, day=min(day.day, calendar.monthrange(year, month + 1)[1])).timestamp()
            db.execute("UPDATE orders SET status='paid' WHERE id=?", (order_id,))
            db.upsert('entitlements', ('account',), {'account': row['account'], 'plan': row['plan'], 'expires': expires})
        return {'received': True}

    def stripe_event(self, event):
        if event.get('type') in ('checkout.session.completed', 'checkout.session.async_payment_succeeded'):
            obj = event['data']['object']
            if obj.get('payment_status') == 'paid':
                return self.settle(obj['client_reference_id'], obj['id'], obj['amount_total'], obj['currency'])
        if event.get('type') in ('checkout.session.expired', 'checkout.session.async_payment_failed'):
            obj = event['data']['object']
            state = 'expired' if event['type'].endswith('expired') else 'failed'
            with self.store.connect() as db:
                db.execute("UPDATE orders SET status=? WHERE provider=? AND status='pending'", (state, obj['id']))
        return {'received': True}

    def payos_event(self, data):
        if data.get('code') != '00':
            return {'received': True}
        with self.store.connect() as db:
            row = db.execute('SELECT * FROM orders WHERE provider=? AND method=?', (data['paymentLinkId'], 'bank_qr')).fetchone()
            if not row:
                # Callback may beat the create-link response. The signed order
                # code must map to exactly one of our reserved pending orders.
                candidates = db.execute("SELECT * FROM orders WHERE method='bank_qr' AND status='pending' AND provider IS NULL").fetchall()
                matches = [candidate for candidate in candidates if int(uuid.UUID(candidate['id'])) % (2 ** 50) == data['orderCode']]
                if len(matches) == 1:
                    row = matches[0]
                    db.execute('UPDATE orders SET provider=?,details=? WHERE id=?', (data['paymentLinkId'], json.dumps({'provider_order_code': data['orderCode']}), row['id']))
                    row = db.execute('SELECT * FROM orders WHERE id=?', (row['id'],)).fetchone()
        if row:
            if json.loads(row['details']).get('provider_order_code') != data['orderCode']:
                raise APIError(400, 'Mã đơn ngân hàng không khớp.')
            return self.settle(row['id'], data['paymentLinkId'], data['amount'], data['currency'])
        return {'received': True}


_application = None


def application(environ, start_response):
    global _application
    if _application is None:
        _application = Application()
    return _application(environ, start_response)


if __name__ == '__main__':
    from wsgiref.simple_server import make_server
    with make_server('127.0.0.1', int(os.getenv('PORT', '8787')), application) as server:
        print('TaskFlow API: http://127.0.0.1:' + str(server.server_port))
        server.serve_forever()
