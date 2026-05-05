# Copyright (c) BrainWise / POS Next

import frappe
from erpnext.accounts.doctype.pricing_rule.pricing_rule import PricingRule as ERPPricingRule
from frappe import _


class PricingRule(ERPPricingRule):
	"""Validates POS Next custom time window fields on Pricing Rule (no core edits)."""

	def cleanup_fields_value(self):
		super().cleanup_fields_value()
		if not self.get("apply_time_window"):
			self.set("valid_time_from", None)
			self.set("valid_time_to", None)

	def validate(self):
		super().validate()
		if self.get("apply_time_window"):
			if not self.get("valid_time_from") or not self.get("valid_time_to"):
				frappe.throw(
					_("Valid Time From and Valid Time To are required when Apply Time Window is enabled")
				)
