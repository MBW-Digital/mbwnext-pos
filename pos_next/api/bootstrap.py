# -*- coding: utf-8 -*-
# Copyright (c) 2024, POS Next and contributors
# For license information, please see license.txt

"""
Bootstrap API - POS Application Startup Data

This module provides a single API endpoint that fetches all data needed
to initialize the POS application. Instead of making 5+ sequential API calls,
the frontend fetches everything in one request.

Data Returned:
    - locale: User's language preference (e.g., "en", "ar")
    - precision: Number formatting settings from System Settings
        - currency: Decimal places for totals (default: 2)
        - float: Decimal places for rates/quantities (default: 3)
        - rounding_method: "Banker's Rounding" or "Commercial Rounding"
        - number_format: Pattern like "#,###.##"
    - shift: Current open POS Opening Shift (if any)
    - pos_profile: POS Profile configuration
    - pos_settings: POS-specific settings
    - payment_methods: Available payment methods

Performance: ~300-500ms faster than multiple API calls
"""

import frappe
from frappe import _
from frappe.query_builder import DocType
from frappe.query_builder.functions import Coalesce
from frappe.utils import cint, flt

from pos_next.api.constants import POS_SETTINGS_FIELDS, DEFAULT_POS_SETTINGS


@frappe.whitelist()
def get_initial_data():
	"""
	Fetch all initial data needed for POS application startup.

	This is the main bootstrap endpoint called when the POS app loads.
	It combines multiple data sources into a single response.

	Returns:
		dict: {
			success: bool,
			locale: str,
			precision: dict,
			shift: dict | None,
			pos_profile: dict | None,
			pos_settings: dict | None,
			payment_methods: list
		}

	Raises:
		AuthenticationError: If user is not logged in (Guest)
	"""
	if frappe.session.user == "Guest":
		frappe.throw(_("Authentication required"), frappe.AuthenticationError)

	from pos_next.api.customers import default_customer_group, default_territory

	result = {
		"success": True,
		"locale": _get_user_language(),
		"precision": _get_precision_settings(),
		"shift": None,
		"pos_profile": None,
		"pos_settings": None,
		"payment_methods": [],
		"pos_external_app_url": frappe.conf.get("pos_external_app_url") or frappe.utils.get_url("/app"),
		# Tên site thật — namespace Socket.IO mà mọi sự kiện realtime được phát vào. App native
		# không đoán được nó từ địa chỉ đang dùng (địa chỉ IP, tunnel, tên miền khác tên site).
		"site_name": frappe.local.site,
		# Máy chủ tự tính mã giảm giá và cộng trên khuyến mại cả hoá đơn khi gói hoá đơn mang
		# `coupon_after_offer` (sales_invoice_hooks.add_pos_coupon_discount). Máy chủ cũ không có
		# khoá này — app native phải gộp mã vào discount_amount như trước và chặn mã + khuyến mại.
		"coupon_after_offer": 1,
		# Khoản giảm cả hoá đơn thu ngân gõ (`posa_manual_discount_amount`) THAY khuyến mại cả hoá đơn
		# (sales_invoice_hooks.apply_pos_manual_discount). Máy chủ cũ không có — app native ẩn ô đó.
		"manual_discount_replaces_offer": 1,
		# Chống gửi trùng được cả Đơn hàng bán lúc mất mạng (`Offline Invoice Sync.reference_*`). Máy chủ
		# cũ chỉ chống trùng Hoá đơn — app native chặn Đơn hàng lúc mất mạng.
		"offline_sales_order": 1,
		# What apply_offers() falls back to when the cart has no customer. The POS
		# needs the same values or it judges customer-scoped promotions differently
		# from the server and shows one as applied that the server refuses
		# (PM-TASK-00033 / PM-TASK-00034).
		"selling_defaults": {
			"customer_group": default_customer_group(),
			"territory": default_territory(),
		},
	}

	# Get open shift - if no shift, return early with defaults
	shift = _get_open_shift()
	if not shift:
		return result

	pos_profile = shift["pos_profile_doc"]
	pos_profile_name = pos_profile.name

	result["shift"] = {
		"name": shift["name"],
		"pos_profile": pos_profile_name,
		"period_start_date": str(shift["period_start_date"]),
		"status": shift["status"],
	}

	result["pos_profile"] = {
		"name": pos_profile.name,
		"company": pos_profile.company,
		"currency": pos_profile.currency,
		# Phần nhỏ nhất của tiền tệ (VND: 100) — ERPNext làm tròn tổng hoá đơn (rounded_total) theo
		# số này, app native phải thu đúng số đó. Đọc ở đây vì tài khoản thu ngân thường không có quyền
		# đọc doctype Currency.
		"currency_fraction": flt(
			frappe.db.get_value("Currency", pos_profile.currency, "smallest_currency_fraction_value", cache=True)
		),
		"warehouse": pos_profile.warehouse,
		"selling_price_list": pos_profile.selling_price_list,
		"customer": pos_profile.customer,
		"write_off_account": pos_profile.write_off_account,
		"write_off_cost_center": pos_profile.write_off_cost_center,
		"write_off_limit": pos_profile.write_off_limit or 0,
		"print_format": pos_profile.get("print_format"),
		"auto_print": pos_profile.get("print_receipt_on_order_complete", 0),
		"country": pos_profile.get("country"),
		"custom_use_shift_in_pos": pos_profile.get("custom_use_shift_in_pos") or 0,
		"custom_print_in_duplicate": pos_profile.get("custom_print_in_duplicate") or 0,
		# Nhóm hàng điểm bán được bán (rỗng là mọi nhóm). App native so với `item_groups` của sự kiện
		# `pos_profile_updated` — sự kiện phát ở MỌI lần lưu POS Profile (`has_value_changed` so bảng con
		# theo đối tượng nên luôn "đổi"), không so thì sửa ô nào cũng làm mọi máy nạp lại danh mục.
		"item_groups": [row.item_group for row in pos_profile.get("item_groups") or [] if row.item_group],
	}

	result["pos_settings"] = _get_pos_settings(pos_profile)
	from pos_next.api.sepay import _get_sepay_settings, mark_sepay_methods
	result["payment_methods"] = mark_sepay_methods(_get_payment_methods(pos_profile_name), pos_profile_name)
	sepay = _get_sepay_settings(pos_profile_name)
	result["pos_settings"]["enable_bank_transfer_check"] = 1 if sepay else 0
	# Hình thức thu bằng QR SePay (ô "SePay Mode of Payment" của POS Profile), None khi SePay tắt. App
	# native chỉ bật QR theo khoá này: máy chủ cũ không gửi, và `is_sepay` của máy chủ cũ đoán theo tên
	# ("Chuyển khoản VNPay" cũng thành SePay).
	result["sepay_mode_of_payment"] = sepay.mode_of_payment if sepay else None

	# Đầu / chân phiếu của điểm bán — app native in phiếu tạm tính (đơn giữ lại) bằng bộ này, kể cả lúc
	# mất mạng. Hỏng thì bỏ: app in đầu phiếu bằng tên công ty.
	try:
		from pos_next.api.receipt_print import receipt_header_for_profile

		result["receipt_header"] = receipt_header_for_profile(pos_profile, shift["name"])
	except Exception:
		frappe.log_error(frappe.get_traceback(), "Bootstrap receipt header error")

	return result


# =============================================================================
# Private Helper Functions
# =============================================================================

def _get_user_language():
	"""
	Get user's language preference from User doctype.

	Returns:
		str: Language code in lowercase (e.g., "en", "ar", "de")
	"""
	lang = frappe.db.get_value("User", frappe.session.user, "language")
	return (lang or "en").lower()


def _get_precision_settings():
	"""
	Get precision and formatting settings from System Settings.

	Fetches all settings in a single query for performance.
	These settings ensure frontend calculations match ERPNext exactly.

	Returns:
		dict: {
			currency: int - Decimal places for currency totals (default: 2)
			float: int - Decimal places for rates/quantities (default: 3)
			rounding_method: str - "Banker's Rounding" or "Commercial Rounding"
			number_format: str - Number format pattern (e.g., "#,###.##")
		}
	"""
	settings = frappe.db.get_value(
		"System Settings",
		"System Settings",
		["currency_precision", "float_precision", "rounding_method", "number_format"],
		as_dict=True
	)

	return {
		"currency": int(settings.currency_precision) if settings.currency_precision else 2,
		"float": int(settings.float_precision) if settings.float_precision else 3,
		"rounding_method": settings.rounding_method,
		"number_format": settings.number_format,
	}


def _get_open_shift():
	"""
	Get user's currently open POS shift.

	Finds the most recent open shift for the current user and fetches
	the associated POS Profile document for reuse in other functions.

	Returns:
		dict | None: Shift data with 'pos_profile_doc' attached, or None if no open shift
			{
				name: str,
				pos_profile: str,
				period_start_date: datetime,
				status: str,
				pos_profile_doc: Document
			}
	"""
	shift = frappe.db.get_value(
		"POS Opening Shift",
		{
			"user": frappe.session.user,
			"pos_closing_shift": ["is", "not set"],
			"docstatus": 1,
			"status": "Open",
		},
		["name", "pos_profile", "period_start_date", "status"],
		as_dict=True,
		order_by="period_start_date desc",
	)

	if not shift:
		return None

	# Fetch POS Profile once, reuse throughout bootstrap
	shift["pos_profile_doc"] = frappe.get_doc("POS Profile", shift["pos_profile"])
	return shift


def _get_pos_settings(pos_profile_doc):
	"""
	Get POS Settings for the given POS Profile.

	Some settings are derived from POS Profile (single source of truth):
	- allow_write_off_change: Based on write_off_account and write_off_limit
	- disable_rounded_total: Directly from POS Profile

	Args:
		pos_profile_doc: POS Profile document object

	Returns:
		dict: POS Settings with derived values
	"""
	try:
		settings = frappe.db.get_value(
			"POS Settings",
			{"pos_profile": pos_profile_doc.name, "enabled": 1},
			POS_SETTINGS_FIELDS,
			as_dict=True
		) or DEFAULT_POS_SETTINGS.copy()

		# Derive from POS Profile (single source of truth)
		settings["allow_write_off_change"] = 1 if (
			pos_profile_doc.write_off_account and (pos_profile_doc.write_off_limit or 0) > 0
		) else 0
		settings["disable_rounded_total"] = _rounding_disabled(pos_profile_doc)

		return settings
	except Exception:
		frappe.log_error(frappe.get_traceback(), "Get POS Settings Error")
		fallback = DEFAULT_POS_SETTINGS.copy()
		fallback["disable_rounded_total"] = _rounding_disabled(pos_profile_doc)
		return fallback


def _rounding_disabled(pos_profile_doc):
	"""Hoá đơn POS có tắt làm tròn tổng không — ĐÚNG luật `update_invoice` (invoices.py) dùng lúc lưu:
	POS Profile để trống thì coi là tắt (1). Bản cũ trả `or 0` (bật làm tròn) — app thu theo số làm
	tròn trong khi hoá đơn lưu ra không làm tròn."""
	value = pos_profile_doc.get("disable_rounded_total")
	return 1 if value is None else cint(value)


def _get_payment_methods(pos_profile_name):
	"""
	Get available payment methods for the POS Profile.

	Uses a single JOIN query to fetch payment methods with their types
	from Mode of Payment, avoiding N+1 query problem.

	Args:
		pos_profile_name: Name of the POS Profile

	Returns:
		list[dict]: Payment methods with fields:
			- mode_of_payment: str
			- default: int (0 or 1)
			- allow_in_returns: int (0 or 1)
			- type: str ("Cash", "Bank", etc.)
	"""
	try:
		POSPaymentMethod = DocType("POS Payment Method")
		ModeOfPayment = DocType("Mode of Payment")

		return (
			frappe.qb.from_(POSPaymentMethod)
			.left_join(ModeOfPayment)
			.on(POSPaymentMethod.mode_of_payment == ModeOfPayment.name)
			.select(
				POSPaymentMethod.mode_of_payment,
				POSPaymentMethod.default,
				POSPaymentMethod.allow_in_returns,
				Coalesce(ModeOfPayment.type, "Cash").as_("type")
			)
			.where(POSPaymentMethod.parent == pos_profile_name)
			.orderby(POSPaymentMethod.idx)
			.run(as_dict=True)
		)
	except Exception:
		frappe.log_error(frappe.get_traceback(), "Get Payment Methods Error")
		return []
