# Copyright (c) 2026, BrainWise and contributors
# For license information, please see license.txt

import frappe
from frappe.utils import cint, flt


def get_loyalty_excluded_item_lines(loyalty_program):
	"""Return all Item Line names excluded from loyalty (including descendants)."""
	if not loyalty_program:
		return set()

	program = frappe.get_cached_doc("Loyalty Program", loyalty_program)
	rows = program.get("loyalty_excluded_item_lines") or []
	if not rows:
		return set()

	excluded = set()
	for row in rows:
		if row.item_line:
			excluded.update(_get_item_line_descendants(row.item_line))
	return excluded


def _get_item_line_descendants(root):
	lft, rgt = frappe.db.get_value("Item Line", root, ["lft", "rgt"])
	if lft is None:
		return {root}

	return set(
		frappe.get_all(
			"Item Line",
			filters={"lft": [">=", lft], "rgt": ["<=", rgt]},
			pluck="name",
		)
	)


def get_item_line_for_row(item):
	if item.get("item_line"):
		return item.item_line
	if item.item_code:
		return frappe.db.get_value("Item", item.item_code, "custom_item_line")
	return None


def get_loyalty_eligible_amount(doc, excluded_item_lines=None):
	"""Calculate loyalty-eligible amount after excluding configured item lines."""
	current_amount = flt(doc.grand_total) - cint(doc.loyalty_amount)

	if not excluded_item_lines or not doc.get("items"):
		return current_amount

	total_net = sum(abs(flt(item.net_amount)) for item in doc.items if item.item_code)
	if not total_net:
		return current_amount

	excluded_net = 0
	for item in doc.items:
		if not item.item_code:
			continue
		item_line = get_item_line_for_row(item)
		if item_line in excluded_item_lines:
			excluded_net += abs(flt(item.net_amount))

	included_ratio = (total_net - excluded_net) / total_net
	return current_amount * included_ratio


def get_returned_loyalty_eligible_amount(doc, excluded_item_lines):
	returns = frappe.get_all(
		"Sales Invoice",
		filters={"docstatus": 1, "is_return": 1, "return_against": doc.name},
		pluck="name",
	)
	if not returns:
		return 0

	returned_eligible = sum(
		get_loyalty_eligible_amount(frappe.get_doc("Sales Invoice", name), excluded_item_lines)
		for name in returns
	)
	return abs(returned_eligible)
