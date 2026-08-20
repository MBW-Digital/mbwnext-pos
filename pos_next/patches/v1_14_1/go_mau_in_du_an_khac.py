"""Gỡ mẫu in của dự án khác khỏi bản dựng Hạ Vàng (PM-TASK-00116).

Nhánh này chỉ phục vụ Hạ Vàng, nhưng app POS dùng chung nên mẫu in
"POS Next Receipt" — dựng cho dự án Bách Hóa Bưu Điện — vẫn nằm trong danh
sách mẫu và có cửa hàng đang khai dùng. Hậu quả: cùng một cửa hàng in ra hai
tờ khác nhau, tờ thì "HÓA ĐƠN BÁN LẺ" của Hạ Vàng, tờ thì "PHIẾU TÍNH TIỀN"
mang logo Bách Hóa Bưu Điện.

Patch làm hai việc:
  1. Cửa hàng nào còn khai mẫu đó thì chuyển sang mẫu của Hạ Vàng.
  2. Tắt mẫu đó đi để không ai chọn lại.

KHÔNG xoá bản ghi mẫu in — xoá là mất luôn dấu vết, mà tắt là đủ để không
dùng được nữa. Cần bật lại thì bỏ dấu tắt trong màn hình Print Format.

Patch tự dò trên site đang chạy, site không dính thì chạy qua không làm gì.
Chạy lại lần nữa vô hại.
"""

from __future__ import annotations

import frappe

MAU_DU_AN_KHAC = "POS Next Receipt"
MAU_HA_VANG = "POS Ha Vang Receipt"


def execute():
	if not frappe.db.exists("Print Format", MAU_DU_AN_KHAC):
		return

	if not frappe.db.exists("Print Format", MAU_HA_VANG):
		# Mẫu Hạ Vàng được dựng lại mỗi lần migrate (install.after_migrate).
		# Chưa có nghĩa là thứ tự chạy đã đổi — dừng còn hơn để cửa hàng trỏ
		# vào một mẫu không tồn tại rồi không in được gì.
		frappe.log_error(
			title="Bo qua patch go mau in du an khac",
			message=f"Chua co mau in {MAU_HA_VANG}, khong chuyen duoc cua hang nao.",
		)
		return

	cua_hang = frappe.get_all(
		"POS Profile", filters={"print_format": MAU_DU_AN_KHAC}, pluck="name"
	)
	for ten in cua_hang:
		frappe.db.set_value(
			"POS Profile", ten, "print_format", MAU_HA_VANG, update_modified=False
		)

	frappe.db.set_value(
		"Print Format", MAU_DU_AN_KHAC, "disabled", 1, update_modified=False
	)
	frappe.db.commit()

	print(
		f"  Da chuyen {len(cua_hang)} cua hang tu '{MAU_DU_AN_KHAC}' sang "
		f"'{MAU_HA_VANG}' va tat mau cu."
	)
	print(
		"  Patch KHONG dat logo cho cua hang — moi cua hang phai tu tai logo "
		"len o 'Logo POS' trong Cai dat cua hang, neu khong phieu in se khong co logo."
	)
