# -*- coding: utf-8 -*-
# Copyright (c) 2024, POS Next and contributors
# For license information, please see license.txt

from __future__ import unicode_literals

import frappe
from frappe import _
from frappe.utils import nowdate, now_datetime

from pos_next.api.pos_profile import get_accessible_pos_profiles_for_user, user_can_open_pos_without_hr_shift


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


EARLY_OPEN_MINUTES_BEFORE_START = 30


def _time_str_to_minutes(timestr):
	if not timestr:
		return None
	parts = str(timestr).split(":")
	try:
		return int(parts[0] or 0) * 60 + int(parts[1] or 0)
	except (ValueError, IndexError):
		return None


def is_within_hr_shift_window(shift_row, now_m=None, early_minutes=EARLY_OPEN_MINUTES_BEFORE_START):
	"""True when wall-clock time is inside roster slot or early-open lead window."""
	start = _time_str_to_minutes(shift_row.get("start_time"))
	end = _time_str_to_minutes(shift_row.get("end_time"))
	if start is None or end is None:
		return False
	if now_m is None:
		dt = now_datetime()
		now_m = dt.hour * 60 + dt.minute
	window_start = max(0, start - early_minutes)
	return window_start <= now_m <= end


def validate_hr_shift_for_pos_opening(user=None):
	"""Raise when HR shift rules apply but employee/shift window requirements are not met."""
	effective = user or frappe.session.user
	employee = _get_employee_for_user(effective)
	if not employee:
		frappe.throw(
			_("No Employee linked to your user account. Please contact your administrator.")
		)

	rows = get_today_roster_shifts_for_user(effective)
	if not rows:
		frappe.throw(_("No shift assigned today. You cannot open a shift without an HR schedule."))

	dt = now_datetime()
	now_m = dt.hour * 60 + dt.minute
	if not any(is_within_hr_shift_window(row, now_m) for row in rows):
		frappe.throw(
			_(
				"Your shift has not started yet or has already ended. "
				"Please open during your scheduled shift window."
			)
		)


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
	accessible_profiles = [
		{
			"name": profile.name,
			"use_shift_in_pos": bool(profile.get("custom_use_shift_in_pos")),
		}
		for profile in get_accessible_pos_profiles_for_user()
	]
	can_open_without_hr_shift = user_can_open_pos_without_hr_shift()

	if not employee:
		return {
			"has_employee": False,
			"employee": None,
			"employee_name": None,
			"shifts": [],
			"accessible_profiles": accessible_profiles,
			"can_open_without_hr_shift": can_open_without_hr_shift,
		}

	employee_name = frappe.db.get_value("Employee", employee, "employee_name")

	rows = fetch_today_shift_assignments(employee, today)
	_normalize_assignment_time_rows(rows)

	return {
		"has_employee": True,
		"employee": employee,
		"employee_name": employee_name,
		"shifts": rows,
		"accessible_profiles": accessible_profiles,
		"can_open_without_hr_shift": can_open_without_hr_shift,
	}
