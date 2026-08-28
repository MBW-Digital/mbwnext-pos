"""Chuyển bút toán tiền ví về đúng tài khoản của công ty ghi sổ (PM-TASK-00059).

Ô khai tài khoản ví trong Cài đặt POS từng nhận cả tài khoản của công ty khác.
Ví sinh ra theo đó mang tài khoản sai, nên bút toán của công ty này nằm trên
tài khoản của công ty kia. Hậu quả nặng nhất không phải sổ sách — số tiền chỉ
là điểm tích luỹ vài đồng mỗi giao dịch — mà là ERPNext chặn HUỶ mọi hoá đơn
có phát sinh ví, vì tài khoản không thuộc công ty của chứng từ.

Quy mô đã gặp: 1.139 bút toán, 1.139 hoá đơn không huỷ được, 750 khách.
Không thể sửa bằng phiếu kế toán điều chỉnh — ERPNext chặn đúng tài khoản đó
trong phiếu của công ty kia, tức chính cái chặn đang gây lỗi. Nên phải đưa bút
toán về đúng tài khoản, giữ nguyên số tiền, khách hàng và ngày hạch toán.

Patch dò theo công ty chứ không gắn cứng tên tài khoản, nên site không dính
lỗi thì chạy qua không làm gì. Chạy lại lần nữa cũng vô hại.
"""

from __future__ import annotations

import frappe
from frappe.utils import flt


def execute():
	sai = frappe.db.sql(
		"""
		SELECT gl.company, gl.account, COUNT(*) AS so_dong
		FROM `tabGL Entry` gl
		JOIN `tabAccount` a ON a.name = gl.account
		WHERE gl.is_cancelled = 0
		  AND gl.voucher_type = 'Wallet Transaction'
		  AND a.company != gl.company
		GROUP BY gl.company, gl.account
		""",
		as_dict=True,
	)
	if not sai:
		return

	if _so_dang_khoa():
		frappe.log_error(
			title="Bo qua patch but toan vi: so ke toan dang khoa",
			message="Mo khoa so roi chay lai: bench --site <site> migrate",
		)
		return

	for dong in sai:
		_chuyen_ve_dung_tai_khoan(dong.company, dong.account, dong.so_dong)


def _so_dang_khoa() -> bool:
	"""Frappe tra ve 0001-01-01 khi o ngay khoa so bo trong, khong phai None."""
	ngay = frappe.db.get_single_value("Accounts Settings", "acc_frozen_upto")
	return bool(ngay and frappe.utils.getdate(ngay).year > 1900)


def _lech_so(company: str) -> float:
	r = frappe.db.sql(
		"""SELECT ROUND(SUM(debit) - SUM(credit), 2) FROM `tabGL Entry`
		   WHERE is_cancelled = 0 AND company = %s""",
		company,
	)
	return flt(r[0][0]) if r else 0.0


def _chuyen_ve_dung_tai_khoan(company: str, tai_khoan_sai: str, so_dong: int):
	tai_khoan_dung = frappe.db.get_value("Company", company, "default_receivable_account")
	if not tai_khoan_dung:
		frappe.log_error(
			title="Khong sua duoc but toan vi: thieu tai khoan phai thu",
			message=f"Cong ty {company} chua khai Default Receivable Account.",
		)
		return

	# Sổ đã lệch từ trước thì đừng đụng vào — sửa tiếp chỉ làm khó truy nguyên.
	lech_truoc = _lech_so(company)
	if lech_truoc:
		frappe.log_error(
			title="Khong sua but toan vi: so da lech tu truoc",
			message=f"Cong ty {company} lech No-Co {lech_truoc}. Tim nguyen nhan truoc.",
		)
		return

	frappe.db.sql(
		"""UPDATE `tabGL Entry` SET account = %s
		   WHERE account = %s AND company = %s AND voucher_type = 'Wallet Transaction'""",
		(tai_khoan_dung, tai_khoan_sai, company),
	)

	if _lech_so(company):
		frappe.db.rollback()
		frappe.log_error(
			title="Da hoan tac sua but toan vi: so bi lech sau khi sua",
			message=f"Cong ty {company}, tai khoan {tai_khoan_sai} -> {tai_khoan_dung}.",
		)
		return

	frappe.db.commit()
	print(
		f"  Da chuyen {so_dong} but toan vi cua {company}: "
		f"{tai_khoan_sai} -> {tai_khoan_dung}"
	)
