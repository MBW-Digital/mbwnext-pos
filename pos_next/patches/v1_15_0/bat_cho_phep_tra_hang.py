"""Bật `allow_return` cho các Cài đặt POS đang có (PM-FEAT-00060, H3).

Trước bản này cờ "Cho phép trả hàng" không có tác dụng: tắt hay bật thì quầy vẫn trả
hàng được, nên gần như mọi site để mặc định là TẮT (đo trên site dev Hạ Vàng: 46/46
cài đặt tắt, trong khi đã có 132 phiếu trả POS). Nay server chặn thật khi cờ tắt — nếu
không bật lại thì sau khi cập nhật, mọi cửa hàng mất chức năng trả hàng.

Bật cho mọi cài đặt đang có để giữ nguyên hành vi trước khi cập nhật. Cửa hàng nào
thật sự không muốn trả hàng thì tắt lại, lần này cờ mới có tác dụng.

Chỉ chạy một lần (Patch Log), nên không đè lên lựa chọn tắt sau này.
"""

from __future__ import annotations

import frappe


def execute():
	ten = frappe.get_all("POS Settings", filters={"allow_return": 0}, pluck="name")
	for name in ten:
		frappe.db.set_value("POS Settings", name, "allow_return", 1, update_modified=False)
	if ten:
		print(f"  Da bat allow_return cho {len(ten)} POS Settings.")
	frappe.db.commit()
