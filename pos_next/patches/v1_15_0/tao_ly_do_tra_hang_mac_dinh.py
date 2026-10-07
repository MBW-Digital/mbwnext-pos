"""Tạo 4 lý do đổi / trả hàng mặc định cho POS (PM-FEAT-00060).

Thu ngân chỉ có quyền đọc `POS Return Reason`, nên nếu danh mục trống thì không ai
ở quầy chọn được lý do và không lập được phiếu đổi / trả. Patch dựng sẵn 4 lý do đã
chốt trong mockup; quản lý cửa hàng thêm / tắt lý do khác sau.

Chỉ tạo lý do chưa có. Site nào đã tự khai lý do trùng tên thì giữ nguyên cấu hình
của họ (kể cả `stock_destination`). Chạy lại lần nữa vô hại.
"""

from __future__ import annotations

import frappe

LY_DO_MAC_DINH = (
	("Không vừa size", "Sellable"),
	("Lỗi sản phẩm", "Defective"),
	("Khách đổi ý", "Sellable"),
	("Giao nhầm hàng", "Sellable"),
)


def execute():
	frappe.reload_doc("pos_next", "doctype", "pos_return_reason")

	for ten, kho in LY_DO_MAC_DINH:
		if frappe.db.exists("POS Return Reason", ten):
			continue
		frappe.get_doc(
			{"doctype": "POS Return Reason", "reason_name": ten, "stock_destination": kho}
		).insert(ignore_permissions=True)

	frappe.db.commit()
