"""Khai lại `doc_type` của mẫu in bán lẻ về Sales Invoice.

Mẫu được dựng với doc_type "POS Invoice", trong khi POS của app này tạo
Sales Invoice. In qua POS vẫn chạy (Frappe không chặn /printview), nhưng mẫu
không hiện trong danh sách mẫu in của Sales Invoice trên desk — kế toán mở
hoá đơn ra thì không chọn được đúng mẫu cửa hàng đang dùng.

Chỉ sửa khi đang khai sai. Chạy lại lần nữa vô hại.
"""

from __future__ import annotations

import frappe

MAU = "POS Retail Receipt"
DUNG = "Sales Invoice"


def execute():
	hien_tai = frappe.db.get_value("Print Format", MAU, "doc_type")
	if not hien_tai or hien_tai == DUNG:
		return

	frappe.db.set_value("Print Format", MAU, "doc_type", DUNG, update_modified=False)
	frappe.db.commit()
	print(f"  Da doi doc_type cua '{MAU}': {hien_tai} -> {DUNG}.")
