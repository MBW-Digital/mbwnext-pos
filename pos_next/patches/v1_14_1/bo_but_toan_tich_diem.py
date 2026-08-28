"""Đảo bút toán đã ghi lúc tích điểm (PM-TASK-00106).

Hệ thống từng ghi sổ ngay khi khách mua hàng được tích điểm:
Nợ (tài khoản chi phí của chương trình) / Có (tài khoản ví, gắn tên khách).

Kế toán bác cách đó: điểm đã tích có thể không bao giờ được dùng, ghi chi phí
ngay lúc tích là ghi cho một khoản chưa chắc phát sinh. Chốt theo hướng chỉ ghi
khi khách THỰC SỰ tiêu điểm — lúc đó hoá đơn tự ghi Nợ 6418 - Chi phí bán hàng /
Có 131 qua hình thức thanh toán "đổi điểm".

Mã đã sửa để từ nay không ghi nữa. Còn những bút toán trót ghi thì phải đảo,
nếu không sổ vẫn gánh một khoản chi phí không có thật, và tài khoản ví vẫn treo
một khoản có lợi cho khách mà khách chưa từng được hưởng.

Quy mô lúc phân tích: 1.221 bút toán, 29.428 đ, chưa khách nào tiêu đồng
điểm nào — nên đảo lúc này là sạch nhất, không ai mất gì.

Patch CHỈ đảo cho công ty đã bật cờ "Không ghi sổ khi tích điểm ví" trong hồ sơ
Công ty — công ty chưa bật giữ nguyên cách cũ và không bị đụng tới. Trong phạm vi
đó, patch dò theo dấu vết thật (bút toán còn sống của chứng từ ví) chứ không gắn
cứng danh sách. Chạy lại lần nữa vô hại.

Bật cờ SAU khi đã migrate thì chạy tay:
  bench --site <site> execute pos_next.patches.v1_14_1.bo_but_toan_tich_diem.execute

Patch KHÔNG làm những việc sau — phải làm tay:
  1. Đổi tài khoản của hình thức thanh toán "đổi điểm" sang 6418 (hoặc tài khoản
     nhóm 641 do kế toán chỉ định). Còn để 131 thì đơn trả bằng điểm vẫn treo
     tiền, vì hai vế bút toán cùng một tài khoản nên triệt tiêu nhau.
  2. Đổi ô Tài khoản chi phí của Chương trình khách hàng thân thiết. Theo hướng
     mới ô đó không còn tác dụng với luồng ví, nhưng để 6238 - Chi phí bằng tiền
     khác (nằm dưới 623 - Chi phí sử dụng máy thi công) thì người sau đọc lại
     hiểu nhầm.
  3. Xoá điểm của khách. Điểm vẫn còn nguyên trong Wallet Transaction, chỉ là
     không còn nằm trên sổ cái nữa — số dư ví nay đếm từ bảng đó.
"""

from __future__ import annotations

import json
import os
import tempfile

import frappe
from frappe.utils import flt, now_datetime
from erpnext.accounts.general_ledger import make_reverse_gl_entries

CHUNG_TU_VI = "Wallet Transaction"


def execute():
	cong_ty_dinh = _cac_cong_ty_con_but_toan_vi()
	if not cong_ty_dinh:
		return

	if _so_dang_khoa():
		frappe.log_error(
			title="Bo qua patch but toan tich diem: so ke toan dang khoa",
			message="Mo khoa so roi chay lai: bench --site <site> migrate",
		)
		return

	for company in cong_ty_dinh:
		_dao_but_toan_cua_cong_ty(company)


def _cac_cong_ty_con_but_toan_vi() -> list[str]:
	rows = frappe.db.sql(
		"""
		SELECT company, COUNT(*) AS so_dong
		FROM `tabGL Entry`
		WHERE is_cancelled = 0 AND voucher_type = %s
		GROUP BY company
		""",
		CHUNG_TU_VI,
		as_dict=True,
	)
	# Chỉ đảo cho công ty đã CHỌN cách hạch toán mới. Đảo bút toán là việc không
	# quay lại được, không được phép tự làm cho công ty vẫn đang ghi sổ lúc tích
	# điểm — với họ những bút toán này là đúng, không phải rác.
	return [
		r.company
		for r in rows
		if frappe.db.get_value("Company", r.company, "pos_next_khong_ghi_so_khi_tich_diem")
	]


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


def _dao_but_toan_cua_cong_ty(company: str):
	# Sổ đã lệch từ trước thì đừng đụng vào — sửa tiếp chỉ làm khó truy nguyên.
	lech_truoc = _lech_so(company)
	if lech_truoc:
		frappe.log_error(
			title="Khong dao but toan tich diem: so da lech tu truoc",
			message=f"Cong ty {company} lech No-Co {lech_truoc}. Tim nguyen nhan truoc.",
		)
		return

	but_toan = frappe.db.sql(
		"""
		SELECT name, voucher_no, account, party, debit, credit, posting_date
		FROM `tabGL Entry`
		WHERE is_cancelled = 0 AND voucher_type = %s AND company = %s
		ORDER BY voucher_no
		""",
		(CHUNG_TU_VI, company),
		as_dict=True,
	)
	if not but_toan:
		return

	# Đảo chỉ những chứng từ đúng bản chất "tích điểm". Chứng từ ví loại khác
	# (nạp tiền thật, hoàn tiền vào ví) là nghĩa vụ có thật với khách, đảo đi là
	# xoá mất khoản mình đang nợ người ta.
	loai_theo_chung_tu = dict(
		frappe.db.sql(
			"""SELECT name, transaction_type FROM `tabWallet Transaction` WHERE company = %s""",
			company,
		)
	)
	chung_tu = sorted(
		{
			d.voucher_no
			for d in but_toan
			if loai_theo_chung_tu.get(d.voucher_no) == "Loyalty Credit"
		}
	)
	if not chung_tu:
		return

	duong_dan = _sao_luu(company, [d for d in but_toan if d.voucher_no in chung_tu])
	tong_tien = sum(flt(d.credit) for d in but_toan if d.voucher_no in chung_tu)

	for voucher_no in chung_tu:
		make_reverse_gl_entries(voucher_type=CHUNG_TU_VI, voucher_no=voucher_no)

	con_sot = frappe.db.count(
		"GL Entry",
		{
			"is_cancelled": 0,
			"voucher_type": CHUNG_TU_VI,
			"voucher_no": ["in", chung_tu],
		},
	)
	lech_sau = _lech_so(company)

	if con_sot or lech_sau:
		frappe.db.rollback()
		frappe.log_error(
			title="Da hoan tac dao but toan tich diem",
			message=(
				f"Cong ty {company}: con {con_sot} but toan chua dao, "
				f"lech No-Co sau khi dao {lech_sau}. Ban sao luu: {duong_dan}"
			),
		)
		return

	so_vi = _cap_nhat_so_du_da_luu(company)

	frappe.db.commit()
	print(
		f"  Da dao {len(chung_tu)} but toan tich diem cua {company} "
		f"(tong {tong_tien:,.0f}), tinh lai so du {so_vi} vi. Ban sao luu: {duong_dan}"
	)
	print(
		"  Patch KHONG doi tai khoan hinh thuc thanh toan 'doi diem' va "
		"tai khoan chi phi cua chuong trinh khach hang than thiet — phai sua tay."
	)


def _cap_nhat_so_du_da_luu(company: str) -> int:
	"""Ghi lại hai ô số dư đang lưu trên từng ví.

	Hai ô này chỉ được tính lại mỗi khi có phiếu ví mới, nên sau khi đổi cách
	tính chúng vẫn giữ số cũ lấy từ sổ cái — đúng những con số 0 mà khách đang
	nhìn thấy. Không cập nhật thì màn hình danh sách ví vẫn báo 0 trong khi POS
	cho tiêu bình thường, người dùng tưởng hệ thống loạn.
	"""
	from pos_next.pos_next.doctype.wallet.wallet import tinh_so_du_vi

	vi = frappe.get_all("Wallet", filters={"company": company}, fields=["name", "customer"])
	for dong in vi:
		so_du = tinh_so_du_vi(dong.customer, company)
		so_du = so_du if so_du > 0 else 0.0
		frappe.db.set_value("Wallet", dong.name, "current_balance", so_du, update_modified=False)
		frappe.db.set_value("Wallet", dong.name, "available_balance", so_du, update_modified=False)
	return len(vi)


def _sao_luu(company: str, but_toan: list[dict]) -> str:
	"""Ghi lại giá trị cũ trước khi đụng vào, để còn đường lần lại.

	Để ngoài repo: đây là dữ liệu kế toán thật của khách.
	"""
	ten = "but_toan_tich_diem_%s_%s.json" % (
		frappe.scrub(company),
		now_datetime().strftime("%Y%m%d_%H%M%S"),
	)
	duong_dan = os.path.join(tempfile.gettempdir(), ten)
	with open(duong_dan, "w", encoding="utf-8") as f:
		json.dump(but_toan, f, ensure_ascii=False, indent=1, default=str)
	return duong_dan
