# -*- coding: utf-8 -*-
# Copyright (c) 2025, BrainWise and contributors
# VNPost Pay (Open Hub / VNPD) — tài liệu VNPost_Pay.pdf
from __future__ import unicode_literals

import base64
import json
import re

import frappe
import requests
from frappe import _
from frappe.utils import cint, flt, get_datetime, now_datetime
from frappe.utils.password import get_decrypted_password

from pos_next.api.bank_transfer_payment import (
	ORDER_PREFIX,
	extract_order_id_from_content,
	gateway_dedup_seen,
	get_bank_transfer_mode_of_payment,
	process_incoming_transfer_for_invoice,
	resolve_invoice_name,
)

# Phương thức: 3 = VietQR (theo tài liệu API v1.5)
PAY_TYPE_VIETQR = 3
AUTH_PATH = "/og-001/partner/v1/auth"
PAYMENT_PATH = "/og-001/partner/v1/pob/payment"
STATUS_PATH = "/og-001/partner/payment/v1/status"


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


def _http_post_json(url, body, timeout=60):
	headers = {"Content-Type": "application/json", "Accept": "application/json"}
	r = requests.post(url, data=json.dumps(body), headers=headers, timeout=timeout)
	try:
		return r.json()
	except Exception:
		frappe.log_error(f"VNPost invalid JSON. URL={url} body={repr(r.text)[:2000]}", "VNPost Pay")
		return {}


def _get_vnpost_password(pos_profile, doc):
	pw = get_decrypted_password("POS Profile", pos_profile, "vnpost_password", raise_exception=False)
	if pw:
		return pw
	return doc.get("vnpost_password") or ""


def _get_vnpost_settings(pos_profile):
	if not pos_profile:
		return None
	doc = frappe.get_cached_doc("POS Profile", pos_profile)
	if not cint(doc.get("enable_sepay_bank_transfer_check")):
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
	po = (doc.get("vnpost_pocode") or "").strip()
	pvk = (doc.get("vnpost_rsa_private_key") or "").strip()
	if not (base and user and pwd and service and partner and acc and po and pvk):
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
	Backward-compatible name. Trả cấu trúc cho UI/ in nhiệt: qr_url, amount, nội dung, thông tin TK (nếu có).
	Thực hiện: auth + API thanh toán VietQR (type=3).
	"""
	_ = template
	return get_vnpost_payment_qr_data(pos_profile, amount, invoice_id)


@frappe.whitelist()
def get_vnpost_payment_qr_data(pos_profile, amount, invoice_id=None):
	settings = _get_vnpost_settings(pos_profile)
	if not settings:
		return {
			"enabled": False,
			"message": _("VNPost Pay is not fully configured for this POS Profile"),
		}
	amount_i = int(flt(amount, 0))
	if not amount_i or amount_i < 0:
		return {"enabled": False, "message": _("Invalid amount")}
	req_auth = f"AUT{frappe.generate_hash(length=10)}"
	meta = get_auth_token_with_meta(settings, req_auth)
	if not meta or not meta.get("token"):
		return {"enabled": False, "message": _("Failed to get VNPost token. Check API URL and keys.")}
	if invoice_id:
		m = re.search(r"(\d+)$", str(invoice_id))
		note = f"{ORDER_PREFIX}{m.group(1) if m else invoice_id}"
	else:
		note = ""
	request_id = str(invoice_id or "").strip() or f"R{frappe.generate_hash(length=12)}"
	dt_str = get_datetime(now_datetime()).strftime("%d/%m/%Y %H:%M:%S")
	raw = "|".join([request_id, str(PAY_TYPE_VIETQR), str(amount_i)])
	pay_sig = _rsa_sign_sha256_b64(raw, settings.private_key_pem)
	pbody = {
		"token": meta["token"],
		"type": PAY_TYPE_VIETQR,
		"amount": amount_i,
		"note": note,
		"dateTime": dt_str,
		"requestId": request_id,
		"signature": pay_sig,
	}
	url = _url_join(settings.base_url, PAYMENT_PATH)
	pres = _http_post_json(url, pbody)
	pcode = (pres.get("code") or "").strip()
	pbd = pres.get("body") or pres.get("data") or {}
	if pcode and pcode not in ("API000", "200", "0") and pbd.get("status") not in (1, 2, 3):
		return {
			"enabled": False,
			"message": f"{pcode} {pres.get('message', '')}" or _("Payment request failed"),
		}
	# Map QR / hiển thị
	qr_url = _extract_qr_url_from_vnpd(pbd, pres, meta)
	bank_code = pbd.get("bankCode") or pbd.get("bank_code") or ""
	account_number = pbd.get("accountNumber") or pbd.get("account") or pbd.get("accountNo") or settings.partner_acc_no
	account_holder = pbd.get("accountName") or pbd.get("account_name") or pbd.get("accName") or ""
	return {
		"enabled": True,
		"qr_url": qr_url or "",
		"account_number": account_number,
		"bank_code": bank_code,
		"account_holder": account_holder,
		"amount": amount_i,
		"content": note,
		"request_id": request_id,
		"trans_id": pbd.get("transId") or pbd.get("id"),
		"sdk": {
			"baseUrl": meta.get("baseUrl") or "",
			"socketUrl": meta.get("socketUrl") or "",
		}
		if not qr_url
		else None,
		"raw_body": pbd,
		"message": pres.get("message") or "",
	}


def _extract_qr_url_from_vnpd(body, full_response, token_meta):
	for key in (
		"qrUrl",
		"qrURL",
		"imageUrl",
		"url",
		"qr",
		"qrcode",
		"dataQr",
		"dataQR",
		"vietqrUrl",
		"qrCodeUrl",
	):
		v = body.get(key) if isinstance(body, dict) else None
		if v and isinstance(v, str) and (v.startswith("http") or v.startswith("data:")):
			return v
	# Có thể trả về mã base64 thuần
	for key in ("qrData", "qrString", "data"):
		v = body.get(key) if isinstance(body, dict) else None
		if v and isinstance(v, str) and len(v) > 40 and not v.startswith("http"):
			return f"data:image/png;base64,{v}" if not v.startswith("data:") else v
	_ = full_response, token_meta
	return ""


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
	amount = flt(doc.grand_total, 2)
	try:
		if doc.docstatus == 0:
			doc.flags.ignore_permissions = True
			frappe.flags.ignore_account_permission = True
			doc.submit()
		mode_of_payment = get_bank_transfer_mode_of_payment()
		from pos_next.api.partial_payments import create_payment_entry
		create_payment_entry(
			invoice_name=invoice_name, amount=amount, mode_of_payment=mode_of_payment, remarks="VNPost Pay manual confirm"
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
				remarks="VNPost Pay callback",
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
