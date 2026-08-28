"""Đổi tên mẫu in "POS Ha Vang Receipt" thành "POS Retail Receipt".

Mẫu này là mẫu bán lẻ dùng chung của app, nhưng bị đặt tên theo một khách hàng
cụ thể. Tên khách trong app lõi làm người sau tưởng mẫu chỉ dành cho khách đó,
và lộ tên khách sang mọi site khác.

Đổi tên chứ không tạo mẫu mới: cửa hàng nào đang khai mẫu cũ trong POS Profile
vẫn in được ngay, không phải khai lại tay.

Site chưa có mẫu cũ thì chạy qua không làm gì. Chạy lại lần nữa vô hại.
"""

from __future__ import annotations

import frappe

TEN_CU = "POS Ha Vang Receipt"
TEN_MOI = "POS Retail Receipt"


def execute():
	if not frappe.db.exists("Print Format", TEN_CU):
		return

	if frappe.db.exists("Print Format", TEN_MOI):
		# Tên mới đã có (install.after_migrate dựng lại mẫu mỗi lần migrate).
		# Chuyển cửa hàng sang tên mới rồi xoá bản ghi cũ, tránh để hai mẫu
		# trùng nội dung đứng cạnh nhau.
		_chuyen_cua_hang()
		frappe.delete_doc("Print Format", TEN_CU, ignore_permissions=True, force=True)
	else:
		frappe.rename_doc("Print Format", TEN_CU, TEN_MOI, force=True, show_alert=False)

	frappe.db.commit()


def _chuyen_cua_hang():
	for ten in frappe.get_all("POS Profile", filters={"print_format": TEN_CU}, pluck="name"):
		frappe.db.set_value("POS Profile", ten, "print_format", TEN_MOI, update_modified=False)
