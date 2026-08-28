# Copyright (c) 2024, BrainWise and contributors
# For license information, please see license.txt

import frappe
from frappe import _
from frappe.model.document import Document
from frappe.utils import flt


class Wallet(Document):
	def validate(self):
		self.validate_account_type()
		self.validate_duplicate_wallet()

	def validate_account_type(self):
		"""Wallet account must be a Receivable account"""
		if self.account:
			account_type = frappe.get_value("Account", self.account, "account_type")
			if account_type != "Receivable":
				frappe.throw(_("Wallet Account must be a Receivable type account"))

	def validate_duplicate_wallet(self):
		"""Check for duplicate wallet for same customer and company"""
		if not self.is_new():
			return
		existing = frappe.db.exists(
			"Wallet",
			{"customer": self.customer, "company": self.company, "name": ("!=", self.name)}
		)
		if existing:
			frappe.throw(_("A wallet already exists for customer {0} in company {1}").format(
				self.customer, self.company
			))

	def get_balance(self):
		"""Số dư ví = tổng điểm đã tích trừ phần khách đã tiêu."""
		return tinh_so_du_vi(self.customer, self.company)

	def get_available_balance(self):
		"""Số dư còn tiêu được.

		Bằng đúng số dư: `tinh_so_du_vi` đã trừ cả hoá đơn nháp đang giữ điểm,
		nên không trừ thêm lần nữa. Giữ hai trường vì giao diện POS đang đọc cả
		hai.
		"""
		return self.get_balance()

	def update_balance(self):
		"""Update the current_balance and available_balance fields"""
		self.current_balance = self.get_balance()
		self.available_balance = self.get_available_balance()
		self.db_set("current_balance", self.current_balance, update_modified=False)
		self.db_set("available_balance", self.available_balance, update_modified=False)


@frappe.whitelist()
def get_customer_wallet(customer, company=None):
	"""Get wallet for a customer"""
	filters = {"customer": customer}
	if company:
		filters["company"] = company

	wallet = frappe.db.get_value(
		"Wallet",
		filters,
		["name", "customer", "company", "account", "status"],
		as_dict=True
	)

	return wallet


@frappe.whitelist()
def get_customer_wallet_balance(customer, company=None, exclude_invoice=None):
	"""Số dư ví khách còn tiêu được.

	Args:
		customer: mã khách
		company: công ty (tuỳ chọn)
		exclude_invoice: hoá đơn đang lập — không tính phần điểm chính nó đang giữ,
			nếu không thì lúc kiểm tra số dư hoá đơn tự trừ chính mình

	Returns:
		float: số dư, không bao giờ âm
	"""
	try:
		filters = {"customer": customer, "status": "Active"}
		if company:
			filters["company"] = company

		if not frappe.db.exists("Wallet", filters):
			return 0.0

		so_du = tinh_so_du_vi(customer, company, exclude_invoice)
		return so_du if so_du > 0 else 0.0

	except Exception:
		frappe.log_error(frappe.get_traceback(), "Wallet Balance Error")
		return 0.0


def tinh_so_du_vi(customer, company=None, exclude_invoice=None):
	"""Số dư ví, tính từ bảng Wallet Transaction chứ KHÔNG từ sổ cái.

	Trước đây số dư đọc bằng `get_balance_on()` trên tài khoản ví. Cách đó chỉ
	đúng khi ví có tài khoản riêng — mà thực tế ví hay dùng chung 131 với công nợ
	bán hàng, nên điểm bị tiền hàng khách còn nợ lấn át và 749 ví hiển thị số dư
	0 (PM-TASK-00106). Từ khi bỏ bút toán lúc tích điểm thì sổ cái không còn dấu
	vết nào của ví nữa, đọc sổ chắc chắn ra 0.

	Nguồn sự thật giờ là hai bảng:
	  Wallet Transaction — điểm đã tích (và điểm bị điều chỉnh giảm, nếu có)
	  hoá đơn có hình thức thanh toán ví — điểm khách đã tiêu
	"""
	da_tich = tong_diem_da_tich(customer, company)
	da_tieu = tong_tien_vi_da_tieu(customer, company, exclude_invoice)
	return flt(da_tich) - flt(da_tieu)


def tong_diem_da_tich(customer, company=None):
	"""Cộng dồn phiếu ví đã ghi sổ: loại cộng thì cộng vào, loại trừ thì trừ ra."""
	dieu_kien = {"customer": customer, "docstatus": 1}
	if company:
		dieu_kien["company"] = company

	rows = frappe.get_all(
		"Wallet Transaction",
		filters=dieu_kien,
		fields=["transaction_type", "amount"],
	)

	tong = 0.0
	for row in rows:
		if row.transaction_type in ("Credit", "Loyalty Credit"):
			tong += flt(row.amount)
		else:
			tong -= flt(row.amount)
	return tong


def tong_tien_vi_da_tieu(customer, company=None, exclude_invoice=None):
	"""Tiền ví khách đã dùng để trả hàng, đọc thẳng từ hoá đơn.

	⚠ Tính CẢ hoá đơn đã thanh toán xong, không chỉ hoá đơn còn nợ. Bản cũ lọc
	`outstanding_amount > 0` vì hồi đó số dư lấy từ sổ cái — hoá đơn ghi sổ rồi
	thì sổ đã trừ, đếm lại là trừ hai lần. Nay số dư đếm từ Wallet Transaction,
	mà bảng đó KHÔNG có dòng nào khi khách tiêu điểm, nên bỏ sót hoá đơn đã
	thanh toán là cho khách tiêu đi tiêu lại cùng một số điểm.

	Hoá đơn trả hàng mang số tiền âm nên tự cộng điểm trả lại cho khách.
	"""
	dieu_kien = ["si.customer = %(customer)s", "si.docstatus in (0, 1)"]
	tham_so = {"customer": customer}
	if company:
		dieu_kien.append("si.company = %(company)s")
		tham_so["company"] = company
	if exclude_invoice:
		dieu_kien.append("si.name != %(exclude_invoice)s")
		tham_so["exclude_invoice"] = exclude_invoice

	tong = frappe.db.sql(
		"""
		select coalesce(sum(p.amount), 0)
		from `tabSales Invoice Payment` p
		join `tabSales Invoice` si on si.name = p.parent
		join `tabMode of Payment` mp on mp.name = p.mode_of_payment
		where mp.is_wallet_payment = 1 and {dieu_kien}
		""".format(dieu_kien=" and ".join(dieu_kien)),
		tham_so,
	)[0][0]

	return flt(tong)


def get_pending_wallet_payments(customer, exclude_invoice=None):
	"""Giữ tên cũ cho chỗ nào còn gọi tới — nay là tổng tiền ví ĐÃ TIÊU."""
	return tong_tien_vi_da_tieu(customer, None, exclude_invoice)


@frappe.whitelist()
def create_customer_wallet(customer, company, account=None):
	"""
	Create a wallet for a customer.

	Args:
		customer: Customer ID
		company: Company
		account: Wallet account (optional, will use default if not provided)

	Returns:
		Wallet document
	"""
	# Check if wallet already exists
	existing = frappe.db.exists("Wallet", {"customer": customer, "company": company})
	if existing:
		return frappe.get_doc("Wallet", existing)

	# Get default wallet account if not provided
	if not account:
		account = get_default_wallet_account(company)

	if not account:
		frappe.throw(_("Please configure a default wallet account for company {0}").format(company))

	wallet = frappe.get_doc({
		"doctype": "Wallet",
		"customer": customer,
		"company": company,
		"account": account,
		"status": "Active"
	})
	wallet.insert(ignore_permissions=True)

	return wallet


def get_default_wallet_account(company):
	"""Get default wallet account for a company"""
	# Try to get from POS Settings
	wallet_account = frappe.db.get_value(
		"POS Settings",
		{"company": company},
		"wallet_account"
	)

	if wallet_account:
		return wallet_account

	# Fallback: Find a receivable account with 'wallet' in the name
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

	return wallet_account


@frappe.whitelist()
def get_or_create_wallet(customer, company):
	"""Get existing wallet or create a new one"""
	wallet = get_customer_wallet(customer, company)

	if not wallet:
		wallet_doc = create_customer_wallet(customer, company)
		wallet = {
			"name": wallet_doc.name,
			"customer": wallet_doc.customer,
			"company": wallet_doc.company,
			"account": wallet_doc.account,
			"status": wallet_doc.status
		}

	return wallet
