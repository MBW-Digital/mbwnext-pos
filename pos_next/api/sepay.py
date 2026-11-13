# -*- coding: utf-8 -*-
# Copyright (c) 2025, BrainWise and contributors
# SePay payment gateway integration for POS Next
# Docs: https://developer.sepay.vn/vi/sepay-webhooks/tich-hop-webhook
#       https://sepay.vn/lap-trinh-cong-thanh-toan.html

from __future__ import unicode_literals
import re
import hmac
import json
from contextlib import contextmanager
import frappe
from frappe import _
from frappe.utils import flt, cint, now


# VietQR base URL (SePay)
VIETQR_BASE = "https://qr.sepay.vn/img"
BANKS_JSON_URL = "https://qr.sepay.vn/banks.json"

# Order code prefix - must match SePay "Cấu trúc mã thanh toán" config
ORDER_PREFIX = "DH"

# How long cleanup_old_drafts() spares an unpaid QR draft on a SePay till
SEPAY_DRAFT_KEEP_HOURS = 24


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
	if not bank_account or not bank_code:
		return None

	return frappe._dict(
		sepay_bank_account=bank_account,
		sepay_bank_code=bank_code,
		sepay_account_holder=account_holder,
	)


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

	amount_int = int(flt(amount, 0))
	# Content: DH + the WHOLE invoice name, letters included. Ha Vang names are
	# {shop code}.YY.MM.DD.#### - the digits alone repeat across shops on the
	# same day, so the old "DH + trailing digits" could match another shop's bill.
	content = f"{ORDER_PREFIX}{_compact(invoice_id)}" if invoice_id else ""

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

	try:
		with _sepay_lock(invoice_name):
			return _manual_confirm(invoice_name)
	except Exception as e:
		frappe.log_error(frappe.get_traceback(), "SePay Manual Confirm")
		return {"success": False, "message": str(e)}


def _manual_confirm(invoice_name):
	# Read inside the lock: the webhook may have just booked this transfer.
	doc = frappe.get_doc("Sales Invoice", invoice_name)
	if doc.docstatus == 1 and flt(doc.outstanding_amount, 2) <= 0:
		return {"success": True, "paid": True, "message": _("Invoice already submitted")}

	# Only the transfer part: cash already paid on a mixed payment stays out.
	amount = flt(doc.outstanding_amount, 2)
	mode_of_payment = (
		frappe.db.get_value("Mode of Payment", "Bank Draft", "name")
		or frappe.db.get_value("Mode of Payment", "Chuyển khoản", "name")
		or frappe.db.get_value("Mode of Payment", {"type": "Bank"}, "name")
		or "Bank"
	)

	if doc.docstatus == 0:
		doc.flags.ignore_permissions = True
		frappe.flags.ignore_account_permission = True
		doc.submit()

	from pos_next.api.partial_payments import create_payment_entry

	create_payment_entry(
		invoice_name=invoice_name,
		amount=amount,
		mode_of_payment=mode_of_payment,
		remarks="SePay manual confirmation",
	)
	return {"success": True, "paid": True, "invoice_name": invoice_name}


@frappe.whitelist(allow_guest=True)
def receive_webhook():
	"""
	Receive SePay webhook when a bank transfer is detected.

	SePay sends POST with JSON body. We must return {"success": true} with HTTP 200/201.

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

	The URL must carry ?key=<site config sepay_webhook_key>. This endpoint is open
	to guests and books money onto invoices, so without the key anyone could post
	a fake "money in". SePay's own "API Key" option cannot be used: it sends
	"Authorization: Apikey ...", which Frappe rejects as a failed login before
	this function runs. Set SePay's webhook auth to "none" and put the key in the URL.
	"""
	if frappe.request.method != "POST":
		return _webhook_response({"success": False, "message": "Method Not Allowed"}, 405)

	expected_key = frappe.conf.get("sepay_webhook_key")
	given_key = frappe.request.args.get("key") or ""
	if not expected_key or not hmac.compare_digest(str(expected_key).encode(), given_key.encode()):
		frappe.log_error(
			title="SePay Webhook",
			message="SePay webhook rejected: wrong or missing key"
			+ ("" if expected_key else " (sepay_webhook_key is not set in site config)"),
		)
		return _webhook_response({"success": False, "message": "Unauthorized"}, 401)

	raw = ""
	try:
		raw = frappe.request.get_data(as_text=True)
		data = json.loads(raw) if raw else {}
	except Exception as e:
		frappe.log_error(title="SePay Webhook", message=f"SePay webhook parse error: {e}\nRaw: {raw}")
		return _webhook_response({"success": True})

	# Only process "in" (money in). Money going OUT of the account must never
	# be booked as a customer payment.
	if data.get("transferType") != "in":
		return _webhook_response({"success": True})

	amount = flt(data.get("transferAmount") or 0)
	sepay_id = data.get("id")
	reference_code = data.get("referenceCode") or ""

	invoice_name = _resolve_invoice_name(data)
	if not invoice_name:
		frappe.log_error(
			title="SePay Webhook",
			message="SePay webhook: no invoice matches this transfer. Check it by hand.\n"
			f"code={data.get('code')!r} content={data.get('content')!r} amount={amount} id={sepay_id}",
		)
		return _webhook_response({"success": True})

	# Process payment (run as Administrator - webhook is allow_guest, needs elevated permissions)
	old_user = frappe.session.user
	try:
		frappe.set_user("Administrator")
		frappe.flags.ignore_permissions = True
		frappe.flags.ignore_account_permission = True
		with _sepay_lock(invoice_name):
			_process_sepay_payment(
				invoice_name=invoice_name,
				amount=amount,
				sepay_id=sepay_id,
				reference_code=reference_code,
				data=data,
			)
	except Exception as e:
		frappe.db.rollback()
		frappe.log_error(
			title="SePay Webhook",
			message=f"SePay webhook process error: {e}\nInvoice: {invoice_name}\nData: {data}\n{frappe.get_traceback()}",
		)
	finally:
		frappe.set_user(old_user)

	return _webhook_response({"success": True})


@contextmanager
def _sepay_lock(invoice_name):
	"""
	One booking at a time per invoice: SePay may deliver the same transfer twice
	at once, and the cashier may confirm by hand while the webhook runs. Named
	lock, not a row lock: submit hooks commit mid-way, which drops row locks.
	"""
	lock = f"sepay:{invoice_name}"
	if not frappe.db.sql("SELECT GET_LOCK(%s, 30)", (lock,))[0][0]:
		raise frappe.ValidationError(f"Timed out waiting for lock {lock}")
	try:
		# Start a fresh transaction: the one opened before the wait still reads
		# the snapshot from before the other booking committed (REPEATABLE READ).
		frappe.db.commit()
		yield
	finally:
		frappe.db.sql("SELECT RELEASE_LOCK(%s)", (lock,))


def _webhook_response(body, status=200):
	"""Exact body SePay expects - a plain Frappe return would wrap it in {"message": ...}."""
	from werkzeug.wrappers import Response

	return Response(json.dumps(body), status=status, mimetype="application/json")


def _compact(value):
	"""Invoice name as it survives a bank transfer note: letters and digits only, upper case."""
	return re.sub(r"[^A-Za-z0-9]", "", str(value or "")).upper()


def _payment_reference(sepay_id):
	return f"SEPAY-{sepay_id}"


def _is_sepay_transaction_processed(sepay_id):
	"""Was this SePay transaction already booked? SePay retries, and may send twice."""
	if not sepay_id:
		return False
	if frappe.db.exists(
		"Sales Invoice Payment",
		{"parenttype": "Sales Invoice", "reference_no": _payment_reference(sepay_id)},
	):
		return True
	if frappe.db.table_exists("SePay Transaction Log"):
		return bool(frappe.db.exists("SePay Transaction Log", {"sepay_transaction_id": str(sepay_id)}))
	return False


def _order_codes(data):
	"""Candidate invoice codes, compacted: SePay's parsed `code` first, then DH... in the note."""
	codes = []
	code = _compact(data.get("code"))
	if code.startswith(ORDER_PREFIX):
		code = code[len(ORDER_PREFIX):]
	if code:
		codes.append(code)
	for m in re.finditer(rf"{re.escape(ORDER_PREFIX)}([A-Za-z0-9]+)", data.get("content") or "", re.IGNORECASE):
		c = _compact(m.group(1))
		if c and c not in codes:
			codes.append(c)
	return codes


def _resolve_invoice_name(data):
	"""
	Exact match only. No "name contains" search: a near miss would book one
	customer's money on another customer's bill.
	"""
	for code in _order_codes(data):
		if frappe.db.exists("Sales Invoice", code):
			return frappe.db.get_value("Sales Invoice", code, "name")
		# Names with separators (SINV-00001, AC.26...) lose them in the bank note.
		# Compare compacted, recent POS invoices only, and only if exactly one fits.
		matches = frappe.db.sql(
			"""
			SELECT name FROM `tabSales Invoice`
			WHERE is_pos = 1 AND docstatus < 2
				AND creation >= DATE_SUB(NOW(), INTERVAL 7 DAY)
				AND UPPER(REPLACE(REPLACE(REPLACE(name, '-', ''), '.', ''), '/', '')) = %s
			LIMIT 2
			""",
			(code,),
			pluck=True,
		)
		if len(matches) == 1:
			return matches[0]
	return None


def _process_sepay_payment(invoice_name, amount, sepay_id, reference_code, data):
	"""
	Process incoming SePay payment: add payment to invoice and submit if draft.

	Uses Payment Entry flow (submit invoice first, then add payment) to avoid
	GL merge issues where receivable debit+credit can cancel to zero.
	"""
	if _is_sepay_transaction_processed(sepay_id):
		return

	doc = frappe.get_doc("Sales Invoice", invoice_name)

	if doc.docstatus == 2:
		frappe.log_error(
			title="SePay Webhook",
			message=f"SePay payment for cancelled invoice {invoice_name}: amount={amount} id={sepay_id}. Refund or rebook by hand.",
		)
		return

	# Already paid by another transfer: this one is extra money from the customer
	if doc.docstatus == 1 and flt(doc.outstanding_amount, 2) <= 0:
		frappe.log_error(
			title="SePay Webhook",
			message=f"SePay transfer {sepay_id} of {amount} for invoice {invoice_name}, which is already paid. Not booked - refund or rebook by hand.",
		)
		return

	# The money must have reached the account this till shows on its QR.
	settings = _get_sepay_settings(doc.pos_profile)
	# A virtual account (VA) on the profile arrives as subAccount, the main account as accountNumber.
	received = {_compact(data.get("accountNumber")), _compact(data.get("subAccount"))} - {""}
	if not settings or (received and _compact(settings.sepay_bank_account) not in received):
		frappe.log_error(
			title="SePay Webhook",
			message=f"SePay payment to account {data.get('accountNumber')!r} does not match POS Profile "
			f"{doc.pos_profile} of invoice {invoice_name} (or SePay is off there). Not booked.",
		)
		return

	# Validate amount: must match outstanding (supports mixed payments: cash + bank transfer)
	outstanding = flt(doc.outstanding_amount, 2)
	if abs(flt(amount, 2) - outstanding) > 0.01:
		frappe.log_error(
			title="SePay Webhook",
			message=f"SePay amount mismatch: invoice={invoice_name} outstanding={outstanding} got={amount}",
		)
		return

	# Prefer "Wire Transfer" (chuyển khoản), fallback to Chuyển khoản, then any Bank type
	mode_of_payment = (
		frappe.db.get_value("Mode of Payment", "Wire Transfer", "name")
		or frappe.db.get_value("Mode of Payment", "Chuyển khoản", "name")
		or frappe.db.get_value("Mode of Payment", {"type": "Bank"}, "name")
		or "Bank"
	)

	if doc.docstatus == 0:
		# Step 1: Submit draft WITHOUT payment (avoids GL merge zero-amount issue)
		doc.flags.ignore_permissions = True
		frappe.flags.ignore_account_permission = True
		doc.submit()
		frappe.db.commit()  # Ensure submit is committed before Payment Entry

	# Step 2: Add payment via Sales Invoice Payment + direct GL entries (like POS, no Payment Entry)
	_add_sepay_payment_direct(
		doc, amount, mode_of_payment,
		reference_no=_payment_reference(sepay_id) if sepay_id else reference_code,
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
