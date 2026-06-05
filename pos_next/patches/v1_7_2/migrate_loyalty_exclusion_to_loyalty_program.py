"""Move loyalty exclusion config from POS Profile to Loyalty Program (cleanup legacy fields)."""

from __future__ import annotations

import frappe


def execute():
	for name in (
		"POS Profile-custom_section_break_loyalty_exclusion",
		"POS Profile-loyalty_excluded_item_lines",
	):
		if frappe.db.exists("Custom Field", name):
			frappe.delete_doc("Custom Field", name, force=1, ignore_permissions=True)

	if frappe.db.exists("DocType", "POS Profile Loyalty Excluded Item Line"):
		frappe.delete_doc(
			"DocType",
			"POS Profile Loyalty Excluded Item Line",
			force=1,
			ignore_permissions=True,
		)

	frappe.db.commit()
