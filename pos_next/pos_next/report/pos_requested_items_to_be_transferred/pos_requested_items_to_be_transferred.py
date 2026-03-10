import frappe
from frappe import _


def execute(filters=None):
	f = frappe._dict(filters or {})

	columns = [
		_("Material Request") + ":Link/Material Request:120",
		_("Date") + ":Date:100",
		_("Item Code") + ":Link/Item:120",
		_("Item Name") + "::150",
		_("Qty") + ":Float:100",
		_("Transferred Qty") + ":Float:120",
		_("Qty to Transfer") + ":Float:120",
		_("Description") + "::200",
		_("POS") + ":Link/POS Profile:140",
		_("Đơn vị") + ":Link/Company:120",
	]

	conditions = [
		"mr_item.parent = mr.name",
		"mr.material_request_type in ('Material Transfer', 'Material Issue')",
		"mr.docstatus = 1",
		"mr.status != 'Stopped'",
		"ifnull(mr_item.ordered_qty, 0) < ifnull(mr_item.qty, 0)",
	]

	if f.company:
		conditions.append("mr.company = %(company)s")
	if f.pos_profile:
		conditions.append("mr.pos_profile = %(pos_profile)s")
	if f.item:
		conditions.append("mr_item.item_code = %(item)s")
	if f.item_group:
		conditions.append("mr_item.item_group = %(item_group)s")
	if f.from_date:
		conditions.append("mr.transaction_date >= %(from_date)s")
	if f.to_date:
		conditions.append("mr.transaction_date <= %(to_date)s")

	where_clause = " and ".join(conditions)

	query = f"""
		select
			mr.name,
			mr.transaction_date,
			mr_item.item_code,
			mr_item.qty,
			mr_item.ordered_qty,
			(mr_item.qty - ifnull(mr_item.ordered_qty, 0)) as qty_to_transfer,
			mr_item.item_name,
			mr_item.description,
			mr.pos_profile,
			mr.company
		from
			`tabMaterial Request` mr,
			`tabMaterial Request Item` mr_item
		where
			{where_clause}
		order by
			mr.transaction_date asc
	"""

	data = frappe.db.sql(query, f, as_list=True)

	return columns, data

