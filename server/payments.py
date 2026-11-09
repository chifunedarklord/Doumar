"""Payment providers stay server-side. No configured provider means no checkout."""
import hashlib
import hmac
import json
import os
import time
from urllib.parse import urlencode
from urllib.request import Request, build_opener
from core.billing import NoRedirect, https_url


def configured(method):
    if not os.getenv('TASKFLOW_PUBLIC_URL'):
        return False
    if method == 'visa':
        return bool(os.getenv('STRIPE_SECRET_KEY') and os.getenv('STRIPE_WEBHOOK_SECRET'))
    return all(os.getenv(key) for key in ('PAYOS_CLIENT_ID', 'PAYOS_API_KEY', 'PAYOS_CHECKSUM_KEY'))


def request(url, headers, data):
    with build_opener(NoRedirect()).open(Request(url, headers=headers, data=data), timeout=20) as response:
        raw = response.read(1048577)
        if len(raw) > 1048576:
            raise ValueError('Phản hồi cổng thanh toán quá lớn.')
        return json.loads(raw)


def create(order):
    """Hosted Visa payment for one month/year; renewal is explicit, never auto-debited."""
    if order['method'] == 'bank_qr':
        return create_payos(order)
    key = os.getenv('STRIPE_SECRET_KEY', '')
    if order['method'] != 'visa' or not key or not os.getenv('STRIPE_WEBHOOK_SECRET'):
        raise ValueError('Phương thức này chưa được kết nối. Chưa có tiền nào được thu.')
    public = https_url(os.getenv('TASKFLOW_PUBLIC_URL', '')).rstrip('/')
    fields = {'mode': 'payment', 'client_reference_id': order['id'],
              'success_url': public + '/payment-return', 'cancel_url': public + '/payment-return',
              'line_items[0][price_data][currency]': 'vnd',
              'line_items[0][price_data][unit_amount]': order['amount'],
              'line_items[0][price_data][product_data][name]': 'TaskFlow ' + order['plan'].title(),
              'line_items[0][quantity]': 1}
    result = request('https://api.stripe.com/v1/checkout/sessions',
                     {'Authorization': 'Bearer ' + key, 'Idempotency-Key': order['id'],
                      'Content-Type': 'application/x-www-form-urlencoded'}, urlencode(fields).encode())
    return {'provider': result['id'], 'checkout_url': https_url(result['url'])}


def payos_signature(data):
    def value(item):
        if item is None or item in ('null', 'undefined'):
            return ''
        if isinstance(item, (list, dict)):
            return json.dumps(item, sort_keys=True, ensure_ascii=False, separators=(',', ':'))
        if isinstance(item, bool):
            return str(item).lower()
        return str(item)
    message = '&'.join(key + '=' + value(data[key]) for key in sorted(data))
    return hmac.new(os.environ['PAYOS_CHECKSUM_KEY'].encode(), message.encode(), hashlib.sha256).hexdigest()


def create_payos(order):
    import uuid
    # A deterministic 50-bit code fits JavaScript's exact integer range and
    # remains stable across retries of the same order.
    code = int(uuid.UUID(order['id'])) % (2 ** 50)
    public = https_url(os.getenv('TASKFLOW_PUBLIC_URL', '')).rstrip('/')
    payload = {'orderCode': code, 'amount': order['amount'], 'description': 'TF' + str(code)[-7:],
               'returnUrl': public + '/payment-return', 'cancelUrl': public + '/payment-return'}
    payload['signature'] = payos_signature(payload)
    headers = {'x-client-id': os.environ['PAYOS_CLIENT_ID'], 'x-api-key': os.environ['PAYOS_API_KEY'], 'Content-Type': 'application/json'}
    result = request('https://api-merchant.payos.vn/v2/payment-requests', headers, json.dumps(payload).encode())
    if result.get('code') != '00':
        # A lost response can leave a real provider order behind. Retrieve the
        # same deterministic order instead of creating another charge.
        result = request('https://api-merchant.payos.vn/v2/payment-requests/' + str(code), headers, None)
        if result.get('code') != '00':
            raise ValueError('Không tạo được đơn payOS.')
    details = result['data']
    if not hmac.compare_digest(payos_signature(details), result.get('signature', '')) or details['amount'] != order['amount'] or details['orderCode'] != code:
        raise ValueError('Đơn payOS không hợp lệ.')
    if details.get('id') and not details.get('paymentLinkId'):
        from urllib.parse import quote
        return {'provider': details['id'], 'checkout_url': 'https://pay.payos.vn/web/' + quote(details['id'], safe=''),
                'hosted_qr': True, 'provider_order_code': code}
    return {'provider': details['paymentLinkId'], 'checkout_url': https_url(details['checkoutUrl']),
            'qr_payload': details['qrCode'], 'bank_name': str(details['bin']),
            'account_number': details['accountNumber'], 'account_name': details['accountName'],
            'transfer_reference': details['description'], 'provider_order_code': code}


def verified_payos_event(raw):
    if not os.getenv('PAYOS_CHECKSUM_KEY'):
        raise ValueError('Webhook chưa được cấu hình.')
    event = json.loads(raw)
    if not hmac.compare_digest(payos_signature(event['data']), event.get('signature', '')):
        raise ValueError('Chữ ký payOS không hợp lệ.')
    return event['data']


def status(order):
    """Reconcile a specific merchant order if a webhook was delayed or lost."""
    from urllib.parse import quote
    if order['method'] == 'visa':
        result = request('https://api.stripe.com/v1/checkout/sessions/' + quote(order['provider'], safe=''),
                         {'Authorization': 'Bearer ' + os.environ['STRIPE_SECRET_KEY']}, None)
        if result['id'] != order['provider'] or result['client_reference_id'] != order['id'] or result['amount_total'] != order['amount'] or result['currency'].lower() != 'vnd':
            raise ValueError('Đơn thẻ không khớp.')
        return 'paid' if result['payment_status'] == 'paid' else 'expired' if result['status'] == 'expired' else 'pending'
    code = json.loads(order['details'])['provider_order_code']
    result = request('https://api-merchant.payos.vn/v2/payment-requests/' + str(code),
                     {'x-client-id': os.environ['PAYOS_CLIENT_ID'], 'x-api-key': os.environ['PAYOS_API_KEY']}, None)
    data = result['data']
    if result.get('code') != '00' or not hmac.compare_digest(payos_signature(data), result.get('signature', '')) or data['id'] != order['provider'] or data['amount'] != order['amount'] or data['orderCode'] != code:
        raise ValueError('Đơn QR không khớp.')
    if data['status'] == 'PAID' and data['amountPaid'] >= order['amount']:
        return 'paid'
    return {'CANCELLED': 'cancelled', 'EXPIRED': 'expired'}.get(data['status'], 'pending')


def verified_stripe_event(raw, signature):
    secret = os.getenv('STRIPE_WEBHOOK_SECRET', '')
    if not secret:
        raise ValueError('Webhook chưa được cấu hình.')
    fields = [item.split('=', 1) for item in signature.split(',') if '=' in item]
    timestamp = next((v for k, v in fields if k == 't'), '')
    if abs(time.time() - int(timestamp)) > 300:
        raise ValueError('Webhook hết hạn.')
    expected = hmac.new(secret.encode(), timestamp.encode() + b'.' + raw, hashlib.sha256).hexdigest()
    if not any(k == 'v1' and hmac.compare_digest(expected, v) for k, v in fields):
        raise ValueError('Chữ ký webhook không hợp lệ.')
    return json.loads(raw)
