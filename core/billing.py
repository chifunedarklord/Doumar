"""Desktop adapter for an authenticated billing service, not a payment processor.

    Merchant secrets and payment confirmation belong to the service. No local
    payment button, bank transfer screenshot or return URL grants an entitlement.
"""
import json
import os
import uuid
from urllib.parse import urlsplit, quote as urlquote
from urllib.request import Request, urlopen, build_opener, HTTPRedirectHandler
from urllib.error import URLError, HTTPError
from datetime import datetime, timezone


class BillingError(ValueError):
    pass


def https_url(value):
    parts = urlsplit(value if isinstance(value, str) else "")
    if parts.scheme != "https" or not parts.hostname or parts.username or parts.password:
        raise BillingError("Địa chỉ thanh toán không hợp lệ.")
    return value


class NoRedirect(HTTPRedirectHandler):
    def redirect_request(self, req, fp, code, msg, headers, newurl):
        return None


class BillingClient:
    def __init__(self, base_url=None, access_token=None):
        self.base_url = (base_url if base_url is not None else os.getenv("TASKFLOW_API_URL", "")).rstrip("/")
        self.token = access_token if access_token is not None else os.getenv("TASKFLOW_ACCESS_TOKEN", "")
        if access_token is None:
            from core.cloud import session_for
            session = session_for()
            if session.get('url') == self.base_url:
                self.token = session.get('token', '')

    @property
    def configured(self):
        return bool(self.base_url and self.token)

    def _request(self, method, path, payload=None):
        if not self.configured:
            raise BillingError("Thanh toán chưa được kết nối. Cần máy chủ và tài khoản thanh toán của nhà phát hành.")
        from core.cloud import validate_api_url, CloudError
        try:
            validate_api_url(self.base_url)
        except CloudError as exc:
            raise BillingError(str(exc)) from exc
        data = json.dumps(payload).encode() if payload is not None else None
        request = Request(self.base_url + path, data=data, method=method,
                          headers={"Authorization": "Bearer " + self.token, "Accept": "application/json", "Content-Type": "application/json"})
        try:
            # Reject redirects rather than forwarding an account bearer token.
            with build_opener(NoRedirect()).open(request, timeout=12) as response:
                content = response.read(1_048_577)
                if len(content) > 1_048_576:
                    raise BillingError("Phản hồi thanh toán quá lớn.")
                result = json.loads(content)
                if not isinstance(result, dict):
                    raise BillingError("Phản hồi thanh toán không hợp lệ.")
                return result
        except (URLError, HTTPError, OSError, UnicodeError, json.JSONDecodeError) as exc:
            raise BillingError("Không kết nối được dịch vụ thanh toán. Hãy thử lại sau.") from exc

    def entitlement(self, account_id):
        result = self._request("GET", "/v1/billing/entitlement")
        if result.get("demo") or result.get("account_id") != account_id or result.get("plan") not in ("free", "plus", "pro"):
            raise BillingError("Quyền sử dụng không khớp với tài khoản này.")
        if result["plan"] != "free":
            try:
                expires = datetime.fromisoformat(result["valid_until"].replace("Z", "+00:00"))
                if expires.tzinfo is None or expires <= datetime.now(timezone.utc):
                    raise ValueError("Expired")
            except (KeyError, ValueError, TypeError) as exc:
                raise BillingError("Gói trả phí đã hết hạn hoặc chưa được xác nhận.") from exc
        return result

    def create_checkout(self, account_id, plan, cycle, method, request_id=None):
        if plan not in ("plus", "pro") or cycle not in ("monthly", "annual") or method not in ("visa", "bank_qr"):
            raise BillingError("Gói hoặc phương thức thanh toán không hợp lệ.")
        # The server computes the price and promotion eligibility; the client
        # deliberately does not send an amount or a first-purchase claim.
        result = self._request("POST", "/v1/billing/checkouts", {
            "plan": plan, "cycle": cycle, "payment_method": method,
            "request_id": request_id or str(uuid.uuid4()),
        })
        if result.get("account_id") != account_id or result.get("plan") != plan or result.get("cycle") != cycle or result.get("payment_method") != method or not isinstance(result.get("order_id"), str) or not 1 <= len(result["order_id"]) <= 200:
            raise BillingError("Đơn thanh toán không khớp yêu cầu.")
        if result.get("currency") != "VND" or type(result.get("amount")) is not int or result["amount"] <= 0:
            raise BillingError("Số tiền thanh toán không hợp lệ.")
        if result.get('demo'):
            raise BillingError('Dịch vụ thanh toán chưa được cấu hình cho bản chính thức.')
        if method == "visa":
            https_url(result.get("checkout_url"))
        else:
            if result.get('hosted_qr') is True:
                https_url(result.get('checkout_url'))
            elif result.get('qr_payload'):
                if not isinstance(result['qr_payload'], str) or len(result['qr_payload']) > 4000:
                    raise BillingError('Mã QR không hợp lệ.')
                https_url(result.get('checkout_url'))
            else:
                https_url(result.get("qr_image_url"))
            for key in (() if result.get('hosted_qr') is True else ("bank_name", "account_number", "account_name", "transfer_reference")):
                if not isinstance(result.get(key), str) or not result[key].strip():
                    raise BillingError("Thiếu thông tin nhận chuyển khoản.")
        return result

    def order_status(self, account_id, order_id):
        result = self._request("GET", "/v1/billing/checkouts/" + urlquote(order_id, safe=""))
        if result.get("account_id") != account_id or result.get("order_id") != order_id or result.get("status") not in ("pending", "paid", "failed", "expired", "cancelled"):
            raise BillingError("Trạng thái giao dịch không hợp lệ.")
        return result

    def orders(self, account_id):
        result = self._request('GET', '/v1/billing/orders')
        if not isinstance(result.get('orders'), list) or any(row.get('account_id') != account_id for row in result['orders']):
            raise BillingError('Lịch sử thanh toán không khớp tài khoản.')
        for row in result['orders']:
            if row.get('checkout_url'):
                https_url(row['checkout_url'])
        return result['orders']
