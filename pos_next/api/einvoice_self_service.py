# Copyright (c) 2026, Tuanbd and contributors
"""Guest self-service e-invoice via QR (POS Next)."""

from __future__ import annotations

import re
import secrets
from typing import Any, Dict, Optional, Tuple

import frappe
from frappe import _
from frappe.rate_limiter import rate_limit
from frappe.utils import add_to_date, get_datetime, get_url, now_datetime


def _meta_has_si_field(fieldname: str) -> bool:
	try:
		return bool(frappe.get_meta("Sales Invoice").has_field(fieldname))
	except Exception:
		return False


def _company_uses_einvoice(company: str) -> bool:
	if not company:
		return False
	cfg = frappe.db.get_value("Company", company, ["use_einvoice"], as_dict=True)
	return bool(cfg and cfg.get("use_einvoice"))


def ensure_self_service_einvoice_token(sales_invoice_name: str) -> None:
	"""After SI submit: generate opaque token + expiry (creation + 2h) for QR URL."""
	if not sales_invoice_name or not frappe.db.exists("Sales Invoice", sales_invoice_name):
		return
	if not _meta_has_si_field("pos_self_service_einvoice_token"):
		return

	from frappe.utils import cint

	si = frappe.db.get_value(
		"Sales Invoice",
		sales_invoice_name,
		["company", "is_pos", "creation", "pos_self_service_einvoice_token", "created_einvoice", "docstatus"],
		as_dict=True,
	)
	if not si or si.docstatus != 1:
		return
	if not cint(si.is_pos):
		return
	if si.created_einvoice:
		return
	if not _company_uses_einvoice(si.company):
		return
	if (si.pos_self_service_einvoice_token or "").strip():
		return

	token = secrets.token_urlsafe(24)
	expires = add_to_date(si.creation, hours=2)
	frappe.db.set_value(
		"Sales Invoice",
		sales_invoice_name,
		{
			"pos_self_service_einvoice_token": token,
			"pos_self_service_einvoice_expires": expires,
			"pos_self_service_einvoice_status": "Pending",
		},
		update_modified=False,
	)
	frappe.db.commit()


def _invoice_names_from_token(token: str) -> Optional[str]:
	token = (token or "").strip()
	if len(token) < 8:
		return None
	row = frappe.db.sql(
		"""select name from `tabSales Invoice`
		where pos_self_service_einvoice_token = %(t)s limit 1""",
		{"t": token},
	)
	if not row:
		return None
	return row[0][0]


def _token_valid(si_name: str, token: str) -> Tuple[bool, str]:
	si = frappe.db.get_value(
		"Sales Invoice",
		si_name,
		[
			"pos_self_service_einvoice_token",
			"pos_self_service_einvoice_expires",
			"creation",
			"created_einvoice",
			"docstatus",
			"name",
		],
		as_dict=True,
	)
	if not si or si.docstatus != 1:
		return False, _("Invoice not found.")
	if (si.pos_self_service_einvoice_token or "").strip() != token.strip():
		return False, _("Invalid link.")
	expires = si.pos_self_service_einvoice_expires or add_to_date(si.creation, hours=2)
	if get_datetime(now_datetime()) > get_datetime(expires):
		return False, _("This QR link has expired (valid for 2 hours from invoice creation).")
	if si.created_einvoice:
		return False, _("E-invoice has already been issued for this sale.")
	return True, ""


def _issue_via_provider(sales_invoice: str) -> Dict[str, Any]:
	company = frappe.db.get_value("Sales Invoice", sales_invoice, "company")
	provider = (frappe.db.get_value("Company", company, "provider") or "").strip()
	old_ignore = frappe.flags.ignore_permissions
	frappe.flags.ignore_permissions = True
	try:
		if provider == "VNPT":
			from mbwnext_einvoice.mbwnext_einvoice.api.vnpt import issue_invoice_for_sales_invoice

			return issue_invoice_for_sales_invoice(sales_invoice)
		if provider == "Viettel":
			from mbwnext_einvoice.mbwnext_einvoice.api.viettel import issue_invoice_for_sales_invoice as viettel_issue

			return viettel_issue(sales_invoice)
		if provider == "MISA":
			from mbwnext_einvoice.mbwnext_einvoice.api.misa import issue_invoice_for_sales_invoice as misa_issue

			return misa_issue(sales_invoice)
		raise RuntimeError(_("Company E-Invoice provider is not configured or not supported for self-service."))
	except ImportError as exc:
		raise RuntimeError(_("E-Invoice integration is not available on this site.") + f" ({exc})") from exc
	finally:
		frappe.flags.ignore_permissions = old_ignore


@frappe.whitelist(allow_guest=True)
@rate_limit(limit=60, seconds=60)
def einvoice_self_service_session(token: str | None = None) -> Dict[str, Any]:
	"""Public: validate token and return minimal invoice info for the form."""
	token = token or frappe.form_dict.get("token") or frappe.form_dict.get("t") or ""
	si_name = _invoice_names_from_token(token)
	if not si_name:
		return {"ok": False, "message": _("Invalid or unknown link.")}

	valid, msg = _token_valid(si_name, token)
	if not valid:
		return {"ok": False, "message": str(msg)}

	si = frappe.db.get_value(
		"Sales Invoice",
		si_name,
		[
			"name",
			"grand_total",
			"currency",
			"company",
			"posting_date",
			"creation",
			"pos_self_service_einvoice_expires",
			"created_einvoice",
			"einvoice_no",
		],
		as_dict=True,
	)
	expires = si.pos_self_service_einvoice_expires or add_to_date(si.creation, hours=2)
	return {
		"ok": True,
		"sales_invoice": si.name,
		"grand_total": si.grand_total,
		"currency": si.currency or "VND",
		"expires_at": str(expires),
		"already_issued": bool(si.created_einvoice),
		"einvoice_no": si.einvoice_no or "",
	}


@frappe.whitelist(allow_guest=True)
@rate_limit(limit=30, seconds=60)
def lookup_buyer_by_tax_id(tax_id: str | None = None) -> Dict[str, Any]:
	"""Best-effort MST lookup in ERPNext Customer / Company masters (no external GDT API)."""
	return _resolve_buyer_master_by_tax_id(tax_id or "")


def _resolve_buyer_master_by_tax_id(tax_id_raw: str) -> Dict[str, Any]:
	tax_id = _normalize_tax_id(tax_id_raw or "")
	if len(tax_id) < 10:
		return {"found": False}

	found = frappe.db.sql(
		"""
		select name, customer_name, tax_id from `tabCustomer`
		where replace(replace(ifnull(tax_id,''), ' ', ''), '-', '') = %(t)s
		limit 1
		""",
		{"t": tax_id},
		as_dict=True,
	)
	if found:
		row = found[0]
		addr = ""
		try:
			from mbwnext_einvoice.integrations.vnpt.service import _pick_customer_address_name, _address_text_with_title

			addr_name = _pick_customer_address_name(row.name)
			if addr_name:
				addr = _address_text_with_title(addr_name)
		except Exception:
			pass
		return {
			"found": True,
			"name": row.customer_name or "",
			"tax_id": row.tax_id or tax_id,
			"address": addr,
		}

	found_co = frappe.db.sql(
		"""
		select name, company_name, tax_id from `tabCompany`
		where replace(replace(ifnull(tax_id,''), ' ', ''), '-', '') = %(t)s
		limit 1
		""",
		{"t": tax_id},
		as_dict=True,
	)
	if found_co:
		row = found_co[0]
		return {
			"found": True,
			"name": row.company_name or "",
			"tax_id": row.tax_id or tax_id,
			"address": "",
		}

	return {"found": False}


def _normalize_tax_id(raw: str) -> str:
	return re.sub(r"[^0-9]", "", (raw or "").strip())


@frappe.whitelist(allow_guest=True)
@rate_limit(limit=15, seconds=3600)
def submit_self_service_einvoice(
	token: str | None = None,
	buyer_type: str | None = None,
	tax_id: str | None = None,
	buyer_name: str | None = None,
	buyer_address: str | None = None,
	email: str | None = None,
	phone: str | None = None,
) -> Dict[str, Any]:
	"""Guest submits buyer data; staging fields on SI then provider issue API."""
	token = (token or "").strip()
	si_name = _invoice_names_from_token(token)
	if not si_name:
		return {"ok": False, "message": _("Invalid link.")}

	valid, msg = _token_valid(si_name, token)
	if not valid:
		return {"ok": False, "message": str(msg)}

	buyer_type = (buyer_type or "retail").strip().lower()
	tax_id = _normalize_tax_id(tax_id or "")
	buyer_name = (buyer_name or "").strip()
	buyer_address = (buyer_address or "").strip()
	email = (email or "").strip()
	phone = (phone or "").strip()

	if buyer_type == "company":
		if len(tax_id) < 10:
			return {"ok": False, "message": _("Please enter a valid tax identification number (MST).")}
		if not buyer_name:
			lu = _resolve_buyer_master_by_tax_id(tax_id)
			if lu.get("found"):
				buyer_name = (lu.get("name") or "").strip()
		if not buyer_name:
			return {"ok": False, "message": _("Please enter or resolve company name (lookup MST).")}
	else:
		if not buyer_name:
			return {"ok": False, "message": _("Please enter buyer name.")}
		if tax_id and len(tax_id) < 10:
			return {"ok": False, "message": _("Please enter a valid personal tax ID.")}

	if not buyer_address:
		return {"ok": False, "message": _("Please enter address.")}
	if not email:
		return {"ok": False, "message": _("Please enter email.")}
	if not phone:
		return {"ok": False, "message": _("Please enter phone number.")}

	# --- Ghi thông tin người mua vào SI (commit ngay, độc lập với kết quả VNPT) ---
	frappe.db.set_value(
		"Sales Invoice",
		si_name,
		{
			"pos_einvoice_buyer_name": buyer_name,
			"pos_einvoice_buyer_tax_id": tax_id or "",
			"pos_einvoice_buyer_address": buyer_address,
			"pos_einvoice_buyer_email": email,
			"pos_einvoice_buyer_phone": phone,
		},
		update_modified=True,
	)
	frappe.db.commit()  # persist buyer info regardless of provider outcome

	# --- Gọi nhà cung cấp HDDT ---
	issue_error: str = ""
	result: Dict[str, Any] = {}
	try:
		result = _issue_via_provider(si_name)
	except frappe.ValidationError as e:
		issue_error = str(e)
		frappe.log_error(frappe.get_traceback(), "POS self-service e-invoice: provider ValidationError")
	except Exception as e:
		issue_error = str(e)
		frappe.log_error(frappe.get_traceback(), "POS self-service e-invoice: provider error")

	if issue_error:
		return {
			"ok": False,
			"buyer_saved": True,
			"message": _("Buyer information saved but e-invoice issue failed: {0}").format(issue_error),
		}

	frappe.db.set_value(
		"Sales Invoice",
		si_name,
		{"pos_self_service_einvoice_status": "Issued"},
		update_modified=False,
	)
	frappe.db.commit()

	einvoice_no = frappe.db.get_value("Sales Invoice", si_name, "einvoice_no") or ""

	return {
		"ok": True,
		"message": _("Yêu cầu xuất hóa đơn điện tử đã được gửi. Hóa đơn sẽ được gửi về email đăng ký."),
		"einvoice_no": einvoice_no,
		"token": token,
		"provider_result": result,
	}


def _fetch_einvoice_pdf_or_portal(token: str) -> dict:
	"""Nội bộ: lấy PDF (base64) hoặc portal URL từ token.

	Trả về dict:
	  {"pdf_b64": "...", "portal_url": "", "si_name": "...", "einvoice_no": "..."}
	  hoặc {"pdf_b64": "", "portal_url": "https://...", ...}
	Raise RuntimeError nếu không lấy được cả hai.
	"""
	si_name = _invoice_names_from_token(token)
	if not si_name:
		raise RuntimeError(_("Invalid link."))

	si = frappe.db.get_value(
		"Sales Invoice",
		si_name,
		["company", "einvoice_uuid", "einvoice_no", "created_einvoice"],
		as_dict=True,
	)
	if not si:
		raise RuntimeError(_("Invoice not found."))
	if not si.get("einvoice_uuid"):
		raise RuntimeError(_("E-invoice has not been issued yet. Please try again in a moment."))

	company = si.company
	provider = (frappe.db.get_value("Company", company, "provider") or "").strip()
	fkey = si.get("einvoice_uuid") or ""
	einvoice_no = si.get("einvoice_no") or ""

	pdf_b64 = ""
	portal_url = ""
	old_ignore = frappe.flags.ignore_permissions
	frappe.flags.ignore_permissions = True
	try:
		if provider == "VNPT":
			from mbwnext_einvoice.integrations.vnpt.service import get_pdf_by_fkey
			from mbwnext_einvoice.integrations.vnpt.config import get_active_vnpt_config
			try:
				pdf_b64 = get_pdf_by_fkey(fkey, company=company)
			except RuntimeError:
				# PDF chưa sẵn sàng — fallback sang portal URL
				try:
					config = get_active_vnpt_config(company=company, throw=False)
					if config and config.invoice_lookup_url and fkey:
						portal_url = f"{config.invoice_lookup_url.rstrip('/')}?fkey={fkey}"
				except Exception:
					pass
		elif provider == "Viettel":
			raise RuntimeError(_("Viettel PDF download chưa hỗ trợ."))
		elif provider == "MISA":
			raise RuntimeError(_("MISA PDF download chưa hỗ trợ."))
		else:
			raise RuntimeError(_("Provider không hỗ trợ tải PDF."))
	except RuntimeError:
		raise
	except Exception:
		frappe.log_error(frappe.get_traceback(), "POS self-service: _fetch_einvoice_pdf_or_portal")
		raise RuntimeError(_("Could not retrieve invoice. Please try again."))
	finally:
		frappe.flags.ignore_permissions = old_ignore

	if not pdf_b64 and not portal_url:
		raise RuntimeError(_("Hóa đơn đang chờ cơ quan thuế cấp mã. Vui lòng thử lại sau 1-2 phút."))

	return {
		"pdf_b64": pdf_b64,
		"portal_url": portal_url,
		"si_name": si_name,
		"einvoice_no": einvoice_no,
	}


@frappe.whitelist(allow_guest=True)
@rate_limit(limit=20, seconds=3600)
def get_einvoice_view_info(t: str | None = None, token: str | None = None) -> Dict[str, Any]:
	"""Guest: trả JSON chứa pdf_b64 (base64) hoặc portal_url để frontend xử lý."""
	raw_token = (t or token or frappe.form_dict.get("t") or frappe.form_dict.get("token") or "").strip()
	try:
		result = _fetch_einvoice_pdf_or_portal(raw_token)
	except RuntimeError as e:
		return {"ok": False, "message": str(e), "cqt_pending": "cơ quan thuế" in str(e) or "chờ" in str(e)}

	return {
		"ok": True,
		"pdf_b64": result.get("pdf_b64") or "",
		"portal_url": result.get("portal_url") or "",
		"einvoice_no": result.get("einvoice_no") or "",
		"cqt_pending": not result.get("pdf_b64") and not result.get("portal_url"),
	}


@frappe.whitelist(allow_guest=True)
@rate_limit(limit=20, seconds=3600)
def serve_einvoice_pdf(t: str | None = None, token: str | None = None) -> None:
	"""Guest: trả thẳng file PDF (chỉ khi PDF đã sẵn sàng từ VNPT)."""
	import base64 as _b64

	raw_token = (t or token or frappe.form_dict.get("t") or frappe.form_dict.get("token") or "").strip()
	try:
		result = _fetch_einvoice_pdf_or_portal(raw_token)
	except RuntimeError as e:
		frappe.throw(str(e))

	if not result.get("pdf_b64"):
		frappe.throw(_("PDF chưa sẵn sàng. Vui lòng thử lại sau."))

	pdf_bytes = _b64.b64decode(result["pdf_b64"])
	safe_no = (result.get("einvoice_no") or result.get("si_name") or "HDDT").replace("/", "-").replace(" ", "_")
	frappe.local.response.filename = f"HDDT_{safe_no}.pdf"
	frappe.local.response.filecontent = pdf_bytes
	frappe.local.response.type = "download"


def get_self_service_qr_payload(sales_invoice_name: str) -> Dict[str, Any]:
	"""For POS receipt / API (authenticated): URL + optional qr image link."""
	if not sales_invoice_name or not _meta_has_si_field("pos_self_service_einvoice_token"):
		return {}
	try:
		# Lazily create token if submit hook missed it or HDDT was enabled after posting
		ensure_self_service_einvoice_token(sales_invoice_name)
	except Exception:
		frappe.log_error(frappe.get_traceback(), "get_self_service_qr_payload: ensure_self_service_einvoice_token")
	token = frappe.db.get_value("Sales Invoice", sales_invoice_name, "pos_self_service_einvoice_token")
	if not token:
		return {}
	import hashlib
	from urllib.parse import urlparse

	url = get_url(f"/einvoice_self_service?t={token}")
	parsed = urlparse(url)
	site_host = (parsed.netloc or "").strip()

	hd_display_code = hashlib.sha256(token.encode("utf-8")).hexdigest()[:4].upper()

	row = frappe.db.get_value(
		"Sales Invoice",
		sales_invoice_name,
		["pos_profile", "name"],
		as_dict=True,
	)
	inv_digits = "".join(c for c in (row.get("name") or "") if c.isdigit())
	if len(inv_digits) < 10:
		inv_digits = "".join(
			c
			for c in hashlib.md5((row.get("name") or sales_invoice_name).encode()).hexdigest()
			if c.isdigit()
		)
	inv_digits = (inv_digits + "0123456789" * 3)
	inv_tail = inv_digits[-10:]
	pp_digits = "".join(c for c in (row.get("pos_profile") or "") if c.isdigit())
	pp_tail = (pp_digits + "00000")[-5:]
	barcode_text = f"{inv_tail}-{pp_tail}"

	return {
		"url": url,
		"token": token,
		"qr_image_url": _qr_image_url(url),
		"hd_display_code": hd_display_code,
		"barcode_text": barcode_text,
		"site_host": site_host,
	}


def _qr_image_url(data: str) -> str:
	from urllib.parse import quote

	return f"https://api.qrserver.com/v1/create-qr-code/?size=180x180&data={quote(data, safe='')}"
