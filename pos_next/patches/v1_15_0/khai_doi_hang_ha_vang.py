"""Dựng sẵn dữ liệu nền cho đổi hàng tại quầy (PM-FEAT-00044, Hạ Vàng).

1. Bốn lý do đổi đã chốt trên mockup. Thu ngân chỉ có quyền đọc `POS Return Reason`,
   danh mục trống thì không ai ở quầy đổi được hàng.
2. Số ngày được đổi mặc định 15 ở Selling Settings (anh Hưng chốt 04/11: mặc định 15,
   0 = không giới hạn). Ô mặc định của Custom Field không tự ghi vào DocType Single,
   để trống thì đọc ra 0 = không giới hạn — ngược hẳn ý khách.

Chỉ thêm cái chưa có, không đè cấu hình site đã tự khai. Chạy lại vô hại.
"""

import frappe

LY_DO_MAC_DINH = ("Không vừa size", "Lỗi sản phẩm", "Khách đổi ý", "Khác")


def execute():
	frappe.reload_doc("pos_next", "doctype", "pos_return_reason")

	for ten in LY_DO_MAC_DINH:
		if not frappe.db.exists("POS Return Reason", ten):
			frappe.get_doc({"doctype": "POS Return Reason", "reason_name": ten}).insert(ignore_permissions=True)

	# Không kiểm meta: patch chạy TRƯỚC khi migrate nạp fixtures, lúc này Custom Field
	# có thể chưa tồn tại. Ghi thẳng vào Singles vẫn đọc được khi trường xuất hiện.
	da_co = frappe.db.sql(
		"select 1 from `tabSingles` where doctype='Selling Settings' and field='custom_pos_exchange_days'"
	)
	if not da_co:
		frappe.db.sql(
			"insert into `tabSingles` (doctype, field, value) values ('Selling Settings', 'custom_pos_exchange_days', '15')"
		)
