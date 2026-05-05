# -*- coding: utf-8 -*-
from __future__ import unicode_literals

try:
    import frappe
except ModuleNotFoundError:  # pragma: no cover - frappe may not be installed during setup
    frappe = None

__version__ = "1.14.0"

try:
	from pos_next.pricing_rule_time_window import apply_pricing_rule_utils_patches

	apply_pricing_rule_utils_patches()
except Exception:
	# Frappe/ERPNext not loaded (e.g. packaging) or patch already applied in worker
	pass


def console(*data):
    """Publish data to browser console for debugging"""
    if frappe:
        frappe.publish_realtime("toconsole", data, user=frappe.session.user)
