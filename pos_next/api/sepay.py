# -*- coding: utf-8 -*-
# Copyright (c) 2025, BrainWise and contributors
# SePay payment gateway integration for POS Next
# Docs: https://developer.sepay.vn/vi/sepay-webhooks/tich-hop-webhook
#       https://sepay.vn/lap-trinh-cong-thanh-toan.html

from __future__ import unicode_literals
import hashlib
import hmac
import re
import json
import time
import frappe
from frappe import _
from frappe.utils import flt, cint, now
from werkzeug.wrappers import Response


# VietQR base URL (SePay)
VIETQR_BASE = "https://qr.sepay.vn/img"
BANKS_JSON_URL = "https://qr.sepay.vn/banks.json"

# Order code prefix - must match SePay "Cấu trúc mã thanh toán" config
ORDER_PREFIX = "DH"

# Chữ ký webhook (HMAC-SHA256) chỉ nhận trong khoảng này quanh giờ máy chủ — chặn gửi lại request cũ.
WEBHOOK_MAX_AGE_SECONDS = 300

# Chuyển khoản luôn là số đồng chẵn, còn số nợ có thể lẻ (site tắt làm tròn, 2 số lẻ): QR in phần
# nguyên (`get_vietqr_url`), nên số về lệch dưới một đồng vẫn coi là trả đủ.
AMOUNT_TOLERANCE = 1


@frappe.whitelist()
def get_sepay_banks():
	"""
	Fetch bank list from SePay/VietQR for Bank Code dropdown.
	Source: https://qr.sepay.vn/banks.json
	"""
	try:
		import urllib.request
		with urllib.request.urlopen(BANKS_JSON_URL, timeout=10) as resp:
			data = json.loads(resp.read().decode())
		banks = data.get("data") or []
		# Return short_name (used in VietQR URL) and display label
		return [
			{"value": b.get("short_name") or b.get("code", ""), "label": f"{b.get('short_name', '')} - {b.get('name', '')}"}
			for b in banks
			if b.get("short_name") or b.get("code")
		]
	except Exception as e:
		frappe.log_error(f"SePay get_sepay_banks: {e}", "SePay Banks")
		# Fallback common banks
		return [
			{"value": "MBBank", "label": "MBBank - Ngân hàng TMCP Quân đội"},
			{"value": "Vietcombank", "label": "Vietcombank - Ngân hàng TMCP Ngoại Thương"},
			{"value": "VietinBank", "label": "VietinBank - Ngân hàng TMCP Công thương"},
			{"value": "BIDV", "label": "BIDV - Ngân hàng TMCP Đầu tư và Phát triển"},
			{"value": "Techcombank", "label": "Techcombank - Ngân hàng TMCP Kỹ thương"},
			{"value": "VPBank", "label": "VPBank - Ngân hàng TMCP Việt Nam Thịnh Vượng"},
			{"value": "ACB", "label": "ACB - Ngân hàng TMCP Á Châu"},
			{"value": "Agribank", "label": "Agribank - Ngân hàng Nông nghiệp và Phát triển Nông thôn"},
		]


def _get_sepay_settings(pos_profile=None):
	"""Get SePay config from POS Profile. Returns dict or None if disabled."""
	if not pos_profile:
		return None

	# Fetch fields - support both naming conventions (custom_field may vary)
	doc = frappe.get_cached_doc("POS Profile", pos_profile)
	# Check enable: payment_gateway==SePay + checkbox, or just checkbox if no payment_gateway
	payment_gateway = doc.get("payment_gateway")
	enable_check = cint(
		doc.get("enable_bank_transfer_check")
	)
	if payment_gateway is not None and payment_gateway != "SePay":
		return None
	if not enable_check:
		return None

	bank_account = doc.get("bank_account_number")
	bank_code = doc.get("bank_code")
	account_holder = doc.get("account_holder_name") or ""
	# Hình thức thanh toán ghi khoản chuyển khoản SePay — khai rõ ở POS Profile. Bản cũ đoán theo tên
	# ("chuyển", "transfer"…) nên "Chuyển khoản VNPay" cũng bật QR SePay.
	mode_of_payment = doc.get("sepay_mode_of_payment")
	if not bank_account or not bank_code or not mode_of_payment:
		return None

	return frappe._dict(
		sepay_bank_account=bank_account,
		sepay_bank_code=bank_code,
		sepay_account_holder=account_holder,
		mode_of_payment=mode_of_payment,
	)


def validate_pos_profile_sepay(doc, method=None):
	"""POS Profile `validate`: hình thức SePay phải nằm trong bảng Payment Methods của chính điểm bán.

	Chọn hình thức ngoài bảng thì màn thanh toán không có hình thức đó (không bao giờ bật QR), trong khi
	tiền chuyển khoản về vẫn ghi vào nó — đóng ca không đối chiếu được. Chỉ kiểm khi SePay đang bật:
	ô bị ẩn (gateway khác, bỏ tick) thì giá trị cũ không chặn lưu.
	"""
	if doc.get("payment_gateway") != "SePay" or not cint(doc.get("enable_bank_transfer_check")):
		return
	mode = doc.get("sepay_mode_of_payment")
	if not mode:
		return
	if mode not in {row.mode_of_payment for row in doc.get("payments") or []}:
		frappe.throw(
			_("SePay Mode of Payment {0} is not in this POS Profile's Payment Methods.").format(frappe.bold(mode)),
			title=_("SePay"),
		)


def _webhook_secret(pos_profile):
	"""Khoá HMAC-SHA256 của webhook SePay khai ở POS Profile, `None` khi chưa khai."""
	if not pos_profile:
		return None
	doc = frappe.get_cached_doc("POS Profile", pos_profile)
	return doc.get_password("sepay_webhook_secret", raise_exception=False) or None


def mark_sepay_methods(payment_methods, pos_profile):
	"""Gắn `is_sepay` cho đúng hình thức SePay của POS Profile — màn thanh toán bật QR theo cờ này."""
	settings = _get_sepay_settings(pos_profile)
	for m in payment_methods:
		m["is_sepay"] = bool(settings) and m.get("mode_of_payment") == settings.mode_of_payment
	return payment_methods


@frappe.whitelist()
def get_vietqr_url(pos_profile, amount, invoice_id=None, template="compact"):
	"""
	Get VietQR image URL for bank transfer payment.

	Args:
		pos_profile: POS Profile name
		amount: Amount in VND (number)
		invoice_id: Invoice name or ID for content (e.g. SINV-00001 -> DH1 or invoice number)
		template: "compact", "qronly", or empty

	Returns:
		dict: { qr_url, account_number, bank_code, account_holder, amount, content }
	"""
	settings = _get_sepay_settings(pos_profile)
	if not settings:
		return {"enabled": False, "message": _("SePay is not configured for this POS Profile")}

	# Hoá đơn đã có trên máy chủ: QR thu đúng số còn nợ máy chủ đang ghi — webhook so số tiền về với
	# chính số này. `amount` của máy bán chỉ dùng khi chưa có hoá đơn.
	if invoice_id and frappe.db.exists("Sales Invoice", invoice_id):
		docstatus, outstanding = frappe.db.get_value(
			"Sales Invoice", invoice_id, ["docstatus", "outstanding_amount"]
		)
		if docstatus < 2 and flt(outstanding) > 0:
			amount = outstanding

	amount_int = int(flt(amount))
	# Content: DH + invoice number. SePay matches this for webhook.
	# Use numeric part of invoice for short content (e.g. SINV-00001 -> 1)
	if invoice_id:
		match = re.search(r"(\d+)$", str(invoice_id))
		content = f"{ORDER_PREFIX}{match.group(1) if match else invoice_id}"
	else:
		content = ""

	params = {
		"acc": settings.sepay_bank_account,
		"bank": settings.sepay_bank_code,
		"amount": amount_int,
		"des": content,
		"template": template or "compact",
	}
	query = "&".join(f"{k}={v}" for k, v in params.items() if v is not None and v != "")
	qr_url = f"{VIETQR_BASE}?{query}"

	return {
		"enabled": True,
		"qr_url": qr_url,
		"account_number": settings.sepay_bank_account,
		"bank_code": settings.sepay_bank_code,
		"account_holder": settings.sepay_account_holder or "",
		"amount": amount_int,
		"content": content,
	}


@frappe.whitelist()
def check_sepay_payment_status(invoice_name):
	"""
	Check if an invoice has been paid (for polling from frontend).

	Returns:
		dict: { paid: bool, invoice_name, outstanding_amount }
	"""
	if not invoice_name:
		return {"paid": False, "message": _("Invoice name is required")}

	if not frappe.db.exists("Sales Invoice", invoice_name):
		return {"paid": False, "message": _("Invoice not found")}

	doc = frappe.get_doc("Sales Invoice", invoice_name)
	outstanding = flt(doc.outstanding_amount, 2)

	return {
		"paid": outstanding <= 0 and doc.docstatus == 1,
		"invoice_name": invoice_name,
		"docstatus": doc.docstatus,
		"outstanding_amount": outstanding,
		"grand_total": doc.grand_total,
	}


@frappe.whitelist()
def manual_confirm_sepay_payment(invoice_name):
	"""
	Manually confirm bank transfer payment and submit the draft invoice.

	Use when webhook cannot reach your server (e.g. localhost) or for testing.
	Only call after you have verified the transfer was received.
	"""
	if not invoice_name:
		return {"success": False, "message": _("Invoice name is required")}

	if not frappe.db.exists("Sales Invoice", invoice_name):
		return {"success": False, "message": _("Invoice not found")}

	doc = frappe.get_doc("Sales Invoice", invoice_name)
	if doc.docstatus == 2:
		return {"success": False, "message": _("Invoice is cancelled")}
	if doc.docstatus == 1 and flt(doc.outstanding_amount, 2) <= 0:
		return {"success": True, "paid": True, "message": _("Invoice already submitted")}

	settings = _get_sepay_settings(doc.pos_profile)
	if not settings:
		return {"success": False, "message": _("SePay is not configured for this POS Profile")}

	try:
		if doc.docstatus == 0:
			# Hoá đơn nháp của luồng PWA: chốt rồi mới thu.
			doc.flags.ignore_permissions = True
			frappe.flags.ignore_account_permission = True
			doc.submit()

		# Thu đúng số CÒN NỢ, không phải tổng hoá đơn: trả trộn (tiền mặt + chuyển khoản) thì hoá đơn đã
		# có khoản tiền mặt — bản cũ ghi cả tổng, phiếu thu vượt số nợ nên bị từ chối sau khi hoá đơn đã
		# chốt, hoá đơn treo nợ.
		outstanding = flt(frappe.db.get_value("Sales Invoice", invoice_name, "outstanding_amount"), 2)
		if outstanding <= 0:
			return {"success": True, "paid": True, "invoice_name": invoice_name}

		from pos_next.api.partial_payments import create_payment_entry

		create_payment_entry(
			invoice_name=invoice_name,
			amount=outstanding,
			mode_of_payment=settings.mode_of_payment,
			remarks="SePay manual confirmation",
		)
		return {"success": True, "paid": True, "invoice_name": invoice_name}
	except Exception as e:
		frappe.log_error(frappe.get_traceback(), "SePay Manual Confirm")
		return {"success": False, "message": str(e)}


@frappe.whitelist(allow_guest=True, methods=["POST"])
def receive_webhook():
	"""
	Receive SePay webhook when a bank transfer is detected.

	SePay sends POST with JSON body. We must return exactly {"success": true} with HTTP 200/201,
	otherwise SePay retries.

	**Xác thực bằng HMAC-SHA256** (trang SePay: webhook → Bảo mật → HMAC-SHA256), khoá khai ở
	POS Profile (`sepay_webhook_secret`). SePay gửi `X-SePay-Signature: sha256=<hex>` và
	`X-SePay-Timestamp`, ký trên `{timestamp}.{raw body}`. Không dùng kiểu "API Key": SePay gửi nó
	trong header `Authorization: Apikey …`, mà Frappe gặp header Authorization không đăng nhập được
	thì trả 401 trước khi tới đây (`frappe.auth.validate_auth`).

	Request không có chữ ký đúng thì trả 401 — SePay gửi lại theo lịch retry, nên khai khoá muộn
	vẫn nhận lại được giao dịch trong thời gian retry.

	Webhook payload fields (from SePay docs):
	- id: SePay transaction ID
	- gateway: Bank name
	- transactionDate: datetime
	- accountNumber: Bank account
	- code: Payment code (from content, can be null)
	- content: Transfer content
	- transferType: "in" | "out"
	- transferAmount: Amount (VND)
	- accumulated: Balance
	- subAccount: VA if any
	- referenceCode: Reference
	- description: Full SMS content
	"""
	raw = frappe.request.get_data() or b""
	try:
		data = json.loads(raw) if raw else {}
	except Exception as e:
		frappe.log_error(f"SePay webhook parse error: {e}\nRaw: {raw[:2000]!r}", "SePay Webhook")
		return _webhook_reply()
	if not isinstance(data, dict):
		return _webhook_reply()

	# Chỉ tiền VÀO. Bản cũ không dừng ở đây (gán kết quả rồi chạy tiếp), nên giao dịch tiền RA có
	# nội dung DH… đúng số tiền cũng được ghi là khách đã trả.
	if data.get("transferType") != "in":
		return _webhook_reply()

	content = (data.get("content") or "").strip()
	amount = flt(data.get("transferAmount") or 0)
	sepay_id = data.get("id")
	reference_code = data.get("referenceCode") or ""

	# Extract order/invoice ID from content (e.g. DH123 -> 123)
	order_id = _extract_order_id(content)
	if not order_id:
		# Chuyển khoản không phải của POS (không có mã DH…) — bình thường, không ghi lỗi.
		return _webhook_reply()

	invoice_name = _resolve_invoice_name(order_id)
	if not invoice_name:
		frappe.log_error(
			f"SePay webhook: Invoice not found for order_id={order_id}",
			"SePay Webhook"
		)
		return _webhook_reply()

	pos_profile = frappe.db.get_value("Sales Invoice", invoice_name, "pos_profile")
	secret = _webhook_secret(pos_profile)
	if not secret:
		frappe.log_error(
			f"SePay webhook: POS Profile {pos_profile} chưa khai khoá webhook (sepay_webhook_secret). "
			f"Giao dịch {sepay_id} cho {invoice_name} chưa được ghi.",
			"SePay Webhook"
		)
		return _webhook_reply(status=401)
	problem = _signature_problem(
		raw,
		secret,
		frappe.get_request_header("X-SePay-Signature") or "",
		frappe.get_request_header("X-SePay-Timestamp") or "",
	)
	if problem:
		frappe.log_error(
			f"SePay webhook: chữ ký không hợp lệ ({problem}). Hoá đơn {invoice_name}, giao dịch {sepay_id}.",
			"SePay Webhook"
		)
		return _webhook_reply(status=401)

	# Deduplication: check if we already processed this SePay transaction
	if sepay_id and _is_sepay_transaction_processed(sepay_id):
		return _webhook_reply()

	# Process payment (run as Administrator - webhook is allow_guest, needs elevated permissions)
	try:
		old_user = frappe.session.user
		frappe.set_user("Administrator")
		frappe.flags.ignore_permissions = True
		frappe.flags.ignore_account_permission = True
		try:
			_process_sepay_payment(
				invoice_name=invoice_name,
				amount=amount,
				sepay_id=sepay_id,
				reference_code=reference_code,
				data=data,
			)
		finally:
			frappe.set_user(old_user)

	except Exception as e:
		frappe.log_error(
			f"SePay webhook process error: {e}\nInvoice: {invoice_name}\nData: {data}",
			"SePay Webhook"
		)

	return _webhook_reply()


def _webhook_reply(status=200):
	"""Câu trả lời cho SePay: body đúng `{"success": true}` (Frappe bọc kết quả thường vào `message`)."""
	body = json.dumps({"success": status in (200, 201)})
	return Response(body, status=status, mimetype="application/json")


def _signature_problem(raw, secret, signature, timestamp):
	"""Lý do chữ ký HMAC-SHA256 của SePay không hợp lệ, `None` khi hợp lệ."""
	if not signature or not timestamp:
		return "thiếu X-SePay-Signature / X-SePay-Timestamp"
	try:
		signed_at = int(timestamp)
	except ValueError:
		return "X-SePay-Timestamp không phải số"
	if abs(time.time() - signed_at) > WEBHOOK_MAX_AGE_SECONDS:
		return f"ký lúc {signed_at}, lệch giờ máy chủ quá {WEBHOOK_MAX_AGE_SECONDS} giây"
	expected = "sha256=" + hmac.new(
		secret.encode(), f"{signed_at}.".encode() + raw, hashlib.sha256
	).hexdigest()
	if not hmac.compare_digest(expected, signature.strip()):
		return "sai chữ ký"
	return None


def _is_sepay_transaction_processed(sepay_id):
	"""Check if we already processed this SePay transaction (deduplication)."""
	if not frappe.db.table_exists("SePay Transaction Log"):
		return False
	return frappe.db.exists("SePay Transaction Log", {"sepay_transaction_id": sepay_id})


def _extract_order_id(content):
	"""Extract order/invoice ID from transfer content. Supports DH123, DH-SINV-00001, etc."""
	if not content:
		return None
	# Match DH + digits or DH + alphanumeric
	m = re.search(rf"{re.escape(ORDER_PREFIX)}([\w\-]+)", content, re.IGNORECASE)
	return m.group(1) if m else None


def _resolve_invoice_name(order_id):
	"""Resolve order_id to Sales Invoice name."""
	# If it looks like full invoice name
	if str(order_id).upper().startswith("SINV-"):
		if frappe.db.exists("Sales Invoice", order_id):
			return order_id
		return None

	# Numeric: could be auto-increment or short form
	if str(order_id).isdigit():
		# Try SINV-00001 style (pad to 5 digits)
		candidates = [
			f"SINV-{int(order_id):05d}",
			f"SINV-{order_id}",
			order_id,
		]
		for name in candidates:
			if frappe.db.exists("Sales Invoice", name):
				return name

	# Mã trong nội dung là phần số CUỐI của tên hoá đơn (`get_vietqr_url`): so đuôi tên, bỏ phiếu trả
	# và hoá đơn đã huỷ, ưu tiên hoá đơn còn nợ. Bản cũ so "chứa" trên mọi hoá đơn — "00103" khớp cả
	# ACC-SINV-2025-00103 lẫn phiếu trả, lấy cái mới nhất. Hoá đơn đã trả vẫn tìm ra để SePay gửi lại
	# giao dịch cũ thì đi vào nhánh "đã trả" (`_process_sepay_payment`), không ghi lỗi.
	filters = {"name": ["like", f"%-{order_id}"], "docstatus": ["<", 2], "is_return": 0}
	return frappe.db.get_value(
		"Sales Invoice", {**filters, "outstanding_amount": [">", 0]}, "name", order_by="creation desc"
	) or frappe.db.get_value("Sales Invoice", filters, "name", order_by="creation desc")


def _process_sepay_payment(invoice_name, amount, sepay_id, reference_code, data):
	"""
	Process incoming SePay payment: add payment to invoice and submit if draft.

	Uses Payment Entry flow (submit invoice first, then add payment) to avoid
	GL merge issues where receivable debit+credit can cancel to zero.
	"""
	doc = frappe.get_doc("Sales Invoice", invoice_name)

	# Already submitted and paid - skip (deduplication)
	if doc.docstatus == 1 and flt(doc.outstanding_amount, 2) <= 0:
		return

	settings = _get_sepay_settings(doc.pos_profile)
	if not settings:
		frappe.log_error(
			f"SePay webhook: POS Profile {doc.pos_profile} của {invoice_name} không bật / chưa khai đủ SePay",
			"SePay Webhook"
		)
		return

	# Validate amount: must match outstanding (supports mixed payments: cash + bank transfer). Lệch
	# dưới một đồng (số nợ lẻ, QR in phần nguyên) thì ghi đúng số nợ cho hoá đơn hết nợ.
	outstanding = flt(doc.outstanding_amount, 2)
	if abs(flt(amount, 2) - outstanding) >= AMOUNT_TOLERANCE:
		frappe.log_error(
			f"SePay amount mismatch: invoice={invoice_name} outstanding={outstanding} got={amount}",
			"SePay Webhook"
		)
		return
	amount = outstanding
	mode_of_payment = settings.mode_of_payment

	if doc.docstatus == 0:
		# Step 1: Submit draft WITHOUT payment (avoids GL merge zero-amount issue)
		doc.flags.ignore_permissions = True
		frappe.flags.ignore_account_permission = True
		doc.submit()
		frappe.db.commit()  # Ensure submit is committed before Payment Entry

	# Step 2: Add payment via Sales Invoice Payment + direct GL entries (like POS, no Payment Entry)
	_add_sepay_payment_direct(
		doc, amount, mode_of_payment,
		reference_no=reference_code or str(sepay_id),
		transaction_id=sepay_id,
	)

	# Log for deduplication and audit
	_log_sepay_transaction(
		sepay_id=sepay_id,
		invoice_name=invoice_name,
		amount=amount,
		reference_code=reference_code,
		data=data,
	)


def _add_sepay_payment_direct(doc, amount, mode_of_payment, reference_no, transaction_id=None):
	"""
	Add Chuyển khoản payment via Sales Invoice Payment + direct GL entries (like POS).
	No Payment Entry - GL entries are created directly against Sales Invoice.
	"""
	from erpnext.accounts.utils import get_account_currency, update_voucher_outstanding
	from erpnext.accounts.general_ledger import make_gl_entries

	invoice_name = doc.name
	company = doc.company
	conversion_rate = flt(doc.conversion_rate) or 1
	precision = doc.precision("base_paid_amount")
	base_amount = flt(amount * conversion_rate, precision)

	# Get account for mode of payment
	from pos_next.api.invoices import get_payment_account
	account_info = get_payment_account(mode_of_payment, company)
	account = account_info.get("account") if account_info else None
	if not account:
		frappe.throw(_("No account found for Mode of Payment {0}").format(mode_of_payment))

	payment_type = frappe.db.get_value("Mode of Payment", mode_of_payment, "type") or "Bank"

	# 1. Add Sales Invoice Payment child row
	max_idx = frappe.db.sql(
		"SELECT COALESCE(MAX(idx), 0) + 1 FROM `tabSales Invoice Payment` WHERE parent = %s",
		(invoice_name,),
	)
	idx = max_idx[0][0] if max_idx else 1

	payment_row = {
		"doctype": "Sales Invoice Payment",
		"parent": invoice_name,
		"parenttype": "Sales Invoice",
		"parentfield": "payments",
		"idx": idx,
		"mode_of_payment": mode_of_payment,
		"amount": amount,
		"base_amount": base_amount,
		"account": account,
		"type": payment_type,
		"reference_no": reference_no or "",
	}
	if transaction_id:
		payment_row["transaction_id"] = str(transaction_id)
	frappe.get_doc(payment_row).insert(ignore_permissions=True)

	# 2. Update paid_amount, base_paid_amount on Sales Invoice
	total_paid = frappe.db.sql(
		"SELECT COALESCE(SUM(amount), 0), COALESCE(SUM(base_amount), 0) FROM `tabSales Invoice Payment` WHERE parent = %s",
		(invoice_name,),
	)
	if total_paid and total_paid[0]:
		frappe.db.set_value(
			"Sales Invoice",
			invoice_name,
			{"paid_amount": total_paid[0][0], "base_paid_amount": total_paid[0][1]},
			update_modified=False,
		)

	# 3. Create GL entries (same logic as make_pos_gl_entries)
	against_voucher = doc.name
	if doc.is_return and doc.return_against and not doc.update_outstanding_for_self:
		against_voucher = doc.return_against

	payment_mode_account_currency = get_account_currency(account)

	gl_entries = []
	# Credit Receivable (reduce debt)
	gl_entries.append(
		doc.get_gl_dict(
			{
				"account": doc.debit_to,
				"party_type": "Customer",
				"party": doc.customer,
				"against": account,
				"credit": base_amount,
				"credit_in_account_currency": base_amount
				if doc.party_account_currency == doc.company_currency
				else amount,
				"credit_in_transaction_currency": amount,
				"against_voucher": against_voucher,
				"against_voucher_type": doc.doctype,
				"cost_center": doc.cost_center,
			},
			doc.party_account_currency,
			item=doc,
		)
	)
	# Debit Bank/Cash (receive money)
	gl_entries.append(
		doc.get_gl_dict(
			{
				"account": account,
				"against": doc.customer,
				"debit": base_amount,
				"debit_in_account_currency": base_amount
				if payment_mode_account_currency == doc.company_currency
				else amount,
				"debit_in_transaction_currency": amount,
				"cost_center": doc.cost_center,
			},
			payment_mode_account_currency,
			item=doc,
		)
	)

	# 4. Post GL entries (update_outstanding=No like POS, then call update_voucher_outstanding)
	make_gl_entries(
		gl_entries,
		update_outstanding="No",
		merge_entries=False,
		from_repost=0,
	)
	update_voucher_outstanding(
		voucher_type=doc.doctype,
		voucher_no=against_voucher,
		account=doc.debit_to,
		party_type="Customer",
		party=doc.customer,
	)
	frappe.db.commit()


def _log_sepay_transaction(sepay_id, invoice_name, amount, reference_code, data):
	"""Log SePay transaction for deduplication. Uses Error Log if no custom doctype."""
	if sepay_id and frappe.db.table_exists("SePay Transaction Log"):
		try:
			frappe.get_doc({
				"doctype": "SePay Transaction Log",
				"sepay_transaction_id": str(sepay_id),
				"sales_invoice": invoice_name,
				"amount": amount,
				"reference_code": reference_code,
				"raw_data": json.dumps(data) if data else "",
			}).insert(ignore_permissions=True)
			frappe.db.commit()
		except Exception as e:
			frappe.log_error(str(e), "SePay Transaction Log")
