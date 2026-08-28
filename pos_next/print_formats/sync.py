# Copyright (c) 2026, POS Next contributors
"""Sync Print Format records from template files."""

from __future__ import annotations

import os

import frappe


def _template_path(filename: str) -> str:
	return os.path.join(
		frappe.get_app_path("pos_next"),
		"templates",
		"print_formats",
		filename,
	)


def sync_print_format_from_template(
	name: str,
	template_filename: str,
	*,
	doc_type: str = "Sales Invoice",
	module: str = "POS Next",
):
	"""Create or update a Jinja Print Format from a template file.

	`doc_type` mặc định là Sales Invoice: POS của app này tạo Sales Invoice chứ
	không phải POS Invoice. Khai nhầm doctype thì mẫu vẫn in được qua /printview
	(Frappe không chặn), nhưng KHÔNG hiện trong danh sách mẫu in của Sales
	Invoice trên desk, nên kế toán không chọn được.
	"""
	path = _template_path(template_filename)
	if not os.path.exists(path):
		return

	with open(path, encoding="utf-8") as f:
		html = f.read()

	if frappe.db.exists("Print Format", name):
		frappe.db.set_value("Print Format", name, "html", html, update_modified=False)
		return

	doc = frappe.get_doc(
		{
			"doctype": "Print Format",
			"name": name,
			"doc_type": doc_type,
			"module": module,
			"html": html,
			"custom_format": 1,
			"disabled": 0,
			"standard": "No",
			"print_format_type": "Jinja",
			"default_print_language": "vi",
			"font_size": 10,
		}
	)
	doc.insert(ignore_permissions=True)


def sync_pos_retail_receipt():
	sync_print_format_from_template("POS Retail Receipt", "pos_retail_receipt.html")
