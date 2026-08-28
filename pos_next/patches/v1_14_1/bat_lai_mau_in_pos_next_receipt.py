"""Bật lại mẫu in "POS Next Receipt" (hoàn tác PM-TASK-00116).

Nhánh ha_vang từng có patch tắt mẫu này đi, vì trên bản dựng riêng của khách đó
mẫu này là của dự án khác và gây in nhầm. Patch đó đã gỡ khỏi develop — nhưng
site nào trót migrate bằng nhánh ha_vang thì mẫu vẫn đang bị tắt, và fixture
không tự bật lại (Frappe không ghi đè `disabled` của bản ghi đã có).

Đây là mẫu mặc định của app, tắt là cửa hàng không chọn được. Patch chỉ bật lại
đúng cái cờ đó, không đụng tới POS Profile — cửa hàng nào đã được chuyển sang
mẫu khác thì giữ nguyên lựa chọn hiện tại của họ.

Site không dính thì chạy qua không làm gì. Chạy lại lần nữa vô hại.
"""

from __future__ import annotations

import frappe

MAU_MAC_DINH = "POS Next Receipt"


def execute():
	if not frappe.db.exists("Print Format", MAU_MAC_DINH):
		return

	if not frappe.db.get_value("Print Format", MAU_MAC_DINH, "disabled"):
		return

	frappe.db.set_value("Print Format", MAU_MAC_DINH, "disabled", 0, update_modified=False)
	frappe.db.commit()
	print(f"  Da bat lai mau in '{MAU_MAC_DINH}'.")
