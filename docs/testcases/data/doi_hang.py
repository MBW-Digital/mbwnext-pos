"""Tạo hóa đơn gốc để test Đổi / Trả hàng (PM-FEAT-00060).

Chạy trên site dev (bench mbwnext_account_ha, site mbw.com), tại thư mục bench:

    bench --site mbw.com execute pos_next.docs_data_doi_hang.tao --kwargs "{'so_luong': 3}"

(chép file này thành apps/pos_next/pos_next/docs_data_doi_hang.py trước khi chạy, xoá sau khi dùng)

Mỗi hóa đơn: 2 đôi giày 3.199.000 (mã 10113010 và 10119576), KM tổng đơn 10% theo Pricing
Rule PRLE-70942 (đơn từ 5.000.000) → tổng 5.758.200. Ghi chú "THỬ PM-FEAT-00060".
Cần: POS Profile HAN_PAZZION HN CENTRE đang có ca mở, khách 05000839.
"""

import json

import frappe

PROFILE = "HAN_PAZZION HN CENTRE"
KHACH = "05000839"
RULE = "PRLE-70942"
MA = ("10113010", "10119576")


def _dong(code):
	rate = frappe.db.get_value("Item Price", {"item_code": code, "price_list": "Standard Selling"}, "price_list_rate")
	return {"item_code": code, "qty": 1, "rate": rate, "price_list_rate": rate,
		"uom": frappe.db.get_value("Item", code, "stock_uom"), "conversion_factor": 1}


def tao(so_luong=1):
	from pos_next.api.invoices import submit_invoice

	ca = frappe.db.get_value("POS Opening Shift", {"pos_profile": PROFILE, "status": "Open", "docstatus": 1}, "name")
	if not ca:
		frappe.throw(f"POS Profile {PROFILE} chưa có ca mở")
	ten = []
	for _ in range(int(so_luong)):
		items = [_dong(m) for m in MA]
		km = round(sum(i["rate"] for i in items) * 0.10)
		inv = {"doctype": "Sales Invoice", "pos_profile": PROFILE, "posa_pos_opening_shift": ca, "customer": KHACH,
			"items": items, "apply_discount_on": "Grand Total", "discount_amount": km,
			"posa_transaction_pricing_rule": RULE, "remarks": "THỬ PM-FEAT-00060",
			"payments": [{"mode_of_payment": "Cash", "amount": sum(i["rate"] for i in items) - km}]}
		ten.append(submit_invoice(invoice=json.dumps(inv), data="{}")["name"])
	frappe.db.commit()
	print(ten)
	return ten
