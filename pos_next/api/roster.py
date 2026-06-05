# -*- coding: utf-8 -*-
# Copyright (c) 2024, POS Next and contributors
# For license information, please see license.txt

from __future__ import unicode_literals

import frappe
from frappe.utils import nowdate


def _get_employee_for_user(user=None):
	"""Map a Frappe user to the linked Employee via Employee.user_id.

	Returns None (does not throw) so callers can handle the "no employee" case
	gracefully on the POS screen.
	"""
	effective_user = user or frappe.session.user
	return frappe.db.get_value(
		"Employee",
		{"user_id": effective_user, "status": "Active"},
		"name",
	)


def _normalize_assignment_time_rows(rows):
	"""Frappe returns Time columns as timedelta; convert to HH:MM strings."""
	for row in rows:
		for field in ("start_time", "end_time"):
			val = row.get(field)
			if val is not None and hasattr(val, "total_seconds"):
				total_secs = int(val.total_seconds())
				h, rem = divmod(total_secs, 3600)
				m = rem // 60
				row[field] = f"{h:02d}:{m:02d}"


def fetch_today_shift_assignments(employee, on_date):
	"""Load Shift Assignment rows for employee on calendar date (ordered by start_time)."""
	return frappe.db.sql(
		"""
		SELECT
			sa.name,
			sa.shift_type,
			sa.shift_location,
			st.start_time,
			st.end_time,
			st.color
		FROM `tabShift Assignment` sa
		INNER JOIN `tabShift Type` st ON sa.shift_type = st.name
		WHERE sa.employee = %s
		  AND sa.docstatus = 1
		  AND sa.start_date <= %s
		  AND (sa.end_date >= %s OR sa.end_date IS NULL)
		ORDER BY st.start_time ASC
		""",
		(employee, on_date, on_date),
		as_dict=True,
	)


def get_today_roster_shifts_for_user(user=None):
	"""Today's roster rows for a user (same shape as get_today_shifts['shifts']). Used by POS rules."""
	effective = user or frappe.session.user
	employee = _get_employee_for_user(effective)
	if not employee:
		return []
	rows = fetch_today_shift_assignments(employee, nowdate())
	_normalize_assignment_time_rows(rows)
	return rows


@frappe.whitelist()
def get_today_shifts():
	"""Return HR Shift Assignments active today for the current POS user.

	Response shape::

		{
		  "has_employee": bool,
		  "employee": str | None,
		  "employee_name": str | None,
		  "shifts": [
		    {
		      "name": str,           # Shift Assignment name
		      "shift_type": str,     # Shift Type name
		      "shift_location": str | None,
		      "start_time": "HH:MM",
		      "end_time": "HH:MM",
		      "color": str | None    # hex color on Shift Type
		    },
		    ...
		  ]
		}
	"""
	today = nowdate()
	employee = _get_employee_for_user()

	if not employee:
		return {
			"has_employee": False,
			"employee": None,
			"employee_name": None,
			"shifts": [],
		}

	employee_name = frappe.db.get_value("Employee", employee, "employee_name")

	rows = fetch_today_shift_assignments(employee, today)
	_normalize_assignment_time_rows(rows)

	return {
		"has_employee": True,
		"employee": employee,
		"employee_name": employee_name,
		"shifts": rows,
	}
