# Copyright (c) BrainWise / POS Next
"""Match Pricing Rules to POS / transaction warehouse (ERPNext tree semantics)."""

from __future__ import annotations

from typing import Iterable, List, Optional, Set

import frappe
from erpnext.stock.doctype.warehouse.warehouse import get_child_warehouses


def pricing_rule_matches_warehouse(
	pr_warehouse: Optional[str], transaction_warehouse: Optional[str]
) -> bool:
	"""
	Return True if a Pricing Rule applies to the transaction warehouse.

	Matches ERPNext pricing_rule.utils warehouse filtering:
	- blank PR warehouse → all warehouses
	- set PR warehouse → transaction warehouse must be the same or a descendant
	"""
	if not pr_warehouse:
		return True
	if not transaction_warehouse:
		return False
	if pr_warehouse == transaction_warehouse:
		return True

	allowed = get_child_warehouses(pr_warehouse) or []
	return transaction_warehouse in allowed


def resolve_transaction_warehouse(pos_profile, items=None) -> Optional[str]:
	"""POS Profile warehouse, or first line warehouse when present."""
	warehouse = getattr(pos_profile, "warehouse", None) or pos_profile.get("warehouse")
	if warehouse:
		return warehouse

	for row in items or []:
		row_wh = row.get("warehouse") if isinstance(row, dict) else getattr(row, "warehouse", None)
		if row_wh:
			return row_wh

	return None


def filter_pricing_rule_names_by_warehouse(
	rule_names: Iterable[str], transaction_warehouse: Optional[str]
) -> List[str]:
	if not rule_names:
		return []

	if not transaction_warehouse:
		return list(rule_names)

	warehouse_map = {
		row["name"]: row.get("warehouse")
		for row in frappe.get_all(
			"Pricing Rule",
			filters={"name": ["in", list(rule_names)]},
			fields=["name", "warehouse"],
		)
	}

	return [
		name
		for name in rule_names
		if pricing_rule_matches_warehouse(warehouse_map.get(name), transaction_warehouse)
	]


def filter_offer_dicts_by_warehouse(
	offers: List[dict], transaction_warehouse: Optional[str]
) -> List[dict]:
	if not transaction_warehouse:
		return offers

	return [
		offer
		for offer in offers
		if pricing_rule_matches_warehouse(offer.get("warehouse"), transaction_warehouse)
	]
