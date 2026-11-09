"""Browser OAuth sign-in, with a separate one-time desktop handoff secret.

Identities bind to provider subject IDs. Matching email never automatically
links an existing password/social account. Calendar permission is separate.
"""
import base64
import hashlib
import hmac
import os
import re
import secrets
import time
import uuid
from urllib.parse import urlencode, urlsplit
import bcrypt
from server.store import digest
from server.google_calendar import http, GoogleError


class SocialError(ValueError):
    pass


def config(provider):
    if provider == 'google':
        return {'client': os.getenv('GOOGLE_LOGIN_CLIENT_ID') or os.getenv('GOOGLE_CLIENT_ID', ''),
            'secret': os.getenv('GOOGLE_LOGIN_CLIENT_SECRET') or os.getenv('GOOGLE_CLIENT_SECRET', ''),
            'redirect': os.getenv('GOOGLE_LOGIN_REDIRECT_URI', '')}
    if provider == 'facebook':
        return {'client': os.getenv('FACEBOOK_APP_ID', ''), 'secret': os.getenv('FACEBOOK_APP_SECRET', ''),
                'redirect': os.getenv('FACEBOOK_LOGIN_REDIRECT_URI', ''), 'version': os.getenv('FACEBOOK_GRAPH_VERSION', '')}
    raise SocialError('Nhà cung cấp đăng nhập không hợp lệ.')


def ready(provider):
    values = config(provider)
    return all(values.values()) and (provider != 'facebook' or bool(re.fullmatch(r'v\d+\.0', values['version'])))


def profile(provider, code, settings, verifier):
    """Only provider-authenticated profile data reaches account creation."""
    if provider == 'google':
        tokens = http('POST', 'https://oauth2.googleapis.com/token', {'client_id': settings['client'],
            'client_secret': settings['secret'], 'code': code, 'redirect_uri': settings['redirect'],
            'grant_type': 'authorization_code', 'code_verifier': verifier}, form=True)
        user = http('GET', 'https://openidconnect.googleapis.com/v1/userinfo', token=tokens['access_token'])
        if user.get('email_verified') is not True or not re.fullmatch(r'[^\s@]+@[^\s@]+\.[^\s@]+', user.get('email', '')):
            raise SocialError('Google chưa xác nhận email của tài khoản này.')
        return {'subject': user.get('sub'), 'name': user.get('name', 'Người dùng Google'), 'email': user['email'].casefold()}
    base = 'https://graph.facebook.com/' + settings['version']
    tokens = http('POST', base + '/oauth/access_token', {'client_id': settings['client'], 'client_secret': settings['secret'],
        'code': code, 'redirect_uri': settings['redirect']}, form=True)
    access = tokens['access_token']
    check = http('GET', base + '/debug_token?' + urlencode({'input_token': access}), token=settings['client'] + '|' + settings['secret'])['data']
    if check.get('is_valid') is not True or str(check.get('app_id')) != settings['client'] or check.get('type') != 'USER' or not check.get('user_id'):
        raise SocialError('Facebook chưa xác nhận được phiên đăng nhập của bạn.')
    for key in ('expires_at', 'data_access_expires_at'):
        if check.get(key) and check[key] <= time.time():
            raise SocialError('Phiên Facebook đã hết hạn. Hãy thử lại.')
    proof = hmac.new(settings['secret'].encode(), access.encode(), hashlib.sha256).hexdigest()
    user = http('GET', base + '/me?' + urlencode({'fields': 'id,name', 'appsecret_proof': proof}), token=access)
    if str(user.get('id')) != str(check['user_id']):
        raise SocialError('Danh tính Facebook không khớp phiên đã xác thực.')
    # No assumption that Facebook's optional email has been verified. A private
    # placeholder is used for account uniqueness, never for password recovery.
    return {'subject': str(user['id']), 'name': user.get('name', 'Người dùng Facebook'), 'email': ''}


class SocialAuth:
    def __init__(self, store):
        self.store = store

    def start(self, provider):
        if not ready(provider):
            raise SocialError(('Google' if provider == 'google' else 'Facebook') + ' chưa được nhà phát hành kết nối. Bạn vẫn có thể dùng tài khoản TaskFlow.')
        settings = config(provider)
        parts = urlsplit(settings['redirect'])
        if not parts.hostname or parts.username or parts.password or parts.query or parts.fragment or (parts.scheme != 'https' and not (parts.scheme == 'http' and parts.hostname in ('127.0.0.1', 'localhost'))):
            raise SocialError('Địa chỉ trả về đăng nhập chưa được thiết lập đúng.')
        ticket, state, verifier = secrets.token_urlsafe(32), secrets.token_urlsafe(32), secrets.token_urlsafe(48)
        with self.store.connect() as db:
            db.execute('DELETE FROM social_requests WHERE expires<?', (time.time(),))
            db.execute('INSERT INTO social_requests VALUES (?,?,?,?,?,?,?,?)',
                (digest(ticket), digest(state), provider, verifier, time.time() + 600, 'waiting', None, None))
        params = {'client_id': settings['client'], 'redirect_uri': settings['redirect'], 'response_type': 'code', 'state': state}
        if provider == 'google':
            challenge = base64.urlsafe_b64encode(hashlib.sha256(verifier.encode()).digest()).rstrip(b'=').decode()
            params.update(scope='openid email profile', prompt='select_account', code_challenge=challenge, code_challenge_method='S256')
            url = 'https://accounts.google.com/o/oauth2/v2/auth'
        else:
            params['scope'] = 'public_profile'
            url = 'https://www.facebook.com/' + settings['version'] + '/dialog/oauth'
        return {'authorization_url': url + '?' + urlencode(params), 'ticket': ticket, 'expires_in': 600}

    def callback(self, provider, state, code, denied=False):
        config(provider)
        with self.store.connect(lock='social-handoff') as db:
            row = db.execute('SELECT * FROM social_requests WHERE state_hash=? AND provider=? AND status=? AND expires>?',
                (digest(state), provider, 'waiting', time.time())).fetchone()
            if not row:
                raise SocialError('Yêu cầu đăng nhập hết hạn hoặc đã sử dụng. Quay lại TaskFlow để thử lại.')
            db.execute('UPDATE social_requests SET status=? WHERE ticket_hash=?', ('exchanging', row['ticket_hash']))
        try:
            if denied or not code:
                raise SocialError('Bạn đã hủy cấp quyền. Có thể đăng nhập bằng tài khoản TaskFlow hoặc thử lại.')
            identity = profile(provider, code, config(provider), row['verifier'])
            subject = identity.get('subject')
            if not isinstance(subject, str) or not 1 <= len(subject) <= 191 or len(identity.get('email', '')) > 254:
                raise SocialError('Thông tin đăng nhập từ nhà cung cấp không hợp lệ.')
            with self.store.connect(lock='social-identities') as db:
                active = db.execute('SELECT 1 FROM social_requests WHERE ticket_hash=? AND status=? AND expires>?',
                    (row['ticket_hash'], 'exchanging', time.time())).fetchone()
                if not active:
                    raise SocialError('Yêu cầu đăng nhập đã hủy hoặc hết hạn.')
                existing = db.execute('SELECT account FROM social_identities WHERE provider=? AND subject=?', (provider, subject)).fetchone()
                if existing:
                    account_id = existing['account']
                    if provider == 'google':
                        email = identity['email']
                        collision = db.execute('SELECT id FROM accounts WHERE email=? AND id<>?', (email, account_id)).fetchone()
                        safe_email = digest(provider + ':' + subject) + '@social.taskflow.invalid' if collision else email
                        previous = db.execute('SELECT email FROM accounts WHERE id=?', (account_id,)).fetchone()
                        if previous['email'] != safe_email:
                            db.execute('UPDATE accounts SET email=? WHERE id=?', (safe_email, account_id))
                            db.execute('DELETE FROM resets WHERE account=?', (account_id,))
                else:
                    email = identity.get('email', '')
                    if email and db.execute('SELECT 1 FROM accounts WHERE email=?', (email,)).fetchone():
                        raise SocialError('Email này đã có tài khoản TaskFlow. Hãy đăng nhập bằng phương thức bạn đã dùng trước đó; ứng dụng không tự ghép hai tài khoản.')
                    account_id = str(uuid.uuid4())
                    email = email or digest(provider + ':' + subject) + '@social.taskflow.invalid'
                    hashed = bcrypt.hashpw(secrets.token_urlsafe(32).encode(), bcrypt.gensalt()).decode()
                    db.execute('INSERT INTO accounts VALUES (?,?,?,?,?,?)',
                        (account_id, provider + '_' + uuid.uuid4().hex[:24], email, hashed, str(identity.get('name') or provider.title())[:200], time.time()))
                    db.execute('INSERT INTO social_identities VALUES (?,?,?)', (provider, subject, account_id))
                db.execute('UPDATE social_requests SET status=?,account=? WHERE ticket_hash=?', ('ready', account_id, row['ticket_hash']))
            return {'message': 'Đã xác thực. Bạn có thể quay lại TaskFlow và đóng thẻ này.'}
        except Exception as exc:
            message = str(exc) if isinstance(exc, SocialError) else 'Chưa xác thực được với nhà cung cấp. Quay lại TaskFlow để thử lại.'
            with self.store.connect() as db:
                db.execute('UPDATE social_requests SET status=?,error=? WHERE ticket_hash=?', ('failed', message, row['ticket_hash']))
            return {'message': message}

    def poll(self, ticket, finish=False, cancel=False):
        if not isinstance(ticket, str) or not 30 <= len(ticket) <= 100:
            raise SocialError('Yêu cầu đăng nhập không hợp lệ.')
        with self.store.connect(lock='social-handoff') as db:
            row = db.execute('SELECT * FROM social_requests WHERE ticket_hash=? AND expires>?', (digest(ticket), time.time())).fetchone()
            if not row:
                raise SocialError('Yêu cầu đăng nhập hết hạn hoặc đã kết thúc. Hãy thử lại.')
            if cancel:
                db.execute('DELETE FROM social_requests WHERE ticket_hash=?', (digest(ticket),))
                return {'status': 'cancelled'}
            if row['status'] == 'failed':
                raise SocialError(row['error'])
            if row['status'] != 'ready':
                return {'status': 'pending'}
            from server.app import public_account
            account = db.execute('SELECT * FROM accounts WHERE id=?', (row['account'],)).fetchone()
            if not finish:
                return {'status': 'ready', 'account': public_account(account)}
            token = secrets.token_urlsafe(32)
            db.execute('INSERT INTO tokens VALUES (?,?,?)', (digest(token), row['account'], time.time() + 30 * 86400))
            db.execute('DELETE FROM social_requests WHERE ticket_hash=?', (digest(ticket),))
            return {'access_token': token, 'account': public_account(account)}
