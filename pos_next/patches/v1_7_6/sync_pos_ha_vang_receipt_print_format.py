"""Install / update POS HA Vang Receipt print format."""

from __future__ import annotations

import frappe

from pos_next.print_formats.sync import sync_pos_ha_vang_receipt


def execute():
	sync_pos_ha_vang_receipt()
	frappe.db.commit()
