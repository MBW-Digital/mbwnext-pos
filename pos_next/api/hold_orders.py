# Copyright (c) 2026, BrainWise and contributors
# For license information, please see license.txt

"""
Giữ hàng cho khách đến nhận tại quầy POS (PM-FEAT-00070).

Đơn giữ = Sales Order submit có `reserve_stock = 1` → ERPNext tạo Stock Reservation Entry (SRE),
khoá tồn ở mọi kênh (POS, desk, xuất kho). Chỉ chạy khi site bật
`Stock Settings.enable_stock_reservation`.

SRE không có hạn, nên đơn quá hạn được nhả NGAY trước mọi thao tác đụng tới tồn của đúng mặt
hàng/kho đó (`release_expired_holds`, gọi từ API POS và từ before_submit của chứng từ xuất kho);
scheduler mỗi phút chỉ dọn đơn không ai đụng tới.

Quyền là quyền THEO QUẦY: user nằm trong danh sách user của quầy và có role trong bảng role của
quầy - kể cả System Manager. Truy vấn đọc dùng frappe.get_all / Query Builder (không lọc User
Permission) SAU KHI đã kiểm quyền quầy và luôn lọc cứng theo kho / quầy.
"""

import json
from contextlib import contextmanager

import frappe
from frappe import _
from frappe.query_builder import DocType
from frappe.query_builder.functions import Count, IfNull, Sum
from frappe.utils import add_to_date, cint, flt, get_datetime, getdate, now_datetime

STATUS_HOLDING = "Holding"
STATUS_PICKED_UP = "Picked Up"
STATUS_EXPIRED = "Expired"
STATUS_CANCELLED = "Cancelled"
ALL_STATUSES = (STATUS_HOLDING, STATUS_PICKED_UP, STATUS_EXPIRED, STATUS_CANCELLED)

QTY_TOLERANCE = 1e-6


class HoldStockChangedError(frappe.ValidationError):
	"""Tồn vừa thay đổi (quầy khác giữ / bán trước) - client phải kiểm lại."""


# ---------------------------------------------------------------------------
# Cấu hình + quyền theo quầy
# ---------------------------------------------------------------------------


def stock_reservation_enabled():
	return cint(frappe.db.get_single_value("Stock Settings", "enable_stock_reservation"))


def _get_profile(pos_profile):
	if not pos_profile or not frappe.db.exists("POS Profile", pos_profile):
		frappe.throw(_("POS Profile {0} does not exist").format(pos_profile or ""))
	return frappe.get_cached_doc("POS Profile", pos_profile)


def _roles_of(profile, fieldname):
	return {row.role for row in (profile.get(fieldname) or []) if row.role}


def _has_hold_access(pos_profile, action, user=None):
	"""True nếu user được làm `action` (view / create / manage) tại quầy. Không throw."""
	user = user or frappe.session.user
	if not pos_profile or not frappe.db.exists("POS Profile", pos_profile):
		return False

	profile = frappe.get_cached_doc("POS Profile", pos_profile)
	if profile.get("disabled") or not cint(profile.get("posa_enable_hold_order")):
		return False
	if not any(row.user == user for row in (profile.get("applicable_for_users") or [])):
		return False

	create_roles = _roles_of(profile, "posa_hold_create_roles")
	manage_roles = _roles_of(profile, "posa_hold_manage_roles")
	allowed = {"create": create_roles, "manage": manage_roles, "view": create_roles | manage_roles}.get(action)
	if not allowed:
		return False
	return bool(allowed & set(frappe.get_roles(user)))


def _check_access(pos_profile, action):
	if not _has_hold_access(pos_profile, action):
		messages = {
			"view": _("You are not allowed to view hold orders at POS Profile {0}"),
			"create": _("You are not allowed to hold stock at POS Profile {0}"),
			"manage": _("You are not allowed to extend or cancel hold orders at POS Profile {0}"),
		}
		frappe.throw(messages.get(action, messages["view"]).format(pos_profile), frappe.PermissionError)
	return _get_profile(pos_profile)


@contextmanager
def _as_administrator():
	"""ERPNext tạo / huỷ Stock Reservation Entry bên trong mã của nó, không truyền ignore_permissions.
	Thu ngân thường không có quyền trên SRE → chạy đúng bước đó dưới Administrator SAU KHI đã kiểm
	quyền theo quầy; người thao tác thật vẫn ghi ở owner của Sales Order và Comment."""
	user = frappe.session.user
	if user == "Administrator":
		yield
		return
	frappe.set_user("Administrator")
	try:
		yield
	finally:
		frappe.set_user(user)


def auto_reserve_batches():
	"""Stock Settings "Auto Reserve Serial and Batch": bật thì ERPNext giữ đúng lô / serial, tắt thì giữ theo số lượng."""
	return cint(frappe.db.get_single_value("Stock Settings", "auto_reserve_serial_and_batch"))


def _require_site_enabled():
	if not stock_reservation_enabled():
		frappe.throw(_("Stock Reservation is not enabled in Stock Settings, so stock cannot be held."))


def _hold_hours(profile):
	default = cint(profile.get("posa_hold_default_hours")) or 24
	maximum = cint(profile.get("posa_hold_max_hours")) or 72
	return min(default, maximum), max(maximum, 1)


def _store_label(pos_profile):
	return pos_profile or ""


def _hold_stores(profile):
	"""Cửa hàng nhận: các quầy cùng company đã bật giữ hàng và có kho."""
	rows = frappe.get_all(
		"POS Profile",
		filters={"company": profile.company, "disabled": 0, "posa_enable_hold_order": 1},
		fields=["name", "warehouse"],
		order_by="name",
	)
	stores = [{"pos_profile": r.name, "warehouse": r.warehouse, "label": _store_label(r.name)} for r in rows if r.warehouse]
	# Quầy đang đứng luôn đứng đầu
	stores.sort(key=lambda s: (s["pos_profile"] != profile.name, s["label"]))
	return stores


def _resolve_store(profile, store_pos_profile):
	store_pos_profile = store_pos_profile or profile.name
	store = next((s for s in _hold_stores(profile) if s["pos_profile"] == store_pos_profile), None)
	if not store:
		frappe.throw(_("{0} is not a pickup store for hold orders").format(store_pos_profile))
	return store


@frappe.whitelist()
def get_hold_access(pos_profile):
	"""Cờ + cấu hình cho POS ẩn/hiện nút Giữ hàng và tab Đơn chờ lấy. Không throw khi thiếu quyền."""
	profile = _get_profile(pos_profile)
	default_hours, max_hours = _hold_hours(profile)
	enabled = cint(profile.get("posa_enable_hold_order"))
	can_view = _has_hold_access(pos_profile, "view")
	live_count = 0
	if enabled and can_view and stock_reservation_enabled():
		release_expired_holds()
		live_count = frappe.db.count(
			"Sales Order",
			{"posa_is_hold_order": 1, "posa_hold_status": STATUS_HOLDING, "posa_hold_pos_profile": profile.name, "docstatus": 1},
		)
	return {
		"site_enabled": stock_reservation_enabled(),
		"enabled": enabled,
		"can_view": can_view,
		"can_create": _has_hold_access(pos_profile, "create"),
		"can_manage": _has_hold_access(pos_profile, "manage"),
		"default_hours": default_hours,
		"max_hours": max_hours,
		"print_slip": cint(profile.get("posa_hold_print_slip")),
		"stores": _hold_stores(profile) if enabled else [],
		"live_count": live_count,
	}


# ---------------------------------------------------------------------------
# Nhả giữ khi hết hạn
# ---------------------------------------------------------------------------


def release_expired_holds(item_codes=None, warehouses=None):
	"""Huỷ SRE của đơn giữ đã quá hạn (lọc theo mặt hàng / kho nếu có). Trả số đơn đã nhả.

	Gọi ngay trước mọi thao tác đụng tới tồn để hàng quá hạn bán được đúng giờ, không chờ job.
	"""
	if not stock_reservation_enabled():
		return 0

	so = DocType("Sales Order")
	query = (
		frappe.qb.from_(so)
		.select(so.name)
		.distinct()
		.where(
			(so.docstatus == 1)
			& (so.posa_is_hold_order == 1)
			& (so.posa_hold_status == STATUS_HOLDING)
			& (so.posa_hold_until <= now_datetime())
		)
	)
	if item_codes or warehouses:
		soi = DocType("Sales Order Item")
		query = query.join(soi).on(soi.parent == so.name)
		if item_codes:
			query = query.where(soi.item_code.isin(list(item_codes)))
		if warehouses:
			query = query.where(soi.warehouse.isin(list(warehouses)))

	names = [r[0] for r in query.run()]
	for name in names:
		_end_hold(name, STATUS_EXPIRED, _("Hold expired, stock released automatically"), only_if_expired=True)
	return len(names)


def _end_hold(name, status, comment, reason=None, only_if_expired=False):
	"""Kết thúc một đơn giữ: huỷ SRE còn lại, đặt trạng thái, Close SO, ghi Comment."""
	# Khoá dòng SO: hai tiến trình cùng nhả / cùng thao tác thì người sau thấy trạng thái mới
	current = frappe.db.sql(
		"select posa_hold_status, posa_hold_until from `tabSales Order` where name=%s for update",
		name,
		as_dict=True,
	)
	if not current or current[0].posa_hold_status != STATUS_HOLDING:
		return False
	if only_if_expired and get_datetime(current[0].posa_hold_until) > now_datetime():
		return False

	doc = frappe.get_doc("Sales Order", name)
	doc.flags.ignore_permissions = True
	with _as_administrator():
		doc.cancel_stock_reservation_entries(notify=False)
	values = {"posa_hold_status": status}
	if reason is not None:
		values["posa_hold_cancel_reason"] = reason
	doc.db_set(values, notify=True)
	if doc.status not in ("Closed", "Completed"):
		doc.reload()
		doc.update_status("Closed")
	doc.add_comment("Comment", comment)
	_publish_stock_update(doc)
	return True


def _publish_stock_update(doc):
	"""Báo các quầy cập nhật tồn (kèm phần đang giữ) của mặt hàng trong đơn giữ."""
	try:
		from pos_next.api.items import get_stock_quantities

		by_warehouse = {}
		for item in doc.items:
			if item.item_code and item.warehouse:
				by_warehouse.setdefault(item.warehouse, set()).add(item.item_code)
		updates = []
		for warehouse, codes in by_warehouse.items():
			for row in get_stock_quantities(list(codes), warehouse) or []:
				row["warehouse"] = row.get("warehouse") or warehouse
				updates.append(row)
		if updates:
			frappe.publish_realtime(
				event="pos_stock_update",
				message={
					"invoice_name": doc.name,
					"warehouses": list(by_warehouse),
					"stock_updates": updates,
					"timestamp": frappe.utils.now(),
					"event_type": "hold",
				},
				user=None,
				after_commit=True,
			)
	except Exception:
		frappe.log_error(frappe.get_traceback(), "Hold order stock update event")


def release_expired_before_stock_submit(doc, method=None):
	"""doc_events before_submit của chứng từ xuất kho: nhả đơn giữ quá hạn đúng mặt hàng/kho."""
	if not stock_reservation_enabled():
		return
	items = doc.get("items") or []
	item_codes = {d.item_code for d in items if d.get("item_code")}
	warehouses = {w for d in items for w in (d.get("warehouse"), d.get("s_warehouse")) if w}
	if doc.get("set_warehouse"):
		warehouses.add(doc.set_warehouse)
	if item_codes:
		release_expired_holds(item_codes, warehouses or None)


def expire_hold_orders():
	"""Scheduler mỗi phút: nhả mọi đơn giữ quá hạn mà chưa ai đụng tới."""
	release_expired_holds()


# ---------------------------------------------------------------------------
# Tồn khả dụng
# ---------------------------------------------------------------------------


def _parse(value, default=None):
	if value is None or value == "":
		return default
	if isinstance(value, str):
		return json.loads(value)
	return value


def _holds_for_items(item_codes, warehouse):
	"""Đơn giữ đang giữ theo mặt hàng tại kho: {item_code: [{name, customer_name, hold_until}]}."""
	if not item_codes:
		return {}
	so = DocType("Sales Order")
	soi = DocType("Sales Order Item")
	rows = (
		frappe.qb.from_(soi)
		.join(so)
		.on(soi.parent == so.name)
		.select(soi.item_code, so.name, so.customer_name, so.posa_hold_until)
		.distinct()
		.where(
			(so.docstatus == 1)
			& (so.posa_is_hold_order == 1)
			& (so.posa_hold_status == STATUS_HOLDING)
			& (soi.warehouse == warehouse)
			& (soi.item_code.isin(list(item_codes)))
		)
		.run(as_dict=True)
	)
	out = {}
	for r in rows:
		out.setdefault(r.item_code, []).append(
			{"name": r.name, "customer_name": r.customer_name, "hold_until": r.posa_hold_until}
		)
	return out


def _availability(item_codes, warehouse, for_update=False):
	"""Tồn thực, phần đang giữ (SRE), khả dụng theo kho. for_update khoá dòng Bin."""
	item_codes = list(dict.fromkeys(item_codes))
	if not item_codes:
		return {}
	lock = " for update" if for_update else ""
	bins = frappe.db.sql(
		f"""select item_code, actual_qty, reserved_stock from `tabBin`
		where warehouse=%(warehouse)s and item_code in %(items)s{lock}""",
		{"warehouse": warehouse, "items": tuple(item_codes)},
		as_dict=True,
	)
	by_code = {b.item_code: b for b in bins}
	meta = {
		r.name: r
		for r in frappe.get_all(
			"Item",
			filters={"name": ["in", item_codes]},
			fields=["name", "item_name", "stock_uom", "is_stock_item", "allow_negative_stock", "has_batch_no", "has_serial_no"],
		)
	}
	out = {}
	for code in item_codes:
		b = by_code.get(code) or frappe._dict(actual_qty=0, reserved_stock=0)
		m = meta.get(code) or frappe._dict(item_name=code, stock_uom="", is_stock_item=0, allow_negative_stock=0)
		actual = flt(b.actual_qty)
		reserved = flt(b.reserved_stock)
		available = flt(actual - reserved)
		unusable = 0.0
		if (m.get("has_batch_no") or m.get("has_serial_no")) and actual > 0 and auto_reserve_batches():
			# Giữ theo lô / serial (cấu hình đang bật): ERPNext chỉ giữ được lô còn dùng (chưa hết hạn, chưa bị giữ).
			# Tắt cấu hình thì giữ theo số lượng, tính như hàng thường.
			usable = _usable_batch_qty(code, warehouse, actual, m)
			if usable + QTY_TOLERANCE < available:
				unusable = flt(available - usable)
				available = usable
		out[code] = {
			"item_code": code,
			"item_name": m.item_name,
			"stock_uom": m.stock_uom,
			"is_stock_item": cint(m.is_stock_item),
			"negative_allowed": cint(m.allow_negative_stock),
			"actual_qty": actual,
			"reserved_qty": reserved,
			"available_qty": available,
			"unusable_qty": unusable,
		}
	return out


def _usable_batch_qty(item_code, warehouse, actual_qty, meta):
	"""SL còn giữ được theo lô / serial — cùng cách ERPNext tự chọn khi tạo SRE (bỏ lô hết hạn, lô đã giữ)."""
	kwargs = frappe._dict(
		item_code=item_code,
		warehouse=warehouse,
		qty=actual_qty,
		based_on=frappe.db.get_single_value("Stock Settings", "pick_serial_and_batch_based_on") or "FIFO",
	)
	try:
		if meta.get("has_serial_no"):
			from erpnext.stock.doctype.serial_no.serial_no import get_serial_nos_for_outward

			return flt(len(get_serial_nos_for_outward(kwargs) or []))
		from erpnext.stock.doctype.batch.batch import get_available_batches

		return flt(sum(flt(q) for q in (get_available_batches(kwargs) or {}).values()))
	except Exception:
		frappe.log_error(frappe.get_traceback(), "Hold order batch availability")
		return 0.0


def get_reserved_stock_map(item_codes, warehouses):
	"""Phần đang giữ theo mặt hàng (cộng các kho) — POS trừ khi hiển thị tồn."""
	if not item_codes or not warehouses or not stock_reservation_enabled():
		return {}
	release_expired_holds(item_codes, warehouses)
	Bin = DocType("Bin")
	rows = (
		frappe.qb.from_(Bin)
		.select(Bin.item_code, Sum(IfNull(Bin.reserved_stock, 0)).as_("reserved_stock"))
		.where(Bin.item_code.isin(list(item_codes)) & Bin.warehouse.isin(list(warehouses)))
		.groupby(Bin.item_code)
		.run(as_dict=True)
	)
	return {r.item_code: flt(r.reserved_stock) for r in rows}


@frappe.whitelist()
def get_held_stock(pos_profile):
	"""Phần đang giữ (SRE) theo mặt hàng tại kho của quầy — POS trừ khi hiển thị tồn."""
	profile = _get_profile(pos_profile)
	if not stock_reservation_enabled() or not profile.get("warehouse"):
		return []
	warehouses = [profile.warehouse]
	if frappe.db.get_value("Warehouse", profile.warehouse, "is_group"):
		warehouses = frappe.db.get_descendants("Warehouse", profile.warehouse) or warehouses
	release_expired_holds(None, warehouses)
	Bin = DocType("Bin")
	return (
		frappe.qb.from_(Bin)
		.select(Bin.item_code, Sum(Bin.reserved_stock).as_("reserved_stock"))
		.where(Bin.warehouse.isin(warehouses) & (Bin.reserved_stock > 0))
		.groupby(Bin.item_code)
		.run(as_dict=True)
	)


def _normalize_items(items):
	"""[{item_code, qty}] (qty theo đơn vị tồn kho) → gộp theo mặt hàng, bỏ dòng ≤ 0."""
	merged = {}
	for row in _parse(items, []) or []:
		code = row.get("item_code")
		qty = flt(row.get("qty"))
		if not code or qty <= 0:
			continue
		merged[code] = flt(merged.get(code)) + qty
	return merged


@frappe.whitelist()
def check_hold_availability(pos_profile, items, store_pos_profile=None):
	profile = _check_access(pos_profile, "create")
	store = _resolve_store(profile, store_pos_profile)
	wanted = _normalize_items(items)
	release_expired_holds(wanted.keys(), [store["warehouse"]])
	avail = _availability(wanted.keys(), store["warehouse"])
	holds = _holds_for_items(wanted.keys(), store["warehouse"])
	lines = []
	for code, qty in wanted.items():
		a = dict(avail[code])
		a["qty"] = qty
		a["held_by"] = holds.get(code, [])
		a["short"] = qty > a["available_qty"] + QTY_TOLERANCE
		lines.append(a)
	return {"warehouse": store["warehouse"], "lines": lines}


# ---------------------------------------------------------------------------
# Tạo đơn giữ
# ---------------------------------------------------------------------------


def _existing_by_request(request_id):
	if not request_id:
		return None
	return frappe.db.get_value("Sales Order", {"posa_hold_request_id": request_id, "docstatus": 1}, "name")


@frappe.whitelist()
def create_hold_order(pos_profile, customer, items, store_pos_profile=None, hold_hours=None, note=None, request_id=None):
	profile = _check_access(pos_profile, "create")
	_require_site_enabled()

	existing = _existing_by_request(request_id)
	if existing:
		return _result(existing, duplicate=True)

	if not customer or not frappe.db.exists("Customer", customer):
		frappe.throw(_("Select a customer for the hold order"))
	if customer == profile.get("customer"):
		frappe.throw(_("Hold orders need a named customer, not the default walk-in customer of the POS"))

	store = _resolve_store(profile, store_pos_profile)
	store_profile = _get_profile(store["pos_profile"])
	default_hours, max_hours = _hold_hours(store_profile)
	hours = cint(hold_hours) or default_hours
	if hours <= 0 or hours > max_hours:
		frappe.throw(_("Hold period must be between 1 and {0} hours").format(max_hours))

	wanted = _normalize_items(items)
	if not wanted:
		frappe.throw(_("No items to hold"))

	warehouse = store["warehouse"]
	release_expired_holds(wanted.keys(), [warehouse])
	# Khoá Bin: hai quầy cùng giữ món cuối thì người sau chờ và thấy tồn mới
	avail = _availability(wanted.keys(), warehouse, for_update=True)
	short = []
	for code, qty in wanted.items():
		a = avail[code]
		if not a["is_stock_item"]:
			frappe.throw(_("{0} is not a stock item and cannot be held").format(a["item_name"]))
		if a["negative_allowed"]:
			frappe.throw(_("{0} allows negative stock, so it cannot be held").format(a["item_name"]))
		if qty > a["available_qty"] + QTY_TOLERANCE:
			line = _("{0}: need {1}, available {2}").format(a["item_name"], qty, a["available_qty"])
			if a["unusable_qty"]:
				line += " " + _("({0} are in expired or unusable batches)").format(a["unusable_qty"])
			short.append(line)
	if short:
		frappe.throw(
			_("Not enough stock to hold:") + "<br>" + "<br>".join(short),
			HoldStockChangedError,
			title=_("Stock changed"),
		)

	now = now_datetime()
	hold_until = add_to_date(now, hours=hours)
	so = frappe.get_doc(
		{
			"doctype": "Sales Order",
			"customer": customer,
			"company": store_profile.company,
			"transaction_date": getdate(now),
			"delivery_date": getdate(hold_until),
			"set_warehouse": warehouse,
			"selling_price_list": store_profile.get("selling_price_list") or profile.get("selling_price_list"),
			"currency": store_profile.get("currency") or profile.get("currency"),
			"pos_profile": store["pos_profile"],
			"reserve_stock": 1,
			"posa_is_hold_order": 1,
			"posa_hold_status": STATUS_HOLDING,
			"posa_hold_until": hold_until,
			"posa_hold_pos_profile": store["pos_profile"],
			"posa_hold_created_pos_profile": profile.name,
			"posa_hold_note": (note or "").strip(),
			"posa_hold_request_id": request_id or None,
			"items": [
				{
					"item_code": code,
					"qty": qty,
					"uom": avail[code]["stock_uom"],
					"conversion_factor": 1,
					"warehouse": warehouse,
					"delivery_date": getdate(hold_until),
					"reserve_stock": 1,
				}
				for code, qty in wanted.items()
			],
		}
	)
	so.flags.ignore_permissions = True
	# Đơn giữ tạo từ POS bỏ qua Workflow của Sales Order (đã chốt)
	so.validate_workflow = lambda: None
	so.insert()
	try:
		with _as_administrator():
			so.submit()
		_assert_fully_reserved(so)
	except Exception:
		frappe.db.rollback()
		_discard_failed_hold(so.name)
		raise
	so.add_comment(
		"Comment",
		_("Hold created at {0} for pickup at {1}, held {2} hours").format(profile.name, store["pos_profile"], hours),
	)
	_publish_stock_update(so)
	return _result(so.name)


def _assert_fully_reserved(so):
	"""ERPNext có thể giữ một phần (allow_partial_reservation) → không đủ thì huỷ cả lần giữ."""
	from erpnext.stock.doctype.stock_reservation_entry.stock_reservation_entry import (
		get_sre_reserved_qty_details_for_voucher,
	)

	reserved = get_sre_reserved_qty_details_for_voucher("Sales Order", so.name)
	for item in so.items:
		if flt(reserved.get(item.name)) + QTY_TOLERANCE < flt(item.stock_qty):
			frappe.throw(
				_("Could not hold the full quantity of {0}. Check the stock and try again.").format(item.item_name),
				HoldStockChangedError,
			)


def _discard_failed_hold(name):
	"""Lần giữ lỗi mà SO vẫn còn (app khác commit giữa lúc submit) → nhả hàng, đóng đơn."""
	if frappe.db.get_value("Sales Order", name, "docstatus") != 1:
		return
	_end_hold(name, STATUS_CANCELLED, _("Hold failed, stock released"), reason=_("Hold failed"))
	frappe.db.commit()


def _result(name, duplicate=False):
	doc = frappe.get_doc("Sales Order", name)
	return {
		"name": doc.name,
		"customer": doc.customer,
		"customer_name": doc.customer_name,
		"hold_until": doc.posa_hold_until,
		"store": doc.posa_hold_pos_profile,
		"store_label": _store_label(doc.posa_hold_pos_profile),
		"line_count": len(doc.items),
		"total_qty": flt(sum(flt(i.stock_qty) for i in doc.items)),
		"note": doc.posa_hold_note,
		"duplicate": duplicate,
	}


# ---------------------------------------------------------------------------
# Danh sách / chi tiết
# ---------------------------------------------------------------------------


def _visible_condition(so, profile):
	"""Đơn giữ thuộc cửa hàng nhận; chỉ POS của cửa hàng đó thấy và thao tác (tài liệu 3.4)."""
	return so.posa_hold_pos_profile == profile.name


@frappe.whitelist()
def get_hold_orders(pos_profile, status=None, search=None, start=0, page_length=30):
	profile = _check_access(pos_profile, "view")
	release_expired_holds()
	so = DocType("Sales Order")
	base = (
		frappe.qb.from_(so)
		.where((so.docstatus == 1) & (so.posa_is_hold_order == 1) & _visible_condition(so, profile))
	)
	if search:
		like = f"%{search.strip()}%"
		customers = frappe.get_all(
			"Customer",
			or_filters={"mobile_no": ["like", like], "customer_name": ["like", like]},
			pluck="name",
			limit=200,
		)
		cond = (so.name.like(like)) | (so.customer_name.like(like))
		if customers:
			cond = cond | so.customer.isin(customers)
		base = base.where(cond)

	counts_rows = base.select(so.posa_hold_status, Count(so.name).as_("n")).groupby(so.posa_hold_status).run(as_dict=True)
	counts = {s: 0 for s in ALL_STATUSES}
	for r in counts_rows:
		counts[r.posa_hold_status] = r.n
	counts["all"] = sum(counts.values())

	query = base.select(
		so.name,
		so.customer,
		so.customer_name,
		so.grand_total,
		so.creation,
		so.posa_hold_status.as_("status"),
		so.posa_hold_until.as_("hold_until"),
		so.posa_hold_pos_profile.as_("store"),
		so.posa_hold_created_pos_profile.as_("created_store"),
		so.posa_hold_note.as_("note"),
		so.posa_hold_cancel_reason.as_("cancel_reason"),
	)
	if status in ALL_STATUSES:
		query = query.where(so.posa_hold_status == status)
	rows = query.orderby(so.creation, order=frappe.qb.desc).limit(cint(page_length) or 30).offset(cint(start)).run(as_dict=True)
	_decorate(rows, profile)

	live = (
		frappe.qb.from_(so)
		.select(Count(so.name).as_("n"), Sum(so.grand_total).as_("v"))
		.where(
			(so.docstatus == 1)
			& (so.posa_is_hold_order == 1)
			& (so.posa_hold_status == STATUS_HOLDING)
			& (so.posa_hold_pos_profile == profile.name)
		)
		.run(as_dict=True)[0]
	)
	return {"rows": rows, "counts": counts, "totals": {"live_count": cint(live.n), "live_value": flt(live.v)}}


def _decorate(rows, profile):
	if not rows:
		return
	names = [r.name for r in rows]
	items = frappe.get_all(
		"Sales Order Item",
		filters={"parent": ["in", names]},
		fields=["parent", "item_name", "stock_qty", "stock_uom"],
		order_by="idx",
	)
	by_parent = {}
	for i in items:
		by_parent.setdefault(i.parent, []).append(i)
	mobiles = dict(
		frappe.get_all("Customer", filters={"name": ["in", list({r.customer for r in rows})]}, fields=["name", "mobile_no"], as_list=True)
	)
	for r in rows:
		lines = by_parent.get(r.name, [])
		if len(lines) == 1:
			r.items_summary = f"{lines[0].item_name} ×{flt(lines[0].stock_qty):g}"
		else:
			r.items_summary = _("{0} items · {1} units").format(len(lines), f"{flt(sum(flt(l.stock_qty) for l in lines)):g}")
		r.mobile_no = mobiles.get(r.customer)
		r.store_label = _store_label(r.store)
		r.read_only = False


@frappe.whitelist()
def get_hold_order(pos_profile, name):
	profile = _check_access(pos_profile, "view")
	doc = _get_visible_hold(profile, name)
	if doc.posa_hold_status == STATUS_HOLDING:
		release_expired_holds([i.item_code for i in doc.items], [doc.set_warehouse])
		doc.reload()
	store_profile = _get_profile(doc.posa_hold_pos_profile)
	max_hours = _hold_hours(store_profile)[1]
	lines = [
		{
			"item_code": i.item_code,
			"item_name": i.item_name,
			"stock_uom": i.stock_uom,
			"qty": flt(i.stock_qty),
			"delivered_qty": flt(i.delivered_qty) * flt(i.conversion_factor or 1),
			"held_qty": flt(i.stock_reserved_qty) if doc.posa_hold_status == STATUS_HOLDING else 0,
		}
		for i in doc.items
	]
	history = [
		{
			"at": c.creation,
			"by": frappe.db.get_value("User", c.owner, "full_name") or c.owner,
			"text": frappe.utils.strip_html(c.content or ""),
		}
		for c in frappe.get_all(
			"Comment",
			filters={"reference_doctype": "Sales Order", "reference_name": doc.name, "comment_type": "Comment"},
			fields=["creation", "owner", "content"],
			order_by="creation",
		)
	]
	return {
		"name": doc.name,
		"customer": doc.customer,
		"customer_name": doc.customer_name,
		"mobile_no": frappe.db.get_value("Customer", doc.customer, "mobile_no"),
		"status": doc.posa_hold_status,
		"hold_until": doc.posa_hold_until,
		"max_until": add_to_date(get_datetime(doc.creation), hours=max_hours),
		"store": doc.posa_hold_pos_profile,
		"store_label": _store_label(doc.posa_hold_pos_profile),
		"created_store_label": _store_label(doc.posa_hold_created_pos_profile),
		"note": doc.posa_hold_note,
		"cancel_reason": doc.posa_hold_cancel_reason,
		"read_only": False,
		"created_by": frappe.db.get_value("User", doc.owner, "full_name") or doc.owner,
		"created_at": doc.creation,
		"lines": lines,
		"history": history,
	}


def _get_visible_hold(profile, name):
	if not frappe.db.exists("Sales Order", {"name": name, "posa_is_hold_order": 1, "docstatus": 1}):
		frappe.throw(_("Hold order {0} not found").format(name))
	doc = frappe.get_doc("Sales Order", name)
	if doc.posa_hold_pos_profile != profile.name:
		frappe.throw(_("Hold order {0} does not belong to this POS").format(name), frappe.PermissionError)
	return doc


def _get_own_live_hold(profile, name):
	"""Đơn của chính quầy nhận, còn đang giữ (sau khi đã nhả đơn quá hạn)."""
	doc = _get_visible_hold(profile, name)
	release_expired_holds([i.item_code for i in doc.items], [doc.set_warehouse])
	doc.reload()
	if doc.posa_hold_status != STATUS_HOLDING:
		frappe.throw(_("Hold order {0} is no longer holding stock. Refresh the list.").format(name), HoldStockChangedError)
	return doc


# ---------------------------------------------------------------------------
# Gia hạn / huỷ / khách đến lấy
# ---------------------------------------------------------------------------


def _user_label():
	return frappe.db.get_value("User", frappe.session.user, "full_name") or frappe.session.user


@frappe.whitelist()
def extend_hold_order(pos_profile, name, add_hours, reason=None):
	profile = _check_access(pos_profile, "manage")
	_require_site_enabled()
	doc = _get_own_live_hold(profile, name)
	max_hours = _hold_hours(profile)[1]
	max_until = add_to_date(get_datetime(doc.creation), hours=max_hours)
	hours = cint(add_hours)
	if hours <= 0:
		frappe.throw(_("Choose how long to extend"))
	new_until = min(add_to_date(get_datetime(doc.posa_hold_until), hours=hours), max_until)
	if new_until <= get_datetime(doc.posa_hold_until):
		frappe.throw(_("This hold is already at the maximum of {0} hours").format(max_hours))
	doc.db_set({"posa_hold_until": new_until, "delivery_date": getdate(new_until)}, notify=True)
	text = _("Extended at {0} until {1}").format(profile.name, frappe.utils.format_datetime(new_until, "HH:mm dd/MM/yyyy"))
	if reason:
		text += f": {reason}"
	doc.add_comment("Comment", text)
	return {"name": doc.name, "hold_until": new_until}


@frappe.whitelist()
def cancel_hold_order(pos_profile, name, reason):
	profile = _check_access(pos_profile, "manage")
	if not (reason or "").strip():
		frappe.throw(_("Enter the cancel reason"))
	doc = _get_own_live_hold(profile, name)
	_end_hold(doc.name, STATUS_CANCELLED, _("Hold cancelled at {0}: {1}").format(profile.name, reason.strip()), reason=reason.strip())
	return {"name": doc.name, "status": STATUS_CANCELLED}


@frappe.whitelist()
def pickup_hold_order(pos_profile, name):
	"""Khách đến quầy lấy: nhả giữ, kết thúc đơn (Đã lấy), trả các dòng để POS nạp vào giỏ."""
	profile = _check_access(pos_profile, "create")
	doc = _get_own_live_hold(profile, name)
	lines = [
		{
			"item_code": i.item_code,
			"item_name": i.item_name,
			"stock_uom": i.stock_uom,
			"qty": flt(i.stock_qty) - flt(i.delivered_qty) * flt(i.conversion_factor or 1),
		}
		for i in doc.items
	]
	lines = [l for l in lines if l["qty"] > QTY_TOLERANCE]
	_end_hold(doc.name, STATUS_PICKED_UP, _("Customer picked up at {0}; items moved to the cart").format(profile.name))
	customer = frappe.db.get_value("Customer", doc.customer, ["name", "customer_name", "mobile_no"], as_dict=True)
	return {"name": doc.name, "customer": customer, "lines": lines}


def on_delivery_note_submit(doc, method=None):
	"""Giao ở desk từ đơn giữ: lấy một lần là hết — phần chưa giao trả về kệ ngay."""
	orders = {d.against_sales_order for d in (doc.get("items") or []) if d.get("against_sales_order")}
	for so_name in orders:
		if frappe.db.get_value("Sales Order", so_name, ["posa_is_hold_order"]) and frappe.db.get_value(
			"Sales Order", so_name, "posa_hold_status"
		) == STATUS_HOLDING:
			_end_hold(so_name, STATUS_PICKED_UP, _("Delivered by {0}; any undelivered quantity was released").format(doc.name))


# ---------------------------------------------------------------------------
# Cảnh báo cấu hình
# ---------------------------------------------------------------------------

AUTO_SUBMIT_FIELDS = ("auto_submit_si_by_so", "auto_submit_dn_by_so")


def on_sales_order_change(doc, method=None):
	"""Đóng (Close) SO đơn giữ ở desk = khách không lấy: nhả hàng, đơn giữ về Đã huỷ.

	⚠ ERPNext không huỷ SRE khi Close. Mở lại SO sau đó cũng không giữ hàng lại.
	"""
	if not doc.get("posa_is_hold_order") or doc.get("posa_hold_status") != STATUS_HOLDING:
		return
	if doc.docstatus == 1 and doc.status == "Closed":
		_end_hold(
			doc.name,
			STATUS_CANCELLED,
			_("Sales Order closed at the desk, stock released"),
			reason=_("Sales Order closed at the desk"),
		)


def on_sales_order_cancel(doc, method=None):
	"""Huỷ SO đơn giữ ở desk: ERPNext đã huỷ SRE, chỉ cần đưa đơn giữ về Đã huỷ."""
	if not doc.get("posa_is_hold_order") or doc.get("posa_hold_status") != STATUS_HOLDING:
		return
	doc.db_set(
		{"posa_hold_status": STATUS_CANCELLED, "posa_hold_cancel_reason": _("Sales Order cancelled at the desk")},
		notify=True,
	)
	doc.add_comment("Comment", _("Sales Order cancelled at the desk, hold cancelled"))
	_publish_stock_update(doc)


def _auto_submit_enabled():
	"""Site cài mbwnext_localization và bật tự sinh hoá đơn / phiếu giao khi submit Sales Order."""
	if not frappe.db.exists("DocType", "MBWNext System Setting"):
		return False
	return any(cint(frappe.db.get_single_value("MBWNext System Setting", f)) for f in AUTO_SUBMIT_FIELDS)


def _auto_submit_warning():
	return _(
		"MBWNext System Setting creates an invoice / delivery note automatically when a Sales Order is submitted. "
		"Hold orders are Sales Orders, so a new hold would be invoiced and its stock issued right away."
	)


def validate_pos_profile_hold(doc, method=None):
	"""POS Profile validate: cảnh báo khi bật giữ hàng mà site chưa sẵn sàng (chỉ cảnh báo, không chặn)."""
	if not cint(doc.get("posa_enable_hold_order")):
		return
	if not stock_reservation_enabled():
		frappe.msgprint(
			_("Stock Reservation is not enabled in Stock Settings, so the Hold Stock button stays hidden at the POS."),
			title=_("Hold orders"),
			indicator="orange",
		)
	if _auto_submit_enabled():
		frappe.msgprint(_auto_submit_warning(), title=_("Hold orders"), indicator="orange")
	if not doc.get("posa_hold_create_roles"):
		frappe.msgprint(
			_("No role is allowed to create hold orders at this POS yet."), title=_("Hold orders"), indicator="orange"
		)


def validate_system_setting_auto_submit(doc, method=None):
	"""MBWNext System Setting validate: cảnh báo khi bật tự sinh hoá đơn mà có quầy đang giữ hàng."""
	if not any(cint(doc.get(f)) for f in AUTO_SUBMIT_FIELDS):
		return
	profiles = frappe.get_all("POS Profile", filters={"posa_enable_hold_order": 1, "disabled": 0}, pluck="name")
	if profiles:
		frappe.msgprint(
			_auto_submit_warning() + "<br>" + _("POS Profiles with hold orders enabled: {0}").format(", ".join(profiles)),
			title=_("Hold orders"),
			indicator="orange",
		)


# ---------------------------------------------------------------------------
# Phiếu giữ hàng
# ---------------------------------------------------------------------------


@frappe.whitelist()
def print_hold_slip(pos_profile, name):
	"""Phiếu giữ hàng khổ 80mm (không phải hoá đơn, chưa thu tiền)."""
	profile = _check_access(pos_profile, "view")
	doc = _get_visible_hold(profile, name)
	store_profile = _get_profile(doc.posa_hold_pos_profile)
	context = {
		"doc": doc,
		"profile": store_profile,
		"company": doc.company,
		"customer_mobile": frappe.db.get_value("Customer", doc.customer, "mobile_no"),
		"created_by": frappe.db.get_value("User", doc.owner, "full_name") or doc.owner,
		"fmt": lambda v: frappe.format_value(v, {"fieldtype": "Currency"}),
	}
	html = frappe.render_template("pos_next/templates/hold_slip.html", context)
	from werkzeug.wrappers import Response

	return Response(html, content_type="text/html; charset=utf-8")
