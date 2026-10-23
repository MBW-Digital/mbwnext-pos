# Copyright (c) 2026, BrainWise and contributors
# For license information, please see license.txt

"""
Thu nợ khách hàng tại quầy POS.

Quyền ở đây là quyền THEO QUẦY (POS Profile): user phải nằm trong danh sách user của
quầy và có role trong bảng role tương ứng của quầy - kể cả System Manager. Vì vậy các
truy vấn đọc dùng frappe.get_all / Query Builder (không lọc User Permission) SAU KHI đã
kiểm quyền quầy, và luôn lọc cứng theo pos_profile + company của quầy.

Phạm vi đơn nợ: chỉ hoá đơn bán (không phải phiếu trả) của chính quầy, cùng company,
còn nợ, và không thấp hơn ngưỡng ẩn nợ lẻ của quầy.
"""

import json
import uuid

import frappe
from frappe import _
from frappe.query_builder import DocType
from frappe.query_builder.functions import Count, IfNull, Max, Min, Sum
from frappe.utils import add_days, cint, date_diff, flt, getdate, nowdate

from pos_next.api.invoices import get_payment_account

# Lệch làm tròn cho phép khi so tổng phân bổ với tổng thanh toán
AMOUNT_TOLERANCE = 0.5
# Lệch làm tròn cho phép khi chặn hoá đơn còn nợ ở quầy không bán chịu
CREDIT_SALE_TOLERANCE = 10

SCOPE_CUSTOMER_GROUP = "Customer Group of this POS Profile"

STATUS_OVERDUE = "Overdue"
STATUS_PARTLY_PAID = "Partly Paid"
STATUS_UNPAID = "Unpaid"
STATUS_PAID = "Paid"
# Lọc màn Công nợ: khách có tiền dư (không phải trạng thái hoá đơn)
STATUS_CREDIT = "Credit"


class DebtChangedError(frappe.ValidationError):
	"""Đơn vừa thay đổi (quầy khác vừa thu / bị huỷ) - client phải tải lại công nợ."""


# ---------------------------------------------------------------------------
# Quyền theo quầy
# ---------------------------------------------------------------------------


def _get_profile(pos_profile):
	if not pos_profile or not frappe.db.exists("POS Profile", pos_profile):
		frappe.throw(_("POS Profile {0} does not exist").format(pos_profile or ""))
	return frappe.get_cached_doc("POS Profile", pos_profile)


def _roles_of(profile, fieldname):
	return {row.role for row in (profile.get(fieldname) or []) if row.role}


def _has_debt_access(pos_profile, action, user=None):
	"""True nếu user được làm `action` (view / collect / refund / cancel) tại quầy. Không throw.

	Không có ngoại lệ cho System Manager / Administrator: quyền phải khai ở quầy.
	"""
	user = user or frappe.session.user
	if not pos_profile or not frappe.db.exists("POS Profile", pos_profile):
		return False

	profile = frappe.get_cached_doc("POS Profile", pos_profile)
	if profile.get("disabled") or not cint(profile.get("posa_enable_debt_collection")):
		return False

	if not any(row.user == user for row in (profile.get("applicable_for_users") or [])):
		return False

	collect_roles = _roles_of(profile, "posa_debt_collect_roles")
	if action == "collect":
		allowed = collect_roles
	elif action == "view":
		allowed = collect_roles | _roles_of(profile, "posa_debt_view_roles")
	elif action == "refund":
		allowed = _roles_of(profile, "posa_debt_refund_roles")
	elif action == "cancel":
		allowed = _roles_of(profile, "posa_debt_cancel_roles")
	else:
		return False

	return bool(allowed & set(frappe.get_roles(user)))


def _check_access(pos_profile, action):
	if not _has_debt_access(pos_profile, action):
		messages = {
			"view": _("You are not allowed to view debts at POS Profile {0}"),
			"collect": _("You are not allowed to collect debts at POS Profile {0}"),
			"refund": _("You are not allowed to refund customer credit at POS Profile {0}"),
			"cancel": _("You are not allowed to cancel debt collections at POS Profile {0}"),
		}
		frappe.throw(
			messages.get(action, messages["view"]).format(pos_profile),
			frappe.PermissionError,
		)
	return _get_profile(pos_profile)


@frappe.whitelist()
def get_debt_access(pos_profile):
	"""Cờ quyền + cấu hình công nợ của quầy cho giao diện (backend vẫn kiểm lại)."""
	if not pos_profile or not frappe.db.exists("POS Profile", pos_profile):
		return {"enabled": 0}
	profile = frappe.get_cached_doc("POS Profile", pos_profile)
	return {
		"enabled": cint(profile.get("posa_enable_debt_collection")),
		"can_view": _has_debt_access(pos_profile, "view"),
		"can_collect": _has_debt_access(pos_profile, "collect"),
		"can_refund": _has_debt_access(pos_profile, "refund"),
		"can_cancel": _has_debt_access(pos_profile, "cancel"),
		"max_amount": flt(profile.get("posa_debt_max_amount")),
		"hide_below": flt(profile.get("posa_debt_hide_below")),
		"credit_days": cint(profile.get("posa_credit_days")),
		"allow_credit_sale": _allow_credit_sale(pos_profile),
		"payment_modes": _payment_modes_info(profile),
		"sepay_enabled": _sepay_enabled(pos_profile, profile),
		"uses_sales_persons": _uses_sales_persons(pos_profile),
		"debtor_count": _debtor_count(profile) if _has_debt_access(pos_profile, "view") else 0,
	}


def _debtor_count(profile):
	si = DocType("Sales Invoice")
	row = _base_debt_query(profile, si).select(Count(si.customer).distinct().as_("n")).run(as_dict=True)
	return cint(row[0].n) if row else 0


def _payment_modes_info(profile):
	modes = []
	for row in profile.get("payments") or []:
		if not row.mode_of_payment:
			continue
		modes.append(
			{
				"mode_of_payment": row.mode_of_payment,
				"type": frappe.get_cached_value("Mode of Payment", row.mode_of_payment, "type"),
				"is_wallet": cint(frappe.get_cached_value("Mode of Payment", row.mode_of_payment, "is_wallet_payment")),
				"default": cint(row.get("default")),
			}
		)
	return modes


def _sepay_enabled(pos_profile, profile):
	from pos_next.api.sepay import _get_sepay_settings

	return bool(_get_sepay_settings(pos_profile)) and bool(_bank_mode_of_payment(profile))


def _allow_credit_sale(pos_profile):
	# Quầy chưa có POS Settings = không bán chịu
	return cint(
		frappe.db.get_value("POS Settings", {"pos_profile": pos_profile}, "allow_credit_sale") or 0
	)


# ---------------------------------------------------------------------------
# Truy vấn đơn nợ
# ---------------------------------------------------------------------------


def _scope_customer_groups(profile):
	"""Nhóm khách (kèm nhóm con) quầy được thu; None = không giới hạn."""
	if profile.get("posa_debt_customer_scope") != SCOPE_CUSTOMER_GROUP:
		return None

	roots = [row.customer_group for row in (profile.get("customer_groups") or []) if row.customer_group]
	if not roots and profile.get("customer_group"):
		roots = [profile.get("customer_group")]
	if not roots:
		return None

	from frappe.utils.nestedset import get_descendants_of

	groups = set(roots)
	for root in roots:
		groups.update(get_descendants_of("Customer Group", root))
	return list(groups)


def _check_customer_scope(profile, customer):
	"""Chặn khách ngoài phạm vi khách của quầy (mọi API đọc / ghi theo khách)."""
	groups = _scope_customer_groups(profile)
	if groups is not None and frappe.db.get_value("Customer", customer, "customer_group") not in groups:
		frappe.throw(
			_("Customer {0} is outside the customer scope of POS Profile {1}").format(customer, profile.name),
			frappe.PermissionError,
		)


def _invoice_total_expr(si):
	# Tổng phải trả của đơn: số đã làm tròn nếu có, không thì grand_total
	from frappe.query_builder import Case

	return Case().when(IfNull(si.rounded_total, 0) != 0, si.rounded_total).else_(si.grand_total)


def _base_debt_query(profile, si):
	"""Điều kiện chung: đơn bán của quầy, cùng company, còn nợ, trên ngưỡng ẩn nợ lẻ."""
	hide_below = flt(profile.get("posa_debt_hide_below"))
	query = (
		frappe.qb.from_(si)
		.where(si.docstatus == 1)
		.where(si.is_return == 0)
		.where(si.pos_profile == profile.name)
		.where(si.company == profile.company)
	)
	if hide_below > 0:
		query = query.where(si.outstanding_amount >= hide_below)
	else:
		query = query.where(si.outstanding_amount > 0)

	groups = _scope_customer_groups(profile)
	if groups is not None:
		customer = DocType("Customer")
		query = query.where(
			si.customer.isin(
				frappe.qb.from_(customer).select(customer.name).where(customer.customer_group.isin(groups))
			)
		)
	return query


def _apply_filters(query, si, profile, filters):
	"""Lọc theo trạng thái / ngày bán / người bán / tìm kiếm."""
	filters = frappe._dict(filters or {})
	total = _invoice_total_expr(si)
	overdue_before = add_days(nowdate(), -cint(profile.get("posa_credit_days")))

	status = filters.get("status")
	if status == STATUS_OVERDUE:
		# Chưa trả đồng nào và hôm nay > ngày bán + số ngày được nợ
		query = query.where(si.outstanding_amount >= total - 0.01).where(si.posting_date < overdue_before)
	elif status == STATUS_PARTLY_PAID:
		query = query.where(si.outstanding_amount < total - 0.01)

	if filters.get("from_date"):
		query = query.where(si.posting_date >= getdate(filters.from_date))
	if filters.get("to_date"):
		query = query.where(si.posting_date <= getdate(filters.to_date))

	seller = filters.get("seller")
	if seller:
		if _uses_sales_persons(profile.name):
			team = DocType("Sales Team")
			query = query.where(
				si.name.isin(
					frappe.qb.from_(team)
					.select(team.parent)
					.where(team.parenttype == "Sales Invoice")
					.where(team.sales_person == seller)
				)
			)
		else:
			# Quầy tắt "nhân viên bán": lọc theo người lập đơn
			query = query.where(si.owner == seller)

	search = (filters.get("search") or "").strip()
	if search:
		like = f"%{search}%"
		customer = DocType("Customer")
		query = query.where(
			(si.name.like(like))
			| (si.customer.like(like))
			| (si.customer_name.like(like))
			| si.customer.isin(
				frappe.qb.from_(customer).select(customer.name).where(customer.mobile_no.like(like))
			)
		)

	customer_filter = filters.get("customer")
	if customer_filter:
		query = query.where(si.customer == customer_filter)

	return query


def _uses_sales_persons(pos_profile):
	value = frappe.db.get_value("POS Settings", {"pos_profile": pos_profile}, "enable_sales_persons")
	return bool(value) and value != "Disabled"


def _decorate_invoice(row, credit_days, today):
	"""Thêm hạn TT (tính khi đọc), trạng thái, số ngày nợ."""
	total = flt(row.get("rounded_total")) or flt(row.get("grand_total"))
	outstanding = flt(row.get("outstanding_amount"))
	paid = flt(total - outstanding, 2)
	due_date = add_days(row.posting_date, credit_days)

	if outstanding <= 0.01:
		status = STATUS_PAID  # đơn đã trả hết, mở từ lịch sử thu
	elif paid > 0.01:
		status = STATUS_PARTLY_PAID
	elif getdate(due_date) < today:
		status = STATUS_OVERDUE
	else:
		status = STATUS_UNPAID

	row.update(
		{
			"invoice_total": total,
			"paid_amount": paid if paid > 0 else 0,
			"due_date": due_date,
			"status": status,
			"age_days": date_diff(today, row.posting_date),
		}
	)
	return row


def _invoice_fields(si):
	return [
		si.name,
		si.customer,
		si.customer_name,
		si.posting_date,
		si.posting_time,
		si.grand_total,
		si.rounded_total,
		si.outstanding_amount,
		si.owner,
		si.debit_to,
		si.currency,
	]


def _query_customer_debts(pos_profile, customer, filters=None):
	"""Đơn còn nợ của một khách tại quầy, cũ trước. KHÔNG kiểm quyền.

	Dùng chung với chức năng Cảnh báo công nợ (debt_warning). Trả `due_date` đã tính theo
	số ngày được nợ của quầy và đã áp ngưỡng ẩn nợ lẻ.
	"""
	if not customer:
		return []
	profile = _get_profile(pos_profile)
	si = DocType("Sales Invoice")
	query = _base_debt_query(profile, si).where(si.customer == customer)
	if filters:
		query = _apply_filters(query, si, profile, filters)
	rows = (
		query.select(*_invoice_fields(si))
		.orderby(si.posting_date)
		.orderby(si.posting_time)
		.orderby(si.name)
		.run(as_dict=True)
	)
	credit_days = cint(profile.get("posa_credit_days"))
	today = getdate(nowdate())
	return [_decorate_invoice(row, credit_days, today) for row in rows]


def _summarize(invoices):
	return {
		"total_outstanding": flt(sum(flt(r.outstanding_amount) for r in invoices), 2),
		"invoice_count": len(invoices),
		"overdue_count": sum(1 for r in invoices if r.status == STATUS_OVERDUE),
		"partly_paid_count": sum(1 for r in invoices if r.status == STATUS_PARTLY_PAID),
	}


@frappe.whitelist()
def get_customer_debts(pos_profile, customer, filters=None):
	"""Đơn nợ của một khách (cột phải màn hình Công nợ, hộp thoại Thu nợ)."""
	profile = _check_access(pos_profile, "view")
	groups = _scope_customer_groups(profile)
	if groups is not None and frappe.db.get_value("Customer", customer, "customer_group") not in groups:
		# Khách ngoài phạm vi: coi như không nợ tại quầy, không trả thông tin khách
		# (huy hiệu nợ ở giỏ gọi hàm này cho mọi khách nên không báo lỗi)
		return {"customer": {}, "invoices": [], **_summarize([]), "out_of_scope": 1}
	filters = _parse(filters) or None
	invoices = _query_customer_debts(pos_profile, customer, filters)
	sellers = _seller_names([i.name for i in invoices], _uses_sales_persons(pos_profile))
	for inv in invoices:
		inv["seller"] = sellers.get(inv.name)
	customer_info = frappe.db.get_value(
		"Customer", customer, ["name", "customer_name", "mobile_no", "customer_group"], as_dict=True
	) or {}
	return {
		"customer": customer_info,
		"invoices": invoices,
		**_summarize(invoices),
		"credit": _get_customer_credit(profile, customer),
		"wallet_balance": _wallet_balance(profile, customer),
		"can_collect": _has_debt_access(pos_profile, "collect"),
		"can_refund": _has_debt_access(pos_profile, "refund"),
		"hidden_count": _customer_hidden_count(profile, customer),
	}


def _customer_hidden_count(profile, customer):
	hide_below = flt(profile.get("posa_debt_hide_below"))
	if hide_below <= 0 or not customer:
		return 0
	return frappe.db.count(
		"Sales Invoice",
		{
			"docstatus": 1,
			"is_return": 0,
			"customer": customer,
			"pos_profile": profile.name,
			"company": profile.company,
			"outstanding_amount": ["between", [0.000001, hide_below - 0.000001]],
		},
	)


@frappe.whitelist()
def search_debts(pos_profile, filters=None, start=0, page_length=50):
	"""Danh sách khách còn nợ tại quầy (cột trái màn hình Công nợ).

	Dòng tổng tính trên TOÀN BỘ kết quả lọc, không chỉ trang đang xem.
	"""
	profile = _check_access(pos_profile, "view")
	filters = _parse(filters)
	credit_customers = _credit_customers(profile, (filters or {}).get("search"))
	if (filters or {}).get("status") == STATUS_CREDIT:
		return _credit_result(profile, credit_customers, start, page_length)
	si = DocType("Sales Invoice")
	base = _apply_filters(_base_debt_query(profile, si), si, profile, filters)

	totals = base.select(
		Sum(si.outstanding_amount).as_("total_outstanding"),
		Count(si.name).as_("invoice_count"),
		Count(si.customer).distinct().as_("customer_count"),
	).run(as_dict=True)[0]

	customers = (
		base.select(
			si.customer,
			Max(si.customer_name).as_("customer_name"),
			Sum(si.outstanding_amount).as_("total_outstanding"),
			Count(si.name).as_("invoice_count"),
			Min(si.posting_date).as_("oldest_posting_date"),
		)
		.groupby(si.customer)
		.orderby(Min(si.posting_date))
		.limit(cint(page_length) or 50)
		.offset(cint(start))
		.run(as_dict=True)
	)

	if customers:
		names = [c.customer for c in customers]
		mobiles = dict(
			frappe.get_all("Customer", filters={"name": ["in", names]}, fields=["name", "mobile_no"], as_list=True)
		)
		# Trạng thái từng khách: có đơn quá hạn / đã trả một phần
		rows = (
			_apply_filters(_base_debt_query(profile, si), si, profile, filters)
			.where(si.customer.isin(names))
			.select(si.customer, si.posting_date, si.grand_total, si.rounded_total, si.outstanding_amount)
			.run(as_dict=True)
		)
		credit_days = cint(profile.get("posa_credit_days"))
		today = getdate(nowdate())
		flags = {}
		for row in rows:
			_decorate_invoice(row, credit_days, today)
			flag = flags.setdefault(row.customer, {"overdue_count": 0, "partly_paid_count": 0})
			if row.status == STATUS_OVERDUE:
				flag["overdue_count"] += 1
			elif row.status == STATUS_PARTLY_PAID:
				flag["partly_paid_count"] += 1
		for c in customers:
			c["mobile_no"] = mobiles.get(c.customer)
			c.update(flags.get(c.customer, {}))
			c["age_days"] = date_diff(today, c.oldest_posting_date)

	# Số đơn theo từng nhãn lọc (cùng các bộ lọc khác, bỏ lọc trạng thái)
	no_status = {k: v for k, v in (filters or {}).items() if k != "status"}
	status_counts = {}
	for key in ("", STATUS_OVERDUE, STATUS_PARTLY_PAID):
		q = _apply_filters(_base_debt_query(profile, si), si, profile, {**no_status, "status": key})
		status_counts[key or "all"] = cint(q.select(Count(si.name).as_("n")).run(as_dict=True)[0].n)
	status_counts[STATUS_CREDIT] = len(credit_customers)

	return {
		"customers": customers,
		"status_counts": status_counts,
		"hidden_count": _hidden_count(profile),
		"hide_below": flt(profile.get("posa_debt_hide_below")),
		"total_outstanding": flt(totals.total_outstanding, 2),
		"invoice_count": cint(totals.invoice_count),
		"customer_count": cint(totals.customer_count),
		"start": cint(start),
		"page_length": cint(page_length) or 50,
	}


def _credit_customers(profile, search=None):
	"""Khách đang có tiền dư tại quầy (từ đơn đã trả hàng), kể cả khách không còn nợ.

	Cùng cách tính với _get_customer_credit: số dư từng chứng từ trên Payment Ledger.
	"""
	rows = frappe.db.sql(
		"""
		select t.customer, sum(t.balance) as balance, count(*) as documents
		from (
			select ple.party as customer, ple.against_voucher_no, sum(ple.amount) as balance
			from `tabPayment Ledger Entry` ple
			join `tabSales Invoice` si on si.name = ple.against_voucher_no
			where ple.delinked = 0 and ple.party_type = 'Customer' and ple.company = %(company)s
				and ple.against_voucher_type = 'Sales Invoice'
				and si.pos_profile = %(pos_profile)s and si.docstatus = 1
			group by ple.party, ple.against_voucher_no
			having sum(ple.amount) < -0.005
		) t
		group by t.customer
		order by balance
		""",
		{"company": profile.company, "pos_profile": profile.name},
		as_dict=True,
	)
	if not rows:
		return []
	info = {
		c.name: c
		for c in frappe.get_all(
			"Customer",
			filters={"name": ["in", [r.customer for r in rows]]},
			fields=["name", "customer_name", "mobile_no", "customer_group"],
		)
	}
	groups = _scope_customer_groups(profile)
	search = (search or "").strip().lower()
	result = []
	for r in rows:
		c = info.get(r.customer) or frappe._dict(name=r.customer)
		if groups is not None and c.get("customer_group") not in groups:
			continue
		if search and not any(search in (v or "").lower() for v in (c.name, c.get("customer_name"), c.get("mobile_no"))):
			continue
		result.append(
			{
				"customer": r.customer,
				"customer_name": c.get("customer_name") or r.customer,
				"mobile_no": c.get("mobile_no"),
				"credit_total": flt(-r.balance, 2),
				"credit_documents": cint(r.documents),
			}
		)
	return result


def _credit_result(profile, customers, start, page_length):
	"""Kết quả search_debts khi lọc "Có tiền dư": danh sách khách để trả lại tiền dư."""
	start, page_length = cint(start), cint(page_length) or 50
	return {
		"customers": customers[start : start + page_length],
		"status_counts": {STATUS_CREDIT: len(customers)},
		"hidden_count": 0,
		"hide_below": flt(profile.get("posa_debt_hide_below")),
		"total_outstanding": 0,
		"credit_total": flt(sum(c["credit_total"] for c in customers), 2),
		"invoice_count": 0,
		"customer_count": len(customers),
		"start": start,
		"page_length": page_length,
	}


def _hidden_count(profile):
	"""Số đơn nợ lẻ dưới ngưỡng ẩn của quầy (vẫn còn trên sổ)."""
	hide_below = flt(profile.get("posa_debt_hide_below"))
	if hide_below <= 0:
		return 0
	return frappe.db.count(
		"Sales Invoice",
		{
			"docstatus": 1,
			"is_return": 0,
			"pos_profile": profile.name,
			"company": profile.company,
			"outstanding_amount": ["between", [0.000001, hide_below - 0.000001]],
		},
	)


def _seller_names(invoice_names, uses_sales_persons):
	"""Tên người bán từng đơn: nhân viên bán (Sales Team) hoặc người lập đơn."""
	if not invoice_names:
		return {}
	result = {}
	if uses_sales_persons:
		for row in frappe.get_all(
			"Sales Team",
			filters={"parenttype": "Sales Invoice", "parent": ["in", invoice_names]},
			fields=["parent", "sales_person"],
		):
			result.setdefault(row.parent, []).append(row.sales_person)
		return {k: ", ".join(v) for k, v in result.items()}
	owners = frappe.get_all("Sales Invoice", filters={"name": ["in", invoice_names]}, fields=["name", "owner"])
	names = {}
	for row in owners:
		if row.owner not in names:
			names[row.owner] = frappe.db.get_value("User", row.owner, "full_name") or row.owner
		result[row.name] = names[row.owner]
	return result


@frappe.whitelist()
def get_debt_filter_options(pos_profile):
	"""Danh sách người bán để lọc: nhân viên bán, hoặc người lập đơn khi quầy tắt NV bán.

	Chỉ lấy trong các đơn nợ của chính quầy, không lộ người của quầy khác.
	"""
	profile = _check_access(pos_profile, "view")
	si = DocType("Sales Invoice")
	base = _base_debt_query(profile, si)
	if _uses_sales_persons(pos_profile):
		team = DocType("Sales Team")
		rows = (
			base.join(team)
			.on((team.parent == si.name) & (team.parenttype == "Sales Invoice"))
			.select(team.sales_person.as_("value"))
			.distinct()
			.run(as_dict=True)
		)
		return {"seller_type": "sales_person", "sellers": [{"value": r.value, "label": r.value} for r in rows]}

	rows = base.select(si.owner.as_("value")).distinct().run(as_dict=True)
	sellers = []
	for r in rows:
		full_name = frappe.db.get_value("User", r.value, "full_name") or r.value
		sellers.append({"value": r.value, "label": full_name})
	return {"seller_type": "owner", "sellers": sellers}


@frappe.whitelist()
def get_invoice_detail(pos_profile, invoice):
	"""Chi tiết một đơn nợ: hàng, thanh toán lúc bán, lịch sử các lần thu nợ."""
	profile = _check_access(pos_profile, "view")
	doc = frappe.get_doc("Sales Invoice", invoice)
	if doc.pos_profile != profile.name or doc.company != profile.company:
		frappe.throw(_("Invoice {0} does not belong to POS Profile {1}").format(invoice, pos_profile))
	_check_customer_scope(profile, doc.customer)

	row = _decorate_invoice(
		frappe._dict(
			posting_date=doc.posting_date,
			grand_total=doc.grand_total,
			rounded_total=doc.rounded_total,
			outstanding_amount=doc.outstanding_amount,
		),
		cint(profile.get("posa_credit_days")),
		getdate(nowdate()),
	)
	sellers = [st.sales_person for st in (doc.get("sales_team") or []) if st.sales_person]
	return {
		"name": doc.name,
		"customer": doc.customer,
		"customer_name": doc.customer_name,
		"posting_date": doc.posting_date,
		"posting_time": doc.posting_time,
		"owner": doc.owner,
		"owner_name": frappe.db.get_value("User", doc.owner, "full_name") or doc.owner,
		"sellers": sellers,
		"items": [
			{
				"item_code": it.item_code,
				"item_name": it.item_name,
				"qty": it.qty,
				"uom": it.uom,
				"rate": it.rate,
				"amount": it.amount,
			}
			for it in doc.items
		],
		"total": doc.total,
		"discount_amount": doc.discount_amount,
		"total_taxes_and_charges": doc.total_taxes_and_charges,
		"mobile_no": frappe.db.get_value("Customer", doc.customer, "mobile_no"),
		"pos_profile": doc.pos_profile,
		"grand_total": doc.grand_total,
		"rounded_total": doc.rounded_total,
		"outstanding_amount": doc.outstanding_amount,
		"invoice_total": row.invoice_total,
		"paid_amount": row.paid_amount,
		"due_date": row.due_date,
		"status": row.status,
		"age_days": row.age_days,
		"payments_at_sale": [
			{"mode_of_payment": p.mode_of_payment, "amount": p.amount}
			for p in (doc.get("payments") or [])
			if flt(p.amount)
		],
		"collections": _collection_history(invoice),
	}


@frappe.whitelist()
def get_invoice_collection_history(pos_profile, invoice):
	profile = _check_access(pos_profile, "view")
	inv = frappe.db.get_value("Sales Invoice", invoice, ["pos_profile", "customer"], as_dict=True)
	if not inv or inv.pos_profile != profile.name:
		frappe.throw(_("Invoice {0} does not belong to POS Profile {1}").format(invoice, pos_profile))
	_check_customer_scope(profile, inv.customer)
	return _collection_history(invoice)


def _collection_history(invoice):
	pe = DocType("Payment Entry")
	ref = DocType("Payment Entry Reference")
	rows = (
		frappe.qb.from_(ref)
		.join(pe)
		.on(pe.name == ref.parent)
		.select(
			pe.name.as_("payment_entry"),
			pe.posting_date,
			pe.creation,
			pe.mode_of_payment,
			pe.payment_type,
			pe.owner,
			pe.posa_debt_collection_id,
			pe.posa_pos_profile,
			ref.allocated_amount,
		)
		.where(ref.reference_doctype == "Sales Invoice")
		.where(ref.reference_name == invoice)
		.where(pe.docstatus == 1)
		.orderby(pe.creation)
		.run(as_dict=True)
	)
	for r in rows:
		r["owner_name"] = frappe.db.get_value("User", r.owner, "full_name") or r.owner
	return rows


# ---------------------------------------------------------------------------
# Thu nợ
# ---------------------------------------------------------------------------


def _parse(value):
	if isinstance(value, str):
		return json.loads(value) if value else {}
	return value or {}


def _get_open_shift(pos_profile, user=None):
	user = user or frappe.session.user
	return frappe.db.get_value(
		"POS Opening Shift",
		{
			"user": user,
			"pos_profile": pos_profile,
			"docstatus": 1,
			"status": "Open",
			"pos_closing_shift": ["is", "not set"],
		},
		"name",
		order_by="period_start_date desc",
	)


def _profile_modes(profile):
	return {row.mode_of_payment for row in (profile.get("payments") or []) if row.mode_of_payment}


def _mode_account(mode_of_payment, company):
	from erpnext.accounts.doctype.sales_invoice.sales_invoice import get_bank_cash_account

	# Hai hàm dò có thể tự báo lỗi (ERPNext) hoặc lỗi truy vấn (get_payment_account dò cột
	# không có): bỏ qua và bỏ luôn thông báo của chúng, chỉ hiện câu hướng dẫn bên dưới.
	log_len = len(frappe.local.message_log or [])
	account = None
	for find in (get_bank_cash_account, get_payment_account):
		try:
			info = find(mode_of_payment, company)
			account = info.get("account") if info else None
		except Exception:
			account = None
		if account:
			break
	if frappe.local.message_log:
		del frappe.local.message_log[log_len:]
	if not account:
		frappe.throw(
			_("Please set default Cash or Bank account in Mode of Payment {0}, or set default accounts in Company {1}").format(
				mode_of_payment, company
			),
			title=_("Missing Account"),
		)
	return account


def _existing_collection(debt_collection_id, profile=None, customer=None):
	"""PE đã có của mã lần thu. Mã đã dùng cho khách / quầy khác thì chặn, không trả thông tin phiếu."""
	rows = _existing_collection_rows(debt_collection_id)
	if rows and profile and any(r.party != customer or r.posa_pos_profile != profile.name for r in rows):
		frappe.throw(_("Debt collection ID {0} is already used. Please reload and try again.").format(debt_collection_id))
	return rows


def _existing_collection_rows(debt_collection_id):
	return frappe.get_all(
		"Payment Entry",
		filters={"posa_debt_collection_id": debt_collection_id, "docstatus": 1},
		fields=["name", "mode_of_payment", "paid_amount", "payment_type", "party", "posa_pos_profile"],
		order_by="creation",
	)


def _lock_invoices(names):
	si = DocType("Sales Invoice")
	rows = (
		frappe.qb.from_(si)
		.select(
			si.name,
			si.customer,
			si.company,
			si.pos_profile,
			si.docstatus,
			si.is_return,
			si.outstanding_amount,
			si.grand_total,
			si.rounded_total,
			si.debit_to,
			si.currency,
			si.posting_date,
			si.due_date,
		)
		.where(si.name.isin(names))
		.for_update()
		.run(as_dict=True)
	)
	return {r.name: r for r in rows}


def _split_allocations(allocations, payments):
	"""Đổ phân bổ (đơn cũ trước) lần lượt vào từng hình thức theo thứ tự.

	Trả [(payment, [(invoice, amount), ...]), ...].
	"""
	queue = [[a["invoice"], flt(a["amount"], 2)] for a in allocations]
	result = []
	for payment in payments:
		need = flt(payment["amount"], 2)
		refs = []
		while need > 0.004 and queue:
			take = min(need, queue[0][1])
			refs.append((queue[0][0], flt(take, 2)))
			need = flt(need - take, 2)
			queue[0][1] = flt(queue[0][1] - take, 2)
			if queue[0][1] <= 0.004:
				queue.pop(0)
		result.append((payment, refs))
	return result


def _make_payment_entry(profile, shift, customer, mode_of_payment, amount, refs, invoices, debt_collection_id, remarks):
	first = invoices[refs[0][0]]
	pe = frappe.new_doc("Payment Entry")
	pe.payment_type = "Receive"
	pe.posting_date = nowdate()
	pe.company = profile.company
	pe.party_type = "Customer"
	pe.party = customer
	pe.mode_of_payment = mode_of_payment
	pe.paid_from = first.debit_to
	pe.paid_to = _mode_account(mode_of_payment, profile.company)
	pe.paid_from_account_currency = first.currency
	pe.paid_to_account_currency = frappe.get_cached_value("Account", pe.paid_to, "account_currency") or first.currency
	pe.paid_amount = amount
	pe.received_amount = amount
	pe.source_exchange_rate = 1
	pe.target_exchange_rate = 1
	pe.reference_no = debt_collection_id[:140]
	pe.reference_date = nowdate()
	pe.posa_pos_opening_shift = shift
	pe.posa_pos_profile = profile.name
	pe.posa_debt_collection_id = debt_collection_id
	pe.remarks = remarks
	if profile.get("cost_center"):
		pe.cost_center = profile.cost_center
	if profile.get("branch") and frappe.get_meta("Payment Entry").has_field("branch"):
		pe.branch = profile.branch

	for invoice_name, allocated in refs:
		inv = invoices[invoice_name]
		pe.append(
			"references",
			{
				"reference_doctype": "Sales Invoice",
				"reference_name": invoice_name,
				"total_amount": flt(inv.rounded_total) or flt(inv.grand_total),
				"outstanding_amount": flt(inv.outstanding_amount),
				"allocated_amount": allocated,
				"due_date": inv.due_date,
			},
		)
		# Số còn nợ của đơn cho phiếu kế tiếp trong cùng lần thu
		inv.outstanding_amount = flt(inv.outstanding_amount - allocated, 2)

	pe.flags.ignore_permissions = True
	frappe.flags.ignore_account_permission = True
	pe.insert()
	pe.submit()
	return pe


@frappe.whitelist()
def collect_debt(pos_profile, customer, allocations, payments, debt_collection_id):
	"""Thu nợ nhiều đơn của một khách trong một lần.

	allocations: [{invoice, amount}] - số thu từng đơn (client đã phân bổ cũ trước).
	payments:    [{mode_of_payment, amount}] - mỗi hình thức sinh một Payment Entry.
	debt_collection_id: mã lần thu do client sinh khi mở hộp thoại; gửi lại cùng mã
	thì trả kết quả lần đầu, không tạo phiếu thứ hai.

	Cả lần thu nằm trong một transaction của request: lỗi ở bất kỳ phiếu nào thì
	Frappe rollback toàn bộ.
	"""
	profile = _check_access(pos_profile, "collect")
	allocations = _parse(allocations)
	payments = [p for p in _parse(payments) if flt(p.get("amount")) > 0]
	debt_collection_id = (debt_collection_id or "").strip()

	if not debt_collection_id:
		frappe.throw(_("Missing debt collection ID"))
	if not allocations:
		frappe.throw(_("Select at least one invoice to collect"))
	if not payments:
		frappe.throw(_("Enter at least one payment"))

	existing = _existing_collection(debt_collection_id, profile, customer)
	if existing:
		return _collection_result(profile, customer, debt_collection_id, existing, duplicate=True)

	shift = _get_open_shift(profile.name)
	if not shift:
		frappe.throw(_("You need an open POS shift at {0} to collect debts").format(profile.name))

	return _collect(profile, customer, allocations, payments, debt_collection_id, shift)


def _collect(profile, customer, allocations, payments, debt_collection_id, shift):
	"""Phần chung của thu nợ tại quầy và thu nợ qua QR SePay (webhook). Đã kiểm quyền."""
	_validate_payments(profile, customer, payments)

	names = [a.get("invoice") for a in allocations]
	if len(set(names)) != len(names):
		frappe.throw(_("Each invoice can appear only once in a collection"))

	# Khoá các đơn: quầy khác thu cùng đơn phải chờ, rồi thấy số nợ mới
	invoices = _lock_invoices(names)

	# Kiểm lại sau khi khoá: request trùng mã đến cùng lúc sẽ thấy phiếu của request trước
	existing = _existing_collection(debt_collection_id, profile, customer)
	if existing:
		return _collection_result(profile, customer, debt_collection_id, existing, duplicate=True)

	_check_customer_scope(profile, customer)

	debit_accounts = set()
	total_allocated = 0
	for alloc in allocations:
		name = alloc.get("invoice")
		amount = flt(alloc.get("amount"), 2)
		inv = invoices.get(name)
		if (
			not inv
			or inv.docstatus != 1
			or inv.is_return
			or inv.customer != customer
			or inv.pos_profile != profile.name
			or inv.company != profile.company
		):
			frappe.throw(_("Invoice {0} cannot be collected at this POS").format(name), DebtChangedError)
		if amount <= 0:
			frappe.throw(_("Amount for invoice {0} must be greater than zero").format(name))
		if amount > flt(inv.outstanding_amount) + 0.004:
			frappe.throw(
				_("Invoice {0} now has outstanding {1}, less than {2}. Another POS may have just collected it - reload and try again.").format(
					name,
					frappe.format_value(inv.outstanding_amount, {"fieldtype": "Currency"}),
					frappe.format_value(amount, {"fieldtype": "Currency"}),
				),
				DebtChangedError,
			)
		debit_accounts.add(inv.debit_to)
		total_allocated += amount

	if len(debit_accounts) > 1:
		frappe.throw(_("Selected invoices use different receivable accounts; collect them separately"))

	total_allocated = flt(total_allocated, 2)
	total_paid = flt(sum(flt(p["amount"]) for p in payments), 2)
	if abs(total_allocated - total_paid) > AMOUNT_TOLERANCE:
		frappe.throw(
			_("Total payments {0} must equal the amount collected {1}").format(
				frappe.format_value(total_paid, {"fieldtype": "Currency"}),
				frappe.format_value(total_allocated, {"fieldtype": "Currency"}),
			)
		)

	max_amount = flt(profile.get("posa_debt_max_amount"))
	if max_amount > 0 and total_allocated > max_amount:
		frappe.throw(
			_("Collection {0} exceeds the limit {1} per collection at this POS").format(
				frappe.format_value(total_allocated, {"fieldtype": "Currency"}),
				frappe.format_value(max_amount, {"fieldtype": "Currency"}),
			)
		)

	# Đơn cũ trước: phiếu thứ nhất nhận các đơn cũ nhất
	allocations = sorted(
		allocations,
		key=lambda a: (invoices[a["invoice"]].posting_date, a["invoice"]),
	)
	# Lệch làm tròn giữa tổng phân bổ và tổng thanh toán dồn vào hình thức cuối
	payments[-1]["amount"] = flt(flt(payments[-1]["amount"]) + total_allocated - total_paid, 2)

	remarks = _("Debt collection at POS {0} ({1})").format(profile.name, debt_collection_id)
	for payment, refs in _split_allocations(allocations, payments):
		if not refs:
			continue
		_make_payment_entry(
			profile,
			shift,
			customer,
			payment["mode_of_payment"],
			flt(sum(r[1] for r in refs), 2),
			refs,
			invoices,
			debt_collection_id,
			remarks,
		)

	return _collection_result(profile, customer, debt_collection_id, _existing_collection(debt_collection_id))


def _validate_payments(profile, customer, payments):
	allowed = _profile_modes(profile)
	seen = set()
	for p in payments:
		mode = p.get("mode_of_payment")
		if mode not in allowed:
			frappe.throw(_("Mode of Payment {0} is not set up for POS Profile {1}").format(mode, profile.name))
		if mode in seen:
			frappe.throw(_("Mode of Payment {0} appears more than once").format(mode))
		seen.add(mode)
		if cint(frappe.get_cached_value("Mode of Payment", mode, "is_wallet_payment")):
			_validate_wallet_balance(profile, customer, flt(p.get("amount")))


def _wallet_balance(profile, customer):
	if not any(m["is_wallet"] for m in _payment_modes_info(profile)):
		return None
	from pos_next.api.wallet import get_customer_wallet_balance

	return flt(get_customer_wallet_balance(customer, profile.company))


def _validate_wallet_balance(profile, customer, amount):
	from pos_next.api.wallet import get_customer_wallet_balance

	balance = flt(get_customer_wallet_balance(customer, profile.company))
	if amount > balance + 0.004:
		frappe.throw(
			_("Wallet balance {0} is not enough for {1}").format(
				frappe.format_value(balance, {"fieldtype": "Currency"}),
				frappe.format_value(amount, {"fieldtype": "Currency"}),
			)
		)


def _collection_result(profile, customer, debt_collection_id, entries, duplicate=False):
	remaining = _query_customer_debts(profile.name, customer)
	return {
		"debt_collection_id": debt_collection_id,
		"duplicate": duplicate,
		"payment_entries": [
			{"name": e.name, "mode_of_payment": e.mode_of_payment, "paid_amount": e.paid_amount}
			for e in entries
		],
		"total_paid": flt(sum(flt(e.paid_amount) for e in entries), 2),
		"remaining_outstanding": flt(sum(flt(r.outstanding_amount) for r in remaining), 2),
		"remaining_invoices": len(remaining),
	}


@frappe.whitelist()
def new_debt_collection_id():
	return uuid.uuid4().hex


# ---------------------------------------------------------------------------
# Tiền dư của khách (từ đơn đã trả hàng tại quầy)
# ---------------------------------------------------------------------------


def _get_customer_credit(profile, customer):
	"""Tiền dư của khách tại quầy: các hoá đơn bán/trả của quầy đang có số dư âm.

	Đọc từ Payment Ledger theo chứng từ (against_voucher), KHÔNG cộng outstanding âm của
	từng hoá đơn: đơn gốc và phiếu trả cùng âm nên cộng thẳng là đếm hai lần. Chỉ lấy
	chứng từ là Sales Invoice của quầy, nên tự loại các bút toán ví (Wallet Transaction).
	"""
	if not customer:
		return {"total": 0, "documents": []}
	ple = DocType("Payment Ledger Entry")
	si = DocType("Sales Invoice")
	rows = (
		frappe.qb.from_(ple)
		.join(si)
		.on(si.name == ple.against_voucher_no)
		.select(ple.against_voucher_no.as_("invoice"), Sum(ple.amount).as_("balance"), si.posting_date)
		.where(ple.delinked == 0)
		.where(ple.party_type == "Customer")
		.where(ple.party == customer)
		.where(ple.company == profile.company)
		.where(ple.against_voucher_type == "Sales Invoice")
		.where(si.pos_profile == profile.name)
		.where(si.docstatus == 1)
		.groupby(ple.against_voucher_no, si.posting_date)
		.having(Sum(ple.amount) < -0.005)
		.orderby(si.posting_date)
		.run(as_dict=True)
	)
	documents = []
	for r in rows:
		returns = frappe.get_all(
			"Sales Invoice",
			filters={"return_against": r.invoice, "docstatus": 1, "is_return": 1},
			pluck="name",
		)
		documents.append(
			{
				"invoice": r.invoice,
				"posting_date": r.posting_date,
				"credit": flt(-r.balance, 2),
				"returns": returns,
			}
		)
	return {"total": flt(sum(d["credit"] for d in documents), 2), "documents": documents}


def _all_customer_debts(profile, customer):
	"""Mọi đơn còn nợ của khách tại quầy, KỂ CẢ nợ lẻ dưới ngưỡng ẩn: cấn trừ thì dọn luôn."""
	si = DocType("Sales Invoice")
	return (
		frappe.qb.from_(si)
		.select(si.name, si.outstanding_amount, si.posting_date, si.debit_to)
		.where(si.docstatus == 1)
		.where(si.is_return == 0)
		.where(si.pos_profile == profile.name)
		.where(si.company == profile.company)
		.where(si.customer == customer)
		.where(si.outstanding_amount > 0)
		.orderby(si.posting_date)
		.orderby(si.name)
		.run(as_dict=True)
	)


def _refund_plan(profile, customer):
	credit = _get_customer_credit(profile, customer)
	debts = _all_customer_debts(profile, customer)
	total_debt = flt(sum(flt(d.outstanding_amount) for d in debts), 2)
	offset = flt(min(credit["total"], total_debt), 2)
	return {
		"credit": credit,
		"debts": debts,
		"total_debt": total_debt,
		"offset_amount": offset,
		"refund_amount": flt(credit["total"] - offset, 2),
	}


@frappe.whitelist()
def get_refund_preview(pos_profile, customer):
	"""Trả lại tiền dư: tiền dư bao nhiêu, trừ nợ bao nhiêu, trả khách bao nhiêu."""
	profile = _check_access(pos_profile, "refund")
	_check_customer_scope(profile, customer)
	return _refund_plan(profile, customer)


def _pair_offsets(credits, debts):
	"""Ghép tiền dư (cũ trước) với đơn nợ (cũ trước): [(credit_invoice, debt_invoice, amount)]."""
	credit_queue = [[c["invoice"], flt(c["credit"], 2)] for c in credits]
	pairs = []
	for debt in debts:
		need = flt(debt.outstanding_amount, 2)
		while need > 0.004 and credit_queue:
			take = flt(min(need, credit_queue[0][1]), 2)
			pairs.append((credit_queue[0][0], debt.name, take))
			need = flt(need - take, 2)
			credit_queue[0][1] = flt(credit_queue[0][1] - take, 2)
			if credit_queue[0][1] <= 0.004:
				credit_queue.pop(0)
	return pairs, [c for c in credit_queue if c[1] > 0.004]


def _make_offset_journal_entry(profile, customer, pairs, debit_to, debt_collection_id, remark, shift):
	cost_center = profile.get("cost_center") or frappe.get_cached_value("Company", profile.company, "cost_center")
	je = frappe.new_doc("Journal Entry")
	je.voucher_type = "Journal Entry"
	je.posting_date = nowdate()
	je.company = profile.company
	je.cheque_no = debt_collection_id[:140]
	je.cheque_date = nowdate()
	# Gắn quầy / ca / lần thu để chỉ huỷ, in đúng bút toán của lần thu này
	je.posa_debt_collection_id = debt_collection_id
	je.posa_pos_profile = profile.name
	je.posa_pos_opening_shift = shift
	je.user_remark = remark
	for credit_invoice, debt_invoice, amount in pairs:
		# Nợ 131 theo đơn đang dư (giảm số âm) / Có 131 theo đơn đang nợ
		je.append(
			"accounts",
			{
				"account": debit_to,
				"party_type": "Customer",
				"party": customer,
				"reference_type": "Sales Invoice",
				"reference_name": credit_invoice,
				"debit_in_account_currency": amount,
				"cost_center": cost_center,
			},
		)
		je.append(
			"accounts",
			{
				"account": debit_to,
				"party_type": "Customer",
				"party": customer,
				"reference_type": "Sales Invoice",
				"reference_name": debt_invoice,
				"credit_in_account_currency": amount,
				"cost_center": cost_center,
			},
		)
	je.flags.ignore_permissions = True
	frappe.flags.ignore_account_permission = True
	je.insert()
	je.submit()
	return je


def _make_refund_payment_entry(profile, shift, customer, mode_of_payment, credits, debit_to, debt_collection_id, remark):
	amount = flt(sum(c[1] for c in credits), 2)
	pe = frappe.new_doc("Payment Entry")
	pe.payment_type = "Pay"
	pe.posting_date = nowdate()
	pe.company = profile.company
	pe.party_type = "Customer"
	pe.party = customer
	pe.mode_of_payment = mode_of_payment
	pe.paid_from = _mode_account(mode_of_payment, profile.company)
	pe.paid_to = debit_to
	pe.paid_from_account_currency = frappe.get_cached_value("Account", pe.paid_from, "account_currency")
	pe.paid_to_account_currency = frappe.get_cached_value("Account", debit_to, "account_currency")
	pe.paid_amount = amount
	pe.received_amount = amount
	pe.source_exchange_rate = 1
	pe.target_exchange_rate = 1
	pe.reference_no = debt_collection_id[:140]
	pe.reference_date = nowdate()
	pe.posa_pos_opening_shift = shift
	pe.posa_pos_profile = profile.name
	pe.posa_debt_collection_id = debt_collection_id
	pe.remarks = remark
	if profile.get("cost_center"):
		pe.cost_center = profile.cost_center
	for invoice, credit in credits:
		# Phiếu chi cho khách: phân bổ ÂM vào đơn đang dư (ERPNext v15 chỉ nhận cách này)
		pe.append(
			"references",
			{
				"reference_doctype": "Sales Invoice",
				"reference_name": invoice,
				"allocated_amount": -credit,
				"outstanding_amount": -credit,
			},
		)
	pe.flags.ignore_permissions = True
	frappe.flags.ignore_account_permission = True
	pe.insert()
	pe.submit()
	return pe


@frappe.whitelist()
def refund_customer_credit(pos_profile, customer, mode_of_payment, expected_refund, debt_collection_id, note=None):
	"""Trả lại tiền dư cho khách tại quầy.

	1. Cấn trừ tiền dư vào mọi đơn còn nợ của khách tại quầy (Journal Entry, không có tiền).
	2. Phần dư còn lại chi cho khách bằng một phiếu chi (Payment Entry Pay) gắn ca đang mở,
	   nên đóng ca trừ đúng số tiền đã chi theo hình thức.
	`expected_refund` là số thu ngân đã thấy trên màn hình: lệch với số tính lại thì chặn.
	"""
	profile = _check_access(pos_profile, "refund")
	_check_customer_scope(profile, customer)
	debt_collection_id = (debt_collection_id or "").strip()
	if not debt_collection_id:
		frappe.throw(_("Missing debt collection ID"))
	if not (note or "").strip():
		frappe.throw(_("Please enter a note for the refund"))

	existing = _existing_collection(debt_collection_id, profile, customer)
	if existing or frappe.db.exists("Journal Entry", {"posa_debt_collection_id": debt_collection_id, "docstatus": 1}):
		return {"debt_collection_id": debt_collection_id, "duplicate": True, "payment_entries": existing}

	shift = _get_open_shift(profile.name)
	if not shift:
		frappe.throw(_("You need an open POS shift at {0} to refund customer credit").format(profile.name))

	if mode_of_payment not in _profile_modes(profile) or cint(
		frappe.get_cached_value("Mode of Payment", mode_of_payment, "is_wallet_payment")
	):
		frappe.throw(_("Mode of Payment {0} cannot be used to refund at this POS").format(mode_of_payment))

	# Khoá mọi hoá đơn của khách tại quầy rồi mới tính lại
	si = DocType("Sales Invoice")
	(
		frappe.qb.from_(si)
		.select(si.name)
		.where(si.customer == customer)
		.where(si.pos_profile == profile.name)
		.where(si.docstatus == 1)
		.for_update()
		.run()
	)

	plan = _refund_plan(profile, customer)
	if plan["credit"]["total"] <= 0:
		frappe.throw(_("Customer {0} has no credit at this POS").format(customer), DebtChangedError)
	if abs(plan["refund_amount"] - flt(expected_refund)) > AMOUNT_TOLERANCE:
		frappe.throw(
			_("Customer credit has changed (refund is now {0}). Reload and try again.").format(
				frappe.format_value(plan["refund_amount"], {"fieldtype": "Currency"})
			),
			DebtChangedError,
		)
	max_amount = flt(profile.get("posa_debt_max_amount"))
	if max_amount > 0 and plan["refund_amount"] > max_amount:
		frappe.throw(
			_("Refund {0} exceeds the limit {1} per collection at this POS").format(
				frappe.format_value(plan["refund_amount"], {"fieldtype": "Currency"}),
				frappe.format_value(max_amount, {"fieldtype": "Currency"}),
			)
		)

	debit_tos = {d.debit_to for d in plan["debts"]} | {
		frappe.db.get_value("Sales Invoice", c["invoice"], "debit_to") for c in plan["credit"]["documents"]
	}
	if len(debit_tos) != 1:
		frappe.throw(_("Customer invoices use different receivable accounts; refund cannot be done at the POS"))
	debit_to = debit_tos.pop()

	remark = _("Customer credit refund at POS {0} ({1}): {2}").format(profile.name, debt_collection_id, note.strip())
	pairs, remaining_credits = _pair_offsets(plan["credit"]["documents"], plan["debts"])

	journal_entry = None
	if pairs:
		journal_entry = _make_offset_journal_entry(profile, customer, pairs, debit_to, debt_collection_id, remark, shift).name

	payment_entry = None
	if remaining_credits:
		payment_entry = _make_refund_payment_entry(
			profile, shift, customer, mode_of_payment, remaining_credits, debit_to, debt_collection_id, remark
		).name

	return {
		"debt_collection_id": debt_collection_id,
		"duplicate": False,
		"journal_entry": journal_entry,
		"payment_entry": payment_entry,
		"credit_total": plan["credit"]["total"],
		"offset_amount": plan["offset_amount"],
		"refund_amount": plan["refund_amount"],
		"mode_of_payment": mode_of_payment,
		"offsets": [{"credit_invoice": c, "debt_invoice": d, "amount": a} for c, d, a in pairs],
	}


# ---------------------------------------------------------------------------
# Hook Payment Entry
# ---------------------------------------------------------------------------


def validate_payment_entry_shift(doc, method=None):
	"""Phiếu thu gắn ca POS: ca phải đang mở và thuộc đúng quầy."""
	if doc.doctype != "Payment Entry":
		return
	shift = doc.get("posa_pos_opening_shift")
	if not shift:
		return
	data = frappe.db.get_value(
		"POS Opening Shift", shift, ["status", "docstatus", "pos_profile", "pos_closing_shift", "user"], as_dict=True
	)
	if not data or data.docstatus != 1 or data.status != "Open" or data.pos_closing_shift:
		frappe.throw(_("POS shift {0} is not open").format(shift))
	# Chỉ chủ ca được ghi phiếu vào ca (webhook QR đã set_user về thu ngân tạo mã)
	if frappe.session.user != "Administrator" and data.user != frappe.session.user:
		frappe.throw(_("POS shift {0} belongs to another cashier").format(shift))
	if doc.get("posa_pos_profile") and data.pos_profile != doc.posa_pos_profile:
		frappe.throw(_("POS shift {0} does not belong to POS Profile {1}").format(shift, doc.posa_pos_profile))


# ---------------------------------------------------------------------------
# Chặn hoá đơn còn nợ ở quầy không bán chịu
# ---------------------------------------------------------------------------


def validate_credit_sale_allowed(invoice_doc, redeemed_credit=0):
	"""Gọi trong submit_invoice sau save(), trước submit(). Áp cả hoá đơn đồng bộ offline.

	Giữ đúng hai ô có sẵn của POS Settings, mỗi ô lo một việc:
	- khách chưa trả gì (ghi nợ toàn bộ) cần "Cho phép bán chịu";
	- khách trả một phần cần "Cho phép thanh toán một phần" hoặc "Cho phép bán chịu".
	Quầy không có / đang tắt POS Settings: coi như tắt cả hai ô (giống giao diện).

	Phần lệch làm tròn ≤ CREDIT_SALE_TOLERANCE không tính là nợ. Tiền dư khách dùng
	để trả (redeemed_credit) được tính là đã trả vì nó chỉ cấn trừ sau khi submit.
	"""
	if invoice_doc.doctype != "Sales Invoice" or invoice_doc.get("is_return"):
		return
	pos_profile = invoice_doc.get("pos_profile")
	if not pos_profile:
		return
	unpaid = flt(invoice_doc.get("outstanding_amount")) - flt(redeemed_credit)
	if unpaid <= CREDIT_SALE_TOLERANCE:
		return
	# Đọc như giao diện: không có / đang tắt POS Settings thì dùng mặc định (tắt cả hai ô)
	from pos_next.api.pos_profile import get_pos_settings

	settings = frappe._dict(get_pos_settings(pos_profile))
	if cint(settings.allow_credit_sale):
		return

	paid = flt(invoice_doc.get("paid_amount")) + flt(redeemed_credit)
	if paid > CREDIT_SALE_TOLERANCE:
		if cint(settings.allow_partial_payment):
			return
		frappe.throw(
			_("POS Profile {0} does not allow partial payment or credit sales. The invoice must be paid in full (still unpaid {1}).").format(
				pos_profile, frappe.format_value(unpaid, {"fieldtype": "Currency"})
			),
			title=_("Partial Payment Not Allowed"),
		)
	if not cint(settings.allow_partial_payment):
		frappe.throw(
			_("POS Profile {0} does not allow partial payment or credit sales. The invoice must be paid in full (still unpaid {1}).").format(
				pos_profile, frappe.format_value(unpaid, {"fieldtype": "Currency"})
			),
			title=_("Credit Sale Not Allowed"),
		)
	frappe.throw(
		_("POS Profile {0} does not allow credit sales. The customer must pay at least part of the invoice (unpaid {1}).").format(
			pos_profile, frappe.format_value(unpaid, {"fieldtype": "Currency"})
		),
		title=_("Credit Sale Not Allowed"),
	)


# ---------------------------------------------------------------------------
# Thu nợ bằng QR SePay: tạo mã chờ tiền, webhook tạo phiếu thu khi tiền về
# ---------------------------------------------------------------------------

DEBT_QR_PREFIX = "TN"
DEBT_QR_TTL = 30 * 60  # giây


def _debt_qr_cache_key(code):
	return f"pos_next:debt_qr:{code}"


def _debt_qr_code(debt_collection_id):
	return DEBT_QR_PREFIX + "".join(ch for ch in debt_collection_id if ch.isalnum())[:10].upper()


def _bank_mode_of_payment(profile):
	"""Hình thức ghi nhận tiền QR: hình thức chuyển khoản của quầy (không phải ví)."""
	modes = [m for m in _profile_modes(profile) if not cint(frappe.get_cached_value("Mode of Payment", m, "is_wallet_payment"))]
	for preferred in ("Wire Transfer", "Chuyển khoản"):
		if preferred in modes:
			return preferred
	for m in modes:
		if frappe.get_cached_value("Mode of Payment", m, "type") == "Bank":
			return m
	return None


@frappe.whitelist()
def create_debt_qr(pos_profile, customer, allocations, payments, qr_amount, debt_collection_id):
	"""Tạo mã QR SePay cho phần thu bằng QR của một lần thu nợ.

	`payments` là các hình thức KHÁC (tiền mặt...) trong cùng lần thu: chưa tạo phiếu ngay,
	mà tạo cùng lúc với phiếu QR khi SePay báo tiền về, để cả lần thu đi chung một transaction.
	"""
	from pos_next.api.sepay import VIETQR_BASE, _get_sepay_settings

	profile = _check_access(pos_profile, "collect")
	_check_customer_scope(profile, customer)
	settings = _get_sepay_settings(pos_profile)
	if not settings:
		frappe.throw(_("SePay is not configured for this POS Profile"))
	mode = _bank_mode_of_payment(profile)
	if not mode:
		frappe.throw(_("POS Profile {0} has no bank transfer Mode of Payment to record QR payments").format(pos_profile))

	shift = _get_open_shift(profile.name)
	if not shift:
		frappe.throw(_("You need an open POS shift at {0} to collect debts").format(profile.name))

	qr_amount = flt(qr_amount, 0)
	if qr_amount <= 0:
		frappe.throw(_("QR amount must be greater than zero"))
	debt_collection_id = (debt_collection_id or "").strip()
	if not debt_collection_id:
		frappe.throw(_("Missing debt collection ID"))

	others = [p for p in _parse(payments) if flt(p.get("amount")) > 0]
	all_payments = others + [{"mode_of_payment": mode, "amount": qr_amount}]
	if len({p["mode_of_payment"] for p in all_payments}) != len(all_payments):
		frappe.throw(_("Mode of Payment {0} appears more than once").format(mode))
	allocations = _parse(allocations)
	_validate_payments(profile, customer, all_payments)
	# Tiền QR về đúng bao nhiêu thì phiếu thu ghi đúng bấy nhiêu: phân bổ phải khớp tuyệt đối
	allocated = flt(sum(flt(a.get("amount")) for a in allocations), 2)
	paid = flt(sum(flt(p["amount"]) for p in all_payments), 2)
	if abs(allocated - paid) > 0.004:
		frappe.throw(
			_("Total payments {0} must equal the amount collected {1}").format(
				frappe.format_value(paid, {"fieldtype": "Currency"}),
				frappe.format_value(allocated, {"fieldtype": "Currency"}),
			)
		)

	code = _debt_qr_code(debt_collection_id)
	frappe.cache.set_value(
		_debt_qr_cache_key(code),
		{
			"pos_profile": profile.name,
			"customer": customer,
			"allocations": allocations,
			"payments": all_payments,
			"qr_amount": qr_amount,
			"debt_collection_id": debt_collection_id,
			"user": frappe.session.user,
			"shift": shift,
		},
		expires_in_sec=DEBT_QR_TTL,
	)

	params = {
		"acc": settings.sepay_bank_account,
		"bank": settings.sepay_bank_code,
		"amount": int(qr_amount),
		"des": code,
		"template": "compact",
	}
	return {
		"qr_url": VIETQR_BASE + "?" + "&".join(f"{k}={v}" for k, v in params.items()),
		"content": code,
		"amount": int(qr_amount),
		"account_number": settings.sepay_bank_account,
		"bank_code": settings.sepay_bank_code,
		"account_holder": settings.sepay_account_holder or "",
		"mode_of_payment": mode,
		"expires_in": DEBT_QR_TTL,
	}


@frappe.whitelist()
def check_debt_qr_status(pos_profile, debt_collection_id):
	"""Client hỏi định kỳ: tiền QR đã về và phiếu thu đã tạo chưa."""
	profile = _check_access(pos_profile, "collect")
	entries = _existing_collection(debt_collection_id)
	if entries and entries[0].posa_pos_profile != profile.name:
		frappe.throw(_("Debt collection ID {0} is already used. Please reload and try again.").format(debt_collection_id))
	if entries:
		customer = entries[0].party
		_check_customer_scope(profile, customer)
		return {"paid": True, **_collection_result(profile, customer, debt_collection_id, entries)}
	code = _debt_qr_code(debt_collection_id)
	failed = frappe.db.get_value(
		"SePay Transaction Log", {"debt_collection_id": debt_collection_id, "status": "Unmatched"}, "message"
	) if frappe.db.table_exists("SePay Transaction Log") else None
	return {
		"paid": False,
		"pending": bool(frappe.cache.get_value(_debt_qr_cache_key(code))),
		"error": failed,
	}


@frappe.whitelist()
def cancel_debt_qr(pos_profile, debt_collection_id):
	_check_access(pos_profile, "collect")
	frappe.cache.delete_value(_debt_qr_cache_key(_debt_qr_code(debt_collection_id)))
	return True


def find_debt_qr_code(content):
	"""Mã thu nợ trong nội dung chuyển khoản (vd "... TN3F9A1C2B7D ...")."""
	import re

	m = re.search(rf"{DEBT_QR_PREFIX}([0-9A-Z]{{10}})", (content or "").upper())
	return DEBT_QR_PREFIX + m.group(1) if m else None


def process_debt_qr_payment(code, amount):
	"""Gọi từ webhook SePay. Trả (status, message, debt_collection_id).

	Chạy dưới tên thu ngân đã tạo mã để phiếu thu mang đúng người thu và ca.
	"""
	request = frappe.cache.get_value(_debt_qr_cache_key(code))
	if not request:
		return "Unmatched", f"QR code {code} not found or expired", None

	request = frappe._dict(request)
	if abs(flt(amount, 0) - flt(request.qr_amount, 0)) > 0.5:
		return "Unmatched", f"Amount {amount} differs from QR amount {request.qr_amount}", request.debt_collection_id

	old_user = frappe.session.user
	try:
		frappe.set_user(request.user)
		profile = _get_profile(request.pos_profile)
		_collect(
			profile,
			request.customer,
			request.allocations,
			request.payments,
			request.debt_collection_id,
			request.shift,
		)
	except Exception as e:
		frappe.db.rollback()
		return "Unmatched", f"Could not create Payment Entry: {e}", request.debt_collection_id
	finally:
		frappe.set_user(old_user)

	frappe.cache.delete_value(_debt_qr_cache_key(code))
	return "Processed", None, request.debt_collection_id


# ---------------------------------------------------------------------------
# Xuất Excel, in phiếu thu / phiếu chi
# ---------------------------------------------------------------------------


@frappe.whitelist()
def export_debts(pos_profile, filters=None):
	"""Xuất Excel từng đơn nợ theo đúng bộ lọc đang xem (nhãn "Có tiền dư" không xuất Excel)."""
	from io import BytesIO

	from openpyxl import Workbook
	from openpyxl.styles import Alignment, Border, Font, PatternFill, Side
	from openpyxl.utils import get_column_letter

	profile = _check_access(pos_profile, "view")
	filters = _parse(filters)
	credit_days = cint(profile.get("posa_credit_days"))
	sheet = _debt_sheet(profile, filters, credit_days)
	columns, table = sheet["columns"], sheet["rows"]

	wb = Workbook()
	ws = wb.active
	ws.title = sheet["title"][:31]
	bold = Font(bold=True)
	thin = Side(style="thin", color="D1D5DB")
	border = Border(left=thin, right=thin, top=thin, bottom=thin)

	# Dòng tiêu đề: quầy, bộ lọc đang áp, ngày xuất
	ws.cell(row=1, column=1, value=sheet["title"] + " · " + profile.name).font = Font(bold=True, size=14)
	ws.cell(row=2, column=1, value=_describe_filters(filters, credit_days)).font = Font(italic=True, color="6B7280")
	ws.cell(row=3, column=1, value=_("Exported {0} by {1}").format(
		frappe.utils.format_datetime(frappe.utils.now_datetime(), "dd/MM/yyyy HH:mm"),
		frappe.db.get_value("User", frappe.session.user, "full_name") or frappe.session.user,
	)).font = Font(color="6B7280")

	header_row = 5
	for idx, (label, width, _kind) in enumerate(columns, start=1):
		cell = ws.cell(row=header_row, column=idx, value=label)
		cell.font = Font(bold=True, color="FFFFFF")
		cell.fill = PatternFill("solid", fgColor="C4161C")
		cell.alignment = Alignment(horizontal="center", vertical="center", wrap_text=True)
		cell.border = border
		ws.column_dimensions[get_column_letter(idx)].width = width
	ws.row_dimensions[header_row].height = 30

	r_idx = header_row
	for values, highlight in table:
		r_idx += 1
		for c_idx, (value, (_label, _width, kind)) in enumerate(zip(values, columns), start=1):
			cell = ws.cell(row=r_idx, column=c_idx, value=value)
			cell.border = border
			if kind == "date":
				cell.number_format = "DD/MM/YYYY"
				cell.alignment = Alignment(horizontal="center")
			elif kind == "money":
				cell.number_format = "#,##0.##"
			elif kind == "int":
				cell.alignment = Alignment(horizontal="center")
		if highlight:
			ws.cell(row=r_idx, column=highlight).font = Font(bold=True, color="B91C1C")

	# Dòng tổng
	total_row = r_idx + 1
	ws.cell(row=total_row, column=1, value=_("Total")).font = bold
	ws.cell(row=total_row, column=2, value=sheet["count_text"])
	for c_idx, (_label, _width, kind) in enumerate(columns, start=1):
		if kind != "money":
			continue
		cell = ws.cell(row=total_row, column=c_idx, value=flt(sum(flt(ws.cell(row=x, column=c_idx).value) for x in range(header_row + 1, total_row)), 2))
		cell.number_format = "#,##0.##"
		cell.font = bold
	for c_idx in range(1, len(columns) + 1):
		ws.cell(row=total_row, column=c_idx).fill = PatternFill("solid", fgColor="FEF3C7")
		ws.cell(row=total_row, column=c_idx).border = border

	ws.freeze_panes = ws.cell(row=header_row + 1, column=1)
	ws.auto_filter.ref = f"A{header_row}:{get_column_letter(len(columns))}{max(r_idx, header_row)}"

	out = BytesIO()
	wb.save(out)
	import unicodedata

	slug = unicodedata.normalize("NFKD", profile.name.replace("đ", "d").replace("Đ", "D")).encode("ascii", "ignore").decode()
	frappe.response["filename"] = f"{sheet['file_prefix']}-{frappe.scrub(slug)}-{nowdate()}.xlsx"
	frappe.response["filecontent"] = out.getvalue()
	frappe.response["type"] = "binary"


def _debt_sheet(profile, filters, credit_days):
	"""Dữ liệu Excel từng đơn nợ theo bộ lọc."""
	si = DocType("Sales Invoice")
	rows = (
		_apply_filters(_base_debt_query(profile, si), si, profile, filters)
		.select(*_invoice_fields(si))
		.orderby(si.customer)
		.orderby(si.posting_date)
		.run(as_dict=True)
	)
	today = getdate(nowdate())
	status_label = {STATUS_OVERDUE: _("Overdue"), STATUS_PARTLY_PAID: _("Paid in part"), STATUS_UNPAID: _("Unpaid"), STATUS_PAID: _("Paid")}
	mobiles = dict(
		frappe.get_all(
			"Customer", filters={"name": ["in", list({r.customer for r in rows}) or [""]]}, fields=["name", "mobile_no"], as_list=True
		)
	)
	sellers = _seller_names([r.name for r in rows], _uses_sales_persons(profile.name))
	table = []
	for r in rows:
		_decorate_invoice(r, credit_days, today)
		values = [
			r.customer, r.customer_name, mobiles.get(r.customer), r.name, getdate(r.posting_date), getdate(r.due_date),
			r.age_days, status_label[r.status], sellers.get(r.name), flt(r.invoice_total), flt(r.paid_amount), flt(r.outstanding_amount),
		]
		table.append((values, 8 if r.status == STATUS_OVERDUE else None))
	return {
		"title": _("Customer Debts"),
		"file_prefix": "cong-no",
		"count_text": _("{0} customers · {1} invoices").format(len({r.customer for r in rows}), len(rows)),
		"columns": [
			(_("Customer"), 16, None),
			(_("Customer Name"), 28, None),
			(_("Mobile No"), 15, None),
			(_("Invoice"), 22, None),
			(_("Posting Date"), 13, "date"),
			(_("Due Date"), 13, "date"),
			(_("Days"), 8, "int"),
			(_("Status"), 16, None),
			(_("Sold by"), 22, None),
			(_("Invoice Total"), 15, "money"),
			(_("Paid"), 15, "money"),
			(_("Outstanding"), 15, "money"),
		],
		"rows": table,
	}


def _describe_filters(filters, credit_days):
	"""Mô tả bộ lọc trên đầu file Excel để người đọc biết danh sách lấy theo điều kiện gì."""
	parts = []
	status = filters.get("status")
	parts.append({STATUS_OVERDUE: _("Overdue"), STATUS_PARTLY_PAID: _("Paid in part")}.get(status, _("Outstanding")))
	if filters.get("from_date") or filters.get("to_date"):
		from_date = frappe.utils.formatdate(filters.get("from_date"), "dd/MM/yyyy") if filters.get("from_date") else "…"
		to_date = frappe.utils.formatdate(filters.get("to_date"), "dd/MM/yyyy") if filters.get("to_date") else "…"
		parts.append(_("Posting date {0} – {1}").format(from_date, to_date))
	if filters.get("seller"):
		parts.append(_("Sold by {0}").format(frappe.db.get_value("User", filters.get("seller"), "full_name") or filters.get("seller")))
	if filters.get("search"):
		parts.append(_("Search \"{0}\"").format(filters.get("search")))
	parts.append(_("Due date = posting date + {0} days").format(credit_days))
	return " · ".join(parts)


@frappe.whitelist()
def print_debt_receipt(pos_profile, debt_collection_id):
	"""Phiếu thu nợ / phiếu chi trả tiền dư khổ 80mm của một lần thu (gom mọi phiếu cùng mã)."""
	profile = _check_access(pos_profile, "view")
	entries = frappe.get_all(
		"Payment Entry",
		filters={"posa_debt_collection_id": debt_collection_id, "docstatus": 1, "posa_pos_profile": profile.name},
		fields=["name", "payment_type", "mode_of_payment", "paid_amount", "party", "party_name", "owner", "creation", "posa_pos_opening_shift", "remarks"],
		order_by="creation",
	)
	journal = frappe.db.get_value(
		"Journal Entry",
		{"posa_debt_collection_id": debt_collection_id, "posa_pos_profile": profile.name, "docstatus": 1},
		["name", "creation", "owner", "user_remark"],
		as_dict=True,
	)
	if not entries and not journal:
		frappe.throw(_("No receipt found for {0}").format(debt_collection_id))

	is_refund = any(e.payment_type == "Pay" for e in entries) or (journal and not entries)
	customer = entries[0].party if entries else frappe.db.get_value(
		"Journal Entry Account", {"parent": journal.name, "party_type": "Customer"}, "party"
	)
	invoices = []
	if entries:
		ref_rows = frappe.get_all(
			"Payment Entry Reference",
			filters={"parent": ["in", [e.name for e in entries]], "reference_doctype": "Sales Invoice"},
			fields=["reference_name", "allocated_amount"],
		)
		agg = {}
		for r in ref_rows:
			agg[r.reference_name] = flt(agg.get(r.reference_name)) + flt(r.allocated_amount)
		invoices = [{"invoice": k, "amount": v} for k, v in agg.items()]
	offsets = []
	if journal:
		offsets = frappe.get_all(
			"Journal Entry Account",
			filters={"parent": journal.name, "credit_in_account_currency": [">", 0]},
			fields=["reference_name", "credit_in_account_currency as amount"],
		)
	first = entries[0] if entries else journal
	remaining = _query_customer_debts(profile.name, customer) if customer else []
	context = {
		"profile": profile,
		"company": profile.company,
		"is_refund": is_refund,
		"debt_collection_id": debt_collection_id,
		"customer": customer,
		"customer_name": frappe.db.get_value("Customer", customer, "customer_name") if customer else "",
		"entries": entries,
		"invoices": invoices,
		"offsets": offsets,
		"total": flt(sum(flt(e.paid_amount) for e in entries), 2),
		"remaining": flt(sum(flt(r.outstanding_amount) for r in remaining), 2),
		"cashier": frappe.db.get_value("User", first.owner, "full_name") or first.owner,
		"created": first.creation,
		"shift": entries[0].posa_pos_opening_shift if entries else "",
		"note": (journal.user_remark if journal else entries[0].remarks) if is_refund else "",
		"fmt": lambda v: frappe.format_value(v, {"fieldtype": "Currency"}),
	}
	html = frappe.render_template("pos_next/templates/debt_receipt.html", context)
	# Trả thẳng trang HTML để trình duyệt hiện và mở hộp in (kiểu "binary" sẽ thành tải file)
	from werkzeug.wrappers import Response

	return Response(html, content_type="text/html; charset=utf-8")


@frappe.whitelist()
def get_customer_collection_history(pos_profile, customer, limit=50):
	"""Các lần thu nợ / trả lại tiền dư của một khách tại quầy, mới nhất trước.

	Gom các Payment Entry cùng posa_debt_collection_id thành một lần (một phiếu in).
	"""
	profile = _check_access(pos_profile, "view")
	_check_customer_scope(profile, customer)
	entries = frappe.get_all(
		"Payment Entry",
		filters={
			"party_type": "Customer",
			"party": customer,
			"posa_pos_profile": profile.name,
			"posa_debt_collection_id": ["is", "set"],
			"docstatus": ["in", [1, 2]],
		},
		fields=[
			"name",
			"payment_type",
			"mode_of_payment",
			"paid_amount",
			"owner",
			"creation",
			"posting_date",
			"posa_debt_collection_id",
			"posa_pos_opening_shift",
			"docstatus",
		],
		order_by="creation desc",
		limit_page_length=cint(limit) * 3,
	)
	refs = {}
	if entries:
		for r in frappe.get_all(
			"Payment Entry Reference",
			filters={"parent": ["in", [e.name for e in entries]], "reference_doctype": "Sales Invoice"},
			fields=["parent", "reference_name", "allocated_amount"],
		):
			refs.setdefault(r.parent, []).append(r)

	groups = {}
	order = []
	names = {}
	for e in entries:
		key = e.posa_debt_collection_id
		if key not in groups:
			if e.owner not in names:
				names[e.owner] = frappe.db.get_value("User", e.owner, "full_name") or e.owner
			groups[key] = {
				"debt_collection_id": key,
				"is_refund": e.payment_type == "Pay",
				"creation": e.creation,
				"posting_date": e.posting_date,
				"cashier": names[e.owner],
				"shift": e.posa_pos_opening_shift,
				"cancelled": e.docstatus == 2,
				"payments": [],
				"invoices": {},
				"total": 0,
			}
			order.append(key)
		g = groups[key]
		g["payments"].append({"mode_of_payment": e.mode_of_payment, "amount": e.paid_amount, "payment_entry": e.name})
		g["total"] = flt(g["total"] + flt(e.paid_amount), 2)
		for r in refs.get(e.name, []):
			g["invoices"][r.reference_name] = flt(g["invoices"].get(r.reference_name, 0) + abs(flt(r.allocated_amount)), 2)

	can_cancel = _has_debt_access(profile.name, "cancel")
	open_shifts = {}
	result = []
	for key in order[: cint(limit)]:
		g = groups[key]
		g["invoices"] = [{"invoice": k, "amount": v} for k, v in g["invoices"].items()]
		if g["cancelled"]:
			g["cancel_info"] = _cancel_info(key)
		shift = g["shift"]
		if shift and shift not in open_shifts:
			open_shifts[shift] = _shift_is_open(shift)
		g["can_cancel"] = bool(can_cancel and not g["cancelled"] and shift and open_shifts.get(shift))
		g["shift_closed"] = bool(shift and not open_shifts.get(shift))
		result.append(g)
	return result


def _shift_is_open(shift):
	data = frappe.db.get_value("POS Opening Shift", shift, ["status", "docstatus", "pos_closing_shift"], as_dict=True)
	return bool(data and data.docstatus == 1 and data.status == "Open" and not data.pos_closing_shift)


def _cancel_info(debt_collection_id):
	"""Ai huỷ, lúc nào, lý do — đọc từ Comment ghi lúc huỷ."""
	pe = frappe.db.get_value("Payment Entry", {"posa_debt_collection_id": debt_collection_id}, "name")
	row = frappe.db.get_value(
		"Comment",
		{"reference_doctype": "Payment Entry", "reference_name": pe, "comment_type": "Comment", "content": ["like", "%[POS]%"]},
		["owner", "creation", "content"],
		as_dict=True,
		order_by="creation desc",
	)
	if not row:
		return None
	import re

	return {
		"by": frappe.db.get_value("User", row.owner, "full_name") or row.owner,
		"at": row.creation,
		"reason": re.sub(r"<[^>]+>", "", row.content).split("|", 1)[-1].strip(),
	}


@frappe.whitelist()
def cancel_debt_collection(pos_profile, debt_collection_id, reason):
	"""Huỷ cả một lần thu nợ / trả lại tiền dư tại quầy (mọi chứng từ cùng mã lần thu).

	Chỉ huỷ được khi ca của lần thu còn mở: ca đã đóng thì số đóng ca đã chốt, phải huỷ ở desk.
	ERPNext tự trả số nợ về các đơn khi huỷ phiếu. Ghi vết bằng Comment trên từng chứng từ.
	"""
	profile = _check_access(pos_profile, "cancel")
	reason = (reason or "").strip()
	if not reason:
		frappe.throw(_("Please enter a reason for cancelling"))

	entries = frappe.get_all(
		"Payment Entry",
		filters={"posa_debt_collection_id": debt_collection_id, "posa_pos_profile": profile.name, "docstatus": 1},
		fields=["name", "posa_pos_opening_shift", "paid_amount", "party"],
		order_by="creation desc",
	)
	journal = frappe.db.get_value(
		"Journal Entry",
		{"posa_debt_collection_id": debt_collection_id, "posa_pos_profile": profile.name, "docstatus": 1},
		["name", "posa_pos_opening_shift"],
		as_dict=True,
	)
	if not entries and not journal:
		frappe.throw(_("No active debt collection {0} at this POS").format(debt_collection_id))

	shifts = {e.posa_pos_opening_shift for e in entries if e.posa_pos_opening_shift}
	if journal:
		shifts.add(journal.posa_pos_opening_shift)
	for shift in shifts:
		# Bút toán không có ca (không đúng luồng POS) thì cũng không cho huỷ ở quầy
		if not shift:
			frappe.throw(_("This collection has no POS shift. Ask the accountant to cancel it at the desk."))
		if not _shift_is_open(shift):
			frappe.throw(
				_("Shift {0} is already closed. Ask the accountant to cancel this collection at the desk.").format(shift)
			)

	user_name = frappe.db.get_value("User", frappe.session.user, "full_name") or frappe.session.user
	note = _("[POS] Debt collection cancelled at {0} by {1} | {2}").format(profile.name, user_name, reason)
	frappe.flags.ignore_account_permission = True
	cancelled = []
	for e in entries:
		doc = frappe.get_doc("Payment Entry", e.name)
		doc.flags.ignore_permissions = True
		doc.cancel()
		doc.add_comment("Comment", note)
		cancelled.append(e.name)
	if journal:
		je = frappe.get_doc("Journal Entry", journal.name)
		je.flags.ignore_permissions = True
		je.cancel()
		je.add_comment("Comment", note)
		cancelled.append(journal.name)

	customer = entries[0].party if entries else None
	return {
		"debt_collection_id": debt_collection_id,
		"cancelled": cancelled,
		"customer": customer,
		"remaining_outstanding": flt(sum(flt(r.outstanding_amount) for r in _query_customer_debts(profile.name, customer)), 2)
		if customer
		else None,
	}
