# Copyright (c) BrainWise / POS Next
"""Pricing Rule time window via Custom Fields + monkey-patch (no ERPNext core edits)."""

from __future__ import annotations

import datetime

import frappe
from frappe import _
from frappe.utils import cint, get_time, nowtime

APPLY_TIME_WINDOW = "apply_time_window"
VALID_TIME_FROM = "valid_time_from"
VALID_TIME_TO = "valid_time_to"


def _coerce_time_value(value):
	if value is None:
		return None
	if isinstance(value, datetime.time):
		return value
	if isinstance(value, datetime.timedelta):
		total = int(value.total_seconds()) % 86400
		if total < 0:
			total += 86400
		h, rem = divmod(total, 3600)
		m, s = divmod(rem, 60)
		return datetime.time(h, m, s)
	return get_time(value)


def _time_to_seconds(t):
	if t is None:
		return None
	t = _coerce_time_value(t)
	if t is None:
		return None
	return t.hour * 3600 + t.minute * 60 + t.second


def _is_current_time_in_window(current_seconds: int, from_seconds: int, to_seconds: int) -> bool:
	if from_seconds <= to_seconds:
		return from_seconds <= current_seconds <= to_seconds
	return current_seconds >= from_seconds or current_seconds <= to_seconds


def get_transaction_eval_time(args=None, doc=None):
	t = None
	if doc is not None:
		if hasattr(doc, "get") and doc.get("posting_time"):
			t = doc.get("posting_time")
		elif hasattr(doc, "posting_time") and doc.posting_time:
			t = doc.posting_time
	if not t and args is not None:
		if hasattr(args, "get"):
			t = args.get("posting_time")
		else:
			t = getattr(args, "posting_time", None)
	if not t:
		return nowtime()
	return _coerce_time_value(t)


def filter_pricing_rules_by_pos_time_window(pricing_rules, args=None, doc=None):
	if not pricing_rules:
		return []

	current_sec = _time_to_seconds(get_transaction_eval_time(args, doc))
	filtered = []

	for rule in pricing_rules:
		if _rule_is_active_for_time(rule, current_sec):
			filtered.append(rule)

	return filtered


def _rule_is_active_for_time(rule, current_sec=None):
	"""Return True when rule passes Apply Time Window (or window disabled)."""
	if isinstance(rule, dict):
		apply_tw = rule.get(APPLY_TIME_WINDOW)
		tf = rule.get(VALID_TIME_FROM)
		tt = rule.get(VALID_TIME_TO)
	else:
		apply_tw = getattr(rule, APPLY_TIME_WINDOW, None)
		tf = getattr(rule, VALID_TIME_FROM, None)
		tt = getattr(rule, VALID_TIME_TO, None)

	if not cint(apply_tw):
		return True

	if current_sec is None:
		current_sec = _time_to_seconds(nowtime())
	if current_sec is None:
		return False

	fs, ts = _time_to_seconds(tf), _time_to_seconds(tt)
	if fs is None or ts is None:
		return False

	return _is_current_time_in_window(current_sec, fs, ts)


def is_pricing_rule_in_time_window(rule, args=None, doc=None):
	"""Public helper — True if rule may apply at transaction/posting time."""
	if isinstance(rule, str):
		try:
			rule = frappe.get_cached_doc("Pricing Rule", rule)
		except Exception:
			return False

	current_sec = _time_to_seconds(get_transaction_eval_time(args, doc))
	return _rule_is_active_for_time(rule, current_sec)


def filter_offer_dicts_by_time_window(offers):
	"""Remove POS offer payloads outside their daily time window."""
	if not offers:
		return []
	return [offer for offer in offers if _offer_dict_in_time_window(offer)]


def _offer_dict_in_time_window(offer):
	if not cint(offer.get("apply_time_window") if isinstance(offer, dict) else 0):
		return True

	current_sec = _time_to_seconds(nowtime())
	rule_like = {
		APPLY_TIME_WINDOW: offer.get("apply_time_window"),
		VALID_TIME_FROM: offer.get("valid_time_from"),
		VALID_TIME_TO: offer.get("valid_time_to"),
	}
	return _rule_is_active_for_time(rule_like, current_sec)


def apply_pricing_rule_utils_patches():
	"""Patch erpnext.accounts.doctype.pricing_rule.utils once per process."""
	from erpnext.accounts.doctype.pricing_rule import utils as pr_utils

	if getattr(pr_utils, "_pos_next_pricing_time_window_patched", False):
		return

	_orig_get_pricing_rules = pr_utils.get_pricing_rules

	def get_pricing_rules(args, doc=None):
		res = _orig_get_pricing_rules(args, doc)
		if not res:
			return res
		return filter_pricing_rules_by_pos_time_window(res, args, doc)

	pr_utils._orig_get_pricing_rules_pos_next = _orig_get_pricing_rules
	pr_utils.get_pricing_rules = get_pricing_rules

	_orig_apply_pricing_rule_on_transaction = pr_utils.apply_pricing_rule_on_transaction

	def apply_pricing_rule_on_transaction(doc):
		conditions = "apply_on = 'Transaction'"
		values = {}
		conditions = pr_utils.get_other_conditions(conditions, values, doc)
		sql_rules = frappe.db.sql(
			f""" Select `tabPricing Rule`.* from `tabPricing Rule`
			where  {conditions} and `tabPricing Rule`.disable = 0
		""",
			values,
			as_dict=1,
		)
		pricing_rules = filter_pricing_rules_by_pos_time_window(sql_rules, doc, doc)
		if sql_rules and not pricing_rules:
			pr_utils.remove_free_item(doc)
			return
		if pricing_rules:
			pricing_rules = pr_utils.filter_pricing_rules_for_qty_amount(doc.total_qty, doc.total, pricing_rules)
			pricing_rules = pr_utils.filter_pricing_rule_based_on_condition(pricing_rules, doc)

			if not pricing_rules:
				pr_utils.remove_free_item(doc)

			for d in pricing_rules:
				if d.price_or_product_discount == "Price":
					if d.apply_discount_on:
						doc.set("apply_discount_on", d.apply_discount_on)
					condition_met = False

					for field in ["additional_discount_percentage", "discount_amount"]:
						pr_field = "discount_percentage" if field == "additional_discount_percentage" else field

						if not d.get(pr_field):
							continue

						if d.validate_applied_rule and (doc.get(field) or 0) < d.get(pr_field):
							frappe.msgprint(_("User has not applied rule on the invoice {0}").format(doc.name))
						else:
							if not d.coupon_code_based:
								doc.set(field, d.get(pr_field))
							elif doc.get("coupon_code"):
								coupon_code_pricing_rule = frappe.db.get_value(
									"Coupon Code", doc.get("coupon_code"), "pricing_rule"
								)
								if coupon_code_pricing_rule == d.name:
									doc.set(field, d.get(pr_field))
									condition_met = True
									break
								else:
									doc.set(field, 0)
							else:
								doc.set(field, 0)

					doc.calculate_taxes_and_totals()

					if condition_met:
						break
				elif d.price_or_product_discount == "Product":
					item_details = frappe._dict({"parenttype": doc.doctype, "free_item_data": []})
					pr_utils.get_product_discount_rule(d, item_details, doc=doc)
					pr_utils.apply_pricing_rule_for_free_items(doc, item_details.free_item_data)
					doc.set_missing_values()
					doc.calculate_taxes_and_totals()

	pr_utils._orig_apply_pricing_rule_on_transaction_pos_next = _orig_apply_pricing_rule_on_transaction
	pr_utils.apply_pricing_rule_on_transaction = apply_pricing_rule_on_transaction
	pr_utils._pos_next_pricing_time_window_patched = True
