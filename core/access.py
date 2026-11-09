"""Free/Plus/Pro feature policy; paid status never comes from local user settings."""
from dataclasses import dataclass
from datetime import datetime, timezone
import time
import hashlib
import threading
from core.billing import BillingClient, BillingError


FEATURES = {
    "tasks": ("free", "Quản lý công việc và việc con"),
    "manual_schedule": ("free", "Lịch cố định và nhắc việc"),
    "basic_reports": ("free", "Báo cáo 7 ngày"),
    "data": ("free", "Sao lưu, xuất dữ liệu và Thùng rác"),
    "projects": ("plus", "Quản lý dự án"),
    "recurrence": ("plus", "Công việc lặp lại"),
    "smart_schedule": ("plus", "Đề xuất lịch thông minh"),
    "ai_chat": ("plus", "Chat AI và lập kế hoạch"),
    "advanced_reports": ("plus", "Báo cáo 30 ngày"),
    "ai_voice": ("pro", "Trò chuyện và nghe bằng giọng nói"),
    "ai_documents": ("pro", "Phân tích PDF, Word và bảng tính"),
    "ai_images": ("pro", "Phân tích ảnh và tạo việc từ ảnh"),
}
LEVELS = {"free": 0, "plus": 1, "pro": 2}
_cache = {}
_lock = threading.RLock()


class UpgradeRequired(ValueError):
    pass


@dataclass(frozen=True)
class Access:
    plan: str = "free"
    source: str = "local"
    valid_until: str = ""

    def allows(self, feature):
        required, _ = FEATURES[feature]
        return LEVELS[self.plan] >= LEVELS[required]


def access_for(account_id, refresh=False):
    client = BillingClient()
    if not client.configured:
        return Access()
    key = (account_id, client.base_url, hashlib.sha256(client.token.encode()).hexdigest())
    with _lock:
        cached = _cache.get(key)
        if not refresh and cached:
            access = cached[1]
            if not access.valid_until or datetime.fromisoformat(access.valid_until.replace("Z", "+00:00")) > datetime.now(timezone.utc):
                return access
        if not refresh:
            return Access(source="pending")
    try:
        result = client.entitlement(account_id)
        access = Access(result["plan"], "verified", result.get("valid_until", "") if result["plan"] != "free" else "")
    except BillingError:
        access = Access(source="unavailable")
    with _lock:
        _cache[key] = (time.monotonic(), access)
    return access


def require_feature(account_id, feature):
    if not access_for(account_id).allows(feature):
        required, label = FEATURES[feature]
        raise UpgradeRequired(f"{label} thuộc gói {required.title()} trở lên. Chọn Nâng cấp để xem quyền lợi.")


def clear_access_cache():
    with _lock:
        _cache.clear()
