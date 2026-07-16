# Copyright (c) 2025, BrainWise and contributors
# For license information, please see license.txt

"""
Sales Invoice Hooks
Event handlers for Sales Invoice document events
"""

import frappe
from frappe import _
from frappe.utils import cint, flt


def validate(doc, method=None):
	"""
	Validate hook for Sales Invoice.
	Apply tax inclusive settings based on POS Profile configuration.
	Auto-assign loyalty program to customer if enabled.

	Args:
		doc: Sales Invoice document
		method: Hook method name (unused)
	"""
	apply_tax_inclusive(doc)
	auto_assign_loyalty_program_on_invoice(doc)
	restore_pos_authoritative_discounts(doc)


def capture_pos_authoritative_discounts(doc, method=None):
	"""Snapshot each item's rate/discount_amount/pricing_rules before core validate() runs.

	ERPNext's set_missing_item_details() (inside core validate(), which runs
	after this before_validate hook) re-fetches each item's Pricing Rule and
	re-derives rate = price_list_rate * (1 - discount_percentage / 100) -
	e.g. 499000 * (1 - 40.08/100) = 299000.8 - overwriting the whole-currency
	rate POS actually charged. restore_pos_authoritative_discounts() (in the
	`validate` hook below) puts this snapshot back afterwards.

	Stored on item.flags (in-memory, not a DB field) - safe since
	before_validate and validate share the same Document instance within one
	save()/submit() call. Idempotent per item: update_invoice() also calls
	this manually, earlier, before its own calculate_taxes_and_totals() call
	can corrupt the values - the framework's own before_validate call must
	not overwrite that earlier, still-correct snapshot.
	"""
	if not cint(doc.get("is_pos")):
		return

	for item in doc.get("items", []):
		if item.flags.get("pos_authoritative_discount"):
			continue
		if not item.price_list_rate or not item.get("pricing_rules"):
			continue
		item.flags.pos_authoritative_discount = {
			"price_list_rate": item.price_list_rate,
			"rate": item.rate,
			"discount_amount": item.discount_amount,
			"pricing_rules": item.pricing_rules,
		}


def restore_pos_authoritative_discounts(doc):
	"""Restore the snapshot from capture_pos_authoritative_discounts() after
	core validate() has re-derived (and mis-rounded) the same fields from the
	live Pricing Rule."""
	if not cint(doc.get("is_pos")):
		return

	changed = False
	for item in doc.get("items", []):
		snapshot = item.flags.get("pos_authoritative_discount")
		if not snapshot:
			continue
		if item.rate == snapshot["rate"] and item.discount_percentage == 0:
			continue

		item.price_list_rate = snapshot["price_list_rate"]
		item.rate = snapshot["rate"]
		item.discount_amount = snapshot["discount_amount"]
		item.pricing_rules = snapshot["pricing_rules"]
		# Zero discount_percentage so calculate_taxes_and_totals() below uses
		# `rate = price_list_rate - discount_amount` instead of re-deriving
		# the same fractional rate from discount_percentage.
		item.discount_percentage = 0
		changed = True

	if changed:
		doc.calculate_taxes_and_totals()


def apply_tax_inclusive(doc):
	"""
	Mark taxes as inclusive based on POS Profile setting.

	This function reads the tax_inclusive setting from POS Settings
	and applies it to all taxes in the invoice (except Actual charge type).

	Args:
		doc: Sales Invoice document
	"""
	if not doc.pos_profile:
		return

	try:
		# Get POS Settings for this profile
		pos_settings = frappe.db.get_value(
			"POS Settings",
			{"pos_profile": doc.pos_profile},
			["tax_inclusive"],
			as_dict=True
		)
		tax_inclusive = pos_settings.get("tax_inclusive", 0) if pos_settings else 0
	except Exception:
		tax_inclusive = 0

	has_changes = False
	for tax in doc.get("taxes", []):
		# Skip Actual charge type - these can't be inclusive
		if tax.charge_type == "Actual":
			if tax.included_in_print_rate:
				tax.included_in_print_rate = 0
				has_changes = True
			continue

		# Apply tax inclusive setting
		if tax_inclusive and not tax.included_in_print_rate:
			tax.included_in_print_rate = 1
			has_changes = True
		elif not tax_inclusive and tax.included_in_print_rate:
			tax.included_in_print_rate = 0
			has_changes = True

	# Recalculate if we made changes
	if has_changes:
		doc.calculate_taxes_and_totals()


def auto_assign_loyalty_program_on_invoice(doc):
	"""
	Auto-assign loyalty program to customer if they qualify for one but
	don't have a loyalty program yet.

	Matches the customer against Loyalty Programs with auto_opt_in enabled,
	respecting each program's Customer Group / Customer Territory restrictions
	(same matching rules as erpnext.selling.doctype.customer.customer.set_loyalty_program).
	This ensures customers created before loyalty was enabled (or before they
	matched a program's conditions) can still be opted in at the point of sale.

	Args:
		doc: Sales Invoice document
	"""
	if not doc.is_pos or not doc.customer:
		return

	customer = frappe.get_cached_doc("Customer", doc.customer)
	if customer.loyalty_program:
		return

	from erpnext.selling.doctype.customer.customer import get_loyalty_programs

	loyalty_programs = get_loyalty_programs(customer)

	if len(loyalty_programs) == 1:
		frappe.db.set_value(
			"Customer",
			doc.customer,
			"loyalty_program",
			loyalty_programs[0],
			update_modified=False
		)


def before_cancel(doc, method=None):
	"""
	Before Cancel hook for Sales Invoice.
	- Cancel wallet transactions from loyalty→wallet conversion
	- Cancel any credit redemption journal entries
	"""
	# Cancel linked Wallet Transactions first (Dynamic Link would otherwise block SI cancel)
	try:
		from pos_next.api.wallet import cancel_wallet_transactions_for_invoice
		cancel_wallet_transactions_for_invoice(doc, method)
	except frappe.ValidationError:
		raise
	except Exception as e:
		frappe.log_error(
			title="Wallet Transaction Cancellation Error",
			message=f"Invoice: {doc.name}, Error: {str(e)}\n{frappe.get_traceback()}"
		)
		frappe.throw(
			_("Cannot cancel invoice because linked wallet transaction(s) could not be cancelled: {0}").format(
				str(e)
			)
		)

	try:
		from pos_next.api.credit_sales import cancel_credit_journal_entries
		cancel_credit_journal_entries(doc.name)
	except Exception as e:
		frappe.log_error(
			title="Credit Sale JE Cancellation Error",
			message=f"Invoice: {doc.name}, Error: {str(e)}\n{frappe.get_traceback()}"
		)
		# Don't block invoice cancellation if JE cancellation fails
		frappe.msgprint(
			_("Warning: Some credit journal entries may not have been cancelled. Please check manually."),
			alert=True,
			indicator="orange"
		)
