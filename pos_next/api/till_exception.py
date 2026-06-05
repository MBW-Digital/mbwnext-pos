# -*- coding: utf-8 -*-
# Copyright (c) 2026, POS Next and contributors
# For license information, please see license.txt

from __future__ import unicode_literals

import frappe
from frappe import _
from frappe.utils import cint, now_datetime

EVENT_TYPES = frozenset(("Manual Open", "Print Bill"))


def _ensure_pos_profile_access(pos_profile: str):
	if not pos_profile:
		frappe.throw(_("POS Profile is required"))

	has_access = frappe.db.exists(
		"POS Profile User",
		{"parent": pos_profile, "user": frappe.session.user},
	)

	if not has_access:
		frappe.throw(_("You don't have access to this POS Profile"))


@frappe.whitelist()
def log_cash_drawer_event(pos_profile, event_type, sales_invoice=None):
	"""
	Record a cash drawer open for audit (Till Exception Report).

	``event_time`` is always set on the server to the current datetime (second precision).
	"""
	event_type = (event_type or "").strip()
	if event_type not in EVENT_TYPES:
		frappe.throw(_("Invalid event type"))

	_ensure_pos_profile_access(pos_profile)

	company = frappe.db.get_value("POS Profile", pos_profile, "company")
	if not company:
		frappe.throw(_("Company not found for POS Profile"))

	pos_enabled = cint(
		frappe.db.get_value("POS Settings", {"pos_profile": pos_profile}, "enabled") or 0
	)
	allow_manual = cint(
		frappe.db.get_value("POS Settings", {"pos_profile": pos_profile}, "allow_manual_cash_drawer")
		or 0
	)

	if event_type == "Manual Open":
		if not pos_enabled:
			frappe.throw(_("POS Settings is disabled for this profile"))
		if not allow_manual:
			frappe.throw(_("Manual cash drawer open is not allowed for this POS Profile"))

	if event_type == "Print Bill":
		if not sales_invoice:
			frappe.throw(_("Sales Invoice is required for this event"))
		inv_profile = frappe.db.get_value("Sales Invoice", sales_invoice, "pos_profile")
		if inv_profile != pos_profile:
			frappe.throw(_("Sales Invoice does not belong to this POS Profile"))

	doc = frappe.new_doc("Till Exception Report")
	doc.event_type = event_type
	doc.event_time = now_datetime()
	doc.pos_profile = pos_profile
	doc.company = company
	doc.cashier = frappe.session.user
	doc.sales_invoice = sales_invoice
	doc.insert()

	return {"name": doc.name, "event_time": doc.event_time}
