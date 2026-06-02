# -*- coding: utf-8 -*-
# Copyright (c) 2025, BrainWise and contributors
# Shared bank-transfer (POS) GL + payment rows — used by VNPost Pay.

from __future__ import unicode_literals

import json
import re

import frappe
from erpnext.accounts.general_ledger import make_gl_entries
from erpnext.accounts.utils import get_account_currency, update_voucher_outstanding
from frappe import _
from frappe.utils import flt

ORDER_PREFIX = "DH"


def get_invoice_payable_outstanding(doc):
	"""Amount still due via bank transfer (handles draft with partial cash payments)."""
	if doc.docstatus == 1:
		return flt(doc.outstanding_amount, 2)
	paid = sum(flt(p.amount) for p in (doc.get("payments") or []))
	return max(flt(doc.grand_total, 2) - paid, 0)


def get_bank_transfer_mode_of_payment():
	return (
		frappe.db.get_value("Mode of Payment", "Bank Draft", "name")
		or frappe.db.get_value("Mode of Payment", "Chuyển khoản", "name")
		or frappe.db.get_value("Mode of Payment", {"type": "Bank"}, "name")
		or "Bank"
	)


def add_bank_transfer_payment_to_invoice(
	doc, amount, mode_of_payment, reference_no, transaction_id=None
):
	"""Chuyển khoản: Sales Invoice Payment child row + direct GL (POS-style, no Payment Entry)."""
	from pos_next.api.invoices import get_payment_account

	invoice_name = doc.name
	company = doc.company
	conversion_rate = flt(doc.conversion_rate) or 1
	precision = doc.precision("base_paid_amount")
	base_amount = flt(amount * conversion_rate, precision)

	account_info = get_payment_account(mode_of_payment, company)
	account = account_info.get("account") if account_info else None
	if not account:
		frappe.throw(_("No account found for Mode of Payment {0}").format(mode_of_payment))

	payment_type = frappe.db.get_value("Mode of Payment", mode_of_payment, "type") or "Bank"

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

	against_voucher = doc.name
	if doc.is_return and doc.return_against and not doc.update_outstanding_for_self:
		against_voucher = doc.return_against

	payment_mode_account_currency = get_account_currency(account)
	gl_entries = [
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
		),
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
		),
	]

	make_gl_entries(gl_entries, update_outstanding="No", merge_entries=False, from_repost=0)
	update_voucher_outstanding(
		voucher_type=doc.doctype,
		voucher_no=against_voucher,
		account=doc.debit_to,
		party_type="Customer",
		party=doc.customer,
	)
	frappe.db.commit()


def process_incoming_transfer_for_invoice(
	invoice_name,
	amount,
	gateway_transaction_id,
	reference_code,
	_remarks,
	raw_data,
):
	"""Submit draft invoice if needed, add bank payment, log."""
	doc = frappe.get_doc("Sales Invoice", invoice_name)
	if doc.docstatus == 2:
		frappe.throw(_("Cannot add payment to cancelled invoice"))
	if doc.docstatus == 0:
		from pos_next.api.invoices import submit_pos_invoice_for_bank_transfer

		doc.flags.ignore_permissions = True
		frappe.flags.ignore_account_permission = True
		submit_pos_invoice_for_bank_transfer(invoice_name)
		frappe.db.commit()
		doc = frappe.get_doc("Sales Invoice", invoice_name)
	elif doc.docstatus == 1:
		against_voucher = doc.name
		if doc.is_return and doc.return_against and not doc.update_outstanding_for_self:
			against_voucher = doc.return_against
		update_voucher_outstanding(
			voucher_type=doc.doctype,
			voucher_no=against_voucher,
			account=doc.debit_to,
			party_type="Customer",
			party=doc.customer,
		)
		doc.reload()
	if flt(doc.outstanding_amount, 2) <= 0:
		return
	outstanding = flt(doc.outstanding_amount, 2)
	if outstanding <= 0:
		return
	pay_amount = min(flt(amount, 2) or outstanding, outstanding)
	if abs(flt(amount, 2) - outstanding) > 0.01:
		frappe.log_error(
			f"VNPost amount mismatch: invoice={invoice_name} outstanding={outstanding} got={amount}; paying {pay_amount}",
			"VNPost Pay",
		)
	mode_of_payment = get_bank_transfer_mode_of_payment()
	add_bank_transfer_payment_to_invoice(
		doc, pay_amount, mode_of_payment, reference_code or str(gateway_transaction_id), gateway_transaction_id
	)
	if gateway_transaction_id:
		gateway_dedup_log(
			gateway_id=str(gateway_transaction_id),
			invoice_name=invoice_name,
			amount=amount,
			reference_code=reference_code,
			data=raw_data,
		)


def extract_order_id_from_content(content):
	if not content:
		return None
	m = re.search(rf"{re.escape(ORDER_PREFIX)}([\w\-]+)", str(content), re.IGNORECASE)
	return m.group(1) if m else None


def resolve_invoice_name(order_id):
	if str(order_id).upper().startswith("SINV-"):
		if frappe.db.exists("Sales Invoice", order_id):
			return order_id
		return None
	if str(order_id).isdigit():
		for name in (f"SINV-{int(order_id):05d}", f"SINV-{order_id}", order_id):
			if frappe.db.exists("Sales Invoice", name):
				return name
	return frappe.db.get_value(
		"Sales Invoice",
		{"name": ["like", f"%{order_id}%"]},
		"name",
		order_by="creation desc",
	)


def gateway_dedup_seen(gateway_id):
	if not gateway_id:
		return False
	key = f"vnpost_tx|{gateway_id}"
	if frappe.cache().get_value(key):
		return True
	return False


def gateway_dedup_set(gateway_id):
	if gateway_id:
		frappe.cache().set_value(f"vnpost_tx|{gateway_id}", 1, expires_in_sec=90 * 24 * 3600)


def gateway_dedup_log(gateway_id, invoice_name, amount, reference_code, data):
	"""Deduplication + best-effort row in VNPost Transaction Log if doctype exists."""
	if not gateway_id:
		return
	if frappe.db.table_exists("VNPost Transaction Log"):
		try:
			frappe.get_doc(
				{
					"doctype": "VNPost Transaction Log",
					"transaction_id": str(gateway_id),
					"sales_invoice": invoice_name,
					"amount": amount,
					"reference_code": reference_code,
					"raw_data": json.dumps(data) if data else "",
				}
			).insert(ignore_permissions=True)
			frappe.db.commit()
		except Exception as e:
			frappe.log_error(str(e), "VNPost Transaction Log")
	gateway_dedup_set(gateway_id)
