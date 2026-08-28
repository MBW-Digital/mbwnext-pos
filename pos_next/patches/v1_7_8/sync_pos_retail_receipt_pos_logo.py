"""Mẫu in bán lẻ — logo lấy từ POS Profile custom_pos_logo.

Patch chỉ gọi lại hàm sync (đọc file template, ghi đè `html` của Print Format)
nên chạy bao nhiêu lần cũng như nhau. Vì thế đổi được tên module mà không sợ
tác dụng phụ, dù site cũ đã ghi tên cũ vào Patch Log và sẽ chạy thêm một lần.
"""

from __future__ import annotations

import frappe

from pos_next.print_formats.sync import sync_pos_retail_receipt


def execute():
	sync_pos_retail_receipt()
	frappe.db.commit()
