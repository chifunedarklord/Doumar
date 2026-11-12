"""Local installation administration, provisioned explicitly from the host CLI."""
from datetime import datetime, timezone


def is_local_admin(user_id):
    from core.orm import SessionLocal, LocalAdminModel
    with SessionLocal() as db:
        return db.get(LocalAdminModel, user_id) is not None


def configure_admin(username, revoke=False):
    from core.orm import SessionLocal, LocalAdminModel, UserModel
    from core.access import clear_access_cache
    with SessionLocal() as db:
        user = db.query(UserModel).filter_by(username=username).one_or_none()
        if user is None:
            raise ValueError('Không tìm thấy tài khoản. Hãy đăng ký tài khoản trước khi cấp quyền.')
        if user.password_hash == 'remote-account':
            raise ValueError('Tài khoản đồng bộ cần được quản lý quyền trên máy chủ.')
        grant = db.get(LocalAdminModel, user.id)
        if revoke:
            if grant is not None:
                db.delete(grant)
        elif grant is None:
            db.add(LocalAdminModel(user_id=user.id, granted_at=datetime.now(timezone.utc).isoformat()))
        db.commit()
        result = {'username': user.username, 'admin': not revoke, 'plan': 'free' if revoke else 'pro'}
    clear_access_cache()
    return result
