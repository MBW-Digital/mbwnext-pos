# Copyright (c) 2024, BrainWise and contributors
# For license information, please see license.txt

"""
Wallet API for POS Next
Handles wallet payments, validation, and loyalty points conversion
"""

import frappe
from frappe import _
from frappe.utils import flt, cint


def validate_wallet_payment(doc, method=None):
	"""
	Validate wallet payment on Sales Invoice.
	Called during validate hook.
	"""
	if not doc.is_pos:
		return

	# Get wallet payment amount from payments
	wallet_amount = get_wallet_amount_from_payments(doc.payments)

	if wallet_amount <= 0:
		return

	# Get customer wallet balance
	wallet_balance = get_customer_wallet_balance(doc.customer, doc.company, exclude_invoice=doc.name)

	if wallet_amount > wallet_balance:
		frappe.throw(
			_("Insufficient wallet balance. Available: {0}, Requested: {1}").format(
				frappe.format_value(wallet_balance, {"fieldtype": "Currency"}),
				frappe.format_value(wallet_amount, {"fieldtype": "Currency"})
			),
			title=_("Wallet Balance Error")
		)


def process_loyalty_to_wallet(doc, method=None):
	"""
	Convert earned loyalty points to wallet balance after invoice submission.
	Called during on_submit hook.
	"""
	if not doc.is_pos or doc.is_return:
		return

	# Check if loyalty to wallet is enabled
	pos_settings = get_pos_settings(doc.pos_profile)
	if not pos_settings:
		return

	if not cint(pos_settings.get("enable_loyalty_program")) or not cint(pos_settings.get("loyalty_to_wallet")):
		return

	# Check if customer has loyalty program
	loyalty_program = frappe.db.get_value("Customer", doc.customer, "loyalty_program")
	if not loyalty_program:
		return

	# Get the loyalty points earned from this invoice
	loyalty_entry = frappe.db.get_value(
		"Loyalty Point Entry",
		{
			"invoice_type": "Sales Invoice",
			"invoice": doc.name,
			"loyalty_points": [">", 0]
		},
		["loyalty_points", "name"],
		as_dict=True
	)

	if not loyalty_entry or loyalty_entry.loyalty_points <= 0:
		return

	# Get conversion rate from Loyalty Program (standard ERPNext field)
	conversion_rate = flt(frappe.db.get_value("Loyalty Program", loyalty_program, "conversion_factor")) or 1.0

	# Calculate wallet credit amount
	credit_amount = flt(loyalty_entry.loyalty_points) * conversion_rate

	if credit_amount <= 0:
		return

	try:
		# Get or create customer wallet
		wallet = get_or_create_wallet(doc.customer, doc.company, pos_settings)

		if not wallet:
			return

		# Create wallet transaction
		from pos_next.pos_next.doctype.wallet_transaction.wallet_transaction import create_wallet_credit

		transaction = create_wallet_credit(
			wallet=wallet.name,
			amount=credit_amount,
			source_type="Loyalty Program",
			remarks=_("Loyalty points conversion from {0}: {1} points = {2}").format(
				doc.name,
				loyalty_entry.loyalty_points,
				frappe.format_value(credit_amount, {"fieldtype": "Currency"})
			),
			reference_doctype="Sales Invoice",
			reference_name=doc.name,
			submit=True
		)

		frappe.msgprint(
			_("Loyalty points converted to wallet: {0} points = {1}").format(
				loyalty_entry.loyalty_points,
				frappe.format_value(credit_amount, {"fieldtype": "Currency"})
			),
			alert=True,
			indicator="green"
		)

	except Exception as e:
		frappe.log_error(
			title="Loyalty to Wallet Conversion Error",
			message=f"Invoice: {doc.name}, Error: {str(e)}\n{frappe.get_traceback()}"
		)


def cancel_wallet_transactions_for_invoice(doc, method=None):
	"""
	Cancel Wallet Transactions created from this Sales Invoice (loyalty → wallet).
	Must run on before_cancel / on_cancel so reverse GL happens and SI is not blocked
	by Dynamic Link from Wallet Transaction.reference_name.
	"""
	if not doc.is_pos:
		return

	transactions = frappe.get_all(
		"Wallet Transaction",
		filters={
			"reference_doctype": "Sales Invoice",
			"reference_name": doc.name,
			"docstatus": 1,
		},
		pluck="name",
	)

	if not transactions:
		return

	# If wallet credit was already spent, reversing it would go negative — block with clear message
	total_credit = 0.0
	for name in transactions:
		wt = frappe.db.get_value(
			"Wallet Transaction",
			name,
			["transaction_type", "amount", "customer", "company"],
			as_dict=True,
		)
		if wt and wt.transaction_type in ("Credit", "Loyalty Credit"):
			total_credit += flt(wt.amount)

	if total_credit > 0:
		balance = get_customer_wallet_balance(doc.customer, doc.company)
		if flt(balance) + 0.0001 < total_credit:
			frappe.throw(
				_(
					"Cannot cancel invoice {0}: wallet credit of {1} from this invoice "
					"was already used. Available wallet balance: {2}. "
					"Please reverse wallet payments first."
				).format(
					doc.name,
					frappe.format_value(total_credit, {"fieldtype": "Currency"}),
					frappe.format_value(balance, {"fieldtype": "Currency"}),
				),
				title=_("Wallet Credit Already Used"),
			)

	for name in transactions:
		wt_doc = frappe.get_doc("Wallet Transaction", name)
		wt_doc.flags.ignore_permissions = True
		wt_doc.cancel()

	frappe.msgprint(
		_("Cancelled {0} wallet transaction(s) linked to this invoice").format(len(transactions)),
		alert=True,
		indicator="orange",
	)


def get_wallet_amount_from_payments(payments):
	"""
	Calculate total wallet payment amount from invoice payments.
	"""
	wallet_amount = 0.0

	for payment in payments:
		if not payment.mode_of_payment:
			continue

		is_wallet = frappe.db.get_value(
			"Mode of Payment",
			payment.mode_of_payment,
			"is_wallet_payment"
		)

		if is_wallet:
			wallet_amount += flt(payment.amount)

	return wallet_amount


@frappe.whitelist()
def get_customer_wallet_balance(customer, company=None, exclude_invoice=None):
	"""Số dư ví khách còn tiêu được.

	⚠ Chỉ gọi lại bản trong doctype Wallet, đừng chép logic sang đây. Trước đây
	hai file giữ hai bản giống hệt nhau; sửa cách tính số dư ở một bên là bên kia
	lệch ngay, mà lỗi lại hiện ra ở tận màn hình POS nên rất khó lần (PM-TASK-00106).
	"""
	from pos_next.pos_next.doctype.wallet.wallet import (
		get_customer_wallet_balance as _tinh_so_du,
	)

	return _tinh_so_du(customer, company, exclude_invoice)


def get_pending_wallet_payments(customer, exclude_invoice=None):
	"""Tổng tiền ví khách đã dùng trả hàng — gọi lại bản trong doctype Wallet."""
	from pos_next.pos_next.doctype.wallet.wallet import tong_tien_vi_da_tieu

	return tong_tien_vi_da_tieu(customer, None, exclude_invoice)


@frappe.whitelist()
def get_customer_wallet(customer, company=None):
	"""Get wallet details for a customer."""
	filters = {"customer": customer}
	if company:
		filters["company"] = company

	wallet = frappe.db.get_value(
		"Wallet",
		filters,
		["name", "customer", "company", "account", "status", "current_balance"],
		as_dict=True
	)

	if wallet:
		# Update balance
		wallet["balance"] = get_customer_wallet_balance(customer, company)

	return wallet


@frappe.whitelist()
def get_or_create_wallet(customer, company, pos_settings=None):
	"""Get existing wallet or create a new one."""

	# Check if wallet exists
	wallet = frappe.db.get_value(
		"Wallet",
		{"customer": customer, "company": company},
		["name", "customer", "company", "account", "status"],
		as_dict=True
	)

	if wallet:
		return wallet

	# Check if auto-create is enabled
	if not pos_settings:
		pos_profile = frappe.db.get_value(
			"POS Profile",
			{"company": company, "disabled": 0},
			"name"
		)
		if pos_profile:
			pos_settings = get_pos_settings(pos_profile)

	if pos_settings and not cint(pos_settings.get("auto_create_wallet")):
		return None

	# Get wallet account
	wallet_account = None
	if pos_settings:
		wallet_account = pos_settings.get("wallet_account")

	# Tài khoản khai trong Cài đặt POS phải THUỘC ĐÚNG CÔNG TY của ca bán.
	#
	# Trước đây lấy thẳng giá trị khai trong cài đặt mà không kiểm tra, nên khi
	# người dùng chọn nhầm tài khoản của công ty khác thì mọi ví tạo ra đều mang
	# tài khoản đó. Hậu quả: bút toán của công ty này rơi vào tài khoản của công
	# ty kia, và tới lúc HUỶ hoá đơn thì ERPNext chặn với thông báo "Account ...
	# does not belong to Company ..." — kế toán không huỷ được đơn sai
	# (PM-TASK-00059: 34/36 Cài đặt POS khai tài khoản của công ty khác,
	# kéo theo 887 ví và 975 bút toán sai sổ).
	if wallet_account:
		cty_taikhoan = frappe.db.get_value("Account", wallet_account, "company")
		if cty_taikhoan and cty_taikhoan != company:
			frappe.log_error(
				title="Wallet Account Company Mismatch",
				message=(
					f"Cài đặt POS khai tài khoản ví {wallet_account} thuộc công ty "
					f"{cty_taikhoan}, không phải {company}. Đã bỏ qua và dùng tài "
					f"khoản mặc định của công ty."
				),
			)
			wallet_account = None

	if not wallet_account:
		# Try to find a receivable account with 'wallet' in name
		wallet_account = frappe.db.get_value(
			"Account",
			{
				"company": company,
				"account_type": "Receivable",
				"is_group": 0,
				"name": ["like", "%wallet%"]
			},
			"name"
		)

	if not wallet_account:
		# Use default receivable account
		wallet_account = frappe.get_cached_value("Company", company, "default_receivable_account")

	if not wallet_account:
		frappe.log_error(
			f"Cannot create wallet for {customer}: No wallet account configured",
			"Wallet Creation Error"
		)
		return None

	# Create new wallet
	try:
		wallet_doc = frappe.get_doc({
			"doctype": "Wallet",
			"customer": customer,
			"company": company,
			"account": wallet_account,
			"status": "Active"
		})
		wallet_doc.insert(ignore_permissions=True)

		return wallet_doc

	except Exception as e:
		frappe.log_error(
			f"Failed to create wallet for {customer}: {str(e)}",
			"Wallet Creation Error"
		)
		return None


def get_pos_settings(pos_profile):
	"""Get POS Settings for a profile."""
	if not pos_profile:
		return None

	return frappe.db.get_value(
		"POS Settings",
		{"pos_profile": pos_profile},
		[
			"enable_loyalty_program",
			"default_loyalty_program",
			"wallet_account",
			"auto_create_wallet",
			"loyalty_to_wallet"
		],
		as_dict=True
	)


@frappe.whitelist()
def get_wallet_payment_methods(pos_profile):
	"""Get payment methods that are wallet-enabled for a POS profile."""
	payment_methods = frappe.get_all(
		"POS Payment Method",
		filters={"parent": pos_profile},
		fields=["mode_of_payment", "default"]
	)

	wallet_methods = []
	for method in payment_methods:
		is_wallet = frappe.db.get_value(
			"Mode of Payment",
			method.mode_of_payment,
			"is_wallet_payment"
		)
		if is_wallet:
			wallet_methods.append({
				"mode_of_payment": method.mode_of_payment,
				"default": method.default,
				"is_wallet_payment": True
			})

	return wallet_methods


@frappe.whitelist()
def get_wallet_info(customer, company, pos_profile=None):
	"""
	Get comprehensive wallet information for a customer.
	Used by POS frontend.
	"""
	result = {
		"wallet_enabled": False,
		"wallet_exists": False,
		"wallet_balance": 0.0,
		"wallet_account": None,
		"wallet_name": None,
		"auto_create": False,
		"loyalty_program": None,
		"loyalty_to_wallet": False
	}

	# Check if loyalty program is enabled in POS Settings
	if pos_profile:
		pos_settings = get_pos_settings(pos_profile)
		if pos_settings:
			result["wallet_enabled"] = cint(pos_settings.get("enable_loyalty_program"))
			result["wallet_account"] = pos_settings.get("wallet_account")
			result["auto_create"] = cint(pos_settings.get("auto_create_wallet"))
			result["loyalty_program"] = pos_settings.get("default_loyalty_program")
			result["loyalty_to_wallet"] = cint(pos_settings.get("loyalty_to_wallet"))

	if not result["wallet_enabled"]:
		return result

	# Get wallet details (support both pos_next and wallete status values)
	wallet = frappe.db.get_value(
		"Wallet",
		{"customer": customer, "company": company, "status": ["in", ["Active", "active"]]},
		["name", "account"],
		as_dict=True
	)

	if wallet:
		result["wallet_exists"] = True
		result["wallet_name"] = wallet.name
		result["wallet_balance"] = get_customer_wallet_balance(customer, company)
	elif result["auto_create"]:
		# Auto-create wallet for customer if enabled
		try:
			new_wallet = get_or_create_wallet(customer, company, pos_settings)
			if new_wallet:
				result["wallet_exists"] = True
				result["wallet_name"] = new_wallet.name if hasattr(new_wallet, 'name') else new_wallet.get("name")
				result["wallet_balance"] = 0.0  # New wallet starts with 0 balance
		except Exception as e:
			frappe.log_error(
				title="Auto-create Wallet Error",
				message=f"Customer: {customer}, Company: {company}, Error: {str(e)}"
			)

	return result


@frappe.whitelist()
def create_manual_wallet_credit(customer, company, amount, remarks=None):
	"""
	Create a manual wallet credit (for admin use).

	Args:
		customer: Customer ID
		company: Company
		amount: Amount to credit
		remarks: Optional remarks

	Returns:
		Wallet Transaction document name
	"""
	frappe.has_permission("Wallet Transaction", "create", throw=True)

	if flt(amount) <= 0:
		frappe.throw(_("Amount must be greater than zero"))

	# Get or create wallet
	wallet = get_or_create_wallet(customer, company)

	if not wallet:
		frappe.throw(_("Could not create wallet for customer {0}").format(customer))

	from pos_next.pos_next.doctype.wallet_transaction.wallet_transaction import create_wallet_credit

	transaction = create_wallet_credit(
		wallet=wallet.name if hasattr(wallet, 'name') else wallet["name"],
		amount=amount,
		source_type="Manual Adjustment",
		remarks=remarks or _("Manual wallet credit"),
		submit=True
	)

	return transaction.name
