# Copyright (c) 2026, BrainWise and contributors
# For license information, please see license.txt

import frappe
from frappe import _


def validate(doc, method=None):
	rows = doc.get("loyalty_excluded_item_lines") or []
	item_lines = [row.item_line for row in rows if row.item_line]

	if len(item_lines) != len(set(item_lines)):
		frappe.throw(
			_("Duplicate Item Line found in Loyalty Excluded Item Lines table"),
			title=_("Duplicate Item Line"),
		)
