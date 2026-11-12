"""Monochrome plan comparison and server-confirmed checkout UI."""
import asyncio
import uuid
import flet as ft
from core.plans import PLANS, format_vnd, quote
from core.access import FEATURES, LEVELS, Access, access_for
from core.billing import BillingClient, BillingError


def build_locked(page, user, navigate, feature):
    required, label = FEATURES[feature]
    return ft.Column([
        ft.Icon(ft.Icons.LOCK_OUTLINE, size=30, color="#111111"),
        ft.Text(label, size=28, weight=ft.FontWeight.W_600),
        ft.Text("Tính năng này có trong gói Pro." if required == "pro" else f"Tính năng này có trong gói {required.title()} và Pro.", color="#666666"),
        ft.Row([ft.OutlinedButton("Xem các gói nâng cấp", icon=ft.Icons.ARROW_FORWARD, on_click=lambda e: navigate("plans"))]),
        ft.Text("Dữ liệu hiện có của bạn vẫn được giữ.", size=13, color="#666666"),
    ], spacing=20, expand=True)


def build_upgrade(page, user, navigate):
    cards = ft.Column(spacing=18, width=780, horizontal_alignment=ft.CrossAxisAlignment.STRETCH)
    cycle = ft.Dropdown(value="monthly", width=300, text_size=14, options=[
        ft.DropdownOption("monthly", "Theo tháng"), ft.DropdownOption("annual", "Theo năm · giảm 20%")])
    status = ft.Text(color="#666666")
    history = ft.Column(spacing=10)
    usage_text = ft.Text(size=13, color='#666666')
    busy = {"value": False}

    def render(update=True):
        current = access_for(user.id)
        status.value = f"Gói hiện tại: {current.plan.title()}"
        if current.source == 'owner':
            status.value += ' · Admin · Quyền chủ ứng dụng'
        if current.valid_until:
            status.value += ' · Hết hạn ' + current.valid_until[:10]
        if current.source in ("unavailable", "pending"):
            status.value += " · Chưa xác nhận được quyền trả phí, hãy kiểm tra kết nối"
        cards.controls = [ft.Container(padding=24, border=ft.Border.all(1, "#E8E8E8"), border_radius=8,
            content=ft.Column([
                ft.Text("Free", size=22, weight=ft.FontWeight.W_600),
                ft.Text("0đ", size=32, weight=ft.FontWeight.W_600),
                ft.Text("Công việc, việc con, lịch cố định, nhắc việc, báo cáo 7 ngày, sao lưu và Thùng rác.", color="#666666"),
                ft.Text("Đang sử dụng" if current.plan == "free" else "Có sẵn trong gói của bạn", size=13),
            ], spacing=10))]
        for plan in PLANS:
            annual = cycle.value == "annual"
            regular = plan.monthly_vnd * 12 if annual else plan.monthly_vnd
            offer = plan.annual_vnd if annual else plan.introductory_month_vnd
            features = [label for minimum, label in FEATURES.values() if minimum == plan.key]
            if plan.key == "pro":
                features.insert(0, "Toàn bộ chức năng của Free và Plus")
            else:
                features.insert(0, "Toàn bộ chức năng Free")
            already = LEVELS[current.plan] >= LEVELS[plan.key]
            cards.controls.append(ft.Container(padding=24, border=ft.Border.all(1, "#111111" if plan.key == "pro" else "#E8E8E8"), border_radius=8,
                content=ft.Column([
                    ft.Row([ft.Text(plan.name, size=22, weight=ft.FontWeight.W_600, expand=True),
                            ft.Text("Đầy đủ tính năng" if plan.key == "pro" else "Cho lịch học và công việc", size=12, color="#666666")]),
                    ft.Text(format_vnd(offer) + (" / năm" if annual else " / tháng đầu"), size=34, weight=ft.FontWeight.W_600),
                    ft.Text(format_vnd(regular) + (" / 12 tháng trước ưu đãi" if annual else " / tháng · giá gốc"), size=13, color="#666666",
                            style=ft.TextStyle(decoration=ft.TextDecoration.LINE_THROUGH)),
                    ft.Text("Tiết kiệm 20% khi thanh toán một năm." if annual else f"Ưu đãi mua lần đầu; từ tháng sau {format_vnd(plan.monthly_vnd)}/tháng.", size=13, color="#666666"),
                    ft.Column([ft.Row([ft.Icon(ft.Icons.CHECK, size=16, color="#111111"), ft.Text(label, size=14, expand=True)]) for label in features], spacing=8),
                    ft.Row([ft.OutlinedButton("Gia hạn " + plan.name if current.plan == plan.key and current.source == 'verified' else "Đang sử dụng" if current.plan == plan.key else "Đã bao gồm" if already else "Mua " + plan.name,
                        disabled=already and not (current.plan == plan.key and current.source == 'verified'), icon=ft.Icons.ARROW_FORWARD,
                        on_click=lambda e, key=plan.key, selected_cycle=cycle.value: navigate("checkout", plan=key, cycle=selected_cycle))]),
                ], spacing=13)))
        if update:
            page.update()

    async def refresh(_):
        if busy["value"]:
            return
        busy["value"] = True
        refresh_button.disabled = True
        status.value = "Đang kiểm tra gói…"
        page.update()
        try:
            await asyncio.to_thread(access_for, user.id, True)
            render()
        finally:
            busy["value"] = False
            refresh_button.disabled = False
            page.update()

    refresh_button = ft.TextButton("Kiểm tra gói đã mua", icon=ft.Icons.REFRESH, on_click=refresh)
    async def load_history(_):
        history_button.disabled = True
        history.controls = [ft.Text('Đang tải lịch sử…', size=13)]
        page.update()
        try:
            rows = await asyncio.to_thread(BillingClient().orders, user.id)
            history.controls = [ft.Row([
                ft.Text(row['plan'].title() + (' · năm' if row['cycle'] == 'annual' else ' · tháng'), expand=True),
                ft.Text(format_vnd(row['amount'])),
                ft.Text({'paid': 'Đã thanh toán', 'pending': 'Chờ thanh toán', 'failed': 'Thất bại', 'expired': 'Hết hạn', 'cancelled': 'Đã hủy'}.get(row['status'], row['status']), size=13),
                ft.TextButton('Mở đơn', visible=row['status'] == 'pending', on_click=lambda e, order=row: navigate('checkout', plan=order['plan'], cycle=order['cycle'], request_id=order['request_id'], payment_method=order['payment_method'])),
            ]) for row in rows] or [ft.Text('Chưa có giao dịch.', size=13, color='#666666')]
            from core.cloud import CloudClient
            usage = await asyncio.to_thread(CloudClient(user.id).request, 'GET', '/v1/ai/usage')
            usage_text.value = f"AI tháng {usage['period']}: {usage['used']}/{usage['limit']} lượt. Lượt lỗi không bị trừ."
        except ValueError as exc:
            history.controls = [ft.Text(str(exc), size=13, color='#666666')]
        finally:
            history_button.disabled = False
            page.update()
    history_button = ft.TextButton('Xem giao dịch và hạn mức AI', on_click=load_history)
    cycle.on_select = lambda e: render()
    render(False)
    return ft.Column([
        ft.Text("Nâng cấp", size=30, weight=ft.FontWeight.W_600),
        ft.Text("Chọn gói phù hợp. Pro mở toàn bộ chức năng.", color="#666666"),
        ft.Row([status, refresh_button], wrap=True), cycle, cards,
        ft.Text("Giá ưu đãi tháng áp dụng cho lần mua đầu tiên. Thanh toán năm giảm 20% trên giá chuẩn; không cộng thêm ưu đãi tháng đầu.", size=13, color="#666666"),
        ft.Text("Số tiền cuối cùng và quyền hưởng ưu đãi sẽ được xác nhận trước khi thanh toán.", size=13, color="#666666"),
        ft.Text('Hạn mức AI mặc định: Plus 300 lượt/tháng, Pro 1.500 lượt/tháng. Làm mới đầu tháng theo UTC.', size=13, color='#666666'),
        ft.Text('Gia hạn chủ động; ứng dụng không tự trừ tiền. Gia hạn cùng gói được cộng tiếp từ ngày hết hạn. Nâng lên Pro bắt đầu kỳ mới ngay khi thanh toán, không cộng dồn thời gian Plus.', size=13, color='#666666'),
        ft.Divider(color='#E8E8E8'), history_button, usage_text, history,
    ], spacing=18, scroll=ft.ScrollMode.AUTO, expand=True)


def build_checkout(page, user, navigate, plan_key, cycle, request_id=None, payment_method=None):
    plan = next((item for item in PLANS if item.key == plan_key), None)
    if plan is None or cycle not in ("monthly", "annual"):
        return ft.Text("Gói không hợp lệ. Hãy quay lại Nâng cấp.")
    estimate = quote(plan_key, cycle, first_purchase=True)
    method = ft.Dropdown(label="Phương thức thanh toán", value=payment_method if payment_method in ('visa', 'bank_qr') else "visa", width=360, options=[
        ft.DropdownOption("visa", "Thẻ Visa"), ft.DropdownOption("bank_qr", "QR ngân hàng")])
    message = ft.Text(selectable=True)
    detail = ft.Column(spacing=12)
    state = {"order": None, "busy": False, "request_id": request_id or str(uuid.uuid4())}
    launcher = ft.UrlLauncher()
    page.services.append(launcher)
    client = BillingClient()

    def busy(value):
        state["busy"] = value
        create.disabled = value or state["order"] is not None
        method.disabled = value or state["order"] is not None
        check.disabled = value or state["order"] is None
        page.update()

    def change_method(_):
        if state["order"] is None:
            state["request_id"] = str(uuid.uuid4())
    method.on_select = change_method

    async def open_card(_):
        try:
            await launcher.launch_url(state["order"]["checkout_url"])
        except Exception:
            message.value = "Không mở được trang thanh toán. Hãy thử lại."
            page.update()

    async def create_order(_):
        if state["busy"]:
            return
        if state["order"] is not None:
            message.value = "Đơn đã được tạo. Hãy kiểm tra trạng thái trước khi tạo đơn khác."
            page.update()
            return
        busy(True)
        message.value = "Đang tạo đơn…"
        page.update()
        try:
            order = await asyncio.to_thread(client.create_checkout, user.id, plan.key, cycle, method.value, state["request_id"])
            state["order"] = order
            detail.controls = [ft.Text("Số tiền được xác nhận: " + format_vnd(order["amount"]), size=22, weight=ft.FontWeight.W_600),
                               ft.Text("Mã đơn: " + order["order_id"], selectable=True)]
            if method.value == "visa":
                detail.controls.append(ft.OutlinedButton("Mở trang thanh toán Visa", icon=ft.Icons.OPEN_IN_NEW, on_click=open_card))
            else:
                qr_src = order.get('qr_image_url')
                if order.get('qr_payload'):
                    try:
                        import qrcode
                        import io
                        import base64
                        output = io.BytesIO()
                        qrcode.make(order['qr_payload']).save(output, format='PNG')
                        qr_src = base64.b64encode(output.getvalue()).decode()
                    except ImportError:
                        qr_src = None
                detail.controls.extend([
                    ft.Image(src=qr_src, width=240, height=240, fit=ft.BoxFit.CONTAIN) if qr_src else ft.Text('Mở trang ngân hàng bên dưới để quét mã QR.'),
                ])
                if order.get('account_number'):
                    detail.controls.extend([
                        ft.Text(order['bank_name'] + ' · ' + order['account_number'], selectable=True),
                        ft.Text('Chủ tài khoản: ' + order['account_name'], selectable=True),
                        ft.Text('Nội dung chuyển khoản: ' + order['transfer_reference'], selectable=True)])
                if order.get('checkout_url'):
                    detail.controls.append(ft.OutlinedButton('Mở trang QR ngân hàng', icon=ft.Icons.OPEN_IN_NEW, on_click=open_card))
            message.value = "Đơn đang chờ thanh toán. Gói chỉ được kích hoạt sau khi giao dịch được xác nhận."
            create.disabled = True
        except BillingError as exc:
            message.value = str(exc)
        finally:
            busy(False)
            create.disabled = state["order"] is not None
            page.update()

    async def check_order(_):
        if state["busy"] or state["order"] is None:
            return
        busy(True)
        message.value = "Đang kiểm tra thanh toán…"
        page.update()
        try:
            result = await asyncio.to_thread(client.order_status, user.id, state["order"]["order_id"])
            if result["status"] == "paid":
                state['order']['status'] = 'paid'
                for row in detail.controls:
                    if isinstance(row, ft.Row):
                        for button in row.controls:
                            button.disabled = True
                access = await asyncio.to_thread(access_for, user.id, True)
                message.value = "Thanh toán đã được xác nhận. Gói " + access.plan.title() + " đã hoạt động." if access.source == "verified" and access.plan == plan.key else "Đã nhận thanh toán; đang chờ xác nhận quyền sử dụng. Hãy kiểm tra lại."
            else:
                message.value = {"pending": "Chưa nhận được xác nhận thanh toán.", "failed": "Giao dịch chưa thành công.", "expired": "Đơn thanh toán đã hết hạn.", "cancelled": "Đơn thanh toán đã hủy."}[result["status"]]
                if result["status"] in ("failed", "expired", "cancelled"):
                    state["order"] = None
                    state["request_id"] = str(uuid.uuid4())
                    detail.controls.clear()
                    message.value += " Bạn có thể tạo đơn mới hoặc chọn phương thức khác."
        except BillingError as exc:
            message.value = str(exc)
        finally:
            busy(False)

    create = ft.OutlinedButton("Tạo đơn thanh toán", icon=ft.Icons.LOCK_OUTLINE, on_click=create_order)
    check = ft.TextButton("Kiểm tra thanh toán", icon=ft.Icons.REFRESH, on_click=check_order, disabled=True)
    return ft.Column([
        ft.Row([ft.TextButton("Nâng cấp", icon=ft.Icons.ARROW_BACK, on_click=lambda e: navigate("plans"))]),
        ft.Text("Mua " + plan.name, size=30, weight=ft.FontWeight.W_600),
        ft.Text("Theo năm" if cycle == "annual" else "Theo tháng", color="#666666"),
        ft.Text(format_vnd(estimate["amount"]) + (" / năm" if cycle == "annual" else " / tháng đầu"), size=32, weight=ft.FontWeight.W_600),
        ft.Text("Giá dự kiến nếu đủ điều kiện ưu đãi. Số tiền chính thức sẽ hiện trên đơn trước khi bạn trả tiền.", size=13, color="#666666"),
        method, ft.Row([create, check], wrap=True), message, detail,
        ft.Text("Không nhập số thẻ, mã CVV hoặc OTP trong TaskFlow. Với Visa, thông tin thẻ được nhập trên trang của cổng thanh toán.", size=13, color="#666666"),
    ], spacing=18, expand=True, scroll=ft.ScrollMode.AUTO)
