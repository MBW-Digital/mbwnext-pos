# Copyright (c) 2026, BrainWise and contributors
# For license information, please see license.txt

"""
Cảnh báo công nợ khi chọn khách trên POS (PM-FEAT-00068).

Chỉ ĐỌC công nợ, không ghi gì. Danh sách đơn nợ lấy từ hàm dùng chung của chức năng
Thu nợ (`debt_collection._query_customer_debts`) để hai màn hình luôn cùng một con số:
cùng phạm vi quầy, cùng hạn thanh toán (ngày bán + POS Profile.posa_credit_days),
cùng ngưỡng ẩn nợ lẻ (posa_debt_hide_below).

Quyền ở đây theo POS Profile (user phải thuộc quầy), không theo User Permission chuẩn,
nên đọc bằng frappe.db / get_all sau khi đã kiểm user thuộc quầy.
"""

import frappe
from frappe import _
from frappe.utils import cint, date_diff, flt, getdate, now_datetime, today
from frappe.utils.nestedset import get_descendants_of

# Giới hạn số khách nạp sẵn cho chế độ mất mạng, tránh một quầy quá nhiều khách nợ làm chậm lúc mở ca
MAX_PRELOAD_CUSTOMERS = 1000


@frappe.whitelist()
def get_customer_debt_warning(pos_profile, customer):
	"""Công nợ của một khách tại quầy để hiện cảnh báo. Trả {show: False} khi không cần cảnh báo."""
	profile = _get_profile(pos_profile)
	return _build_warning(profile, customer)


@frappe.whitelist()
def get_profile_debtors(pos_profile):
	"""Mọi khách đang nợ tại quầy, nạp vào IndexedDB lúc mở ca để cảnh báo được khi mất mạng."""
	profile = _get_profile(pos_profile)
	if not profile.enabled:
		return {"enabled": False, "customers": [], "fetched_at": now_datetime()}

	customers = _candidate_debtors(profile)

	result = []
	for customer in customers:
		data = _build_warning(profile, customer)
		if data.get("show"):
			result.append(data)

	return {"enabled": True, "customers": result, "fetched_at": now_datetime()}


def _candidate_debtors(profile):
	"""Khách đáng cảnh báo tại quầy, lọc sẵn trong SQL trước khi giới hạn số lượng.

	Dùng cùng điều kiện với Thu nợ (quầy, company, phạm vi khách, ngưỡng ẩn nợ lẻ), rồi bỏ nhóm loại trừ
	và khách dưới ngưỡng, để giới hạn MAX_PRELOAD_CUSTOMERS không cắt mất khách thật sự cần cảnh báo.
	"""
	from frappe.query_builder import DocType
	from frappe.query_builder.functions import Sum

	from pos_next.api.debt_collection import _base_debt_query
	from pos_next.api.debt_collection import _get_profile as _get_collection_profile

	si = DocType("Sales Invoice")
	query = _base_debt_query(_get_collection_profile(profile.name), si)
	if profile.walk_in_customer:
		query = query.where(si.customer != profile.walk_in_customer)
	if profile.excluded_groups:
		customer = DocType("Customer")
		query = query.where(
			si.customer.notin(
				frappe.qb.from_(customer)
				.select(customer.name)
				.where(customer.customer_group.isin(list(profile.excluded_groups)))
			)
		)
	query = query.select(si.customer).groupby(si.customer)
	if profile.threshold > 0:
		query = query.having(Sum(si.outstanding_amount) >= profile.threshold)
	return [row[0] for row in query.orderby(Sum(si.outstanding_amount), order=frappe.qb.desc).limit(MAX_PRELOAD_CUSTOMERS).run()]


def _get_profile(pos_profile):
	"""Kiểm user thuộc quầy rồi đọc cấu hình cảnh báo của quầy."""
	if not pos_profile:
		frappe.throw(_("POS Profile is required"))

	if not frappe.db.exists("POS Profile User", {"parent": pos_profile, "user": frappe.session.user}):
		frappe.throw(_("You are not assigned to POS Profile {0}").format(pos_profile), frappe.PermissionError)

	values = frappe.db.get_value(
		"POS Profile",
		pos_profile,
		["name", "company", "customer", "disabled", "posa_enable_debt_warning", "posa_debt_warning_threshold"],
		as_dict=True,
	)
	if not values:
		frappe.throw(_("POS Profile {0} not found").format(pos_profile))

	excluded = frappe.get_all(
		"POS Profile Customer Group",
		filters={"parent": pos_profile, "parenttype": "POS Profile", "parentfield": "posa_debt_warning_excluded_groups"},
		pluck="customer_group",
	)
	# Loại nhóm cha thì loại luôn các nhóm con
	for group in list(excluded):
		excluded.extend(get_descendants_of("Customer Group", group))

	return frappe._dict(
		name=values.name,
		company=values.company,
		walk_in_customer=values.customer,
		# Quầy đã vô hiệu thì coi như tắt cảnh báo
		enabled=cint(values.posa_enable_debt_warning) and not cint(values.disabled),
		threshold=flt(values.posa_debt_warning_threshold),
		excluded_groups=set(excluded),
	)


def _build_warning(profile, customer):
	hidden = {"show": False, "customer": customer}
	if not profile.enabled or not customer or customer == profile.walk_in_customer:
		return hidden

	info = frappe.db.get_value("Customer", customer, ["customer_name", "mobile_no", "customer_group"], as_dict=True)
	if not info or info.customer_group in profile.excluded_groups:
		return hidden

	# Hàm dùng chung của chức năng Thu nợ: đã lọc theo quầy + company + phạm vi khách, đã áp ngưỡng ẩn nợ lẻ
	from pos_next.api.debt_collection import _has_debt_access, _query_customer_debts

	rows = _query_customer_debts(profile.name, customer) or []
	invoices = [_normalize(r) for r in rows]
	invoices.sort(key=lambda r: (r["posting_date"], r["name"]))

	total = sum(r["outstanding_amount"] for r in invoices)
	if total <= 0 or total < profile.threshold:
		return hidden

	credit_limit = flt(
		frappe.db.get_value(
			"Customer Credit Limit",
			{"parent": customer, "parenttype": "Customer", "company": profile.company},
			"credit_limit",
		)
	)

	return {
		"show": True,
		"customer": customer,
		"customer_name": info.customer_name,
		"mobile_no": info.mobile_no,
		"total_outstanding": total,
		"invoice_count": len(invoices),
		"overdue_count": sum(1 for r in invoices if r["is_overdue"]),
		"credit_limit": credit_limit,
		"over_limit": bool(credit_limit and total > credit_limit),
		"invoices": invoices,
		"can_collect": bool(_has_debt_access(profile.name, "collect")),
		"fetched_at": now_datetime(),
	}


def _normalize(row):
	"""Chuẩn hoá một dòng từ _query_customer_debts về đúng các khoá giao diện dùng."""
	row = frappe._dict(row)
	posting_date = getdate(row.posting_date)
	due_date = getdate(row.due_date) if row.due_date else posting_date
	outstanding = flt(row.outstanding_amount)
	# Quá hạn = chưa trả đồng nào và hôm nay đã qua hạn; ưu tiên cờ do chức năng 1 tính
	if row.get("is_overdue") is not None:
		is_overdue = bool(row.is_overdue)
	else:
		is_overdue = row.get("status") in ("Overdue", "Quá hạn")
	return {
		"name": row.name,
		"posting_date": str(posting_date),
		"due_date": str(due_date),
		"outstanding_amount": outstanding,
		"days": date_diff(today(), posting_date),
		"days_overdue": max(0, date_diff(today(), due_date)),
		"is_overdue": is_overdue,
		"partly_paid": row.get("status") in ("Partly Paid", "Đã trả một phần"),
	}
