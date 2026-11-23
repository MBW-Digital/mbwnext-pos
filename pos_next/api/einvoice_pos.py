# Copyright (c) 2026, Tuanbd and contributors
"""Cashier issues the e-invoice from the POS right after the sale (PM-FEAT-00094 Ha Vang)."""

from __future__ import annotations

from typing import Any, Dict

import frappe
from frappe import _
from frappe.utils import cint

from pos_next.api.einvoice_self_service import (
	_company_uses_einvoice,
	_issue_via_provider,
	_meta_has_si_field,
	_resolve_buyer_master_by_tax_id,
)

BUYER_FIELDS = (
	"pos_einvoice_buyer_name",
	"pos_einvoice_buyer_tax_id",
	"pos_einvoice_buyer_address",
	"pos_einvoice_buyer_email",
	"pos_einvoice_buyer_phone",
)


def _load_invoice(sales_invoice: str):
	if not sales_invoice or not frappe.db.exists("Sales Invoice", sales_invoice):
		return None
	# Read permission carries the till's User Permission: a cashier only reaches bills of their own till
	if not frappe.has_permission("Sales Invoice", "read", sales_invoice):
		frappe.throw(_("You don't have permission to view this invoice"), frappe.PermissionError)
	return frappe.get_doc("Sales Invoice", sales_invoice)


def _blocked_reason(si) -> str:
	if si.docstatus != 1:
		return _("The invoice is not completed yet.")
	if si.is_return:
		return _("Return invoices are adjusted by the accountant, not from the POS.")
	if not _company_uses_einvoice(si.company):
		return _("E-invoicing is not enabled for this company.")
	return ""


def _customer_prefill(si) -> Dict[str, str]:
	"""Buyer data the cashier starts from: what is staged on the bill, else the customer master."""
	staged = {f: (si.get(f) or "").strip() for f in BUYER_FIELDS if _meta_has_si_field(f)}
	if staged.get("pos_einvoice_buyer_name"):
		return {
			"buyer_name": staged.get("pos_einvoice_buyer_name", ""),
			"tax_id": staged.get("pos_einvoice_buyer_tax_id", ""),
			"address": staged.get("pos_einvoice_buyer_address", ""),
			"email": staged.get("pos_einvoice_buyer_email", ""),
			"phone": staged.get("pos_einvoice_buyer_phone", ""),
		}

	tax_id = (si.get("tax_id") or frappe.db.get_value("Customer", si.customer, "tax_id") or "").strip()
	address, phone = "", ""
	try:
		from mbwnext_einvoice.integrations.common import buyer_address_and_mobile

		address, phone = buyer_address_and_mobile(si)
	except Exception:
		pass
	return {
		"buyer_name": si.customer_name or si.customer or "",
		"tax_id": tax_id,
		"address": address or "",
		"email": (si.get("contact_email") or "").strip(),
		"phone": phone or (si.get("contact_mobile") or "").strip(),
	}


@frappe.whitelist()
def get_pos_einvoice_state(sales_invoice: str) -> Dict[str, Any]:
	"""Can this bill get its e-invoice from the POS, and with which buyer data to start."""
	si = _load_invoice(sales_invoice)
	if not si:
		# Sold offline and not synced yet: the bill is not on the server
		return {"can_issue": False, "reason": _("The invoice is still syncing. Try again in a moment.")}
	if cint(si.get("created_einvoice")):
		return {
			"can_issue": False,
			"issued": True,
			"einvoice_no": si.get("einvoice_no") or "",
			"cqt_status": si.get("einvoice_cqt_status") or "",
		}
	reason = _blocked_reason(si)
	if reason:
		return {"can_issue": False, "reason": reason}
	prefill = _customer_prefill(si)
	return {
		"can_issue": True,
		"prefill": prefill,
		# A buyer with a tax code is most likely a company: open on that tab
		"buyer_type": "company" if len("".join(c for c in prefill["tax_id"] if c.isdigit())) in (10, 13) else "retail",
	}


@frappe.whitelist()
def lookup_buyer(tax_id: str) -> Dict[str, Any]:
	"""Company name and address from the customer list by tax code (no call to the tax authority)."""
	return _resolve_buyer_master_by_tax_id(tax_id or "")


@frappe.whitelist()
def issue_pos_einvoice(
	sales_invoice: str,
	buyer_type: str = "retail",
	buyer_name: str | None = None,
	tax_id: str | None = None,
	address: str | None = None,
	email: str | None = None,
	phone: str | None = None,
) -> Dict[str, Any]:
	"""Stage the buyer on the bill, then issue through the company's provider (same path as the QR page)."""
	from mbwnext_einvoice.integrations.common import ensure_valid_buyer_tax_code

	si = _load_invoice(sales_invoice)
	if not si:
		frappe.throw(_("The invoice is still syncing. Try again in a moment."))
	if cint(si.get("created_einvoice")):
		frappe.throw(_("E-invoice {0} has already been issued for this invoice.").format(si.get("einvoice_no") or ""))
	reason = _blocked_reason(si)
	if reason:
		frappe.throw(reason)

	buyer_name = (buyer_name or "").strip()
	tax_id = "".join((tax_id or "").split())
	address = (address or "").strip()
	email = (email or "").strip()
	phone = (phone or "").strip()

	if buyer_type == "company":
		if not tax_id:
			frappe.throw(_("Please enter the company's tax code."))
		ensure_valid_buyer_tax_code(tax_id)
		if not buyer_name:
			buyer_name = (_resolve_buyer_master_by_tax_id(tax_id).get("name") or "").strip()
		if not buyer_name:
			frappe.throw(_("Please enter the company name."))
		if not address:
			frappe.throw(_("Please enter the company address."))
	else:
		ensure_valid_buyer_tax_code(tax_id)
		buyer_name = buyer_name or si.customer_name or si.customer

	if email and not frappe.utils.validate_email_address(email):
		frappe.throw(_("Email {0} is not valid.").format(email))

	staged = dict(
		zip(BUYER_FIELDS, (buyer_name, tax_id, address, email, phone)),
	)
	staged = {k: v for k, v in staged.items() if _meta_has_si_field(k)}
	if staged:
		frappe.db.set_value("Sales Invoice", si.name, staged, update_modified=False)
		frappe.db.commit()

	result = _issue_via_provider(si.name)
	if _meta_has_si_field("pos_self_service_einvoice_status"):
		frappe.db.set_value("Sales Invoice", si.name, "pos_self_service_einvoice_status", "Issued", update_modified=False)
		frappe.db.commit()

	issued = frappe.db.get_value(
		"Sales Invoice", si.name, ["einvoice_no", "einvoice_cqt_status"], as_dict=True
	)
	return {
		"ok": True,
		"einvoice_no": issued.einvoice_no or result.get("einvoice_no") or "",
		"cqt_status": issued.einvoice_cqt_status or "",
		"paired_return": result.get("paired_return"),
	}
