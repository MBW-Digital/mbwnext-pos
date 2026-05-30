# Copyright (c) 2026, BrainWise and contributors
# For license information, please see license.txt

"""
Product Bundle match detection for POS.

When cashiers add individual components instead of the bundle parent item,
detect complete or partial matches against Product Bundle definitions.
"""

from __future__ import annotations

import json
import math
from typing import Any

import frappe
from frappe.utils import flt


def _parse_cart_items(cart_items):
	if isinstance(cart_items, str):
		cart_items = json.loads(cart_items)
	return cart_items or []


@frappe.request_cache
def _get_bundle_parent_codes() -> set[str]:
	return set(
		frappe.get_all(
			"Product Bundle",
			filters={"disabled": 0},
			pluck="new_item_code",
		)
	)


def _component_match_codes(comp: dict) -> list[str]:
	codes = []
	for key in ("item_code", "bundle_item"):
		code = comp.get(key)
		if code and code not in codes:
			codes.append(code)
	return codes


def _component_available(cart_qty: dict[str, float], comp: dict) -> float:
	return sum(flt(cart_qty.get(code, 0)) for code in _component_match_codes(comp))


def _suggest_item_for_component(comp: dict) -> tuple[str, str]:
	"""Return (item_code, item_name) to offer when this component is missing."""
	if comp.get("bundle_item"):
		return comp["bundle_item"], comp.get("bundle_item_name") or comp.get("bundle_item")
	return comp.get("item_code"), comp.get("item_name") or comp.get("item_code")


@frappe.request_cache
def _get_active_bundles() -> list[dict[str, Any]]:
	bundles = frappe.get_all(
		"Product Bundle",
		filters={"disabled": 0},
		fields=["name", "new_item_code", "description"],
	)
	if not bundles:
		return []

	parent_codes = [b.new_item_code for b in bundles if b.new_item_code]
	item_names = {}
	if parent_codes:
		for row in frappe.get_all(
			"Item",
			filters={"name": ["in", parent_codes]},
			fields=["name", "item_name"],
		):
			item_names[row.name] = row.item_name

	component_fields = ["parent", "item_code", "qty", "uom", "description"]
	pbi_meta = frappe.get_meta("Product Bundle Item")
	if pbi_meta.has_field("custom_bundle_item"):
		component_fields.append("custom_bundle_item")
	if pbi_meta.has_field("custom_bundle_item_name"):
		component_fields.append("custom_bundle_item_name")

	components = frappe.get_all(
		"Product Bundle Item",
		filters={"parent": ["in", [b.name for b in bundles]]},
		fields=component_fields,
		order_by="parent asc, idx asc",
	)

	component_names = {}
	component_codes = list({c.item_code for c in components if c.item_code})
	bundle_item_codes = list(
		{c.get("custom_bundle_item") for c in components if c.get("custom_bundle_item")}
	)
	all_item_codes = list(set(component_codes + bundle_item_codes))
	if all_item_codes:
		for row in frappe.get_all(
			"Item",
			filters={"name": ["in", all_item_codes]},
			fields=["name", "item_name"],
		):
			component_names[row.name] = row.item_name

	components_by_parent: dict[str, list] = {}
	for comp in components:
		bundle_item = comp.get("custom_bundle_item")
		components_by_parent.setdefault(comp.parent, []).append(
			{
				"item_code": comp.item_code,
				"item_name": component_names.get(comp.item_code) or comp.description or comp.item_code,
				"bundle_item": bundle_item,
				"bundle_item_name": (
					comp.get("custom_bundle_item_name")
					or (component_names.get(bundle_item) if bundle_item else None)
				),
				"qty": flt(comp.qty),
				"uom": comp.uom,
			}
		)

	result = []
	for bundle in bundles:
		items = components_by_parent.get(bundle.name) or []
		if not items:
			continue
		parent = bundle.new_item_code
		entry = {
			"bundle_code": parent,
			"bundle_name": item_names.get(parent) or bundle.description or parent,
			"components": items,
			"component_count": len(items),
		}
		item_meta = frappe.db.get_value(
			"Item",
			parent,
			["item_name", "stock_uom", "description", "image", "is_stock_item"],
			as_dict=True,
		)
		if item_meta:
			entry.update(
				{
					"stock_uom": item_meta.stock_uom,
					"item_name": item_meta.item_name or entry["bundle_name"],
					"description": item_meta.description,
					"image": item_meta.image,
					"is_stock_item": item_meta.is_stock_item or 0,
				}
			)
		result.append(entry)
	return result


def _aggregate_loose_cart(cart_items: list[dict], bundle_parents: set[str]) -> dict[str, float]:
	qty_map: dict[str, float] = {}
	for row in cart_items:
		item_code = row.get("item_code")
		if not item_code or row.get("is_free_item"):
			continue
		# Only exclude applied bundle parent lines — not every item that is a bundle parent code
		if row.get("is_bundle"):
			continue
		qty = flt(row.get("quantity") or row.get("qty") or 0)
		if qty <= 0:
			continue
		qty_map[item_code] = qty_map.get(item_code, 0) + qty
	return qty_map


def _complete_sets(cart_qty: dict[str, float], components: list[dict]) -> int:
	sets = None
	for comp in components:
		required = flt(comp.get("qty"))
		if required <= 0:
			continue
		available = _component_available(cart_qty, comp)
		possible = int(math.floor(available / required + 1e-9))
		sets = possible if sets is None else min(sets, possible)
	return max(0, sets or 0)


def _missing_for_one_set(cart_qty: dict[str, float], components: list[dict]) -> list[dict]:
	merged: dict[str, dict] = {}
	for comp in components:
		required = flt(comp.get("qty"))
		if required <= 0:
			continue
		available = _component_available(cart_qty, comp)
		need = required - available
		if need > 1e-9:
			suggest_code, suggest_name = _suggest_item_for_component(comp)
			existing = merged.get(suggest_code)
			if existing:
				existing["qty"] = flt(existing["qty"]) + flt(need)
			else:
				merged[suggest_code] = {
					"item_code": suggest_code,
					"item_name": suggest_name or suggest_code,
					"qty": flt(need),
					"uom": comp.get("uom"),
					"component_item_code": comp.get("item_code"),
				}
	return list(merged.values())


def _consume_plan(components: list[dict], sets: int) -> list[dict]:
	return [
		{
			"item_code": comp.get("item_code"),
			"item_name": comp.get("item_name") or comp.get("item_code"),
			"qty": flt(comp.get("qty")) * sets,
			"uom": comp.get("uom"),
			"match_codes": _component_match_codes(comp),
		}
		for comp in components
		if flt(comp.get("qty")) > 0
	]


def _bundle_match_payload(bundle: dict, cart_qty: dict[str, float]) -> dict:
	components = bundle["components"]
	complete = _complete_sets(cart_qty, components)
	missing = _missing_for_one_set(cart_qty, components) if complete < 1 else []
	has_component = any(_component_available(cart_qty, c) > 0 for c in components)

	return {
		"bundle_code": bundle["bundle_code"],
		"bundle_name": bundle["bundle_name"],
		"complete_sets": complete,
		"component_count": bundle["component_count"],
		"missing_items": missing,
		"has_component": has_component,
		"consume": _consume_plan(components, complete) if complete >= 1 else [],
	}


MIN_COMPONENTS_FOR_AUTO_APPLY = 2


def evaluate_product_bundle_matches(cart_items, pos_profile=None):
	"""Evaluate cart against Product Bundle definitions."""
	cart_items = _parse_cart_items(cart_items)
	bundle_parents = _get_bundle_parent_codes()
	cart_qty = _aggregate_loose_cart(cart_items, bundle_parents)

	if not cart_qty:
		return {"auto_apply": None, "choices": [], "suggestions": []}

	full_matches = []
	suggestions = []

	for bundle in _get_active_bundles():
		match = _bundle_match_payload(bundle, cart_qty)
		if (
			match["complete_sets"] >= 1
			and match["component_count"] >= MIN_COMPONENTS_FOR_AUTO_APPLY
		):
			full_matches.append(match)
		elif match["has_component"] and match["missing_items"]:
			suggestions.append(match)
		elif (
			match["complete_sets"] >= 1
			and match["component_count"] < MIN_COMPONENTS_FOR_AUTO_APPLY
		):
			suggestions.append({**match, "is_ready_to_apply": True, "missing_items": []})

	full_matches.sort(
		key=lambda m: (m["complete_sets"], m["component_count"]),
		reverse=True,
	)
	suggestions.sort(
		key=lambda m: (1 if m.get("is_ready_to_apply") else 0, len(m.get("missing_items") or []))
	)

	result = {"auto_apply": None, "choices": [], "suggestions": suggestions}

	if len(full_matches) == 1:
		result["auto_apply"] = full_matches[0]
	elif len(full_matches) > 1:
		result["choices"] = full_matches

	return result


@frappe.whitelist()
def get_product_bundle_matches(cart_items, pos_profile=None):
	"""API: detect auto-apply, cashier choices, and partial combo suggestions."""
	frappe.has_permission("Product Bundle", "read", throw=True)
	return evaluate_product_bundle_matches(cart_items, pos_profile)


@frappe.whitelist()
def get_product_bundle_definitions():
	"""API: export active Product Bundle definitions for offline cache."""
	frappe.has_permission("Product Bundle", "read", throw=True)
	return _get_active_bundles()
