# Copyright (c) 2026, POS Next contributors
"""Shared receipt metadata and Vietnamese amount formatting for print templates."""

from __future__ import annotations

from typing import Any

import frappe
from frappe.utils import flt, format_datetime, now_datetime


def format_vn_amount(value, decimals: int = 0) -> str:
	"""Format number Việt Nam: thousands `.`, decimal `,` (vd. 27.685,19)."""
	v = flt(value)
	decimals = int(decimals or 0)
	if decimals <= 0:
		n = int(round(abs(v)))
		int_part = f"{n:,}".replace(",", ".")
		return f"-{int_part}" if v < 0 else int_part
	sign = "-" if v < 0 else ""
	v = abs(v)
	whole = int(v)
	frac = round((v - whole) * (10**decimals))
	if frac >= 10**decimals:
		whole += 1
		frac = 0
	int_part = f"{whole:,}".replace(",", ".")
	frac_str = str(int(frac)).zfill(decimals)
	return f"{sign}{int_part},{frac_str}"


def primary_tax_rate_percent(doc) -> float | None:
	"""Lấy % thuế dòng đầu có rate > 0 (Sales Taxes and Charges)."""
	rows = getattr(doc, "taxes", None) or []
	for row in rows:
		rate = flt(getattr(row, "rate", None) or 0)
		if rate > 0:
			return rate
	return None


def receipt_vat_amount_for_print(doc) -> float:
	"""Tiền thuế hiển thị phiếu: total_taxes_and_charges hoặc cộng tax_amount các dòng (tax-inclusive)."""
	base = flt(getattr(doc, "total_taxes_and_charges", None) or 0)
	if base > 0:
		return base
	s = 0.0
	for row in getattr(doc, "taxes", None) or []:
		s += flt(getattr(row, "tax_amount", None) or 0)
	return flt(s)


def receipt_invoice_discount_for_print(doc) -> float:
	"""Chiết khấu cấp hóa đơn — luôn hiển thị như số dương."""
	return abs(flt(getattr(doc, "discount_amount", None) or 0))


def receipt_vat_label_for_print(doc, vat_amt: float) -> str:
	rate = primary_tax_rate_percent(doc)
	if rate is not None:
		if rate == int(rate):
			return f"VAT {int(rate)}%"
		return f"VAT {rate:g}%"
	if flt(vat_amt) > 0:
		return "Thuế GTGT"
	return "VAT 0%"


def receipt_totals_aux_for_print(doc):
	"""Meta cho khối tổng kết phiếu in (Chiết khấu / VAT)."""
	vat_amt = receipt_vat_amount_for_print(doc)
	disc = receipt_invoice_discount_for_print(doc)
	vat_lbl = receipt_vat_label_for_print(doc, vat_amt)
	return frappe._dict(vat_amt=vat_amt, disc=disc, vat_lbl=vat_lbl)


def enrich_invoice_dict_for_print(inv: dict[str, Any]) -> dict[str, Any]:
	"""Các key bổ sung cho phiếu in (HTML fallback POS + có thể dùng API)."""
	out: dict[str, Any] = {}
	out["receipt_print_datetime"] = format_datetime(now_datetime(), "dd/MM/yyyy HH:mm")
	company = inv.get("company") or ""
	if company:
		row = frappe.db.get_value(
			"Company",
			company,
			["company_name", "phone_no"],
			as_dict=True,
		)
		out["receipt_company_display_name"] = (row or {}).get("company_name") or company
		out["receipt_company_phone"] = (row or {}).get("phone_no") or ""
	else:
		out["receipt_company_display_name"] = company
		out["receipt_company_phone"] = ""
	out["receipt_company_address"] = (inv.get("company_address_display") or "").strip()
	pp = inv.get("pos_profile")
	wh = frappe.db.get_value("POS Profile", pp, "warehouse") if pp else None
	out["receipt_branch_label"] = (
		frappe.db.get_value("Warehouse", wh, "warehouse_name") if wh else (pp or "")
	)
	owner = inv.get("owner")
	out["receipt_salesperson"] = (
		frappe.db.get_value("User", owner, "full_name") if owner else ""
	) or (owner or "")
	out["receipt_customer_phone"] = (
		(inv.get("contact_mobile") or "").strip()
		or (inv.get("mobile_no") or "").strip()
		or (inv.get("pos_einvoice_buyer_phone") or "").strip()
	)
	out["receipt_msch"] = ""

	inv_name = inv.get("name")
	cust = inv.get("customer")
	earned = 0.0
	if inv_name and frappe.db.table_exists("Loyalty Point Entry"):
		res = frappe.db.sql(
			"""
			select coalesce(sum(loyalty_points), 0)
			from `tabLoyalty Point Entry`
			where invoice = %(inv)s and invoice_type = %(dt)s and loyalty_points > 0
			""",
			{"inv": inv_name, "dt": "Sales Invoice"},
		)
		if res:
			earned = flt(res[0][0])
	balance = 0.0
	if cust and frappe.db.table_exists("Loyalty Program Member"):
		res2 = frappe.db.sql(
			"""
			select coalesce(loyalty_points, 0) from `tabLoyalty Program Member`
			where customer = %(c)s
			order by modified desc
			limit 1
			""",
			{"c": cust},
		)
		if res2:
			balance = flt(res2[0][0])
	out["receipt_loyalty_earned"] = earned
	out["receipt_loyalty_balance"] = balance
	return out


def invoice_meta_for_jinja(doc):
	"""Print Format (Jinja): frappe.get_attr('pos_next.api.receipt_print.invoice_meta_for_jinja')(doc)"""
	return enrich_invoice_dict_for_print(doc.as_dict())


def einvoice_qr_payload_for_jinja(invoice_name: str) -> dict[str, Any]:
	from pos_next.api.einvoice_self_service import get_self_service_qr_payload

	return get_self_service_qr_payload(invoice_name or "") or {}
