# Copyright (c) 2024, BrainWise and contributors
# For license information, please see license.txt

import frappe
from frappe import _
from frappe.utils import flt, today
from erpnext.accounts.general_ledger import make_reverse_gl_entries
from erpnext.controllers.accounts_controller import AccountsController


class WalletTransaction(AccountsController):
	def validate(self):
		self.validate_wallet()
		self.validate_amount()
		self.set_customer_from_wallet()

	def validate_wallet(self):
		"""Validate wallet exists and is active"""
		if not self.wallet:
			frappe.throw(_("Wallet is required"))

		wallet_status = frappe.db.get_value("Wallet", self.wallet, "status")
		if wallet_status != "Active":
			frappe.throw(_("Wallet {0} is not active").format(self.wallet))

	def validate_amount(self):
		"""Validate amount is positive"""
		if flt(self.amount) <= 0:
			frappe.throw(_("Amount must be greater than zero"))

		# For debit transactions, check if sufficient balance
		if self.transaction_type == "Debit":
			from pos_next.pos_next.doctype.wallet.wallet import get_customer_wallet_balance
			balance = get_customer_wallet_balance(self.customer, self.company)
			if flt(self.amount) > flt(balance):
				frappe.throw(
					_("Insufficient wallet balance. Available: {0}, Requested: {1}").format(
						frappe.format_value(balance, {"fieldtype": "Currency"}),
						frappe.format_value(self.amount, {"fieldtype": "Currency"})
					)
				)

	def set_customer_from_wallet(self):
		"""Fetch customer from wallet"""
		if self.wallet and not self.customer:
			self.customer = frappe.db.get_value("Wallet", self.wallet, "customer")

	def on_submit(self):
		"""Ghi nhận điểm — KHÔNG sinh bút toán.

		Trước đây mỗi lần khách mua hàng được tích điểm là ghi ngay
		Nợ (tài khoản chi phí của chương trình) / Có (tài khoản ví).

		Kế toán bác cách đó (PM-TASK-00106): điểm đã tích có thể không bao giờ
		được dùng, ghi chi phí ngay lúc tích là ghi cho một khoản chưa chắc phát
		sinh. Theo nguyên tắc thận trọng, chi phí chỉ ghi khi khách THỰC SỰ tiêu
		điểm — lúc đó hoá đơn tự ghi Nợ 6418 - Chi phí bán hàng / Có 131 qua hình
		thức thanh toán "đổi điểm". Chương trình khách hàng thân thiết vẫn giữ ô
		tài khoản chi phí nhưng luồng ví không còn đọc tới.

		Bỏ bút toán ở đây cũng gỡ luôn hai lỗi cùng gốc: tài khoản ví trùng tài
		khoản công nợ 131 nên hai vế triệt tiêu nhau, đơn trả bằng điểm treo lại
		đúng số điểm đã dùng, và số dư ví bị tiền hàng khách còn nợ lấn át nên
		hàng loạt ví hiển thị 0.
		"""
		self.update_wallet_balance()

	def on_cancel(self):
		# Must be set before post-cancel link validation (same pattern as Sales Invoice)
		self.ignore_linked_doctypes = (
			"GL Entry",
			"Payment Ledger Entry",
			"Repost Payment Ledger",
			"Repost Payment Ledger Items",
			"Repost Accounting Ledger",
			"Repost Accounting Ledger Items",
		)
		self.dao_but_toan_cu()
		self.update_wallet_balance()

	def dao_but_toan_cu(self):
		"""Đảo bút toán của những phiếu tích điểm ghi sổ theo cách CŨ.

		Phiếu tạo từ nay không có bút toán nào, huỷ là xong. Nhưng phiếu tích
		điểm cũ đã ghi sổ rồi — huỷ mà không đảo là bỏ lại bút toán mồ côi, sổ
		lệch. Đảo theo đúng những gì đã ghi chứ không dựng lại từ cấu hình hiện
		tại: cấu hình đã đổi, dựng lại sẽ ra tài khoản khác.
		"""
		co_but_toan_cu = frappe.db.exists(
			"GL Entry",
			{"voucher_type": self.doctype, "voucher_no": self.name, "is_cancelled": 0},
		)
		if co_but_toan_cu:
			make_reverse_gl_entries(voucher_type=self.doctype, voucher_no=self.name)

	def update_wallet_balance(self):
		"""Update the wallet's current balance"""
		wallet_doc = frappe.get_doc("Wallet", self.wallet)
		wallet_doc.update_balance()

	def get_source_account(self):
		"""Get source account based on source type"""
		if self.source_account:
			return self.source_account

		if self.source_type == "Mode of Payment" and self.source_account:
			return self.source_account

		if self.source_type == "Loyalty Program":
			# Get loyalty expense account from loyalty program or company
			loyalty_account = frappe.db.get_value(
				"Loyalty Program",
				{"company": self.company},
				"expense_account"
			)
			if loyalty_account:
				return loyalty_account

			# Fallback to company's default expense account
			return frappe.get_cached_value("Company", self.company, "default_expense_account")

		if self.source_type == "Refund":
			# Use company's default receivable account
			return frappe.get_cached_value("Company", self.company, "default_receivable_account")

		if self.source_type == "Manual Adjustment":
			# Use company's adjustment account or default expense
			return frappe.get_cached_value("Company", self.company, "default_expense_account")

		return None


@frappe.whitelist()
def create_wallet_credit(wallet, amount, source_type="Manual Adjustment", remarks=None,
						 reference_doctype=None, reference_name=None, submit=True):
	"""
	Create a wallet credit transaction.

	Args:
		wallet: Wallet name
		amount: Amount to credit
		source_type: Source of credit (Manual Adjustment, Loyalty Program, Refund)
		remarks: Transaction remarks
		reference_doctype: Reference document type
		reference_name: Reference document name
		submit: Whether to submit the transaction

	Returns:
		Wallet Transaction document
	"""
	wallet_doc = frappe.get_doc("Wallet", wallet)

	# Get source account based on source type
	source_account = None
	if source_type == "Loyalty Program":
		loyalty_program = frappe.db.get_value(
			"Loyalty Program",
			{"company": wallet_doc.company},
			"name"
		)
		if loyalty_program:
			source_account = frappe.db.get_value(
				"Loyalty Program", loyalty_program, "expense_account"
			)

	if not source_account:
		source_account = frappe.get_cached_value(
			"Company", wallet_doc.company, "default_expense_account"
		)

	transaction = frappe.get_doc({
		"doctype": "Wallet Transaction",
		"transaction_type": "Loyalty Credit" if source_type == "Loyalty Program" else "Credit",
		"wallet": wallet,
		"company": wallet_doc.company,
		"posting_date": today(),
		"amount": amount,
		"source_type": source_type,
		"source_account": source_account,
		"remarks": remarks,
		"reference_doctype": reference_doctype,
		"reference_name": reference_name
	})

	transaction.insert(ignore_permissions=True)

	if submit:
		transaction.submit()

	return transaction


@frappe.whitelist()
def credit_loyalty_points_to_wallet(customer, company, loyalty_points, conversion_factor=None):
	"""
	Convert loyalty points to wallet credit.

	Args:
		customer: Customer ID
		company: Company
		loyalty_points: Number of loyalty points to convert
		conversion_factor: Points to currency conversion (optional, fetched from program if not provided)

	Returns:
		Wallet Transaction document or None
	"""
	if flt(loyalty_points) <= 0:
		return None

	# Get conversion factor from loyalty program if not provided
	if not conversion_factor:
		loyalty_program = frappe.db.get_value("Customer", customer, "loyalty_program")
		if loyalty_program:
			conversion_factor = frappe.db.get_value(
				"Loyalty Program", loyalty_program, "conversion_factor"
			)

	if not conversion_factor:
		conversion_factor = 1.0  # Default: 1 point = 1 currency

	# Calculate wallet credit amount
	credit_amount = flt(loyalty_points) * flt(conversion_factor)

	if credit_amount <= 0:
		return None

	# Get or create customer wallet
	from pos_next.pos_next.doctype.wallet.wallet import get_or_create_wallet
	wallet = get_or_create_wallet(customer, company)

	# Create wallet credit transaction
	transaction = create_wallet_credit(
		wallet=wallet["name"],
		amount=credit_amount,
		source_type="Loyalty Program",
		remarks=_("Loyalty points conversion: {0} points = {1}").format(
			loyalty_points,
			frappe.format_value(credit_amount, {"fieldtype": "Currency"})
		),
		submit=True
	)

	return transaction
