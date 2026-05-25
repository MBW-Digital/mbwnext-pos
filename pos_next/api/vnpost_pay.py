# -*- coding: utf-8 -*-
# Copyright (c) 2025, BrainWise and contributors
# VNPost Pay — ưu tiên VietQR qua API /pob/payment; fallback Web SDK iframe
from __future__ import unicode_literals

import base64
import json
import re
from urllib.parse import quote, urlencode, urlparse

import frappe
import requests
from frappe import _
from frappe.utils import cint, flt, now_datetime
from frappe.utils.password import get_decrypted_password

from pos_next.api.bank_transfer_payment import (
	ORDER_PREFIX,
	extract_order_id_from_content,
	gateway_dedup_seen,
	get_bank_transfer_mode_of_payment,
	process_incoming_transfer_for_invoice,
	resolve_invoice_name,
)

AUTH_PATH = "/og-001/partner/v1/auth"
STATUS_PATH = "/og-001/partner/payment/v1/status"
PAYMENT_PATH = "/og-001/partner/v1/pob/payment"
PAY_TYPE_VIETQR = 3
# Mô phỏng callback ngân hàng → PostPay (chỉ Dev), theo hướng dẫn VNPD
VNPOST_DEV_CALLBACK_QR_PATH = "/cob-partner/account/v1/callbackQR"


def _load_crypto():
	try:
		from cryptography.hazmat.backends import default_backend
		from cryptography.hazmat.primitives import hashes, serialization
		from cryptography.hazmat.primitives.asymmetric import padding
	except ImportError as e:
		raise ImportError("Install pyca/cryptography: pip install cryptography") from e
	return default_backend, hashes, padding, serialization


def _rsa_sign_sha256_b64(message, pem_private):
	"""signature = RSASHA256(rawData) — bản mã hóa base64."""
	default_backend, hashes, padding, serialization = _load_crypto()
	key = serialization.load_pem_private_key(
		pem_private.encode("utf-8"), password=None, backend=default_backend()
	)
	sig = key.sign(
		message.encode("utf-8"), padding.PKCS1v15(), hashes.SHA256()
	)
	return base64.b64encode(sig).decode("ascii")


def _rsa_verify_sha256_b64(message, signature_b64, pem_public) -> bool:
	if not (pem_public and signature_b64):
		return False
	default_backend, hashes, padding, serialization = _load_crypto()
	try:
		pub = serialization.load_pem_public_key(
			pem_public.encode("utf-8"), backend=default_backend()
		)
		pub.verify(
			base64.b64decode(signature_b64),
			message.encode("utf-8"),
			padding.PKCS1v15(),
			hashes.SHA256(),
		)
		return True
	except Exception:
		return False


def _url_join(base, path):
	base = (base or "").rstrip("/")
	path = path if path.startswith("/") else "/" + path
	return base + path


def _resolve_vnpd_sdk_ui_base(doc):
	"""
	Host trang nhúng Web SDK (iframe), khác base API.
	Xem VNPD_SDK_integration.pdf — ví dụ: https://vnpostpayment-dev.postpay.vn
	"""
	explicit = (doc.get("vnpost_sdk_ui_url") or "").strip().rstrip("/")
	if explicit:
		return explicit
	api = (doc.get("vnpost_api_base_url") or "").strip().rstrip("/")
	if not api:
		return ""
	try:
		p = urlparse(api)
		host = (p.hostname or "").lower()
		if not host:
			return ""
		if host.startswith("api-bdvn-dev"):
			new_host = host.replace("api-bdvn-dev", "vnpostpayment-dev", 1)
		elif host.startswith("api-bdvn"):
			new_host = host.replace("api-bdvn", "vnpostpayment", 1)
		else:
			return ""
		port = f":{p.port}" if p.port else ""
		scheme = p.scheme or "https"
		return f"{scheme}://{new_host}{port}"
	except Exception:
		return ""


def _build_vnpd_sdk_iframe_url(
	sdk_ui_base, meta, settings, amount_i, description, request_id, order_code, show_pttt
):
	"""Query iframe theo VNPD_SDK_integration.pdf (token, baseUrl, socketUrl, showPTTT, …)."""
	base_api = (meta.get("baseUrl") or settings.base_url or "").strip().rstrip("/")
	socket_u = (meta.get("socketUrl") or "").strip().rstrip("/")
	tok = (meta.get("token") or "").strip()
	sdk_ui_base = (sdk_ui_base or "").strip().rstrip("/")
	if not (sdk_ui_base and tok and base_api and socket_u):
		return ""
	params = {
		"token": tok,
		"baseUrl": base_api,
		"socketUrl": socket_u,
		"showPTTT": (show_pttt or "3").strip() or "3",
		"amount": str(int(amount_i)),
		"numberPhone": "",
		"description": description or "",
		"requestId": request_id,
		"userid": "",
		"ordercode": order_code or request_id,
		"extend": "",
		"extend2": "",
		"extend3": "",
	}
	query = urlencode(params, quote_via=quote, safe="")
	return f"{sdk_ui_base}/?{query}"


def _http_post_json(url, body, timeout=60):
	headers = {"Content-Type": "application/json", "Accept": "application/json"}
	r = requests.post(url, data=json.dumps(body), headers=headers, timeout=timeout)
	try:
		return r.json()
	except Exception:
		frappe.log_error(f"VNPost invalid JSON. URL={url} body={repr(r.text)[:2000]}", "VNPost Pay")
		return {}


def _generate_qr_svg_data_uri(content):
	"""Render VietQR EMV payload as inline SVG data URI for POS UI."""
	if not content:
		return ""
	try:
		from io import BytesIO

		from pyqrcode import create as qrcreate

		qr = qrcreate(str(content), error="M")
		stream = BytesIO()
		try:
			qr.svg(stream, scale=3, background="white", module_color="black")
			svg = stream.getvalue().decode().replace("\n", "")
			return "data:image/svg+xml;base64," + base64.b64encode(svg.encode()).decode()
		finally:
			stream.close()
	except Exception:
		frappe.log_error(frappe.get_traceback(), "VNPost QR render")
		return ""


def _call_vnpost_payment_api(settings, meta, amount_i, note, request_id):
	"""Partner /pob/payment — trả body có field `qr` (EMV VietQR)."""
	from frappe.utils import get_datetime as _gdt

	dt_str = _gdt(now_datetime()).strftime("%d/%m/%Y %H:%M:%S")
	raw_pay = "|".join([request_id, str(PAY_TYPE_VIETQR), str(amount_i)])
	pay_sig = _rsa_sign_sha256_b64(raw_pay, settings.private_key_pem)
	pbody = {
		"token": meta["token"],
		"type": PAY_TYPE_VIETQR,
		"amount": amount_i,
		"note": note,
		"dateTime": dt_str,
		"requestId": request_id,
		"signature": pay_sig,
	}
	pres = _http_post_json(_url_join(settings.base_url, PAYMENT_PATH), pbody)
	code = (pres.get("code") or "").strip()
	if code and code not in ("API000", "200", "0"):
		return None, pres
	pbd = pres.get("body") or pres.get("data") or {}
	if not isinstance(pbd, dict) or not pbd.get("qr"):
		return None, pres
	return pbd, pres


def _payment_body_fields(pbd, settings):
	"""Map optional display fields from payment API body."""
	return {
		"account_number": (
			pbd.get("accNo")
			or pbd.get("accountNo")
			or pbd.get("account_number")
			or settings.partner_acc_no
			or ""
		),
		"bank_code": pbd.get("bankCode") or pbd.get("bank_code") or "",
		"account_holder": pbd.get("accName") or pbd.get("account_holder") or "",
		"trans_id": pbd.get("transId") or pbd.get("trans_id"),
	}


def _is_vnpost_dev_api_base(base_url):
	return "api-bdvn-dev" in (base_url or "").lower()


def _vnpd_dev_callback_simulation_allowed(settings):
	if not settings or not settings.base_url:
		return False
	if not (
		cint(frappe.conf.get("developer_mode"))
		or cint(frappe.conf.get("allow_vnpost_dev_callback_simulation"))
	):
		return False
	return _is_vnpost_dev_api_base(settings.base_url)


def extract_vnpost_dev_acc_no_from_qr(qr_emv_string):
	"""
	Trích accNo cho API callbackQR Dev từ field `qr` (chuỗi EMV VietQR).
	Mẫu: 99VP + 6 chữ số + M + 7 ký tự (theo ví dụ đối tác VNPD).
	"""
	if not qr_emv_string or not isinstance(qr_emv_string, str):
		return ""
	m = re.search(r"(99VP[A-Z0-9]{6}M[A-Z0-9]{7})", qr_emv_string, re.IGNORECASE)
	return m.group(1).upper() if m else ""


@frappe.whitelist()
def get_vnpd_dev_acc_no_from_qr_emv(qr_emv_string):
	"""Trích accNo cho callbackQR Dev từ chuỗi `qr` (copy từ Network)."""
	return {"acc_no": extract_vnpost_dev_acc_no_from_qr(qr_emv_string)}


@frappe.whitelist()
def simulate_vnpd_dev_bank_callback_qr(pos_profile, acc_no, fixed_amount):
	"""
	Chỉ Dev: GET .../cob-partner/account/v1/callbackQR?accNo=&fixedAmount=
	Để PostPay coi như ngân hàng đã báo có tiền; sau đó merchant callback (nếu URL public).
	Cần developer_mode=1 hoặc site_config allow_vnpost_dev_callback_simulation=1,
	và POS Profile trỏ tới api-bdvn-dev.
	"""
	settings = _get_vnpost_settings(pos_profile)
	if not settings:
		return {"success": False, "message": _("VNPost Pay is not fully configured for this POS Profile")}
	if not _vnpd_dev_callback_simulation_allowed(settings):
		frappe.throw(
			_("VNPD bank callback simulation is only allowed on dev API base with developer_mode (or allow_vnpost_dev_callback_simulation)."),
			frappe.PermissionError,
		)
	acc_no = (acc_no or "").strip()
	if not acc_no:
		return {"success": False, "message": _("acc_no is required")}
	try:
		amt = int(flt(fixed_amount, 0))
	except Exception:
		amt = 0
	if amt <= 0:
		return {"success": False, "message": _("Invalid fixed_amount")}
	url = _url_join(settings.base_url, VNPOST_DEV_CALLBACK_QR_PATH)
	try:
		r = requests.get(
			url,
			params={"accNo": acc_no, "fixedAmount": str(amt)},
			headers={"accept": "*/*"},
			timeout=60,
		)
	except Exception as e:
		frappe.log_error(frappe.get_traceback(), "VNPost Dev callbackQR")
		return {"success": False, "message": str(e)}
	text = (r.text or "")[:2000]
	out = {"success": 200 <= r.status_code < 300, "status_code": r.status_code, "body_preview": text}
	try:
		out["json"] = r.json()
	except Exception:
		out["json"] = None
	return out


def _get_vnpost_password(pos_profile, doc):
	pw = get_decrypted_password("POS Profile", pos_profile, "vnpost_password", raise_exception=False)
	if pw:
		return pw
	return doc.get("vnpost_password") or ""


def _get_vnpost_settings(pos_profile):
	if not pos_profile:
		return None
	
	doc = frappe.get_cached_doc("POS Profile", pos_profile)
	if not cint(doc.get("enable_bank_transfer_check")):
		return None

	pg = doc.get("payment_gateway")
	if pg and pg != "VNPost Pay":
		return None

	base = (doc.get("vnpost_api_base_url") or "").strip().rstrip("/")
	user = (doc.get("vnpost_username") or "").strip()
	pwd = _get_vnpost_password(pos_profile, doc)
	service = (doc.get("vnpost_service_code") or "").strip()
	partner = (doc.get("vnpost_partner_code") or "").strip()
	acc = (doc.get("vnpost_partner_acc_no") or "").strip()
	po = (doc.get("vnpost_pocode") or "").strip()  # để trống nếu không cần; điền sai → auth fail → SDK fallback
	pvk = (doc.get("vnpost_rsa_private_key") or "").strip()

	if not (base and user and service and partner and acc and pvk):
		return None
	
	return frappe._dict(
		base_url=base,
		username=user,
		password=pwd,
		service_code=service,
		partner_code=partner,
		partner_acc_no=acc,
		po_code=po,
		private_key_pem=pvk,
		public_key_pem=(doc.get("vnpost_vnpd_public_key") or "").strip(),
		pos_profile=pos_profile,
	)


def _get_vnpost_payable_amount(invoice_id, fallback_amount):
	"""
	Số tiền VNPost cần thu.
	- Nếu invoice đã submit (docstatus=1): dùng outstanding_amount.
	- Nếu là draft: fallback_amount từ frontend (grand_total - other_payments thực sự).
	  Không tính lại từ inv.payments vì set_missing_values() tự thêm Cash payment
	  từ POS Profile mặc định, khiến payable = 0 và rơi vào fallback sai.
	"""
	if invoice_id:
		doctype = "Sales Invoice"
		if not frappe.db.exists(doctype, invoice_id):
			# Thử Sales Order
			doctype = "Sales Order"
		if frappe.db.exists(doctype, invoice_id):
			inv = frappe.get_doc(doctype, invoice_id)
			if inv.docstatus == 1:
				payable = flt(inv.get("outstanding_amount") or inv.get("grand_total"), 2)
				if payable > 0:
					return int(flt(payable, 0))
	# Draft hoặc không tìm thấy: tin tưởng giá trị frontend đã tính đúng
	return int(flt(fallback_amount, 0))


def get_auth_token_with_meta(settings, request_id_for_auth):
	"""
	Lấy token (có cache theo thời gian expired từ VNPD).
	Auth: rawData = partnerCode | requestId | username | password | serviceCode | partnerAccNo
	"""
	cache_key = f"vnpost_token|{settings.pos_profile}"
	cached = frappe.cache().get_value(cache_key)
	if isinstance(cached, dict) and cached.get("token") and not cached.get("stale"):
		return cached
	
	raw = "|".join(
		[
			settings.partner_code,
			request_id_for_auth,
			settings.username,
			settings.password,
			settings.service_code,
			settings.partner_acc_no,
		]
	)
	
	sig = _rsa_sign_sha256_b64(raw, settings.private_key_pem)
	body = {
		"username": settings.username,
		"password": settings.password,
		"serviceCode": settings.service_code,
		"partnerAccNo": settings.partner_acc_no,
		"requestId": request_id_for_auth,
		"POCode": settings.po_code,
		"partnerCode": settings.partner_code,
		"signature": sig,
	}
	url = _url_join(settings.base_url, AUTH_PATH)
	res = _http_post_json(url, body)
	code = (res.get("code") or "").strip()
	if code and code not in ("API000", "200", "0"):
		frappe.log_error(
			f"VNPost auth error: {code} {res.get('message')}\n{res!r}"[:2000], "VNPost Pay"
		)
		return None
	bd = res.get("body") or res.get("data") or {}
	token = bd.get("token")
	if not token:
		return None
	expired = 0
	try:
		expired = int(bd.get("expired") or 300)
	except Exception:
		expired = 300
	out = {
		"token": token,
		"expired": expired,
		"baseUrl": bd.get("baseUrl") or "",
		"socketUrl": bd.get("socketUrl") or "",
	}
	ttl = max(60, expired - 30)
	frappe.cache().set_value(cache_key, {**out, "stale": False}, expires_in_sec=ttl)
	# Xác thực chữ ký trả về nếu có public key
	pub = settings.public_key_pem
	if pub and res.get("signature"):
		vraw = "|".join(
			[
				str(res.get("code") or ""),
				str(res.get("message") or ""),
				str(bd.get("token") or ""),
				str(bd.get("expired") or ""),
				str(bd.get("baseUrl") or ""),
				str(bd.get("socketUrl") or ""),
			]
		)
		if not _rsa_verify_sha256_b64(vraw, res.get("signature"), pub):
			frappe.log_error("VNPost auth response signature invalid", "VNPost Pay")
	return out


@frappe.whitelist()
def get_vietqr_url(pos_profile, amount, invoice_id=None, template="compact"):
	"""
	Trả dữ liệu cho UI: ưu tiên VietQR từ API /pob/payment; fallback SDK iframe.
	"""
	_ = template
	return get_vnpost_payment_qr_data(pos_profile, amount, invoice_id)


@frappe.whitelist()
def get_vnpost_payment_qr_data(pos_profile, amount, invoice_id=None):
	"""
	VNPost Pay: ưu tiên VietQR qua API /pob/payment (không spinner SDK).
	Nếu API lỗi thì fallback iframe Web SDK (VNPD_SDK).
	"""
	settings = _get_vnpost_settings(pos_profile)
	if not settings:
		return {
			"enabled": False,
			"message": _("VNPost Pay is not fully configured for this POS Profile"),
		}

	amount_i = _get_vnpost_payable_amount(invoice_id, amount)
	if not amount_i or amount_i < 0:
		return {"enabled": False, "message": _("Invalid amount")}

	req_auth = f"AUT{frappe.generate_hash(length=10)}"
	meta = get_auth_token_with_meta(settings, req_auth)
	if not meta or not meta.get("token"):
		return {"enabled": False, "message": _("Failed to get VNPost token. Check API URL and keys.")}

	pos_doc = frappe.get_cached_doc("POS Profile", pos_profile)
	sdk_ui_base = _resolve_vnpd_sdk_ui_base(pos_doc)
	show_pttt = (pos_doc.get("vnpost_sdk_show_pttt") or "3").strip() or "3"

	if invoice_id:
		m = re.search(r"(\d+)$", str(invoice_id))
		note = f"{ORDER_PREFIX}{m.group(1) if m else invoice_id}"
	else:
		note = ""

	if invoice_id:
		inv_num = re.sub(r"[^0-9A-Za-z]", "", str(invoice_id))
		ts = now_datetime().strftime("%m%d%H%M%S")
		request_id = f"{inv_num}{ts}"[:32]
	else:
		request_id = f"R{frappe.generate_hash(length=20)}"

	order_code = str(invoice_id or request_id).strip()

	# --- Primary: partner payment API → static VietQR (no SDK spinner) ---
	pbd, pres = _call_vnpost_payment_api(settings, meta, amount_i, note, request_id)
	if pbd:
		qr_emv = pbd.get("qr") or ""
		display = _payment_body_fields(pbd, settings)
		acc_no_suggestion = extract_vnpost_dev_acc_no_from_qr(qr_emv)
		vnpd_dev_simulation = None
		if _vnpd_dev_callback_simulation_allowed(settings):
			vnpd_dev_simulation = {
				"show": True,
				"acc_no_suggestion": acc_no_suggestion,
				"fixed_amount": amount_i,
				"hint": _("Dev-only: PostPay callbackQR."),
			}
		return {
			"enabled": True,
			"qr_url": _generate_qr_svg_data_uri(qr_emv),
			"qr_emv": qr_emv,
			"sdk_iframe_url": "",
			"account_number": display["account_number"],
			"bank_code": display["bank_code"],
			"account_holder": display["account_holder"],
			"amount": amount_i,
			"content": note,
			"request_id": request_id,
			"trans_id": display["trans_id"],
			"sdk": None,
			"raw_body": pbd,
			"vnpd_dev_simulation": vnpd_dev_simulation,
			"message": "",
			"payment_api_warning": "",
			"payment_mode": "api_qr",
		}

	payment_api_warning = ""
	if pres:
		payment_api_warning = " ".join(
			filter(
				None,
				[
					str(pres.get("code") or "").strip(),
					str(pres.get("message") or "").strip(),
				],
			)
		)
		po_hint = f"POCode='{settings.po_code}'" if settings.po_code else "POCode=<trống>"
		frappe.logger("vnpost_pay").warning(
			f"VNPost /pob/payment fail ({po_hint}) → fallback SDK. "
			f"Response: code={pres.get('code')!r} msg={pres.get('message')!r}"
		)

	# --- Fallback: Web SDK iframe ---
	sdk_iframe_url = _build_vnpd_sdk_iframe_url(
		sdk_ui_base, meta, settings, amount_i, note, request_id, order_code, show_pttt
	)

	if not sdk_iframe_url:
		return {
			"enabled": False,
			"message": _(
				"Could not create VNPost payment. Payment API failed and SDK URL could not be built."
			),
			"payment_api_warning": payment_api_warning,
		}

	vnpd_dev_simulation = None
	if _vnpd_dev_callback_simulation_allowed(settings):
		vnpd_dev_simulation = {
			"show": True,
			"acc_no_suggestion": "",
			"fixed_amount": amount_i,
			"hint": _("Dev-only: PostPay callbackQR."),
		}

	return {
		"enabled": True,
		"qr_url": "",
		"sdk_iframe_url": sdk_iframe_url,
		"account_number": settings.partner_acc_no or "",
		"bank_code": "",
		"account_holder": "",
		"amount": amount_i,
		"content": note,
		"request_id": request_id,
		"trans_id": None,
		"sdk": {
			"baseUrl": meta.get("baseUrl") or settings.base_url,
			"socketUrl": meta.get("socketUrl") or "",
		},
		"raw_body": {},
		"vnpd_dev_simulation": vnpd_dev_simulation,
		"message": "",
		"payment_api_warning": payment_api_warning,
		"payment_mode": "sdk_iframe",
	}


@frappe.whitelist()
def check_vnpost_payment_status(invoice_name):
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
def manual_confirm_vnpost_payment(invoice_name):
	"""Dùng khi callback không tới (localhost) hoặc test."""
	if not invoice_name:
		return {"success": False, "message": _("Invoice name is required")}
	if not frappe.db.exists("Sales Invoice", invoice_name):
		return {"success": False, "message": _("Invoice not found")}
	doc = frappe.get_doc("Sales Invoice", invoice_name)
	if doc.docstatus == 1 and flt(doc.outstanding_amount, 2) <= 0:
		return {"success": True, "paid": True, "message": _("Invoice already submitted")}
	try:
		if doc.docstatus == 0:
			doc.flags.ignore_permissions = True
			frappe.flags.ignore_account_permission = True
			doc.submit()
			frappe.db.commit()
			doc.reload()
		amount = flt(doc.outstanding_amount, 2)
		if amount <= 0:
			return {"success": True, "paid": True, "message": _("Invoice already paid")}
		mode_of_payment = get_bank_transfer_mode_of_payment()
		from pos_next.api.partial_payments import create_payment_entry
		create_payment_entry(
			invoice_name=invoice_name,
			amount=amount,
			mode_of_payment=mode_of_payment,
			remarks="VNPost Pay manual confirm",
		)
		return {"success": True, "paid": True, "invoice_name": invoice_name}
	except Exception as e:
		frappe.log_error(frappe.get_traceback(), "VNPost Manual Confirm")
		return {"success": False, "message": str(e)}


@frappe.whitelist(allow_guest=True)
def receive_callback():
	"""
	Callback từ VNPD: POST JSON.
	Đăng ký URL công khai: /api/method/pos_next.api.vnpost_pay.receive_callback
	"""
	if frappe.request.method != "POST":
		frappe.response["http_status_code"] = 405
		return _callback_response("ERR-001", "Method Not Allowed", {})
	try:
		raw = frappe.request.get_data(as_text=True)
		data = json.loads(raw) if raw else {}
	except Exception as e:
		frappe.log_error(f"VNPost callback parse: {e}\n{raw!r}"[:2000], "VNPost Pay")
		return _callback_response("ERR-001", "Bad JSON", {})

	trans_id = str(data.get("transId") or "")
	ref_id = str(data.get("referenceId") or data.get("reference_id") or "")
	req_id = str(data.get("requestId") or data.get("request_id") or "")
	amount = flt(data.get("amount") or 0, 0)
	typ = data.get("type")
	trans_date = str(data.get("transDate") or data.get("trans_date") or "")
	trans_note = str(data.get("transNote") or data.get("trans_note") or "")
	sig = data.get("signature") or data.get("Signature")

	# Xác thực chữ ký (có chữ ký: bắt buộc xác nếu đã cấp public key VNPD)
	verified = not bool(sig)
	any_key = False
	amt_s = str(int(flt(amount)))
	vraw = "|".join(
		[trans_id, ref_id, amt_s, str(typ or ""), trans_date, trans_note]
	)
	if sig:
		for name in frappe.get_all("POS Profile", pluck="name"):
			s = _get_vnpost_settings(name)
			if not s or not s.public_key_pem:
				continue
			any_key = True
			if _rsa_verify_sha256_b64(vraw, sig, s.public_key_pem):
				verified = True
				break
		if not any_key and sig:
			frappe.log_error(
				"VNPost callback: signature present but no vnpost_vnpd_public_key on any POS Profile",
				"VNPost Pay",
			)
			verified = bool(frappe.local.conf.get("developer_mode"))
		if not verified and any_key:
			frappe.log_error(
				f"VNPost callback signature fail. raw={vraw!r} data={data!r}"[:2000], "VNPost Pay"
			)
			return _callback_response("OG-006", "Invalid signature", {})

	dedup_id = trans_id or f"{ref_id}|{req_id}"
	if not dedup_id or gateway_dedup_seen(dedup_id):
		return _callback_response("API000", "OK", {})

	inv_key = req_id or ref_id
	if not inv_key:
		inv_key = extract_order_id_from_content(trans_note) or ""
	invoice_name = inv_key
	if not frappe.db.exists("Sales Invoice", inv_key) and ref_id:
		invoice_name = resolve_invoice_name(ref_id) or resolve_invoice_name(req_id) or ref_id
	if not invoice_name or not frappe.db.exists("Sales Invoice", invoice_name):
		invoice_name = resolve_invoice_name(extract_order_id_from_content(trans_note) or "")
	if not invoice_name or not frappe.db.exists("Sales Invoice", invoice_name):
		frappe.log_error(
			f"VNPost callback: no invoice. data={data!r}"[:2000], "VNPost Pay"
		)
		return _callback_response("API000", "OK", {})

	if flt(data.get("status") if "status" in data else 1) == 0:
		return _callback_response("API000", "OK", {})

	try:
		old_user = frappe.session.user
		frappe.set_user("Administrator")
		frappe.flags.ignore_permissions = True
		try:
			gid = trans_id or dedup_id
			process_incoming_transfer_for_invoice(
				invoice_name=invoice_name,
				amount=amount,
				gateway_transaction_id=gid,
				reference_code=ref_id or req_id,
				_remarks="VNPost Pay callback",
				raw_data=data,
			)
		finally:
			frappe.set_user(old_user)
	except Exception as e:
		frappe.log_error(
			f"VNPost callback process error: {e}\nInvoice={invoice_name}\n{data!r}"[:2000],
			"VNPost Pay",
		)
	return _callback_response("API000", "OK", {})


def _callback_response(code, message, body):
	"""Một số bài toán yêu cầu chữ ký; trả tối thiểu code/message/body."""
	frappe.response["type"] = "json"
	out = {"code": code, "message": message, "body": body}
	frappe.response["result"] = out
	frappe.response["http_status_code"] = 200
	return out
