# -*- coding: utf-8 -*-
# Copyright (c) 2025, POS Next and contributors
# For license information, please see license.txt

"""
Offers API - Fetches and manages promotional offers and pricing rules for POS

This module provides a clean API for retrieving promotional offers from both
Promotional Schemes and standalone Pricing Rules.
"""

from typing import Dict, List, Optional
import datetime
from dataclasses import dataclass, asdict, field
import frappe
from frappe import _
from frappe.utils import flt, getdate, nowdate, cint


# ============================================================================
# Constants
# ============================================================================

class DiscountType:
	"""Discount type constants"""
	PRICE = "Price"
	PRODUCT = "Product"


class ApplyOn:
	"""Apply on constants"""
	ITEM_CODE = "Item Code"
	ITEM_GROUP = "Item Group"
	BRAND = "Brand"
	TRANSACTION = "Transaction"


class OfferSource:
	"""Offer source constants"""
	PROMOTIONAL_SCHEME = "Promotional Scheme"
	PRICING_RULE = "Pricing Rule"


# Cache for get_offers(): avoids re-scanning `tabPricing Rule` (can be tens of
# thousands of rows) on every POS item add. Invalidated explicitly whenever a
# Pricing Rule / Promotional Scheme / Promotion Campaign is saved or deleted
# (see hooks.py doc_events -> clear_offers_cache), with a TTL as a safety net.
OFFERS_CACHE_KEY_PREFIX = "pos_offers_v1"
OFFERS_CACHE_TTL_SECONDS = 3600


def clear_offers_cache(doc=None, method=None):
	"""Invalidate cached POS offers. Hooked to Pricing Rule / Promotional
	Scheme / Promotion Campaign on_update and on_trash."""
	frappe.cache().delete_keys(OFFERS_CACHE_KEY_PREFIX)


# ============================================================================
# Data Classes
# ============================================================================

@dataclass
class OfferEligibility:
	"""Eligibility criteria for an offer"""
	items: List[str]
	item_groups: List[str]
	brands: List[str]


@dataclass
class Offer:
	"""Structured offer data"""
	name: str
	title: str
	description: str
	apply_on: str
	offer: str
	auto: int
	coupon_based: int
	min_qty: float
	max_qty: float
	min_amt: float
	max_amt: float
	discount_type: Optional[str]
	rate: float
	discount_amount: float
	discount_percentage: float
	valid_from: Optional[str]
	valid_upto: Optional[str]
	source: str
	promotional_scheme: Optional[str]
	promotional_scheme_id: Optional[str]
	eligible_items: List[str]
	eligible_item_groups: List[str]
	eligible_brands: List[str]
	# Free item fields for product discounts
	free_item: Optional[str] = None
	free_qty: float = 0
	free_item_uom: Optional[str] = None
	same_item: int = 0  # 1 if free item should be same as purchased item
	is_recursive: int = 0  # 1 if offer applies recursively (e.g., buy 2 get 1 free for every 2)
	recurse_for: float = 0  # Give free item for every N quantity (used when is_recursive=1)
	apply_recursion_over: float = 0  # Qty for which recursion isn't applicable
	# Transaction-level discount base (Net Total / Grand Total)
	apply_discount_on: Optional[str] = None
	# POS Next: daily time window on Pricing Rule (custom fields)
	apply_time_window: int = 0
	valid_time_from: Optional[str] = None
	valid_time_to: Optional[str] = None
	warehouse: Optional[str] = None
	# Whether the rule measures qty/amount over the whole matching set (1) or per
	# cart line (0). The POS has to mirror this or it offers promos ERPNext will
	# refuse — see PM-TASK-00035.
	mixed_conditions: int = 0
	# Customer scoping (PM-TASK-00034). `applicable_values` is the resolved set of
	# names that satisfy the scope, tree descendants already expanded, so the POS
	# can match with a plain lookup instead of walking the tree in the browser.
	applicable_for: Optional[str] = None
	applicable_values: List[str] = field(default_factory=list)

	def to_dict(self) -> Dict:
		"""Convert to dictionary for API response"""
		return asdict(self)


# ============================================================================
# Helpers (customer scoping)
# ============================================================================

# applicable_for -> the Pricing Rule field holding the scoped value.
_APPLICABLE_FOR_FIELD = {
	"Customer": "customer",
	"Customer Group": "customer_group",
	"Territory": "territory",
	"Sales Partner": "sales_partner",
	"Campaign": "campaign",
}

# Scopes that are trees: a rule on a parent node also covers every node under it.
_APPLICABLE_FOR_TREE = {
	"Customer Group": "Customer Group",
	"Territory": "Territory",
}


def _resolve_applicable_scope(rule: Dict) -> tuple:
	"""Return (applicable_for, values) describing who a rule is limited to.

	Descendants are expanded here, on the server, so the POS can decide with a
	set lookup — the browser has no way to walk a Customer Group tree.
	Returns ("", []) for an unrestricted rule, which every customer satisfies.
	"""
	applicable_for = rule.get("applicable_for") or ""
	fieldname = _APPLICABLE_FOR_FIELD.get(applicable_for)
	if not fieldname:
		return "", []

	value = rule.get(fieldname)
	if not value:
		# Scope selected but left blank: ERPNext treats it as unrestricted.
		return "", []

	values = [value]
	tree_doctype = _APPLICABLE_FOR_TREE.get(applicable_for)
	if tree_doctype:
		try:
			from frappe.utils.nestedset import get_descendants_of

			values.extend(get_descendants_of(tree_doctype, value) or [])
		except Exception:
			frappe.log_error(frappe.get_traceback(), "POS Offers Scope Resolution")

	return applicable_for, list(dict.fromkeys(values))


def _applicable_sql_columns() -> str:
	"""Extra SELECT columns needed to resolve customer scoping."""
	return ", applicable_for, customer, customer_group, territory, sales_partner, campaign"


# ============================================================================
# Helpers (time window on Pricing Rule)
# ============================================================================

def _pricing_rule_time_sql_columns() -> str:
	"""Extra SELECT columns when Custom Fields exist on Pricing Rule."""
	if not frappe.db.has_column("Pricing Rule", "apply_time_window"):
		return ""
	return ", apply_time_window, valid_time_from, valid_time_to"


def _format_time_for_offer(val) -> Optional[str]:
	if val is None:
		return None
	if isinstance(val, datetime.timedelta):
		secs = int(val.total_seconds()) % 86400
		if secs < 0:
			secs += 86400
		h = secs // 3600
		m = (secs % 3600) // 60
		s = secs % 60
		return f"{h:02d}:{m:02d}:{s:02d}"
	if isinstance(val, datetime.time):
		return f"{val.hour:02d}:{val.minute:02d}:{val.second:02d}"
	st = str(val)
	return st.split(".")[0] if st else None


def _time_window_from_rule(rule: Dict) -> tuple:
	aw = cint(rule.get("apply_time_window") or 0)
	tf = _format_time_for_offer(rule.get("valid_time_from"))
	tt = _format_time_for_offer(rule.get("valid_time_to"))
	return aw, tf, tt


# ============================================================================
# Database Query Helpers
# ============================================================================

class EligibilityFetcher:
	"""Fetches eligibility criteria for pricing rules/schemes in bulk"""

	@staticmethod
	def fetch_all(parent_names: List[str]) -> Dict[str, OfferEligibility]:
		"""
		Fetch all eligibility criteria for given parent names

		Args:
			parent_names: List of pricing rule or scheme names

		Returns:
			Dict mapping parent name to OfferEligibility
		"""
		if not parent_names:
			return {}

		items_map = EligibilityFetcher._fetch_items(parent_names)
		item_groups_map = EligibilityFetcher._fetch_item_groups(parent_names)
		brands_map = EligibilityFetcher._fetch_brands(parent_names)

		# Combine all maps into OfferEligibility objects
		eligibility = {}
		for parent in parent_names:
			eligibility[parent] = OfferEligibility(
				items=items_map.get(parent, []),
				item_groups=item_groups_map.get(parent, []),
				brands=brands_map.get(parent, [])
			)

		return eligibility

	@staticmethod
	def _fetch_items(parent_names: List[str]) -> Dict[str, List[str]]:
		"""
		Fetch item codes for given parents, expanding template items to include variants.

		When a pricing rule is created for a template item (has_variants=1), this method
		automatically includes all its variant items in the eligible items list.
		This ensures offers work correctly when variants are added to cart.
		"""
		results = frappe.db.sql("""
			SELECT parent, item_code
			FROM `tabPricing Rule Item Code`
			WHERE parent IN %s
		""", [parent_names], as_dict=1)

		if not results:
			return {}

		# Collect all unique item codes
		all_item_codes = list({row["item_code"] for row in results})

		# Find which items are templates (have variants)
		template_items = frappe.get_all(
			"Item",
			filters={
				"name": ["in", all_item_codes],
				"has_variants": 1
			},
			pluck="name"
		)

		# Fetch variants for all template items in one query
		variants_map = {}
		if template_items:
			variants = frappe.get_all(
				"Item",
				filters={
					"variant_of": ["in", template_items],
					"disabled": 0
				},
				fields=["name", "variant_of"]
			)
			for variant in variants:
				variants_map.setdefault(variant["variant_of"], []).append(variant["name"])

		# Build items map, expanding templates to include their variants
		items_map = {}
		for row in results:
			parent = row["parent"]
			item_code = row["item_code"]

			items_map.setdefault(parent, []).append(item_code)

			# If this item is a template, also add all its variants
			if item_code in variants_map:
				items_map[parent].extend(variants_map[item_code])

		return items_map

	@staticmethod
	def _fetch_item_groups(parent_names: List[str]) -> Dict[str, List[str]]:
		"""Fetch item groups for given parents"""
		results = frappe.db.sql("""
			SELECT parent, item_group
			FROM `tabPricing Rule Item Group`
			WHERE parent IN %s
		""", [parent_names], as_dict=1)

		groups_map = {}
		for row in results:
			groups_map.setdefault(row["parent"], []).append(row["item_group"])
		return groups_map

	@staticmethod
	def _fetch_brands(parent_names: List[str]) -> Dict[str, List[str]]:
		"""Fetch brands for given parents"""
		results = frappe.db.sql("""
			SELECT parent, brand
			FROM `tabPricing Rule Brand`
			WHERE parent IN %s
		""", [parent_names], as_dict=1)

		brands_map = {}
		for row in results:
			brands_map.setdefault(row["parent"], []).append(row["brand"])
		return brands_map


class SlabFetcher:
	"""Fetches discount slabs for promotional schemes"""

	@staticmethod
	def fetch_price_slabs(scheme_names: List[str]) -> Dict[str, Dict]:
		"""Fetch first price discount slab for each scheme"""
		if not scheme_names:
			return {}

		results = frappe.db.sql("""
			SELECT
				parent, min_qty, max_qty, min_amount, max_amount,
				rate_or_discount, rate, discount_amount, discount_percentage,
				apply_multiple_pricing_rules
			FROM `tabPromotional Scheme Price Discount`
			WHERE parent IN %s AND disable = 0
			ORDER BY parent, min_amount ASC, min_qty ASC
		""", [scheme_names], as_dict=1)

		# Take first slab for each parent
		slabs_map = {}
		for slab in results:
			if slab["parent"] not in slabs_map:
				slabs_map[slab["parent"]] = slab

		return slabs_map

	@staticmethod
	def fetch_product_slabs(scheme_names: List[str]) -> Dict[str, Dict]:
		"""Fetch first product discount slab for each scheme"""
		if not scheme_names:
			return {}

		results = frappe.db.sql("""
			SELECT
				parent, min_qty, max_qty, min_amount, max_amount,
				apply_multiple_pricing_rules,
				free_item, free_qty, free_item_uom, same_item, is_recursive,
				recurse_for, apply_recursion_over
			FROM `tabPromotional Scheme Product Discount`
			WHERE parent IN %s AND disable = 0
			ORDER BY parent, min_amount ASC, min_qty ASC
		""", [scheme_names], as_dict=1)

		# Take first slab for each parent
		slabs_map = {}
		for slab in results:
			if slab["parent"] not in slabs_map:
				slabs_map[slab["parent"]] = slab

		return slabs_map

	@staticmethod
	def fetch_price_slabs_by_id(slab_names: List[str]) -> Dict[str, Dict]:
		"""Fetch price discount slabs keyed by child row name (promotional_scheme_id)."""
		if not slab_names:
			return {}

		results = frappe.db.sql(
			"""
			SELECT
				name, parent, min_qty, max_qty, min_amount, max_amount,
				rate_or_discount, rate, discount_amount, discount_percentage,
				apply_multiple_pricing_rules
			FROM `tabPromotional Scheme Price Discount`
			WHERE name IN %s AND disable = 0
			""",
			[slab_names],
			as_dict=1,
		)
		return {row["name"]: row for row in results}

	@staticmethod
	def fetch_product_slabs_by_id(slab_names: List[str]) -> Dict[str, Dict]:
		"""Fetch product discount slabs keyed by child row name (promotional_scheme_id)."""
		if not slab_names:
			return {}

		results = frappe.db.sql(
			"""
			SELECT
				name, parent, min_qty, max_qty, min_amount, max_amount,
				apply_multiple_pricing_rules,
				free_item, free_qty, free_item_uom, same_item, is_recursive,
				recurse_for, apply_recursion_over
			FROM `tabPromotional Scheme Product Discount`
			WHERE name IN %s AND disable = 0
			""",
			[slab_names],
			as_dict=1,
		)
		return {row["name"]: row for row in results}


# ============================================================================
# Offer Builders
# ============================================================================

class OfferBuilder:
	"""Builds Offer objects from pricing rules and schemes"""

	@staticmethod
	def build_from_scheme_rule(
		rule: Dict,
		slab: Dict,
		eligibility: OfferEligibility
	) -> Offer:
		"""Build offer from promotional scheme pricing rule"""

		# Determine if auto-apply
		is_auto = 0
		if not rule.get("coupon_code_based"):
			if not slab.get("apply_multiple_pricing_rules"):
				is_auto = 1

		# Extract eligibility based on apply_on
		eligible_items = []
		eligible_item_groups = []
		eligible_brands = []

		if rule["apply_on"] == ApplyOn.ITEM_CODE:
			eligible_items = eligibility.items
		elif rule["apply_on"] == ApplyOn.ITEM_GROUP:
			eligible_item_groups = eligibility.item_groups
		elif rule["apply_on"] == ApplyOn.BRAND:
			eligible_brands = eligibility.brands

		# Determine offer type
		is_price_discount = rule.get("price_or_product_discount") == DiscountType.PRICE

		aw, tf, tt = _time_window_from_rule(rule)
		scope_for, scope_values = _resolve_applicable_scope(rule)

		return Offer(
			name=rule["name"],
			title=rule.get("title") or rule.get("promotional_scheme") or rule["name"],
			description=rule.get("custom_promotion_campaign") or "",
			apply_on=rule["apply_on"],
			offer="Item Price" if is_price_discount else "Give Product",
			auto=is_auto,
			coupon_based=1 if rule.get("coupon_code_based") else 0,
			min_qty=flt(slab.get("min_qty", 0)),
			max_qty=flt(slab.get("max_qty", 0)),
			min_amt=flt(slab.get("min_amount", 0)),
			max_amt=flt(slab.get("max_amount", 0)),
			discount_type=slab.get("rate_or_discount") if is_price_discount else None,
			rate=flt(slab.get("rate", 0)) if is_price_discount else 0,
			discount_amount=flt(slab.get("discount_amount", 0)) if is_price_discount else 0,
			discount_percentage=flt(slab.get("discount_percentage", 0)) if is_price_discount else 0,
			valid_from=rule.get("valid_from"),
			valid_upto=rule.get("valid_upto"),
			source=OfferSource.PROMOTIONAL_SCHEME,
			promotional_scheme=rule.get("promotional_scheme"),
			promotional_scheme_id=rule.get("promotional_scheme_id"),
			eligible_items=eligible_items,
			eligible_item_groups=eligible_item_groups,
			eligible_brands=eligible_brands,
			# Free item fields for product discounts
			free_item=slab.get("free_item") if not is_price_discount else None,
			free_qty=flt(slab.get("free_qty", 0)) if not is_price_discount else 0,
			free_item_uom=slab.get("free_item_uom") if not is_price_discount else None,
			same_item=1 if slab.get("same_item") and not is_price_discount else 0,
			is_recursive=1 if slab.get("is_recursive") and not is_price_discount else 0,
			recurse_for=flt(slab.get("recurse_for", 0)) if not is_price_discount else 0,
			apply_recursion_over=flt(slab.get("apply_recursion_over", 0)) if not is_price_discount else 0,
			apply_discount_on=rule.get("apply_discount_on") or None,
			apply_time_window=aw,
			valid_time_from=tf,
			valid_time_to=tt,
			warehouse=rule.get("warehouse") or None,
			mixed_conditions=cint(rule.get("mixed_conditions")),
			applicable_for=scope_for or None,
			applicable_values=scope_values,
		)

	@staticmethod
	def build_from_standalone_rule(
		rule: Dict,
		eligibility: OfferEligibility
	) -> Offer:
		"""Build offer from standalone pricing rule (price or product discount)."""

		# Standalone rules auto-apply unless coupon-based
		is_auto = 0 if rule.get("coupon_code_based") else 1
		is_price_discount = rule.get("price_or_product_discount") == DiscountType.PRICE

		# Extract eligibility based on apply_on
		eligible_items = []
		eligible_item_groups = []
		eligible_brands = []

		if rule["apply_on"] == ApplyOn.ITEM_CODE:
			eligible_items = eligibility.items
		elif rule["apply_on"] == ApplyOn.ITEM_GROUP:
			eligible_item_groups = eligibility.item_groups
		elif rule["apply_on"] == ApplyOn.BRAND:
			eligible_brands = eligibility.brands

		aw, tf, tt = _time_window_from_rule(rule)
		scope_for, scope_values = _resolve_applicable_scope(rule)

		return Offer(
			name=rule["name"],
			title=rule.get("title") or rule["name"],
			description=rule.get("title") or f"Pricing Rule: {rule['name']}",
			apply_on=rule["apply_on"],
			offer="Item Price" if is_price_discount else "Give Product",
			auto=is_auto,
			coupon_based=1 if rule.get("coupon_code_based") else 0,
			min_qty=flt(rule.get("min_qty", 0)),
			max_qty=flt(rule.get("max_qty", 0)),
			min_amt=flt(rule.get("min_amt", 0)),
			max_amt=flt(rule.get("max_amt", 0)),
			discount_type=rule.get("rate_or_discount") if is_price_discount else None,
			rate=flt(rule.get("rate", 0)) if is_price_discount else 0,
			discount_amount=flt(rule.get("discount_amount", 0)) if is_price_discount else 0,
			discount_percentage=flt(rule.get("discount_percentage", 0)) if is_price_discount else 0,
			valid_from=rule.get("valid_from"),
			valid_upto=rule.get("valid_upto"),
			source=OfferSource.PRICING_RULE,
			promotional_scheme=None,
			promotional_scheme_id=None,
			eligible_items=eligible_items,
			eligible_item_groups=eligible_item_groups,
			eligible_brands=eligible_brands,
			free_item=rule.get("free_item") if not is_price_discount else None,
			free_qty=flt(rule.get("free_qty", 0)) if not is_price_discount else 0,
			free_item_uom=rule.get("free_item_uom") if not is_price_discount else None,
			same_item=1 if rule.get("same_item") and not is_price_discount else 0,
			is_recursive=1 if rule.get("is_recursive") and not is_price_discount else 0,
			recurse_for=flt(rule.get("recurse_for", 0)) if not is_price_discount else 0,
			apply_recursion_over=flt(rule.get("apply_recursion_over", 0)) if not is_price_discount else 0,
			apply_discount_on=rule.get("apply_discount_on") or None,
			apply_time_window=aw,
			valid_time_from=tf,
			valid_time_to=tt,
			warehouse=rule.get("warehouse") or None,
			mixed_conditions=cint(rule.get("mixed_conditions")),
			applicable_for=scope_for or None,
			applicable_values=scope_values,
		)


# ============================================================================
# Main API Functions
# ============================================================================

@frappe.whitelist()
def get_offers(pos_profile: str) -> List[Dict]:
	"""
	Fetch all auto-applicable offers for the POS profile

	Args:
		pos_profile: POS Profile name

	Returns:
		List of offer dictionaries
	"""
	cache_key = f"{OFFERS_CACHE_KEY_PREFIX}::{pos_profile}"
	cached = frappe.cache().get_value(cache_key, expires=True)
	if cached is not None:
		return cached

	try:
		profile = frappe.get_doc("POS Profile", pos_profile)
		date = nowdate()

		offers = []

		pos_warehouse = profile.warehouse

		# Get offers from promotional schemes
		scheme_offers = _get_promotional_scheme_offers(profile.company, date, pos_warehouse)
		offers.extend(scheme_offers)

		# Get standalone pricing rule offers
		standalone_offers = _get_standalone_pricing_rule_offers(
			profile.company, date, pos_warehouse
		)
		offers.extend(standalone_offers)

		from pos_next.pricing_rule_time_window import filter_offer_dicts_by_time_window
		from pos_next.pricing_rule_warehouse import filter_offer_dicts_by_warehouse

		offer_dicts = filter_offer_dicts_by_time_window([offer.to_dict() for offer in offers])
		result = filter_offer_dicts_by_warehouse(offer_dicts, pos_warehouse)

		frappe.cache().set_value(cache_key, result, expires_in_sec=OFFERS_CACHE_TTL_SECONDS)
		return result

	except Exception as e:
		frappe.log_error(f"Error fetching offers: {str(e)}", "Offers API")
		return []


def _campaign_valid_on_date(campaign_name: str, date) -> bool:
	"""Valid From <= date <= Valid Upto (blank date bounds are ignored)."""
	if not campaign_name:
		return False
	if not frappe.db.exists("Promotion Campaign", campaign_name):
		return False
	meta = frappe.get_meta("Promotion Campaign")
	check_date = getdate(date)
	if meta.has_field("custom_valid_from"):
		valid_from = frappe.db.get_value("Promotion Campaign", campaign_name, "custom_valid_from")
		if valid_from and getdate(valid_from) > check_date:
			return False
	if meta.has_field("custom_valid_upto"):
		valid_upto = frappe.db.get_value("Promotion Campaign", campaign_name, "custom_valid_upto")
		if valid_upto and getdate(valid_upto) < check_date:
			return False
	return True


def _campaign_matches_pos_warehouse(campaign_name: str, pos_warehouse: Optional[str]) -> bool:
	"""Child table Promotional Scheme Warehouse must include a row matching POS warehouse."""
	if not campaign_name or not pos_warehouse:
		return False

	meta = frappe.get_meta("Promotion Campaign")
	child_field = "custom_promotional_scheme_warehouse"
	if not meta.has_field(child_field):
		return False

	child_rows = frappe.get_all(
		"Promotional Scheme Warehouse",
		filters={
			"parent": campaign_name,
			"parenttype": "Promotion Campaign",
			"parentfield": child_field,
		},
		fields=["warehouse"],
		pluck="warehouse",
	)
	if not child_rows:
		return False

	from pos_next.pricing_rule_warehouse import pricing_rule_matches_warehouse

	return any(
		pricing_rule_matches_warehouse(row_warehouse, pos_warehouse) for row_warehouse in child_rows
	)


@frappe.whitelist()
def get_promotion_campaigns_for_pos(pos_profile: str) -> List[Dict]:
	"""Promotion Campaign names for POS: valid today and warehouse matches POS Profile."""
	if not pos_profile:
		return []
	if not frappe.db.exists("DocType", "Promotion Campaign"):
		return []
	if not frappe.db.exists("POS Profile", pos_profile):
		return []

	pos_warehouse = frappe.db.get_value("POS Profile", pos_profile, "warehouse")
	if not pos_warehouse:
		return []

	date = getdate()
	result = []

	for row in frappe.get_all(
		"Promotion Campaign",
		fields=["name", "promotion_name"],
		order_by="promotion_name asc",
		limit_page_length=100,
	):
		if not _campaign_valid_on_date(row.name, date):
			continue
		if not _campaign_matches_pos_warehouse(row.name, pos_warehouse):
			continue
		result.append(
			{
				"name": row.name,
				"promotion_name": row.promotion_name or row.name,
			}
		)

	return result


def _get_promotional_scheme_offers(
	company: str, date: str, pos_warehouse: Optional[str] = None
) -> List[Offer]:
	"""Fetch offers from promotional schemes"""

	time_cols = _pricing_rule_time_sql_columns()
	applicable_cols = _applicable_sql_columns()

	# Fetch pricing rules linked to promotional schemes
	pricing_rules = frappe.db.sql(f"""
		SELECT
			name, title, apply_on, selling, promotional_scheme,
			promotional_scheme_id, coupon_code_based,
			price_or_product_discount, apply_discount_on, priority,
			warehouse, valid_from, valid_upto, custom_promotion_campaign,
			mixed_conditions
			{applicable_cols}
			{time_cols}
		FROM `tabPricing Rule`
		WHERE
			disable = 0
			AND selling = 1
			AND promotional_scheme IS NOT NULL
			AND company = %(company)s
			AND (valid_from IS NULL OR valid_from <= %(date)s)
			AND (valid_upto IS NULL OR valid_upto >= %(date)s)
		ORDER BY priority DESC, name
	""", {"company": company, "date": date}, as_dict=1)

	if not pricing_rules:
		return []

	from pos_next.pricing_rule_warehouse import pricing_rule_matches_warehouse

	if pos_warehouse:
		pricing_rules = [
			r
			for r in pricing_rules
			if pricing_rule_matches_warehouse(r.get("warehouse"), pos_warehouse)
		]

	if not pricing_rules:
		return []

	slab_ids = list(
		{r["promotional_scheme_id"] for r in pricing_rules if r.get("promotional_scheme_id")}
	)
	price_slabs = SlabFetcher.fetch_price_slabs_by_id(slab_ids)
	product_slabs = SlabFetcher.fetch_product_slabs_by_id(slab_ids)
	eligibility_map = EligibilityFetcher.fetch_all([r["name"] for r in pricing_rules])

	# Build offers
	offers = []
	for rule in pricing_rules:
		slab_id = rule.get("promotional_scheme_id")
		if not slab_id:
			continue

		if rule.get("price_or_product_discount") == DiscountType.PRICE:
			slab = price_slabs.get(slab_id)
		else:
			slab = product_slabs.get(slab_id)

		if not slab:
			continue

		eligibility = eligibility_map.get(rule["name"], OfferEligibility([], [], []))
		offer = OfferBuilder.build_from_scheme_rule(rule, slab, eligibility)
		offers.append(offer)

	return offers


def _get_standalone_pricing_rule_offers(
	company: str, date: str, pos_warehouse: Optional[str] = None
) -> List[Offer]:
	"""Fetch offers from standalone pricing rules (price and product discounts)."""

	time_cols = _pricing_rule_time_sql_columns()
	applicable_cols = _applicable_sql_columns()

	# Fetch standalone pricing rules (not linked to schemes).
	# Include both Price discounts (%, amount) and Product discounts (free items).
	pricing_rules = frappe.db.sql(f"""
		SELECT
			name, title, apply_on, selling,
			coupon_code_based, price_or_product_discount, apply_discount_on,
			rate_or_discount, rate, discount_amount, discount_percentage,
			min_qty, max_qty, min_amt, max_amt,
			free_item, free_qty, free_item_uom, same_item, is_recursive,
			recurse_for, apply_recursion_over,
			priority, warehouse, valid_from, valid_upto,
			mixed_conditions
			{applicable_cols}
			{time_cols}
		FROM `tabPricing Rule`
		WHERE
			disable = 0
			AND selling = 1
			AND promotional_scheme IS NULL
			AND company = %(company)s
			AND (valid_from IS NULL OR valid_from <= %(date)s)
			AND (valid_upto IS NULL OR valid_upto >= %(date)s)
			AND price_or_product_discount IN (%(price_type)s, %(product_type)s)
		ORDER BY priority DESC, name
	""", {
		"company": company,
		"date": date,
		"price_type": DiscountType.PRICE,
		"product_type": DiscountType.PRODUCT,
	}, as_dict=1)

	if not pricing_rules:
		return []

	from pos_next.pricing_rule_warehouse import pricing_rule_matches_warehouse

	if pos_warehouse:
		pricing_rules = [
			r
			for r in pricing_rules
			if pricing_rule_matches_warehouse(r.get("warehouse"), pos_warehouse)
		]

	if not pricing_rules:
		return []

	rule_names = [rule["name"] for rule in pricing_rules]
	eligibility_map = EligibilityFetcher.fetch_all(rule_names)

	# Build offers
	offers = []
	for rule in pricing_rules:
		eligibility = eligibility_map.get(rule["name"], OfferEligibility([], [], []))
		offer = OfferBuilder.build_from_standalone_rule(rule, eligibility)
		offers.append(offer)

	return offers


# ============================================================================
# Coupon Functions
# ============================================================================

@frappe.whitelist()
def get_active_coupons(customer: str, company: str) -> List[Dict]:
	"""Get active gift card coupons for a customer"""
	if not frappe.db.table_exists("POS Coupon"):
		return []

	coupons = frappe.get_all(
		"POS Coupon",
		filters={
			"company": company,
			"coupon_type": "Gift Card",
			"customer": customer,
			"used": 0,
		},
		fields=["name", "coupon_code", "coupon_name", "valid_from", "valid_upto"],
	)

	return coupons


@frappe.whitelist()
def validate_coupon(coupon_code: str, customer: str, company: str) -> Dict:
	"""Validate a coupon code and return its details"""
	if not frappe.db.table_exists("POS Coupon"):
		return {"valid": False, "message": _("Coupons are not enabled")}

	date = getdate()

	# Fetch coupon with case-insensitive code matching
	# Note: coupon_code field is unique, so we can fetch directly
	coupon = frappe.db.get_value(
		"POS Coupon",
		{"coupon_code": coupon_code, "company": company},
		["*"],
		as_dict=1
	)

	if not coupon:
		return {"valid": False, "message": _("Invalid coupon code")}

	if coupon.disabled:
		return {"valid": False, "message": _("This coupon is disabled")}

	# Check usage limits
	if coupon.coupon_type == "Gift Card":
		if coupon.used:
			return {"valid": False, "message": _("This gift card has already been used")}
	else:
		# Promotional coupons
		if coupon.maximum_use > 0 and coupon.used >= coupon.maximum_use:
			return {"valid": False, "message": _("This coupon has reached its usage limit")}

	# Check validity dates
	if coupon.valid_from and coupon.valid_from > date:
		return {"valid": False, "message": _("This coupon is not yet valid")}

	if coupon.valid_upto and coupon.valid_upto < date:
		return {"valid": False, "message": _("This coupon has expired")}

	# Check customer restriction
	if coupon.customer and coupon.customer != customer:
		return {"valid": False, "message": _("This coupon is not valid for this customer")}

	return {
		"valid": True,
		"coupon": coupon
	}


@frappe.whitelist()
def get_offline_coupons(company: str) -> List[Dict]:
	"""Mã giảm giá được phép áp khi POS mất mạng (PM-TASK-00071).

	Chỉ trả về mã mà máy POS có thể tự kiểm tra ĐÚNG khi không hỏi được máy chủ:

	- Không giới hạn số lượt dùng (`maximum_use = 0`): mã có giới hạn thì phải
	  biết đã dùng bao nhiêu lần trên TOÀN hệ thống mới kết luận được, mà con số
	  đó chỉ máy chủ có. Cho áp offline là mở đường cho một mã bị dùng vượt hạn
	  ở nhiều cửa hàng cùng lúc.
	- Không gán riêng khách (`customer` trống): mã gán riêng cần đối chiếu khách
	  đang chọn, mà POS offline có thể đang dùng khách lưu sẵn không còn đúng.
	- Không phải Gift Card: thẻ quà tặng dùng một lần, cũng cần máy chủ chốt.

	Ngày hiệu lực thì trả kèm để máy POS tự lọc theo ngày bán, không lọc sẵn ở
	đây — danh sách được lưu trên máy nhiều ngày, lọc sẵn theo hôm nay sẽ sai
	vào những ngày sau.
	"""
	if not frappe.db.table_exists("POS Coupon"):
		return []

	return frappe.get_all(
		"POS Coupon",
		filters={
			"company": company,
			"disabled": 0,
			"coupon_type": "Promotional",
			"maximum_use": 0,
		},
		or_filters=[
			["customer", "is", "not set"],
			["customer", "=", ""],
		],
		fields=[
			"name", "coupon_name", "coupon_code", "coupon_type", "company",
			"discount_type", "discount_percentage", "discount_amount",
			"min_amount", "max_amount", "apply_on",
			"valid_from", "valid_upto", "pricing_rule",
		],
		limit_page_length=0,
	)
