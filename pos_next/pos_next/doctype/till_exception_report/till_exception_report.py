# Copyright (c) 2026, POS Next and contributors
# For license information, please see license.txt

import frappe
from frappe import _
from frappe.model.document import Document
from frappe.utils import format_datetime, get_url_to_form, now_datetime


class TillExceptionReport(Document):
	def before_insert(self):
		if not self.event_time:
			self.event_time = now_datetime()
		if not self.cashier:
			self.cashier = frappe.session.user
		if self.pos_profile and not self.company:
			self.company = frappe.db.get_value("POS Profile", self.pos_profile, "company")

	# def after_insert(self):
	# 	frappe.enqueue(
	# 		"pos_next.pos_next.doctype.till_exception_report.till_exception_report.send_manager_notification",
	# 		queue="short",
	# 		job_name=f"till_exception_notify_{self.name}",
	# 		doc_name=self.name,
	# 		now=frappe.flags.in_test,
	# 	)


def send_manager_notification(doc_name):
	try:
		doc = frappe.get_doc("Till Exception Report", doc_name)
	except frappe.DoesNotExistError:
		return

	recipients = _sales_manager_emails_for_company(doc.company)
	if not recipients:
		return

	subject = _("POS cash drawer event: {0}").format(doc.event_type)
	time_disp = format_datetime(doc.event_time)
	body = "\n".join(
		[
			_("Event type: {0}").format(doc.event_type),
			_("Time (server): {0}").format(time_disp),
			_("POS Profile: {0}").format(doc.pos_profile),
			_("Company: {0}").format(doc.company or ""),
			_("Cashier: {0}").format(doc.cashier),
			_("Sales Invoice: {0}").format(doc.sales_invoice or "—"),
			"",
			_("Open in desk: {0}").format(get_url_to_form("Till Exception Report", doc.name)),
		]
	)

	try:
		frappe.sendmail(recipients=recipients, subject=subject, message=body)
	except Exception:
		frappe.log_error(frappe.get_traceback(), "Till Exception Report email")


def _sales_manager_emails_for_company(company):
	if not company:
		return []

	rows = frappe.db.sql(
		"""
		SELECT DISTINCT u.email
		FROM `tabUser` u
		INNER JOIN `tabHas Role` hr
			ON hr.parent = u.name AND hr.parenttype = 'User'
		WHERE hr.role = 'Sales Manager'
			AND IFNULL(u.enabled, 0) = 1
			AND IFNULL(u.email, '') != ''
			AND (
				EXISTS (
					SELECT 1 FROM `tabUser Permission` up
					WHERE up.user = u.name
						AND IFNULL(up.ignore_user_permissions, 0) = 0
						AND up.allow = 'Company'
						AND up.for_value = %(company)s
				)
				OR NOT EXISTS (
					SELECT 1 FROM `tabUser Permission` up2
					WHERE up2.user = u.name
						AND IFNULL(up2.ignore_user_permissions, 0) = 0
						AND up2.allow = 'Company'
				)
			)
		""",
		{"company": company},
	)

	return [r[0] for r in rows if r and r[0]]
