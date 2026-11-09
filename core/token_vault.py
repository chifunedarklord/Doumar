"""Persist account tokens only in an approved operating-system credential store."""
import hashlib


def backend():
    try:
        import keyring
        store = keyring.get_keyring()
        approved = ('keyring.backends.Windows', 'keyring.backends.SecretService',
                    'keyring.backends.libsecret', 'keyring.backends.kwallet', 'keyring.backends.macOS')
        candidates = list(store.backends) if type(store).__module__ == 'keyring.backends.chainer' else [store]
        for candidate in candidates:
            if candidate.priority > 0 and type(candidate).__module__.startswith(approved):
                return candidate
    except Exception:
        pass
    return None


def service(url):
    return 'TaskFlow/' + hashlib.sha256(url.encode()).hexdigest()


def save(url, account_id, token):
    store = backend()
    try:
        if store:
            store.set_password(service(url), account_id, token)
            return True
    except Exception:
        pass
    return False


def load(url, account_id):
    store = backend()
    try:
        return store.get_password(service(url), account_id) if store else None
    except Exception:
        return None


def remove(url, account_id):
    store = backend()
    try:
        if store:
            store.delete_password(service(url), account_id)
    except Exception:
        pass
