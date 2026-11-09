"""Account API client. Access tokens live in memory, never in backups/settings."""
import json
import os
import threading
from urllib.error import HTTPError, URLError
from urllib.parse import urlsplit
from urllib.request import Request, build_opener
from core.billing import NoRedirect

_lock = threading.RLock()
_session = {}


class CloudError(ValueError):
    def __init__(self, message, status=0, details=None):
        self.status, self.details = status, details or {}
        super().__init__(message)


def session_for(account_id=None):
    with _lock:
        if account_id is not None and _session.get('account_id') != account_id:
            return {}
        return dict(_session)


def clear_session():
    with _lock:
        _session.clear()
    from core.access import clear_access_cache
    clear_access_cache()


def restore_session(account_id):
    url = os.getenv('TASKFLOW_API_URL', '').rstrip('/')
    if not url or session_for(account_id):
        return bool(session_for(account_id))
    from core.token_vault import load
    token = load(url, account_id)
    if token:
        with _lock:
            _session.clear()
            _session.update(account_id=account_id, url=url, token=token, persistent=True)
        return True
    return False


def revoke_session(current):
    """Best-effort remote logout after the local token has already been erased."""
    if not current.get('token'):
        return
    try:
        validate_api_url(current['url'])
        request = Request(current['url'] + '/v1/auth/logout', data=b'{}', method='POST',
            headers={'Content-Type': 'application/json', 'Authorization': 'Bearer ' + current['token']})
        with build_opener(NoRedirect()).open(request, timeout=12) as response:
            response.read(1024)
    except (URLError, OSError, ValueError):
        # Offline logout is still immediate locally; server token has a finite
        # expiry and is revoked by a password reset if necessary.
        pass


def validate_api_url(url):
    parts = urlsplit(url)
    local = parts.scheme == 'http' and parts.hostname in ('127.0.0.1', 'localhost', '::1') and os.getenv('TASKFLOW_ALLOW_LOCAL_API') == '1'
    if (parts.scheme != 'https' and not local) or not parts.hostname or parts.username or parts.password or parts.query or parts.fragment:
        raise CloudError('Máy chủ cần địa chỉ HTTPS hợp lệ. HTTP chỉ dùng trên máy phát triển với TASKFLOW_ALLOW_LOCAL_API=1.')


class CloudClient:
    def __init__(self, account_id=None):
        self.account_id = account_id
        self.url = os.getenv('TASKFLOW_API_URL', '').rstrip('/')

    @property
    def configured(self):
        return bool(self.url)

    def request(self, method, path, data=None, authenticated=True):
        if not self.url:
            raise CloudError('Chưa kết nối máy chủ. Dữ liệu vẫn được lưu trên máy này.')
        validate_api_url(self.url)
        headers = {'Content-Type': 'application/json', 'Accept': 'application/json'}
        if authenticated:
            current = session_for(self.account_id)
            if not current.get('token') or current.get('url') != self.url:
                raise CloudError('Hãy đăng nhập lại để kết nối tài khoản máy chủ.', 401)
            headers['Authorization'] = 'Bearer ' + current['token']
        request = Request(self.url + path, data=json.dumps(data).encode() if data is not None else None,
                          headers=headers, method=method)
        try:
            with build_opener(NoRedirect()).open(request, timeout=60) as response:
                raw = response.read(8 * 1024 * 1024 + 1)
                if len(raw) > 8 * 1024 * 1024:
                    raise CloudError('Dữ liệu máy chủ vượt giới hạn 8 MB.')
                result = json.loads(raw)
                if not isinstance(result, dict):
                    raise CloudError('Dữ liệu máy chủ không hợp lệ.')
                return result
        except HTTPError as exc:
            try:
                details = json.loads(exc.read(16384))
            except (ValueError, UnicodeError):
                details = {}
            if exc.code == 401 and authenticated:
                current = session_for(self.account_id)
                if current.get('token') and headers.get('Authorization') == 'Bearer ' + current['token']:
                    from core.token_vault import remove
                    remove(self.url, current['account_id'])
                    clear_session()
            raise CloudError(details.get('error', 'Máy chủ từ chối yêu cầu.'), exc.code, details) from exc
        except (URLError, OSError, ValueError) as exc:
            if isinstance(exc, CloudError):
                raise
            raise CloudError('Không kết nối được máy chủ. Dữ liệu trên máy vẫn được giữ; hãy thử lại khi có mạng.') from exc

    def login(self, username, password):
        result = self.request('POST', '/v1/auth/login', {'username': username, 'password': password}, False)
        return self.accept_login(result)

    def accept_login(self, result):
        account = result['account']
        if not isinstance(account.get('id'), str) or not isinstance(result.get('access_token'), str):
            raise CloudError('Phản hồi đăng nhập không hợp lệ.')
        with _lock:
            _session.clear()
            _session.update(account_id=account['id'], token=result['access_token'], url=self.url)
        from core.token_vault import save
        persistent = save(self.url, account['id'], result['access_token'])
        with _lock:
            _session['persistent'] = persistent
        return account


def generate_ai(user_id, message, instruction='', feature='ai_chat', image_path=None):
    import base64
    from pathlib import Path
    payload = {'message': message, 'instruction': instruction, 'feature': feature}
    if image_path:
        path = Path(image_path)
        if path.stat().st_size > 4 * 1024 * 1024:
            raise CloudError('Ảnh vượt giới hạn 4 MB.')
        mime = {'.png': 'image/png', '.jpg': 'image/jpeg', '.jpeg': 'image/jpeg', '.webp': 'image/webp'}.get(path.suffix.lower())
        if not mime:
            raise CloudError('Hãy chọn ảnh PNG, JPEG hoặc WebP.')
        payload.update(image=base64.b64encode(path.read_bytes()).decode(), mime=mime, feature='ai_images')
    return CloudClient(user_id).request('POST', '/v1/ai/generate', payload)['text']
