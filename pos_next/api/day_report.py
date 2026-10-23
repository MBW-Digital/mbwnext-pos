# Copyright (c) 2026, BrainWise and contributors
# For license information, please see license.txt

"""
Báo cáo kết ngày theo ca tại quầy POS (chỉ đọc).

Mỗi dòng là một ca (POS Opening Shift) của quầy, tính về NGÀY MỞ CA. Số bán / trả tính lại từ
Sales Invoice của ca vì phiếu đóng ca chỉ lưu tổng gộp bán − trả.

- Tổng bán = Doanh thu + VAT − Phí trả hàng.
- Thực thu = tiền thật vào két theo hình thức (expected − opening), trừ hình thức ví.
  Ca đã đóng lấy đúng số trên phiếu đóng ca; ca đang mở tính tạm như lúc đóng ca.
- Thu nợ = phiếu thu (Payment Entry Receive) gắn ca; đã nằm trong Thực thu.

Quyền theo quầy (POS Profile) như thu nợ: user phải có trong danh sách user của quầy và có role
trong bảng role của báo cáo — kể cả System Manager. Truy vấn lọc cứng theo quầy sau khi kiểm quyền.
"""

import json

import frappe
from frappe import _
from frappe.query_builder import Case, DocType
from frappe.query_builder.functions import Count, Sum
from frappe.utils import add_days, cint, flt, fmt_money, getdate, now_datetime, nowdate

from pos_next.pos_next.doctype.pos_closing_shift.pos_closing_shift import (
	_get_cash_mode_of_payment,
	get_base_value,
	get_payments_entries,
)



def _roles_of(profile, fieldname):
	return {row.role for row in (profile.get(fieldname) or []) if row.role}


def _has_access(pos_profile, action, user=None):
	"""action: view / print / all_staff. Không throw."""
	user = user or frappe.session.user
	if not pos_profile or not frappe.db.exists("POS Profile", pos_profile):
		return False
	profile = frappe.get_cached_doc("POS Profile", pos_profile)
	if profile.get("disabled") or not cint(profile.get("posa_enable_day_report")):
		return False
	if not any(row.user == user for row in (profile.get("applicable_for_users") or [])):
		return False

	print_roles = _roles_of(profile, "posa_day_report_print_roles")
	all_staff_roles = _roles_of(profile, "posa_day_report_all_staff_roles")
	if action == "view":
		allowed = _roles_of(profile, "posa_day_report_view_roles") | print_roles | all_staff_roles
	elif action == "print":
		allowed = print_roles
	elif action == "all_staff":
		allowed = all_staff_roles
	else:
		return False
	return bool(allowed & set(frappe.get_roles(user)))


def _check_access(pos_profile, action):
	if not _has_access(pos_profile, action):
		message = (
			_("You are not allowed to print the day report at POS Profile {0}")
			if action == "print"
			else _("You are not allowed to view the day report at POS Profile {0}")
		)
		frappe.throw(message.format(pos_profile), frappe.PermissionError)
	return frappe.get_cached_doc("POS Profile", pos_profile)


@frappe.whitelist()
def get_day_report_access(pos_profile):
	"""Cờ quyền cho giao diện (backend vẫn kiểm lại)."""
	if not pos_profile or not frappe.db.exists("POS Profile", pos_profile):
		return {"enabled": 0}
	profile = frappe.get_cached_doc("POS Profile", pos_profile)
	return {
		"enabled": cint(profile.get("posa_enable_day_report")),
		"can_view": _has_access(pos_profile, "view"),
		"can_print": _has_access(pos_profile, "print"),
		"can_see_all": _has_access(pos_profile, "all_staff"),
	}


@frappe.whitelist()
def get_day_report(pos_profile, report_date=None, staff=None, closed_by=None):
	profile = _check_access(pos_profile, "view")
	return _build_report(profile, report_date, staff, closed_by)


def _build_report(profile, report_date=None, staff=None, closed_by=None):
	report_date = str(getdate(report_date or nowdate()))
	can_see_all = _has_access(profile.name, "all_staff")
	if not can_see_all:
		# Role thường chỉ thấy ca của chính mình
		staff = frappe.session.user

	shifts = _shifts_of_day(profile.name, report_date)
	closings = _closings_of(shifts)
	for s in shifts:
		closing = closings.get(s.name)
		s.closing_shift = closing.name if closing else None
		s.closed_by = closing.owner if closing else None
		s.period_end_date = closing.period_end_date if closing else None
		s.is_open = not closing

	# Lựa chọn của bộ lọc lấy trên mọi ca trong ngày, trước khi lọc
	staff_options = sorted({s.user for s in shifts if s.user and (can_see_all or s.user == staff)})
	closer_options = sorted({s.closed_by for s in shifts if s.closed_by and (can_see_all or s.user == staff)})

	if staff:
		shifts = [s for s in shifts if s.user == staff]
	if closed_by:
		shifts = [s for s in shifts if s.closed_by == closed_by]

	rows = _compute_rows(profile, shifts, closings)
	names = _full_names({*staff_options, *closer_options, *(r["user"] for r in rows), *(r["closed_by"] for r in rows if r["closed_by"])})
	for r in rows:
		r["user_name"] = names.get(r["user"], r["user"])
		r["closed_by_name"] = names.get(r["closed_by"], r["closed_by"]) if r["closed_by"] else None

	totals = {
		key: flt(sum(flt(r[key]) for r in rows), 2)
		for key in ("qty", "sales_count", "net", "vat", "returns", "returns_count", "total_sales", "debt", "actual", "wallet")
	}
	return {
		"pos_profile": profile.name,
		"company": profile.company,
		"store_name": profile.get("custom_store_name_2") or profile.name,
		"report_date": report_date,
		"generated_at": str(now_datetime())[:19],
		"can_see_all": can_see_all,
		"staff": staff or None,
		"closed_by": closed_by or None,
		"staff_options": [{"value": u, "label": names.get(u, u)} for u in staff_options],
		"closer_options": [{"value": u, "label": names.get(u, u)} for u in closer_options],
		"rows": rows,
		"totals": totals,
	}


def _shifts_of_day(pos_profile, report_date):
	"""Ca mở trong ngày (ca qua nửa đêm vẫn thuộc ngày mở ca)."""
	ops = DocType("POS Opening Shift")
	return (
		frappe.qb.from_(ops)
		.select(ops.name, ops.user, ops.period_start_date, ops.company)
		.where(ops.pos_profile == pos_profile)
		.where(ops.docstatus == 1)
		.where(ops.period_start_date >= f"{report_date} 00:00:00")
		.where(ops.period_start_date < f"{add_days(report_date, 1)} 00:00:00")
		.orderby(ops.period_start_date)
		.run(as_dict=True)
	)


def _closings_of(shifts):
	if not shifts:
		return {}
	rows = frappe.get_all(
		"POS Closing Shift",
		filters={"pos_opening_shift": ["in", [s.name for s in shifts]], "docstatus": 1},
		fields=["name", "pos_opening_shift", "owner", "period_end_date"],
	)
	return {r.pos_opening_shift: r for r in rows}


def _compute_rows(profile, shifts, closings):
	if not shifts:
		return []
	names = [s.name for s in shifts]
	sales = _sales_by_shift(names)
	debt = _debt_by_shift(names)
	wallet_modes = set(frappe.get_all("Mode of Payment", filters={"is_wallet_payment": 1}, pluck="name"))

	closed_names = [closings[n].name for n in names if n in closings]
	modes_closed = _modes_of_closed(closed_names)
	open_shifts = [s.name for s in shifts if s.is_open]
	modes_open = _modes_of_open(profile, open_shifts)

	rows = []
	for s in shifts:
		sale = sales.get((s.name, 0), {})
		ret = sales.get((s.name, 1), {})
		modes = modes_closed.get(s.closing_shift, []) if s.closing_shift else modes_open.get(s.name, [])
		mode_rows = [
			{"mode_of_payment": m, "amount": flt(amount, 2), "is_wallet": m in wallet_modes}
			for m, amount in modes
			if abs(flt(amount)) >= 0.005
		]
		net = flt(sale.get("net"), 2)
		vat = flt(sale.get("vat"), 2)
		returns = flt(-flt(ret.get("grand")), 2)
		rows.append(
			{
				"shift": s.name,
				"closing_shift": s.closing_shift,
				"user": s.user,
				"closed_by": s.closed_by,
				"is_open": s.is_open,
				"start": str(s.period_start_date)[:19],
				"end": str(s.period_end_date)[:19] if s.period_end_date else None,
				"qty": flt(sale.get("qty"), 3),
				"sales_count": cint(sale.get("n")),
				"net": net,
				"vat": vat,
				"returns": returns,
				"returns_count": cint(ret.get("n")),
				"total_sales": flt(net + vat - returns, 2),
				"debt": flt(debt.get(s.name), 2),
				"actual": flt(sum(r["amount"] for r in mode_rows if not r["is_wallet"]), 2),
				"wallet": flt(sum(r["amount"] for r in mode_rows if r["is_wallet"]), 2),
				"modes": mode_rows,
			}
		)
	return rows


def _sales_by_shift(shift_names):
	"""{(ca, is_return): {n, qty, net, vat, grand}} — một truy vấn cho cả ngày."""
	si = DocType("Sales Invoice")
	data = (
		frappe.qb.from_(si)
		.select(
			si.posa_pos_opening_shift.as_("shift"),
			si.is_return,
			Count(si.name).as_("n"),
			Sum(si.total_qty).as_("qty"),
			Sum(si.base_net_total).as_("net"),
			Sum(si.base_total_taxes_and_charges).as_("vat"),
			Sum(si.base_grand_total).as_("grand"),
		)
		.where(si.docstatus == 1)
		.where(si.posa_pos_opening_shift.isin(shift_names))
		.groupby(si.posa_pos_opening_shift, si.is_return)
		.run(as_dict=True)
	)
	return {(r.shift, cint(r.is_return)): r for r in data}


def _debt_by_shift(shift_names):
	pe = DocType("Payment Entry")
	data = (
		frappe.qb.from_(pe)
		.select(pe.posa_pos_opening_shift.as_("shift"), Sum(pe.base_paid_amount).as_("amount"))
		.where(pe.docstatus == 1)
		.where(pe.payment_type == "Receive")
		.where(pe.posa_pos_opening_shift.isin(shift_names))
		.groupby(pe.posa_pos_opening_shift)
		.run(as_dict=True)
	)
	return {r.shift: flt(r.amount) for r in data}


def _modes_of_closed(closing_names):
	"""Số đã đối soát trên phiếu đóng ca: {phiếu đóng: [(hình thức, expected − opening)]}."""
	if not closing_names:
		return {}
	rows = frappe.get_all(
		"POS Closing Shift Detail",
		filters={"parent": ["in", closing_names], "parenttype": "POS Closing Shift"},
		fields=["parent", "mode_of_payment", "opening_amount", "expected_amount"],
		order_by="idx",
	)
	result = {}
	for r in rows:
		result.setdefault(r.parent, []).append((r.mode_of_payment, flt(r.expected_amount) - flt(r.opening_amount)))
	return result


def _modes_of_open(profile, shift_names):
	"""Ca đang mở: tính như make_closing_shift_from_opening nhưng không ghi gì
	(hàm đó submit các đơn nháp đã in nên không gọi được từ báo cáo)."""
	if not shift_names:
		return {}
	cash_mode = _get_cash_mode_of_payment(profile.name)
	si = DocType("Sales Invoice")
	sip = DocType("Sales Invoice Payment")
	data = (
		frappe.qb.from_(sip)
		.join(si)
		.on(sip.parent == si.name)
		.select(
			si.posa_pos_opening_shift.as_("shift"),
			sip.mode_of_payment,
			# Như _process_invoice: dòng tiền mặt trừ tiền thối lại
			Sum(sip.base_amount - Case().when(sip.mode_of_payment == cash_mode, si.base_change_amount).else_(0)).as_("amount"),
		)
		.where(si.docstatus == 1)
		.where(sip.parenttype == "Sales Invoice")
		.where(si.posa_pos_opening_shift.isin(shift_names))
		.groupby(si.posa_pos_opening_shift, sip.mode_of_payment)
		.orderby(sip.mode_of_payment)
		.run(as_dict=True)
	)
	result = {name: {} for name in shift_names}
	for r in data:
		result[r.shift][r.mode_of_payment] = flt(result[r.shift].get(r.mode_of_payment)) + flt(r.amount)
	for name in shift_names:
		for py in get_payments_entries(name):
			amount = get_base_value(py, "paid_amount", "base_paid_amount")
			result[name][py.mode_of_payment] = flt(result[name].get(py.mode_of_payment)) + amount
	return {name: list(modes.items()) for name, modes in result.items()}


def _full_names(users):
	users = [u for u in users if u]
	if not users:
		return {}
	rows = frappe.get_all("User", filters={"name": ["in", users]}, fields=["name", "full_name"])
	return {r.name: r.full_name or r.name for r in rows}


@frappe.whitelist()
def print_day_report(pos_profile, report_date=None, staff=None, closed_by=None, **kwargs):
	"""Trang in A4 ngang; mỗi lần in ghi một POS Day Report Print Log.
	kwargs: bỏ qua tham số `size` của bản giao diện cũ còn trong cache."""
	profile = _check_access(pos_profile, "print")
	report = _build_report(profile, report_date, staff or None, closed_by or None)

	frappe.get_doc(
		{
			"doctype": "POS Day Report Print Log",
			"pos_profile": profile.name,
			"company": profile.company,
			"report_date": report["report_date"],
			"printed_by": frappe.session.user,
			"printed_at": now_datetime(),
			"filters": json.dumps({"staff": report["staff"], "closed_by": report["closed_by"]}, ensure_ascii=False),
			"shift_count": len(report["rows"]),
		}
	).insert(ignore_permissions=True)
	# Yêu cầu GET không tự commit
	frappe.db.commit()

	staff_label = next((o["label"] for o in report["staff_options"] if o["value"] == report["staff"]), report["staff"])
	closer_label = next((o["label"] for o in report["closer_options"] if o["value"] == report["closed_by"]), report["closed_by"])
	html = frappe.render_template(
		"pos_next/templates/day_report.html",
		{
			"r": report,
			"staff_label": staff_label,
			"closer_label": closer_label,
			"printed_by": frappe.db.get_value("User", frappe.session.user, "full_name") or frappe.session.user,
			# Không kèm ký hiệu tiền: chân báo cáo đã ghi đơn vị là đồng
			"fmt": lambda v: fmt_money(v, precision=2),
			"fmt_num": lambda v: frappe.format_value(v, {"fieldtype": "Float", "precision": 0}),
		},
	)
	from werkzeug.wrappers import Response

	return Response(html, content_type="text/html; charset=utf-8")
