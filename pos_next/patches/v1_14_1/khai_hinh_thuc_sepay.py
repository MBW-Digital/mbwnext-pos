"""Điền ô "SePay Mode of Payment" cho POS Profile đang bật SePay.

Trước đây máy chủ đoán hình thức chuyển khoản SePay theo tên (có "chuyển", "transfer"…), nên
"Chuyển khoản VNPay" cũng bật QR SePay. Nay POS Profile phải khai rõ một hình thức, để trống thì
SePay không bật (`api/sepay.py` `_get_sepay_settings`).

Để không tắt SePay của cửa hàng đang dùng: POS Profile nào đang bật mà chưa khai, có ĐÚNG MỘT hình
thức thanh toán khớp cách đoán cũ thì điền hình thức đó. Khớp từ hai trở lên (hay không khớp) thì
để trống và in ra, quản trị chọn tay. Chạy lại lần nữa vô hại.

Ô khoá webhook (`sepay_webhook_secret`) thì không điền được — lấy ở trang SePay.
"""

from __future__ import annotations

import frappe


def _doan_theo_ten_cu(name: str) -> bool:
	name = (name or "").lower()
	return (
		name in ("bank draft", "chuyển khoản", "bank transfer", "wire transfer")
		or "transfer" in name
		or "chuyển" in name
	)


def execute():
	if not frappe.db.has_column("POS Profile", "sepay_mode_of_payment"):
		# Custom Field mới nằm trong fixtures, mà fixtures đồng bộ SAU patch.
		from frappe.utils.fixtures import sync_fixtures

		sync_fixtures("pos_next")
		frappe.clear_cache(doctype="POS Profile")

	profiles = frappe.get_all(
		"POS Profile",
		filters={"enable_bank_transfer_check": 1},
		fields=["name", "payment_gateway", "sepay_mode_of_payment"],
	)
	for profile in profiles:
		if profile.sepay_mode_of_payment or (profile.payment_gateway and profile.payment_gateway != "SePay"):
			continue
		methods = frappe.get_all(
			"POS Payment Method", filters={"parent": profile.name}, pluck="mode_of_payment", order_by="idx"
		)
		khop = [m for m in methods if _doan_theo_ten_cu(m)]
		if len(khop) == 1:
			frappe.db.set_value(
				"POS Profile", profile.name, "sepay_mode_of_payment", khop[0], update_modified=False
			)
			print(f"  {profile.name}: SePay ghi vao '{khop[0]}'.")
		else:
			print(
				f"  {profile.name}: khong tu chon duoc hinh thuc SePay ({', '.join(khop) or 'khong co hinh thuc nao khop'})"
				" - quan tri chon tay o o 'SePay Mode of Payment', khong thi SePay tat."
			)
	frappe.db.commit()
