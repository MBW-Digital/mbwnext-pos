"""Sync POS Next Receipt print format HTML (add Bách Hóa Bưu Điện logo)."""

from __future__ import annotations

import json
import os

import frappe


def execute():
	fixture_path = os.path.join(
		frappe.get_app_path("pos_next"),
		"pos_next",
		"fixtures",
		"print_format.json",
	)
	if not os.path.exists(fixture_path):
		return

	with open(fixture_path, encoding="utf-8") as f:
		rows = json.load(f)

	html = next((row.get("html") for row in rows if row.get("name") == "POS Next Receipt"), None)
	if not html or not frappe.db.exists("Print Format", "POS Next Receipt"):
		return

	frappe.db.set_value("Print Format", "POS Next Receipt", "html", html, update_modified=False)
	frappe.db.commit()
