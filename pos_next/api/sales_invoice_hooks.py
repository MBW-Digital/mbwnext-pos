# Copyright (c) 2025, BrainWise and contributors
# For license information, please see license.txt

"""
Sales Invoice Hooks
Event handlers for Sales Invoice document events
"""

import frappe
from frappe import _
from frappe.utils import cint, flt, fmt_money


def validate(doc, method=None):
	"""
	Validate hook for Sales Invoice.
	Apply tax inclusive settings based on POS Profile configuration.
	Auto-assign loyalty program to customer if enabled.

	Args:
		doc: Sales Invoice document
		method: Hook method name (unused)
	"""
	apply_tax_inclusive(doc)
	auto_assign_loyalty_program_on_invoice(doc)
	restore_pos_authoritative_discounts(doc)
	apply_pos_manual_discount(doc)
	add_pos_coupon_discount(doc)
	reconcile_base_grand_total(doc)
	reconcile_inclusive_tax_rounding(doc)


# ==========================================
# Mã giảm giá cộng trên khuyến mại cả hoá đơn
# ==========================================
#
# Hoá đơn ERPNext chỉ có MỘT ô giảm cả hoá đơn (`discount_amount` / `additional_discount_percentage`
# + `apply_discount_on`), và mỗi lần lưu / chốt, `validate` của ERPNext áp lại khuyến mại theo giao
# dịch (`apply_pricing_rule_on_transaction`) ghi đè ô đó — tiền giảm của mã nằm chung ô bị xoá.
#
# Hai bước dưới giữ được cả hai:
# 1. `strip_pos_coupon_discount` (before_validate): bỏ phần của mã ra khỏi ô, ô chỉ còn khuyến mại;
# 2. ERPNext áp lại khuyến mại như thường (tự kiểm mức tối thiểu, ngày hiệu lực...);
# 3. `add_pos_coupon_discount` (validate): máy chủ TỰ TÍNH tiền giảm của mã trên số đã trừ khuyến
#    mại (`coupon_discount_on_totals`) rồi cộng vào ô. Dòng `custom_pos_coupons` ghi hai số:
#    `discount_amount` — tiền khách thực được bớt (đã gồm thuế), cho người xem / báo cáo;
#    `invoice_discount_amount` (ẩn) — đúng phần đã cộng vào ô, theo gốc `apply_discount_on` của ô
#    (gốc "Net Total" thì là phần trước thuế), cho bước 1 lần lưu sau.
#
# Chỉ chạy khi máy bán yêu cầu (`coupon_after_offer` trong gói gửi `update_invoice` /
# `submit_invoice` → `doc.flags.pos_coupon_after_offer`). Bản PWA chưa gửi cờ này: nó tự tính mã theo
# luật cũ rồi gộp vào `discount_amount`, máy chủ giữ nguyên cách cũ cho nó — đổi số dưới chân PWA là
# hoá đơn lệch tiền thu ngân vừa thu.


def _pos_coupon_row(doc):
	if not doc.flags.get("pos_coupon_after_offer") or not doc.meta.get_field("custom_pos_coupons"):
		return None
	rows = doc.get("custom_pos_coupons") or []
	return rows[0] if rows and rows[0].get("coupon") else None


def strip_pos_coupon_discount(doc, method=None):
	"""Bước 1: bỏ phần của mã (đã cộng ở lần lưu trước) ra khỏi ô giảm cả hoá đơn.

	`custom_pos_coupons[0].invoice_discount_amount` là đúng phần đã cộng vào `discount_amount`, cùng
	gốc `apply_discount_on`. Lần lưu đầu nó là 0 (`update_invoice` đặt) — không có gì để bỏ.
	"""
	row = _pos_coupon_row(doc)
	if not row:
		return
	added = flt(row.get("invoice_discount_amount"))
	if added <= 0:
		return
	# Đang có % thì ô do % quyết định — số tiền chưa gồm phần của mã.
	if not flt(doc.get("additional_discount_percentage")):
		doc.discount_amount = max(0.0, flt(doc.discount_amount) - added)
	row.invoice_discount_amount = 0


def apply_pos_manual_discount(doc):
	"""Khoản giảm cả hoá đơn thu ngân gõ (`posa_manual_discount_amount`) THAY khuyến mại cả hoá đơn.

	Luật chốt 05/10/2026: có khoản gõ tay thì khuyến mại cả hoá đơn không áp; mã giảm giá vẫn trừ
	tiếp sau đó (`add_pos_coupon_discount` chạy ngay sau hàm này). ERPNext áp lại khuyến mại trong
	mỗi lần validate, nên mỗi lần đều đặt lại ô giảm bằng khoản gõ tay — số đó lưu trên hoá đơn nên
	lưu lại từ Desk cũng giữ. Khuyến mại theo dòng và khuyến mại tặng hàng không đụng tới.

	Máy chủ kiểm: điểm bán có cho thu ngân giảm giá cả hoá đơn không, và trần `max_discount_allowed`
	(% trên tổng cộng trước giảm giá cả hoá đơn — cùng gốc app tính %). Bản PWA chỉ kiểm trần ở máy
	bán. Gói không mang số này (PWA) thì không đổi gì.
	"""
	manual = flt(doc.get("posa_manual_discount_amount"))
	if manual <= 0 or not cint(doc.get("is_pos")):
		return

	settings = frappe.db.get_value(
		"POS Settings",
		{"pos_profile": doc.pos_profile},
		["allow_user_to_edit_additional_discount", "max_discount_allowed"],
		as_dict=True,
	) or {}
	if not cint(settings.get("allow_user_to_edit_additional_discount")):
		frappe.throw(_("POS Profile {0} does not allow cashiers to discount the whole invoice.").format(doc.pos_profile))

	precision = doc.precision("discount_amount")
	# Tổng cộng trước mọi giảm giá cả hoá đơn — gốc để kiểm trần.
	doc.additional_discount_percentage = 0
	doc.discount_amount = 0
	doc.apply_discount_on = "Grand Total"
	doc.calculate_taxes_and_totals()
	base = flt(doc.grand_total)

	if manual > base:
		frappe.throw(
			_("Additional discount {0} is greater than the invoice grand total ({1}).").format(
				fmt_money(manual, currency=doc.currency), fmt_money(base, currency=doc.currency)
			)
		)
	max_pct = flt(settings.get("max_discount_allowed"))
	if max_pct > 0 and manual > flt(base * max_pct / 100, precision) + 1:
		frappe.throw(
			_("Additional discount is at most {0}% ({1}), but {2} was given.").format(
				f"{max_pct:g}",
				fmt_money(base * max_pct / 100, currency=doc.currency),
				fmt_money(manual, currency=doc.currency),
			)
		)

	# Mã giảm giá máy chủ tự tính (có cờ) do `add_pos_coupon_discount` cộng sau. Không có cờ (lưu lại
	# từ Desk) thì giữ phần của mã đã ghi lần trước, đừng để mã mất theo.
	kept_coupon = 0.0
	if not doc.flags.get("pos_coupon_after_offer"):
		kept_coupon = sum(flt(r.get("invoice_discount_amount")) for r in doc.get("custom_pos_coupons") or [])

	doc.discount_amount = flt(manual + kept_coupon, precision)
	if doc.meta.get_field("posa_transaction_pricing_rule"):
		# Khuyến mại không áp — trả hàng không được thu hồi khuyến mại này.
		doc.posa_transaction_pricing_rule = None
	doc.calculate_taxes_and_totals()
	if hasattr(doc, "set_default_additional_discount_account"):
		doc.set_default_additional_discount_account()


def add_pos_coupon_discount(doc):
	"""Bước 3: tính tiền giảm của mã trên hoá đơn đã trừ khuyến mại, cộng vào ô giảm cả hoá đơn."""
	row = _pos_coupon_row(doc)
	if not row:
		return

	from pos_next.pos_next.doctype.pos_coupon.pos_coupon import coupon_discount_on_totals

	coupon = frappe.get_cached_doc("POS Coupon", row.coupon)
	precision = doc.precision("discount_amount")
	result = coupon_discount_on_totals(
		coupon, doc.grand_total, doc.total_taxes_and_charges, precision
	)
	if result["amount"] <= 0:
		# Gửi mã mà máy chủ thấy không giảm thì lúc chốt vẫn bị trừ lượt dùng — chặn.
		frappe.throw(
			_("The invoice has not reached the minimum amount for coupon {0} ({1} short).").format(
				row.coupon_code or row.coupon,
				fmt_money(result["missing"], currency=doc.currency),
			)
		)

	# Số máy bán đã trừ cho khách phải khớp số máy chủ tính — lệch là đã thu sai tiền.
	client_amount = doc.flags.get("pos_coupon_client_amount")
	if client_amount is not None and abs(flt(client_amount) - result["amount"]) > 1:
		frappe.throw(
			_("Discount for coupon {0}: the POS calculated {1}, the server calculated {2}. Reload the cart and check out again.").format(
				row.coupon_code or row.coupon,
				fmt_money(client_amount, currency=doc.currency),
				fmt_money(result["amount"], currency=doc.currency),
			)
		)

	has_offer = flt(doc.get("additional_discount_percentage")) or flt(doc.get("discount_amount"))
	if not has_offer:
		# Chỉ có mã: số của mã đã gồm thuế, trừ thẳng khỏi tổng cộng.
		doc.apply_discount_on = "Grand Total"
	# Cộng theo gốc của ô: "Net Total" thì cộng phần trước thuế, ERPNext tự tính lại thuế.
	added = result["net_amount"] if doc.get("apply_discount_on") == "Net Total" else result["amount"]

	# % của khuyến mại đổi thành số tiền ERPNext vừa tính từ nó, để cộng được phần của mã.
	doc.additional_discount_percentage = 0
	doc.discount_amount = flt(flt(doc.discount_amount) + added, precision)
	row.invoice_discount_amount = added
	row.discount_amount = result["amount"]
	doc.calculate_taxes_and_totals()

	# Ô giảm vừa có tiền — điền tài khoản chiết khấu nếu `validate` của hoá đơn chưa điền (lúc đó ô
	# có thể đang 0 vì phần của mã đã bị bỏ ra ở bước 1).
	if hasattr(doc, "set_default_additional_discount_account"):
		doc.set_default_additional_discount_account()


def capture_pos_authoritative_discounts(doc, method=None):
	"""Snapshot each item's rate/discount_amount/pricing_rules before core validate() runs.

	ERPNext's set_missing_item_details() (inside core validate(), which runs
	after this before_validate hook) re-fetches each item's Pricing Rule and
	re-derives rate = price_list_rate * (1 - discount_percentage / 100) -
	e.g. 499000 * (1 - 40.08/100) = 299000.8 - overwriting the whole-currency
	rate POS actually charged. restore_pos_authoritative_discounts() (in the
	`validate` hook below) puts this snapshot back afterwards.

	Stored on item.flags (in-memory, not a DB field) - safe since
	before_validate and validate share the same Document instance within one
	save()/submit() call. Idempotent per item: update_invoice() also calls
	this manually, earlier, before its own calculate_taxes_and_totals() call
	can corrupt the values - the framework's own before_validate call must
	not overwrite that earlier, still-correct snapshot.
	"""
	if not cint(doc.get("is_pos")):
		return

	for item in doc.get("items", []):
		if item.flags.get("pos_authoritative_discount"):
			continue
		if not item.price_list_rate or not item.get("pricing_rules"):
			continue
		item.flags.pos_authoritative_discount = {
			"price_list_rate": item.price_list_rate,
			"rate": item.rate,
			"discount_amount": item.discount_amount,
			"pricing_rules": item.pricing_rules,
		}


def restore_pos_authoritative_discounts(doc):
	"""Restore the snapshot from capture_pos_authoritative_discounts() after
	core validate() has re-derived (and mis-rounded) the same fields from the
	live Pricing Rule."""
	if not cint(doc.get("is_pos")):
		return

	changed = False
	for item in doc.get("items", []):
		snapshot = item.flags.get("pos_authoritative_discount")
		if not snapshot:
			continue
		if item.rate == snapshot["rate"] and item.discount_percentage == 0:
			continue

		item.price_list_rate = snapshot["price_list_rate"]
		item.rate = snapshot["rate"]
		item.discount_amount = snapshot["discount_amount"]
		item.pricing_rules = snapshot["pricing_rules"]
		# Zero discount_percentage so calculate_taxes_and_totals() below uses
		# `rate = price_list_rate - discount_amount` instead of re-deriving
		# the same fractional rate from discount_percentage.
		item.discount_percentage = 0
		changed = True

	if changed:
		doc.calculate_taxes_and_totals()


def apply_tax_inclusive(doc):
	"""
	Mark taxes as inclusive based on POS Profile setting.

	This function reads the tax_inclusive setting from POS Settings
	and applies it to all taxes in the invoice (except Actual charge type).

	Args:
		doc: Sales Invoice document
	"""
	if not doc.pos_profile:
		return

	try:
		# Get POS Settings for this profile
		pos_settings = frappe.db.get_value(
			"POS Settings",
			{"pos_profile": doc.pos_profile},
			["tax_inclusive"],
			as_dict=True
		)
		tax_inclusive = pos_settings.get("tax_inclusive", 0) if pos_settings else 0
	except Exception:
		tax_inclusive = 0

	has_changes = False
	for tax in doc.get("taxes", []):
		# Skip Actual charge type - these can't be inclusive
		if tax.charge_type == "Actual":
			if tax.included_in_print_rate:
				tax.included_in_print_rate = 0
				has_changes = True
			continue

		# Apply tax inclusive setting
		if tax_inclusive and not tax.included_in_print_rate:
			tax.included_in_print_rate = 1
			has_changes = True
		elif not tax_inclusive and tax.included_in_print_rate:
			tax.included_in_print_rate = 0
			has_changes = True

	# Recalculate if we made changes
	if has_changes:
		doc.calculate_taxes_and_totals()


def reconcile_base_grand_total(doc):
	"""Fix an ERPNext core bug: when total_taxes_and_charges rounds to exactly
	0, calculate_totals() sets base_grand_total = base_net_total instead of
	deriving it from grand_total (see erpnext/controllers/taxes_and_totals.py,
	calculate_totals(), the "else: self.doc.base_net_total" branch).

	That branch silently ignores a "Grand Total"-level discount whenever it
	zeroes out tax on a heavily-discounted (or free, 100%-off) POS invoice -
	net_total no longer equals grand_total in that case, but base_grand_total
	gets set from net_total anyway, so it disagrees with grand_total even
	though conversion_rate=1. make_gl_entries() then debits/credits from the
	two mismatched totals and submit fails with "Debit and Credit not equal".

	Re-derive base_grand_total from grand_total directly - the correct
	formula regardless of whether total_taxes_and_charges is zero.
	"""
	if not cint(doc.get("is_pos")):
		return

	expected_base_grand_total = flt(
		flt(doc.grand_total) * flt(doc.conversion_rate or 1),
		doc.precision("base_grand_total"),
	)
	if flt(doc.base_grand_total) == expected_base_grand_total:
		return

	doc.base_grand_total = expected_base_grand_total

	if doc.meta.get_field("base_rounded_total") and not doc.is_rounded_total_disabled():
		doc.base_rounded_total = flt(
			flt(doc.rounded_total) * flt(doc.conversion_rate or 1),
			doc.precision("base_rounded_total"),
		)


def reconcile_inclusive_tax_rounding(doc):
	taxes = doc.get("taxes") or []
	if not taxes:
		return
	if not any(cint(t.included_in_print_rate) for t in taxes):
		return

	sum_net = flt(sum(flt(item.base_net_amount) for item in doc.get("items", [])))
	sum_tax = flt(sum(flt(tax.base_tax_amount_after_discount_amount) for tax in taxes))
	diff = flt(flt(doc.base_grand_total) - (sum_net + sum_tax))

	# Same tolerance ERPNext itself uses to decide a diff is legitimate
	# per-line rounding noise (see adjust_grand_total_for_inclusive_tax) -
	# beyond that, don't silently mask what could be a real data problem.
	if not diff or abs(diff) > 5:
		return

	last_tax = taxes[-1]
	last_tax.tax_amount = flt(last_tax.tax_amount + diff)
	last_tax.base_tax_amount = flt(last_tax.base_tax_amount + diff)
	last_tax.tax_amount_after_discount_amount = flt(last_tax.tax_amount_after_discount_amount + diff)
	last_tax.base_tax_amount_after_discount_amount = flt(
		last_tax.base_tax_amount_after_discount_amount + diff
	)
	last_tax.total = flt(last_tax.total + diff)
	last_tax.base_total = flt(last_tax.base_total + diff)


def auto_assign_loyalty_program_on_invoice(doc):
	"""
	Auto-assign loyalty program to customer if they qualify for one but
	don't have a loyalty program yet.

	Matches the customer against Loyalty Programs with auto_opt_in enabled,
	respecting each program's Customer Group / Customer Territory restrictions
	(same matching rules as erpnext.selling.doctype.customer.customer.set_loyalty_program).
	This ensures customers created before loyalty was enabled (or before they
	matched a program's conditions) can still be opted in at the point of sale.

	Args:
		doc: Sales Invoice document
	"""
	if not doc.is_pos or not doc.customer:
		return

	customer = frappe.get_cached_doc("Customer", doc.customer)
	if customer.loyalty_program:
		return

	from erpnext.selling.doctype.customer.customer import get_loyalty_programs

	loyalty_programs = get_loyalty_programs(customer)

	if len(loyalty_programs) == 1:
		frappe.db.set_value(
			"Customer",
			doc.customer,
			"loyalty_program",
			loyalty_programs[0],
			update_modified=False
		)


def before_cancel(doc, method=None):
	"""
	Before Cancel hook for Sales Invoice.
	- Cancel wallet transactions from loyalty→wallet conversion
	- Cancel any credit redemption journal entries
	"""
	# Cancel linked Wallet Transactions first (Dynamic Link would otherwise block SI cancel)
	try:
		from pos_next.api.wallet import cancel_wallet_transactions_for_invoice
		cancel_wallet_transactions_for_invoice(doc, method)
	except frappe.ValidationError:
		raise
	except Exception as e:
		frappe.log_error(
			title="Wallet Transaction Cancellation Error",
			message=f"Invoice: {doc.name}, Error: {str(e)}\n{frappe.get_traceback()}"
		)
		frappe.throw(
			_("Cannot cancel invoice because linked wallet transaction(s) could not be cancelled: {0}").format(
				str(e)
			)
		)

	try:
		from pos_next.api.credit_sales import cancel_credit_journal_entries
		cancel_credit_journal_entries(doc.name)
	except Exception as e:
		frappe.log_error(
			title="Credit Sale JE Cancellation Error",
			message=f"Invoice: {doc.name}, Error: {str(e)}\n{frappe.get_traceback()}"
		)
		# Don't block invoice cancellation if JE cancellation fails
		frappe.msgprint(
			_("Warning: Some credit journal entries may not have been cancelled. Please check manually."),
			alert=True,
			indicator="orange"
		)
