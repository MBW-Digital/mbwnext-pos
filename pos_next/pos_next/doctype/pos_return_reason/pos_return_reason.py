# Copyright (c) 2026, MBW and contributors
# For license information, please see license.txt

from frappe.model.document import Document


class POSReturnReason(Document):
	"""Lý do khách đổi hàng trên POS (PM-FEAT-00044, Hạ Vàng).

	Thu ngân bắt buộc chọn một lý do khi đổi. Hàng trả luôn nhập lại kho bán của
	cửa hàng, kể cả hàng lỗi (anh Thắng chốt 30/10) — nhánh `develop` có thêm ô kho
	hàng lỗi, nhánh này cố ý không có.
	"""

	pass
