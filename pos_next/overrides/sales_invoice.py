# Copyright (c) 2025, BrainWise and contributors
# For license information, please see license.txt

"""
Sales Invoice Override
Handles wallet payments that require party information for Receivable accounts.

"""

import frappe
from frappe.utils import add_days, cint, flt, getdate
from erpnext.accounts.doctype.loyalty_program.loyalty_program import (
	get_loyalty_program_details_with_points,
)
from erpnext.accounts.doctype.sales_invoice.sales_invoice import SalesInvoice
from erpnext.accounts.utils import get_account_currency
from erpnext.controllers import taxes_and_totals as _taxes_and_totals

from pos_next.api.loyalty_exclusion import (
	get_loyalty_eligible_amount,
	get_loyalty_excluded_item_lines,
	get_returned_loyalty_eligible_amount,
)

def _get_post_change_gl_entries_setting():
	"""
	Get post_change_gl_entries setting compatible with ERPNext v15 and v16.

	- ERPNext v15: Field is in 'Accounts Settings'
	- ERPNext v16: Field moved to ERPNext's 'POS Settings' (singleton)

	Since pos_next has its own 'POS Settings' doctype (non-singleton) that overrides
	ERPNext's, we read directly from the Singles table for v16 compatibility.

	Returns:
		int: 1 if post_change_gl_entries is enabled, 0 otherwise (default: 0)
	"""
	# Check if field exists in Accounts Settings schema (v15)
	meta = frappe.get_meta("Accounts Settings")
	if meta.has_field("post_change_gl_entries"):
		value = frappe.db.get_single_value("Accounts Settings", "post_change_gl_entries")
		return cint(value) if value is not None else 0

	# For v16, read directly from Singles table using Query Builder to avoid ORM issues
	# ERPNext's POS Settings is a singleton, data stored in Singles table
	Singles = frappe.qb.DocType("Singles")
	result = (
		frappe.qb.from_(Singles)
		.select(Singles.value)
		.where(Singles.doctype == "POS Settings")
		.where(Singles.field == "post_change_gl_entries")
		.limit(1)
		.run()
	)
	return cint(result[0][0]) if result else 0

class CustomSalesInvoice(SalesInvoice):
	"""
	Custom Sales Invoice class that handles wallet payments correctly.

	When a wallet payment is made using a Receivable account, ERPNext requires
	party information in the GL entry. This override adds party_type and party
	for wallet payment methods marked with is_wallet_payment.
	"""

	def make_pos_gl_entries(self, gl_entries):
		"""
		Override to add party information for wallet payment accounts.

		The standard ERPNext implementation doesn't set party_type/party for
		payment mode accounts, which causes validation errors for Receivable
		accounts (like wallet accounts).
		"""
		if cint(self.is_pos):
			skip_change_gl_entries = not _get_post_change_gl_entries_setting()

			for payment_mode in self.payments:
				if skip_change_gl_entries and payment_mode.account == self.account_for_change_amount:
					payment_mode.base_amount -= flt(self.change_amount)

				if payment_mode.amount:
					# POS, make payment entries
					# Credit entry to debit_to (customer receivable)
					gl_entries.append(
						self.get_gl_dict(
							{
								"account": self.debit_to,
								"party_type": "Customer",
								"party": self.customer,
								"against": payment_mode.account,
								"credit": payment_mode.base_amount,
								"credit_in_account_currency": payment_mode.base_amount
								if self.party_account_currency == self.company_currency
								else payment_mode.amount,
								"against_voucher": self.return_against
								if cint(self.is_return) and self.return_against
								else self.name,
								"against_voucher_type": self.doctype,
								"cost_center": self.cost_center,
							},
							self.party_account_currency,
							item=self,
						)
					)

					# Debit entry to payment mode account
					payment_mode_account_currency = get_account_currency(payment_mode.account)

					# Get party info for wallet payments
					party_type, party = self.get_party_and_party_type_for_pos_gl_entry(
						payment_mode.mode_of_payment, payment_mode.account
					)

					gl_entries.append(
						self.get_gl_dict(
							{
								"account": payment_mode.account,
								"party_type": party_type,
								"party": party,
								"against": self.customer,
								"debit": payment_mode.base_amount,
								"debit_in_account_currency": payment_mode.base_amount
								if payment_mode_account_currency == self.company_currency
								else payment_mode.amount,
								"cost_center": self.cost_center,
							},
							payment_mode_account_currency,
							item=self,
						)
					)

			if not skip_change_gl_entries:
				if hasattr(self, "get_gle_for_change_amount"):
					# ERPNext v16+: Method renamed and returns a list of GL entries
					# that needs to be extended to the main gl_entries list
					gl_entries.extend(self.get_gle_for_change_amount())
				else:
					# ERPNext v15: Method takes gl_entries as parameter
					# and appends change amount entries directly to it
					self.make_gle_for_change_amount(gl_entries)

	def get_party_and_party_type_for_pos_gl_entry(self, mode_of_payment, account):
		"""
		Get party type and party for wallet payment GL entries.

		For wallet payments (Mode of Payment with is_wallet_payment=1),
		returns Customer as party_type and the invoice customer as party.
		For regular payments, returns empty strings.
		"""
		is_wallet_mode_of_payment = frappe.db.get_value(
			"Mode of Payment", mode_of_payment, "is_wallet_payment"
		)

		party_type, party = "", ""
		if is_wallet_mode_of_payment:
			party_type, party = "Customer", self.customer

		return party_type, party

	def make_loyalty_point_entry(self):
		excluded_item_lines = get_loyalty_excluded_item_lines(self.loyalty_program)
		if not excluded_item_lines:
			return super().make_loyalty_point_entry()

		current_amount = get_loyalty_eligible_amount(self, excluded_item_lines)
		returned_amount = get_returned_loyalty_eligible_amount(self, excluded_item_lines)
		eligible_amount = current_amount - returned_amount

		lp_details = get_loyalty_program_details_with_points(
			self.customer,
			company=self.company,
			current_transaction_amount=current_amount,
			loyalty_program=self.loyalty_program,
			expiry_date=self.posting_date,
			include_expired_entry=True,
		)
		if (
			lp_details
			and getdate(lp_details.from_date) <= getdate(self.posting_date)
			and (not lp_details.to_date or getdate(lp_details.to_date) >= getdate(self.posting_date))
		):
			collection_factor = lp_details.collection_factor if lp_details.collection_factor else 1.0
			points_earned = cint(eligible_amount / collection_factor)

			doc = frappe.get_doc(
				{
					"doctype": "Loyalty Point Entry",
					"company": self.company,
					"loyalty_program": lp_details.loyalty_program,
					"loyalty_program_tier": lp_details.tier_name,
					"customer": self.customer,
					"invoice_type": self.doctype,
					"invoice": self.name,
					"loyalty_points": points_earned,
					"purchase_amount": eligible_amount,
					"expiry_date": add_days(self.posting_date, lp_details.expiry_duration),
					"posting_date": self.posting_date,
				}
			)
			doc.flags.ignore_permissions = 1
			doc.save()
			self.set_loyalty_program_tier()

	def get_item_list(self):
		"""Skip stock deduction for promo free-gift lines without batch stock."""
		item_list = super().get_item_list()
		if not cint(getattr(self, "is_pos", 0)):
			return item_list
		return [
			row
			for row in item_list
			if not cint(getattr(row.item_row, "pos_skip_stock_deduction", 0))
		]

	def validate(self):
		super().validate()
		self.set_default_additional_discount_account()

	def set_default_additional_discount_account(self):
		"""Gán sẵn tài khoản chiết khấu cho Additional Discount.

		Selling Settings bật `enable_discount_accounting` thì ERPNext đặt
		`additional_discount_account` là BẮT BUỘC mỗi khi hoá đơn có
		`discount_amount` — thu ngân phải gõ tay từng hoá đơn. Lấy theo
		`Company.discount_account` (tài khoản 521 khai ở tab Accounts của
		Company, cùng nguồn mà Sales Voucher đang dùng).

		Chỉ điền khi đang trống — người dùng chọn tài khoản khác thì giữ nguyên.
		"""
		if self.get("additional_discount_account") or not flt(self.get("discount_amount")):
			return

		if not self.get("company"):
			return

		# discount_account là custom field của mbwnext_localization;
		# default_discount_account là field gốc ERPNext, dùng dự phòng.
		accounts = frappe.db.get_value(
			"Company", self.company, ["discount_account", "default_discount_account"], as_dict=True
		)
		if not accounts:
			return

		self.additional_discount_account = accounts.get("discount_account") or accounts.get(
			"default_discount_account"
		)

	def get_tax_amounts(self, tax, enable_discount_accounting):
		"""Thuế đầu ra luôn hạch toán theo Tax Amount After Discount Amount.

		ERPNext gốc (accounts_controller.get_tax_amounts) cố ý dùng `tax_amount`
		— tức số thuế TRƯỚC khi trừ chiết khấu tổng đơn — khi hoá đơn vừa bật
		discount accounting, vừa có `additional_discount_account`, vừa
		`apply_discount_on = "Grand Total"`. Lý do của ERPNext: coi khoản chiết
		khấu là chi phí riêng nên giữ thuế trên giá gộp.

		Kế toán VAS thì ngược lại: 33311 phải bằng đúng số thuế thực kê khai
		(`tax_amount_after_discount_amount`). Phần chênh giữa hai con số được
		dồn vào tài khoản doanh thu ở `make_discount_gl_entries` bên dưới, nên
		bút toán vẫn cân.
		"""
		return tax.tax_amount_after_discount_amount, tax.base_tax_amount_after_discount_amount

	def get_gl_entries(self, warehouse_account=None):
		gl_entries = super().get_gl_entries(warehouse_account)
		self.book_tax_discount_difference_to_income(gl_entries)
		return gl_entries

	def book_tax_discount_difference_to_income(self, gl_entries):
		"""Dồn phần chênh thuế (do get_tax_amounts ở trên) vào tài khoản doanh thu.

		ERPNext gốc ghi 33311 theo `tax_amount`; ta ghi theo
		`tax_amount_after_discount_amount` nên bên Có hụt đúng bằng phần chênh
		giữa hai số. Bên Nợ (131 và 521) không đổi, nên phải cộng phần chênh đó
		vào doanh thu thì bút toán mới cân — đây chính là "511 = giá trị cũ +
		phần chênh lệch tính sai thuế".

		Cộng đúng phần LỆCH THỰC TẾ của bộ bút toán chứ không cộng phần chênh
		tính từ bảng thuế: từng dòng bút toán được làm tròn riêng nên hai số có
		thể lệch nhau 1–2 đồng, cộng theo bảng thuế sẽ để lại chênh lệch nợ/có
		(đã gặp ở 11/40 hoá đơn khi thử).
		"""
		expected = self.get_tax_discount_difference()
		if not expected:
			return

		precision = self.precision("base_net_total")
		residual = flt(
			sum(flt(gle.get("debit")) for gle in gl_entries)
			- sum(flt(gle.get("credit")) for gle in gl_entries),
			precision,
		)
		if not residual:
			return

		# Chỉ hấp thụ phần lệch đúng bằng chênh thuế (cộng/trừ vài đồng làm tròn).
		# Lệch nhiều hơn nghĩa là có nguyên nhân khác — để nguyên cho ERPNext báo
		# "Debit and Credit not equal" thay vì che mất một lỗi thật.
		if abs(residual - expected) > 5:
			return

		income_accounts = {item.income_account for item in self.get("items") if item.income_account}
		income_entries = [gle for gle in gl_entries if gle.get("account") in income_accounts]
		if not income_entries:
			return

		# Cộng vào dòng doanh thu lớn nhất: hoá đơn nhiều dòng hàng vẫn chỉ có
		# một bút toán chênh lệch, không rải nhỏ ra từng dòng.
		target = max(income_entries, key=lambda gle: flt(gle.get("credit")))
		for field in ("credit", "credit_in_account_currency", "credit_in_transaction_currency"):
			if target.get(field):
				target[field] = flt(flt(target[field]) + residual, precision)

	def get_tax_discount_difference(self):
		"""Phần thuế ERPNext gốc sẽ ghi thừa, = tax_amount - tax_amount_after_discount_amount.

		Chỉ phát sinh đúng trong điều kiện mà ERPNext đổi sang `tax_amount`
		(xem get_tax_amounts): bật discount accounting + có chiết khấu tổng đơn +
		có tài khoản chiết khấu + áp trên Grand Total.
		"""
		if not (
			self.enable_discount_accounting
			and self.get("discount_amount")
			and self.get("additional_discount_account")
			and self.get("apply_discount_on") == "Grand Total"
		):
			return 0.0

		return flt(
			sum(
				flt(tax.base_tax_amount) - flt(tax.base_tax_amount_after_discount_amount)
				for tax in self.get("taxes")
			),
			self.precision("base_net_total"),
		)


# ==========================================================================
# Vá ERPNext: đừng xoá bảng thanh toán của phiếu trả vì lệch vài đồng
# ==========================================================================

# Lệch tối đa (VND) được coi là sai số làm tròn, không phải sai số liệu. Mỗi
# dòng hoá đơn góp tối đa ~0,5 đồng nên 10 đồng đủ cho hoá đơn rất nhiều dòng,
# mà vẫn nhỏ hơn mọi sai lệch thật một khoảng rất xa.
NGUONG_LECH_LAM_TRON = 10

_set_total_amount_to_default_mop_goc = (
	_taxes_and_totals.calculate_taxes_and_totals.set_total_amount_to_default_mop
)


def _set_total_amount_to_default_mop(self, total_amount_to_pay):
	"""Chênh lệch làm tròn thì cộng vào dòng thanh toán cuối, đừng thay cả bảng.

	Bản gốc của ERPNext thấy tổng thanh toán chưa đủ `total_amount_to_pay` là
	XOÁ SẠCH bảng payments rồi thay bằng đúng MỘT dòng bằng phần còn thiếu.
	Với phiếu trả POS, phần còn thiếu thường chỉ là chênh lệch làm tròn: POS
	cộng tiền hoàn theo từng dòng (`net_rate` + thuế, mỗi dòng làm tròn riêng),
	còn ERPNext phân bổ chiết khấu bill một lần trên tổng.

	Hậu quả rất nặng: phiếu trả 4.638.272 bị ghi thành hoàn 1 đồng, treo công
	nợ 4.638.271 trên cả phiếu trả lẫn đơn gốc, trong khi thu ngân đã đưa khách
	đủ tiền. Đã tái hiện trên hoá đơn 3 dòng có coupon 15%.

	Lệch lớn thì vẫn để bản gốc xử lý — đó là sai số liệu thật, không được che.
	"""
	tong_da_tra = sum(
		flt(p.amount) if self.doc.party_account_currency == self.doc.currency else flt(p.base_amount)
		for p in self.doc.get("payments") or []
	)
	con_thieu = flt(total_amount_to_pay) - flt(tong_da_tra)

	if self.doc.get("payments") and 0 < abs(con_thieu) <= NGUONG_LECH_LAM_TRON:
		dong_cuoi = self.doc.payments[-1]
		dong_cuoi.amount = flt(dong_cuoi.amount + con_thieu)
		dong_cuoi.base_amount = flt(dong_cuoi.amount * flt(self.doc.conversion_rate or 1))

		# ERPNext tính outstanding_amount TRƯỚC khi gọi hàm này rồi không tính
		# lại, nên phần chênh vừa cộng vào sẽ treo nguyên trên công nợ. Bảng
		# thanh toán giờ đã bằng đúng total_amount_to_pay nên công nợ phải về 0.
		self.doc.outstanding_amount = flt(
			flt(total_amount_to_pay) - flt(tong_da_tra) - flt(con_thieu),
			self.doc.precision("outstanding_amount"),
		)
		return

	return _set_total_amount_to_default_mop_goc(self, total_amount_to_pay)


_taxes_and_totals.calculate_taxes_and_totals.set_total_amount_to_default_mop = (
	_set_total_amount_to_default_mop
)
