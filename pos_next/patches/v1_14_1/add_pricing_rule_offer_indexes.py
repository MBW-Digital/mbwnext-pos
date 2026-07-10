"""Speed up pos_next.api.offers.get_offers on large Pricing Rule tables.

Without these indexes, get_offers() runs a full table scan over `tabPricing
Rule` (filtered on company/disable/selling/promotional_scheme/valid dates) on
every POS offer refresh, which becomes very slow once the table holds tens
of thousands of rows.
"""

from __future__ import annotations

import frappe


def execute():
	frappe.db.add_index(
		"Pricing Rule",
		["company", "disable", "selling", "promotional_scheme"],
		index_name="company_disable_selling_scheme_index",
	)
	frappe.db.add_index(
		"Pricing Rule",
		["valid_from", "valid_upto"],
		index_name="valid_from_valid_upto_index",
	)
	frappe.db.commit()
