# Copyright (c) 2026, MBW and contributors
# For license information, please see license.txt

from frappe.model.document import Document


class POSReturnReason(Document):
	"""Lý do khách đổi / trả hàng trên POS (PM-FEAT-00060).

	`stock_destination` quyết định kho nhận hàng trả: `Sellable` nhập lại kho bán của
	POS Profile, `Defective` nhập vào `POS Profile.posa_defective_warehouse`.
	"""

	pass
