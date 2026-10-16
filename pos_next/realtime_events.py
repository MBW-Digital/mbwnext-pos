# -*- coding: utf-8 -*-
# Copyright (c) 2024, POS Next and contributors
# For license information, please see license.txt

"""
Real-time event handlers for POS Next.
Emits Socket.IO events when stock-affecting transactions occur.
"""

import frappe
from frappe import _

from pos_next.api.items import get_stock_quantities


def emit_stock_update_event(doc, method=None):
	"""
	Emit real-time stock update event when Sales Invoice is submitted.

	This event notifies all connected POS terminals about stock changes,
	allowing them to update their cached item quantities in real-time.

	Args:
		doc: Sales Invoice document
		method: Hook method name (on_submit, on_cancel, etc.)
	"""
	if not doc.update_stock:
		return

	# Skip if not a POS invoice (check if field exists first)
	if hasattr(doc, 'is_pos') and not doc.is_pos:
		return

	try:
		# Collect unique item codes per warehouse to avoid redundant queries
		item_codes_by_warehouse = {}
		for item in doc.items:
			item_code = getattr(item, "item_code", None)
			warehouse = getattr(item, "warehouse", None)

			# Skip rows that don't affect stock
			if not item_code or not warehouse:
				continue

			if hasattr(item, "is_stock_item") and item.is_stock_item is not None:
				if not int(item.is_stock_item):
					continue
			elif hasattr(item, "stock_qty") and not frappe.utils.flt(item.stock_qty):
				continue

			item_codes_by_warehouse.setdefault(warehouse, set()).add(item_code)

		if not item_codes_by_warehouse:
			return

		# Biến thể vừa bán thì gửi kèm tồn mới của hàng mẫu — danh mục hiện tổng tồn các biến thể
		# trên ô hàng mẫu, mà quầy khác không biết biến thể này thuộc mẫu nào.
		all_codes = set().union(*item_codes_by_warehouse.values())
		template_of = dict(
			frappe.get_all(
				"Item",
				filters={"name": ["in", list(all_codes)], "variant_of": ["is", "set"]},
				fields=["name", "variant_of"],
				as_list=True,
			)
		)
		if template_of:
			for codes in item_codes_by_warehouse.values():
				codes.update(template_of[code] for code in list(codes) if code in template_of)

		# Build stock updates with current quantities
		stock_updates = []
		warehouses = set()
		for warehouse, codes in item_codes_by_warehouse.items():
			warehouses.add(warehouse)
			# Use shared stock utility to keep logic consistent with API responses
			warehouse_updates = get_stock_quantities(list(codes), warehouse)

			# Ensure events always have numeric qty fields, even if API returns None
			for update in warehouse_updates:
				actual_qty = frappe.utils.flt(update.get("actual_qty"))
				update["actual_qty"] = actual_qty
				update["stock_qty"] = actual_qty if update.get("stock_qty") is None else update["stock_qty"]
				update["warehouse"] = update.get("warehouse") or warehouse

			stock_updates.extend(warehouse_updates)

		if not stock_updates:
			return

		# Prepare event data
		event_data = {
			"invoice_name": doc.name,
			"warehouses": list(warehouses),
			"stock_updates": stock_updates,
			"timestamp": frappe.utils.now(),
			"event_type": "cancel" if method == "on_cancel" else "submit"
		}

		# Emit event to all connected clients
		# Event name: pos_stock_update
		# Clients can subscribe to this event and filter by warehouse
		frappe.publish_realtime(
			event="pos_stock_update",
			message=event_data,
			user=None,  # Broadcast to all users
			after_commit=True  # Only emit after successful DB commit
		)

	except Exception as e:
		# Log error but don't fail the transaction
		frappe.log_error(
			title=_("Real-time Stock Update Event Error"),
			message=f"Failed to emit stock update event for {doc.name}: {str(e)}"
		)


def emit_invoice_created_event(doc, method=None):
	"""
	Emit real-time event when invoice is created.

	This can be used to notify other terminals about new sales,
	update dashboards, or trigger other real-time UI updates.

	Args:
		doc: Sales Invoice document
		method: Hook method name
	"""
	if not doc.is_pos:
		return

	try:
		event_data = {
			"invoice_name": doc.name,
			"grand_total": doc.grand_total,
			"customer": doc.customer,
			"pos_profile": doc.pos_profile,
			"timestamp": frappe.utils.now(),
		}

		frappe.publish_realtime(
			event="pos_invoice_created",
			message=event_data,
			user=None,
			after_commit=True
		)

	except Exception as e:
		frappe.log_error(
			title=_("Real-time Invoice Created Event Error"),
			message=f"Failed to emit invoice created event for {doc.name}: {str(e)}"
		)


def emit_pos_profile_updated_event(doc, method=None):
	"""
	Emit real-time event when POS Profile is updated.

	This event notifies all connected POS terminals about configuration changes,
	particularly item group filters, allowing them to clear their cache and reload
	items automatically without manual intervention.

	Args:
		doc: POS Profile document
		method: Hook method name (on_update, validate, etc.)
	"""
	try:
		# Check if item_groups have changed by comparing with the original doc
		if doc.has_value_changed("item_groups"):
			# Extract current item groups
			current_item_groups = [{"item_group": ig.item_group} for ig in doc.get("item_groups", [])]

			# Prepare event data
			event_data = {
				"pos_profile": doc.name,
				"item_groups": current_item_groups,
				"timestamp": frappe.utils.now(),
				"change_type": "item_groups_updated"
			}

			# Emit event to all connected clients
			# Event name: pos_profile_updated
			# Clients can subscribe to this event and invalidate their cache
			frappe.publish_realtime(
				event="pos_profile_updated",
				message=event_data,
				user=None,  # Broadcast to all users
				after_commit=True  # Only emit after successful DB commit
			)

			frappe.logger().info(
				f"Emitted pos_profile_updated event for {doc.name} - item groups changed"
			)

	except Exception as e:
		# Log error but don't fail the transaction
		frappe.log_error(
			title=_("Real-time POS Profile Update Event Error"),
			message=f"Failed to emit POS profile update event for {doc.name}: {str(e)}"
		)


def emit_pos_settings_updated_event(doc, method=None):
	"""
	Phát sự kiện `pos_settings_updated` khi Cài đặt POS được lưu hoặc xoá.

	Máy đang bán chỉ đọc Cài đặt POS lúc nạp dữ liệu đầu phiên. Không có sự kiện này thì quản trị
	đổi "Cho phép tồn âm" giữa ca, quầy vẫn chạy theo cài đặt cũ tới khi đăng nhập lại.

	Chỉ gửi TÊN điểm bán, không gửi giá trị cài đặt: sự kiện phát cho phòng `all` (mọi tài khoản
	System User), mà cài đặt có tài khoản ví, mức giảm giá tối đa... Máy nhận tự gọi lại
	`get_initial_data`, nên cài đặt chỉ có một nguồn và được tính đúng một cách.

	Đổi điểm bán của bản ghi (sửa trường `pos_profile`) thì báo cả điểm bán cũ: nó vừa mất cài đặt.
	"""
	try:
		profiles = {doc.pos_profile}
		before = doc.get_doc_before_save() if method == "on_update" else None
		if before and before.pos_profile:
			profiles.add(before.pos_profile)

		for pos_profile in filter(None, profiles):
			frappe.publish_realtime(
				event="pos_settings_updated",
				message={
					"pos_profile": pos_profile,
					"timestamp": frappe.utils.now(),
					"change_type": "deleted" if method == "on_trash" else "updated",
				},
				user=None,  # Mọi quầy; máy nhận tự lọc theo điểm bán của mình
				after_commit=True,  # Chỉ phát khi lưu thành công
			)

	except Exception as e:
		# Ghi lỗi nhưng không chặn việc lưu cài đặt
		frappe.log_error(
			title=_("Real-time POS Settings Update Event Error"),
			message=f"Failed to emit POS settings update event for {doc.name}: {str(e)}"
		)


def emit_offers_updated_event(doc, method=None):
	"""
	Phát sự kiện `pos_offers_updated` khi Pricing Rule / Promotional Scheme / Promotion Campaign được
	lưu hoặc xoá — gọi từ `pos_next.api.offers.clear_offers_cache`.

	Quầy đang bán chỉ lấy danh sách ưu đãi lúc mở màn bán (hay khi thu ngân bấm tải lại). Không có
	sự kiện này thì quản trị tắt một khuyến mại giữa ca, quầy vẫn liệt kê nó tới lần nạp sau.

	Chỉ gửi TÊN chứng từ và công ty, không gửi nội dung khuyến mại: sự kiện phát cho phòng `all`.
	Máy nhận tự gọi lại `get_offers`, lọc theo công ty của điểm bán mình (công ty trống là mọi quầy).

	Lưu một Promotional Scheme sinh lại hàng loạt Pricing Rule, mỗi cái một lần `on_update`: trong một
	request chỉ phát MỘT sự kiện cho mỗi công ty.
	"""
	try:
		company = doc.get("company") if doc else None
		sent = frappe.flags.setdefault("pos_offers_updated_sent", set())
		if company in sent:
			return
		sent.add(company)

		frappe.publish_realtime(
			event="pos_offers_updated",
			message={
				"doctype": doc.doctype if doc else None,
				"name": doc.name if doc else None,
				"company": company,
				"timestamp": frappe.utils.now(),
				"change_type": "deleted" if method == "on_trash" else "updated",
			},
			user=None,  # Mọi quầy; máy nhận tự lọc theo công ty của mình
			after_commit=True,  # Chỉ phát khi lưu thành công
		)

	except Exception as e:
		# Ghi lỗi nhưng không chặn việc lưu khuyến mại
		frappe.log_error(
			title=_("Real-time POS Offers Update Event Error"),
			message=f"Failed to emit POS offers update event for {getattr(doc, 'name', None)}: {str(e)}"
		)
