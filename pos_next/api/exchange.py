# Copyright (c) 2026, MBW and contributors
# For license information, please see license.txt

"""Đổi / trả hàng trên POS (PM-FEAT-00060).

Một lần đổi hàng sinh ra 2 chứng từ trong CÙNG một transaction:

1. Phiếu trả (Sales Invoice `is_return=1`) gắn HĐ gốc.
2. HĐ mới (Sales Invoice thường) cho hàng khách lấy thêm — nếu có.

Lỗi ở bất kỳ bước nào thì Frappe rollback cả request, không có trường hợp trả xong
mà không có HĐ mới. Trả hàng thuần (không lấy hàng mới) đi cùng đường này, chỉ là
không có bước 2.

Tiền tính theo GIỎ GỘP (spec `docs/features/doi-hang.md` mục 6.2):

    Phải trả mới = hàng giữ lại (giá lúc mua) + hàng mới (giá hiện hành)
                   − KM tổng đơn gốc nếu giỏ gộp vẫn đủ ngưỡng
    Chênh        = Phải trả mới − tổng HĐ gốc

Cách chia số tiền đó vào 2 chứng từ:

- Phiếu trả luôn hoàn theo giá THỰC TRẢ của dòng trả (đã trừ phần KM tổng đơn
  phân bổ cho dòng đó — y như hộp thoại trả hàng cũ, PM-TASK-00100).
- KM còn hiệu lực → phần KM của dòng trả CHUYỂN sang HĐ mới (`discount_amount`),
  nên đổi size cùng giá thì chênh 0đ.
- KM mất hiệu lực → thu hồi phần KM đang nằm trên hàng GIỮ LẠI qua `write_off`
  của phiếu trả. Đúng bằng `KM − phần đã phân bổ cho dòng trả`, KHÔNG phải cả KM:
  trừ cả KM là trừ trùng phần của dòng trả (lỗi số 1 của hộp thoại cũ).

Thứ tự dùng tiền trả lại: trừ công nợ HĐ gốc trước (D7), rồi trả cho HĐ mới, phần
còn dư mới hoàn / ghi có / chặn theo `POS Settings.exchange_negative_difference`.
"""

from __future__ import annotations

import json
from contextlib import contextmanager

import frappe
from frappe import _
from frappe.utils import cint, flt, getdate, nowdate

from pos_next.api.invoices import (
	_build_return_transaction_rule_data,
	submit_invoice,
	validate_return_items,
)

DOCTYPE = "Sales Invoice"
# Sai số làm tròn cho phép khi so số tiền dự tính với số ERPNext tính thật
SAI_SO = 1.0


# ---------------------------------------------------------------------------
# Đọc cấu hình & kiểm tra HĐ gốc
# ---------------------------------------------------------------------------


def _pos_settings(pos_profile):
	fields = [
		"allow_return",
		"return_validity_days",
		"exchange_negative_difference",
		"allow_credit_sale",
		"allow_customer_credit_payment",
	]
	row = frappe.db.get_value("POS Settings", {"pos_profile": pos_profile}, fields, as_dict=True)
	return row or frappe._dict({f: None for f in fields})


def _co_the_ghi_co(settings):
	"""Số dư khách chỉ tiêu được khi bật bán chịu hoặc thanh toán bằng số dư (PM-TASK-00186)."""
	return bool(cint(settings.allow_credit_sale) or cint(settings.allow_customer_credit_payment))


def _ngay_khoa_so(company):
	"""Ngày khóa sổ muộn nhất của công ty (Accounts Settings hoặc Period Closing Voucher)."""
	ngay = [
		getdate(d)
		for d in (
			frappe.db.get_single_value("Accounts Settings", "acc_frozen_upto"),
			frappe.db.get_value("Period Closing Voucher", {"company": company, "docstatus": 1}, "max(period_end_date)"),
		)
		if d
	]
	return max(ngay) if ngay else None


def _ky_da_khoa_so(company, posting_date):
	"""Ngày cuối cùng đã khóa sổ của công ty, nếu `posting_date` rơi vào đó."""
	posting_date = getdate(posting_date)
	frozen = frappe.db.get_single_value("Accounts Settings", "acc_frozen_upto")
	if frozen and posting_date <= getdate(frozen):
		return getdate(frozen)
	pcv = frappe.db.get_value(
		"Period Closing Voucher",
		{"company": company, "docstatus": 1},
		"max(period_end_date)",
	)
	if pcv and posting_date <= getdate(pcv):
		return getdate(pcv)
	return None


def _kiem_tra_hoa_don_goc(original, pos_profile, lock=False):
	"""Các luật chặn đã chốt (A3, A5, A6, A8, H3). Ném lỗi nếu không được đổi trả."""
	if lock:
		# H8: hai quầy cùng lập phiếu trên một HĐ — quầy sau phải chờ quầy trước xong
		frappe.db.sql(f"select name from `tab{DOCTYPE}` where name=%s for update", original.name)

	if original.docstatus != 1 or cint(original.is_return):
		frappe.throw(_("Invoice {0} cannot be returned.").format(original.name))

	if original.pos_profile != pos_profile:
		frappe.throw(
			_("Invoice {0} was sold at another store ({1}). Returns are only accepted at the store that sold it.").format(
				original.name, original.pos_profile
			)
		)

	settings = _pos_settings(pos_profile)
	if not cint(settings.allow_return):
		frappe.throw(_("Returns are disabled for this store."))

	da_tra = frappe.db.get_value(
		DOCTYPE,
		{"return_against": original.name, "is_return": 1, "docstatus": 1},
		["name", "posting_date"],
		as_dict=True,
	)
	if da_tra:
		frappe.throw(
			_("Invoice {0} was already returned / exchanged on {1} ({2}). Each invoice can only be returned once.").format(
				original.name, frappe.format_value(da_tra.posting_date, {"fieldtype": "Date"}), da_tra.name
			)
		)

	khoa = _ky_da_khoa_so(original.company, original.posting_date)
	if khoa:
		frappe.throw(
			_("Invoice {0} belongs to a closed accounting period (up to {1}). It cannot be returned.").format(
				original.name, frappe.format_value(khoa, {"fieldtype": "Date"})
			)
		)
	# Hạn đổi trả (A6) do validate_return_items kiểm — chặn cứng, không duyệt vượt.
	return settings


# ---------------------------------------------------------------------------
# Dựng chứng từ trong bộ nhớ để tính tiền (không lưu)
# ---------------------------------------------------------------------------


def _tong_thanh_toan(doc):
	"""[mobile] Tổng ERPNext dùng để đối chiếu thanh toán và ghi công nợ: `rounded_total` khi chứng từ có
	làm tròn, không thì `grand_total` (giữ dấu của chứng từ).

	Tính tiền theo `grand_total` trong khi ERPNext ghi công nợ theo `rounded_total` là lệch đúng phần làm
	tròn. Đo 17/10 trên ACC-SINV-2026-00116 (tổng 2.682, làm tròn 2.700, đã trả 1.000, nợ 1.700): trả hết thì
	hoàn 982 + trừ nợ 1.700 = 2.682, HĐ gốc còn treo −18 — khách được ghi có ảo 18đ.
	"""
	if not cint(doc.get("disable_rounded_total")) and flt(doc.get("rounded_total")):
		return flt(doc.rounded_total)
	return flt(doc.grand_total)


@contextmanager
def _khoa_commit():
	"""[mobile] Trong khối này `frappe.db.commit()` không làm gì: phiếu trả và HĐ mới chỉ được ghi khi cả
	request xong (Frappe tự commit), lỗi ở bước nào thì rollback hết.

	Cờ `pos_next_dang_doi_hang` chỉ chặn được commit của pos_next. Hook của app khác vẫn commit giữa chừng:
	`mbwnext_integration_dms` (`sync_helper.create_sync_queue_item`, chạy ở on_submit Sales Invoice) gọi
	`frappe.db.commit()`. Đo 17/10: thu hồi tiền ví lỗi sau đó thì phiếu trả vẫn còn, ở trạng thái dở.
	Các hàm `after_commit` đã đăng ký vẫn chạy ở lần commit thật cuối request.
	"""
	frappe.db.commit = lambda *args, **kwargs: None
	try:
		yield
	finally:
		# Bỏ thuộc tính gắn trên đối tượng là về lại phương thức `commit` của lớp.
		del frappe.db.commit


def _dung_tam(data):
	"""Dựng Sales Invoice trong bộ nhớ, tính thuế và tổng y như update_invoice()
	nhưng KHÔNG lưu — lưu nháp sẽ bắn sự kiện realtime "có hóa đơn mới" tới các quầy.
	"""
	from pos_next.api.sales_invoice_hooks import capture_pos_authoritative_discounts
	from pos_next.controllers.python.sales_invoice import apply_selling_item_tax_templates

	doc = frappe.get_doc(dict(data, doctype=DOCTYPE))
	doc.is_pos = 1
	doc.update_stock = 1
	if not doc.get("posting_date"):
		doc.posting_date = nowdate()
	if doc.pos_profile:
		profile = frappe.get_cached_doc("POS Profile", doc.pos_profile)
		if not doc.get("company"):
			doc.company = profile.company
		if not doc.get("currency"):
			doc.currency = profile.currency
		disable_rounded = frappe.db.get_value("POS Profile", doc.pos_profile, "disable_rounded_total")
		doc.disable_rounded_total = cint(disable_rounded) if disable_rounded is not None else 1
	capture_pos_authoritative_discounts(doc)
	doc.set_missing_values()
	# set_missing_values() chép ignore_pricing_rule từ POS Profile, đè giá trị đã đặt
	if cint(data.get("ignore_pricing_rule")):
		doc.ignore_pricing_rule = 1
	apply_selling_item_tax_templates(doc)
	doc.calculate_taxes_and_totals()
	# Chạy đủ validate (gồm hook của các app) như lúc lưu thật. Chỉ tính một lần
	# calculate_taxes_and_totals() thì thuế gồm trong giá + chiết khấu tổng đơn ra sai
	# (đo: phiếu trả 3.135.020 thay vì 2.879.100) — số đúng chỉ có sau validate.
	doc.flags.ignore_permissions = True
	doc.run_method("validate")
	return doc


def _diem_cua_hd(invoice_name):
	return cint(
		frappe.db.get_value(
			"Loyalty Point Entry",
			{"invoice_type": DOCTYPE, "invoice": invoice_name, "loyalty_points": [">", 0]},
			"sum(loyalty_points)",
		)
	)


def _thu_hoi_diem(original, tra_tam):
	"""E2: điểm của HĐ gốc đã quy ra tiền ví (POS Settings `loyalty_to_wallet`).

	Khi trả hàng, ERPNext tự tính lại điểm của HĐ gốc (ít đi) nhưng tiền đã cộng
	vào ví thì `pos_next` không thu lại — khách giữ tiền ví của món đã trả. Ở đây
	tính phần phải thu: trừ vào ví trước, ví không đủ thì phần thiếu trừ vào tiền
	hoàn (anh Thắng chốt 24/09).

	Số điểm sau trả dự tính theo đúng công thức của CustomSalesInvoice /
	ERPNext (make_loyalty_point_entry), rồi đối chiếu lại sau khi lưu phiếu trả.
	"""
	from pos_next.api.loyalty_exclusion import (
		get_loyalty_eligible_amount,
		get_loyalty_excluded_item_lines,
	)
	from pos_next.pos_next.doctype.wallet.wallet import tinh_so_du_vi

	rong = frappe._dict(diem_truoc=0, diem_sau=0, tien=0.0, tru_vi=0.0, thieu=0.0)
	if not original.loyalty_program:
		return rong
	cai_dat = frappe.db.get_value(
		"POS Settings", {"pos_profile": original.pos_profile},
		["enable_loyalty_program", "loyalty_to_wallet"], as_dict=True,
	)
	if not cai_dat or not (cint(cai_dat.enable_loyalty_program) and cint(cai_dat.loyalty_to_wallet)):
		return rong

	da_cong_vi = flt(
		frappe.db.get_value(
			"Wallet Transaction",
			{"reference_doctype": DOCTYPE, "reference_name": original.name,
			 "transaction_type": "Loyalty Credit", "docstatus": 1},
			"sum(amount)",
		)
	)
	diem_truoc = _diem_cua_hd(original.name)
	if not da_cong_vi or not diem_truoc:
		return rong

	loai_tru = get_loyalty_excluded_item_lines(original.loyalty_program)
	hien_tai = get_loyalty_eligible_amount(original, loai_tru)
	da_tra = abs(get_loyalty_eligible_amount(tra_tam, loai_tru))
	he_so = flt(frappe.db.get_value("Loyalty Program", original.loyalty_program, "conversion_factor")) or 1.0
	# Hạng thành viên (và hệ số tích điểm) do ERPNext chọn theo tổng chi tiêu, tính lúc
	# dựng lại điểm — khi đó điểm cũ của HĐ gốc ĐÃ bị xoá. Giả lập đúng trạng thái đó
	# trong một savepoint rồi hoàn tác.
	from erpnext.accounts.doctype.loyalty_program.loyalty_program import (
		get_loyalty_program_details_with_points,
	)

	frappe.db.savepoint("pos_next_du_tinh_diem")
	try:
		frappe.db.delete("Loyalty Point Entry", {"invoice_type": DOCTYPE, "invoice": original.name})
		lp = get_loyalty_program_details_with_points(
			original.customer,
			company=original.company,
			current_transaction_amount=hien_tai,
			loyalty_program=original.loyalty_program,
			expiry_date=original.posting_date,
			include_expired_entry=True,
		)
	finally:
		frappe.db.rollback(save_point="pos_next_du_tinh_diem")
	tich_luy = flt(lp.collection_factor) if lp else 1.0
	diem_sau = max(0, cint((hien_tai - da_tra) / (tich_luy or 1.0)))
	tien = min(da_cong_vi, flt((diem_truoc - diem_sau) * he_so))
	if tien <= 0:
		return frappe._dict(rong, diem_truoc=diem_truoc, diem_sau=diem_sau)

	so_du = max(0.0, flt(tinh_so_du_vi(original.customer, original.company)))
	tru_vi = min(so_du, tien)
	return frappe._dict(
		diem_truoc=diem_truoc, diem_sau=diem_sau, tien=tien, tru_vi=tru_vi, thieu=flt(tien - tru_vi)
	)


def _gia_tri_tinh_nguong(rows):
	"""Giá trị so với ngưỡng KM: price_list_rate × qty — cùng cơ sở với POS lúc bán."""
	return sum(flt(r.get("price_list_rate") or r.get("rate")) * abs(flt(r.get("qty"))) for r in rows)


def _chuan_hoa(payload):
	if isinstance(payload, str):
		payload = json.loads(payload)
	return frappe._dict(payload or {})


def _serial_cua_dong(row):
	"""[mobile] Serial đã bán trên một dòng HĐ gốc, theo thứ tự. Đọc bundle trước (v15), rồi tới ô `serial_no`."""
	if row.get("serial_and_batch_bundle"):
		ds = frappe.get_all(
			"Serial and Batch Entry",
			filters={"parent": row.serial_and_batch_bundle},
			order_by="idx asc",
			pluck="serial_no",
		)
		ds = [s for s in ds if s]
		if ds:
			return ds
	return [s.strip() for s in (row.get("serial_no") or "").splitlines() if s.strip()]


def _serial_tra(goc, qty, chon):
	"""[mobile] Serial khách trả của một dòng có serial (F2: đúng máy đã bán).

	Không chỉ rõ thì chỉ cho khi trả cả dòng. Trả bớt mà để ERPNext tự chọn thì nó lấy serial ĐẦU của dòng gốc,
	không phải máy khách mang tới — đo thật: bán DTB-0001 + 0002, trả 1 máy, sổ ghi 0001 về kho.
	"""
	ban = _serial_cua_dong(goc)
	if isinstance(chon, str):
		chon = chon.splitlines()
	chon = list(dict.fromkeys(s.strip() for s in (chon or []) if s and s.strip()))
	if not chon:
		if qty < len(ban):
			frappe.throw(_("Select which serial numbers of {0} the customer is returning.").format(goc.item_name))
		chon = ban
	la = [s for s in chon if s not in ban]
	if la:
		frappe.throw(_("Serial number {0} was not sold on this line of {1}.").format(la[0], goc.item_name))
	if len(chon) != qty:
		frappe.throw(
			_("Returning {0} of {1} needs exactly {0} serial numbers ({2} selected).").format(
				frappe.format_value(qty), goc.item_name, len(chon)
			)
		)
	return "\n".join(chon)


def _dong_tra(original, return_items, reason):
	"""Dòng phiếu trả lấy từ HĐ GỐC, không tin giá client gửi lên."""
	if not return_items:
		frappe.throw(_("Select at least one item to return."))

	ly_do = frappe.db.get_value(
		"POS Return Reason", reason, ["name", "stock_destination", "disabled"], as_dict=True
	) if reason else None
	if not ly_do or cint(ly_do.disabled):
		frappe.throw(_("Please select a return reason."))

	kho_loi = None
	if ly_do.stock_destination == "Defective":
		kho_loi = frappe.db.get_value("POS Profile", original.pos_profile, "posa_defective_warehouse")
		if not kho_loi:
			frappe.throw(
				_("Reason {0} sends items to the Defective Warehouse, but POS Profile {1} has no Defective Warehouse.").format(
					ly_do.name, original.pos_profile
				)
			)

	theo_dong = {row.name: row for row in original.items}
	rows = []
	for it in return_items:
		goc = theo_dong.get(it.get("sales_invoice_item"))
		qty = abs(flt(it.get("qty")))
		if not goc or qty <= 0:
			frappe.throw(_("Invalid return line."))
		if qty > flt(goc.qty) + 1e-9:
			frappe.throw(_("You are trying to return more {0} than was sold.").format(goc.item_name))

		# F7: hàng dịch vụ / không quản kho thì không hoàn. Combo (Product Bundle) cũng
		# là mã không quản kho nhưng có hàng thật bên trong, nên vẫn trả được.
		if not cint(frappe.get_cached_value("Item", goc.item_code, "is_stock_item")) and not frappe.db.exists(
			"Product Bundle", {"new_item_code": goc.item_code, "disabled": 0}
		):
			frappe.throw(_("{0} is a service item and cannot be returned.").format(goc.item_name))

		# F3/F4: chỉ trả số lẻ khi ĐVT cho phép (hàng cân)
		if qty != int(qty) and cint(frappe.get_cached_value("UOM", goc.uom, "must_be_whole_number")):
			frappe.throw(_("{0} must be returned in whole {1}.").format(goc.item_name, goc.uom))

		# [mobile] Dòng có serial: trả đúng các serial khách mang tới, ERPNext dựng bundle theo ô `serial_no`
		serial_tra = _serial_tra(goc, qty, it.get("serial_no")) if _serial_cua_dong(goc) else None

		rows.append(
			{
				"item_code": goc.item_code,
				"item_name": goc.item_name,
				"qty": -qty,
				"rate": goc.rate,
				"price_list_rate": goc.price_list_rate,
				"discount_percentage": goc.discount_percentage,
				"is_free_item": goc.is_free_item,
				"item_tax_template": goc.item_tax_template,
				"warehouse": kho_loi or goc.warehouse,
				"uom": goc.uom,
				"conversion_factor": goc.conversion_factor or 1,
				"sales_invoice_item": goc.name,
				"batch_no": goc.get("batch_no"),
				"serial_no": serial_tra if serial_tra is not None else goc.get("serial_no"),
				**({"use_serial_batch_fields": 1} if serial_tra is not None else {}),
			}
		)
	return rows, ly_do.name


# ---------------------------------------------------------------------------
# Lập kế hoạch tiền
# ---------------------------------------------------------------------------


def _lap_ke_hoach(original, pos_profile, pos_opening_shift, return_items, new_items, reason, ghi_co=False):
	"""Tính toàn bộ số tiền của một lần đổi / trả. Dùng chung cho xem trước và lưu thật."""
	dong_tra, ly_do = _dong_tra(original, return_items, reason)

	# Hạn đổi trả, quà tặng kèm (C5): dùng lại kiểm tra của hộp thoại cũ
	kq = validate_return_items(original.name, [dict(d, qty=d["qty"]) for d in dong_tra])
	if not kq.get("valid"):
		frappe.throw(kq.get("message"))

	ck_tong = abs(flt(original.discount_amount))
	tong_dong_goc = abs(flt(original.total))
	tong_dong_tra = sum(flt(d["rate"]) * abs(flt(d["qty"])) for d in dong_tra)
	ck_dong_tra = flt(ck_tong * tong_dong_tra / tong_dong_goc) if ck_tong and tong_dong_goc else 0
	ck_dong_tra = flt(round(ck_dong_tra))

	# --- KM ngưỡng còn hiệu lực trên giỏ gộp? ---
	rule = _build_return_transaction_rule_data(
		original.name, original.as_dict(), frappe.db.has_column(DOCTYPE, "posa_transaction_pricing_rule")
	)
	so_tra_theo_dong = {d["sales_invoice_item"]: abs(flt(d["qty"])) for d in dong_tra}
	dong_giu_lai = [
		{"price_list_rate": r.price_list_rate, "rate": r.rate, "qty": flt(r.qty) - so_tra_theo_dong.get(r.name, 0)}
		for r in original.items
		if not cint(r.is_free_item)
	]
	gia_tri_giu_lai = _gia_tri_tinh_nguong(dong_giu_lai)
	gia_tri_moi = _gia_tri_tinh_nguong(new_items or [])
	nguong = flt(rule.get("min_amount")) if rule else 0
	giu_km = not nguong or (gia_tri_giu_lai + gia_tri_moi) >= nguong

	# --- Phiếu trả ---
	tra = {
		"customer": original.customer,
		"company": original.company,
		"pos_profile": pos_profile,
		"posa_pos_opening_shift": pos_opening_shift,
		"is_return": 1,
		"return_against": original.name,
		"update_outstanding_for_self": 0,
		"selling_price_list": original.selling_price_list,
		"currency": original.currency,
		"items": dong_tra,
		"posa_return_reason": ly_do,
		"remarks": _("Return against {0}").format(original.name),
		# KM tổng đơn do logic giỏ gộp quyết định, ERPNext không được tự áp lại
		"ignore_pricing_rule": 1,
	}
	if ck_dong_tra:
		tra["apply_discount_on"] = original.apply_discount_on or "Grand Total"
		tra["discount_amount"] = -ck_dong_tra
	tra_tam = _dung_tam(tra)
	hoan_theo_dong = -_tong_thanh_toan(tra_tam)  # số dương

	thu_hoi_km = 0.0
	chuyen_km = 0.0
	if ck_tong:
		if giu_km:
			chuyen_km = ck_dong_tra if new_items else 0.0
		else:
			# Chỉ thu phần KM đang nằm trên hàng giữ lại (lỗi trừ trùng số 1)
			thu_hoi_km = flt(round(ck_tong - ck_dong_tra))

	# --- HĐ mới ---
	moi_tam = None
	tong_moi = 0.0
	if new_items:
		tong_truoc_ck = sum(flt(d.get("rate")) * flt(d.get("qty")) for d in new_items)
		# KM không quy ra tiền: phần chuyển sang không vượt giá trị hàng mới
		chuyen_km = min(chuyen_km, tong_truoc_ck)
		moi = {
			"customer": original.customer,
			"company": original.company,
			"pos_profile": pos_profile,
			"posa_pos_opening_shift": pos_opening_shift,
			"selling_price_list": original.selling_price_list,
			"currency": original.currency,
			"items": new_items,
			"posa_is_exchange": 1,
			# Không để ERPNext tự áp KM tổng đơn cho riêng HĐ mới: KM tổng đơn của lần
			# đổi tính trên GIỎ GỘP (chuyển phần KM của dòng trả sang). Đo thật: món mới
			# 5 triệu tự đủ ngưỡng, ERPNext giảm thêm 10% đè lên → khách trả thiếu 180.100.
			# Giá từng dòng vẫn là giá giỏ POS gửi (đã gồm KM dòng hiện hành, B8).
			"ignore_pricing_rule": 1,
		}
		if chuyen_km:
			moi["apply_discount_on"] = original.apply_discount_on or "Grand Total"
			moi["discount_amount"] = chuyen_km
		moi_tam = _dung_tam(moi)
		tong_moi = _tong_thanh_toan(moi_tam)

	hoan = max(0.0, hoan_theo_dong - thu_hoi_km)
	thu_hoi_km = hoan_theo_dong - hoan  # không thu hồi quá số hoàn

	# E2: tiền ví sinh ra từ điểm của phần hàng trả. Ví không đủ thì trừ vào tiền hoàn
	# (phần này ghi sổ bằng bút toán riêng, không qua write-off của phiếu trả).
	diem = _thu_hoi_diem(original, tra_tam)
	hoan = hoan - diem.thieu

	# --- Chia tiền: công nợ HĐ gốc → HĐ mới → phần dư ---
	no_goc = max(0.0, flt(original.outstanding_amount))
	tru_no = min(no_goc, hoan)
	con_lai = hoan - tru_no
	dung_cho_hd_moi = min(con_lai, tong_moi)
	khach_tra_them = tong_moi - dung_cho_hd_moi
	du = con_lai - dung_cho_hd_moi

	settings = _pos_settings(pos_profile)
	cach_xu_ly_du = None
	if du > SAI_SO:
		if new_items:
			# Đổi sang hàng rẻ hơn: cửa hàng cấu hình (B3)
			cach_xu_ly_du = settings.exchange_negative_difference or "Refund"
		else:
			# Trả hàng thuần: thu ngân chọn hoàn tiền hay ghi vào số dư (như hộp thoại cũ)
			cach_xu_ly_du = "Customer Credit" if ghi_co else "Refund"
		# Số dư khách không tiêu được thì ghi có là làm khách mất tiền (PM-TASK-00186)
		if cach_xu_ly_du == "Customer Credit" and not _co_the_ghi_co(settings):
			cach_xu_ly_du = "Refund"

	return frappe._dict(
		original=original,
		settings=settings,
		dong_tra=dong_tra,
		ly_do=ly_do,
		tra=tra,
		moi=moi if new_items else None,
		giu_km=giu_km,
		nguong_km=nguong,
		gia_tri_gio_gop=gia_tri_giu_lai + gia_tri_moi,
		ck_tong=ck_tong,
		ck_dong_tra=ck_dong_tra,
		chuyen_km=chuyen_km,
		thu_hoi_km=thu_hoi_km,
		hoan_theo_dong=hoan_theo_dong,
		hoan=hoan,
		diem=diem,
		tong_moi=tong_moi,
		no_goc=no_goc,
		tru_no=tru_no,
		dung_cho_hd_moi=dung_cho_hd_moi,
		khach_tra_them=khach_tra_them,
		du=du if du > SAI_SO else 0.0,
		cach_xu_ly_du=cach_xu_ly_du,
		chenh=tong_moi - hoan,  # > 0 khách trả thêm, < 0 trả lại khách (trước khi trừ nợ)
	)


def _tom_tat(plan):
	"""Phần trả về cho màn hình POS (không lộ chứng từ nháp)."""
	return {
		"keeps_promotion": plan.giu_km,
		"promotion_threshold": plan.nguong_km,
		"basket_value": plan.gia_tri_gio_gop,
		"promotion_total": plan.ck_tong,
		"promotion_on_returned_lines": plan.ck_dong_tra,
		"promotion_moved_to_new_invoice": plan.chuyen_km,
		"promotion_reclaimed": plan.thu_hoi_km,
		"loyalty_points_before": plan.diem.diem_truoc,
		"loyalty_points_after": plan.diem.diem_sau,
		"loyalty_wallet_reclaimed": plan.diem.tien,
		"loyalty_taken_from_wallet": plan.diem.tru_vi,
		"loyalty_deducted_from_refund": plan.diem.thieu,
		"return_value": plan.hoan_theo_dong,
		"refund_value": plan.hoan,
		"new_invoice_total": plan.tong_moi,
		"original_outstanding": plan.no_goc,
		"applied_to_outstanding": plan.tru_no,
		"applied_to_new_invoice": plan.dung_cho_hd_moi,
		"customer_pays": plan.khach_tra_them,
		"leftover": plan.du,
		"leftover_mode": plan.cach_xu_ly_du,
		"difference": plan.chenh,
	}


# ---------------------------------------------------------------------------
# API
# ---------------------------------------------------------------------------


@frappe.whitelist()
def calculate_exchange(payload):
	"""Xem trước số tiền của một lần đổi / trả. Không lưu gì.

	payload: {invoice_name, pos_profile, pos_opening_shift, return_reason,
	          return_items: [{sales_invoice_item, qty}], new_items: [dòng giỏ hàng POS]}
	"""
	p = _chuan_hoa(payload)
	original = frappe.get_doc(DOCTYPE, p.invoice_name)
	original.check_permission("read")
	_kiem_tra_hoa_don_goc(original, p.pos_profile)
	plan = _lap_ke_hoach(
		original, p.pos_profile, p.pos_opening_shift, p.return_items, p.new_items, p.return_reason,
		ghi_co=cint(p.add_to_customer_credit),
	)
	ket_qua = _tom_tat(plan)
	# Cho màn hình biết trước quỹ tiền mặt để gợi ý cách hoàn (D9)
	if p.pos_opening_shift and plan.du and plan.cach_xu_ly_du == "Refund":
		ket_qua["cash_mode_of_payment"], ket_qua["cash_in_shift"] = _tien_mat_trong_ca(p.pos_opening_shift)
	return ket_qua


def _thuc_hien_thu_hoi_diem(original, phieu_tra, diem):
	"""Trừ ví phần tiền điểm của hàng trả; phần ví không đủ thì ghi bút toán thu lại.

	Phần thiếu đã được trừ khỏi tiền hoàn trong kế hoạch. Bút toán ghi:
	    Nợ 131 (khách, gắn HĐ gốc) / Có TK chi phí của Chương trình khách hàng thân thiết
	tức đảo đúng bút toán lúc khách tiêu tiền ví (Nợ 6418 / Có 131, PM-TASK-00106).
	"""
	diem_that = _diem_cua_hd(original.name)
	if diem_that != diem.diem_sau:
		frappe.throw(
			_("Loyalty points after return ({0}) do not match the calculation ({1}). Nothing was saved.").format(
				diem_that, diem.diem_sau
			)
		)

	tk_chi_phi = frappe.db.get_value("Loyalty Program", original.loyalty_program, "expense_account")
	if diem.tru_vi > SAI_SO:
		vi = frappe.db.get_value("Wallet", {"customer": original.customer, "company": original.company}, "name")
		if not vi:
			frappe.throw(_("Customer {0} has no wallet to reclaim loyalty credit from.").format(original.customer))
		gd = frappe.get_doc(
			{
				"doctype": "Wallet Transaction",
				"transaction_type": "Debit",
				"wallet": vi,
				"company": original.company,
				"posting_date": nowdate(),
				"amount": diem.tru_vi,
				"source_type": "Loyalty Program",
				"source_account": tk_chi_phi,
				"reference_doctype": DOCTYPE,
				"reference_name": phieu_tra.name,
				"remarks": _("Reclaim loyalty credit of returned items: {0} ({1} → {2} points)").format(
					original.name, diem.diem_truoc, diem.diem_sau
				),
			}
		)
		gd.insert(ignore_permissions=True)
		gd.submit()

	if diem.thieu > SAI_SO:
		if not tk_chi_phi:
			frappe.throw(_("Loyalty Program {0} has no Expense Account.").format(original.loyalty_program))
		cost_center = frappe.get_cached_value("Company", original.company, "cost_center")
		je = frappe.get_doc(
			{
				"doctype": "Journal Entry",
				"voucher_type": "Journal Entry",
				"posting_date": nowdate(),
				"company": original.company,
				"user_remark": _("Loyalty credit already spent, deducted from refund of {0} (return {1})").format(
					original.name, phieu_tra.name
				),
				"accounts": [
					{
						"account": original.debit_to,
						"party_type": "Customer",
						"party": original.customer,
						"reference_type": DOCTYPE,
						"reference_name": original.name,
						"debit_in_account_currency": diem.thieu,
						"cost_center": cost_center,
					},
					{
						"account": tk_chi_phi,
						"credit_in_account_currency": diem.thieu,
						"cost_center": cost_center,
					},
				],
			}
		)
		je.flags.ignore_permissions = True
		je.insert()
		je.submit()


def _tien_mat_trong_ca(pos_opening_shift):
	"""Tiền mặt đang có trong ca = đầu ca + thu − chi bằng tiền mặt, tính y như lúc đóng ca."""
	from pos_next.pos_next.doctype.pos_closing_shift.pos_closing_shift import (
		_get_cash_mode_of_payment,
		make_closing_shift_from_opening,
	)

	mo_ca = frappe.get_doc("POS Opening Shift", pos_opening_shift)
	hinh_thuc_tien_mat = _get_cash_mode_of_payment(mo_ca.pos_profile)
	du_lieu = make_closing_shift_from_opening(json.dumps(mo_ca.as_dict(), default=str))
	for row in du_lieu.get("payment_reconciliation") or []:
		if row.get("mode_of_payment") == hinh_thuc_tien_mat:
			return hinh_thuc_tien_mat, flt(row.get("expected_amount"))
	return hinh_thuc_tien_mat, 0.0


def _kiem_tra_quy_tien_mat(pos_opening_shift, tien_hoan):
	"""D9: không cho hoàn tiền mặt nhiều hơn số tiền mặt đang có trong ca."""
	hinh_thuc, dang_co = _tien_mat_trong_ca(pos_opening_shift)
	can_chi = sum(flt(r.get("amount")) for r in tien_hoan if r.get("mode_of_payment") == hinh_thuc)
	if can_chi > dang_co + SAI_SO:
		frappe.throw(
			_("Cash in this shift is {0}, not enough to refund {1} in cash. Refund by bank transfer or add it to the customer's balance.").format(
				frappe.format_value(dang_co, {"fieldtype": "Currency"}),
				frappe.format_value(can_chi, {"fieldtype": "Currency"}),
			)
		)


def _hinh_thuc_mac_dinh(pos_profile):
	rows = frappe.get_all(
		"POS Payment Method",
		filters={"parent": pos_profile, "parenttype": "POS Profile"},
		fields=["mode_of_payment", "default"],
		order_by="`default` desc, idx asc",
		limit=1,
	)
	if not rows:
		frappe.throw(_("POS Profile {0} has no payment methods.").format(pos_profile))
	return rows[0].mode_of_payment


def _tong_tien(rows):
	return sum(flt(r.get("amount")) for r in rows or [])


@frappe.whitelist(methods=["POST"])
def submit_exchange(payload):
	"""Lưu một lần đổi / trả: phiếu trả + HĐ mới (nếu có) trong một transaction.

	Ngoài các khóa của calculate_exchange, payload có thêm:
	    refund_payments: [{mode_of_payment, amount}]  số dương, khi phần dư được HOÀN
	    payments:        [{mode_of_payment, amount}]  khách trả thêm cho HĐ mới
	    add_to_customer_credit: 1 — trả hàng thuần, ghi phần hoàn vào số dư khách
	    expected_difference: chênh lệch màn hình đã hiện — lệch so với server thì dừng
	"""
	frappe.flags.pos_next_dang_doi_hang = True
	try:
		with _khoa_commit():
			return _submit_exchange(payload)
	finally:
		frappe.flags.pos_next_dang_doi_hang = False


def _submit_exchange(payload):
	from pos_next.api.credit_sales import (
		_create_credit_allocation_journal_entry,
		_validate_and_lock_invoice_credit,
	)

	p = _chuan_hoa(payload)
	if not p.pos_opening_shift:
		frappe.throw(_("Please open a shift before returning items."))

	original = frappe.get_doc(DOCTYPE, p.invoice_name)
	original.check_permission("read")
	_kiem_tra_hoa_don_goc(original, p.pos_profile, lock=True)
	plan = _lap_ke_hoach(
		original, p.pos_profile, p.pos_opening_shift, p.return_items, p.new_items, p.return_reason,
		ghi_co=cint(p.add_to_customer_credit),
	)

	# Màn hình thu ngân đã hiện một con số; server tính ra số khác thì không lưu
	if p.get("expected_difference") is not None and abs(flt(p.expected_difference) - plan.chenh) > SAI_SO:
		frappe.throw(
			_("The amounts changed while you were working (expected {0}, now {1}). Please review and try again.").format(
				frappe.format_value(p.expected_difference, {"fieldtype": "Currency"}),
				frappe.format_value(plan.chenh, {"fieldtype": "Currency"}),
			)
		)

	if plan.du and plan.cach_xu_ly_du == "Require Top-up":
		frappe.throw(
			_("This store does not refund when exchanging for cheaper items. The customer needs to pick at least {0} more.").format(
				frappe.format_value(plan.du, {"fieldtype": "Currency"})
			)
		)

	# --- Thanh toán của phiếu trả: chỉ khi phần dư được hoàn ---
	tien_hoan = []
	if plan.du and plan.cach_xu_ly_du == "Refund":
		tien_hoan = [r for r in (p.refund_payments or []) if flt(r.get("amount")) > 0]
		if abs(_tong_tien(tien_hoan) - plan.du) > SAI_SO:
			frappe.throw(
				_("Refund payments ({0}) must equal the refund amount ({1}).").format(
					frappe.format_value(_tong_tien(tien_hoan), {"fieldtype": "Currency"}),
					frappe.format_value(plan.du, {"fieldtype": "Currency"}),
				)
			)
	if tien_hoan:
		_kiem_tra_quy_tien_mat(p.pos_opening_shift, tien_hoan)
	tra = dict(plan.tra, posa_is_exchange=1 if plan.moi else 0)
	tra["payments"] = [{"mode_of_payment": r["mode_of_payment"], "amount": -abs(flt(r["amount"]))} for r in tien_hoan]
	if plan.thu_hoi_km:
		# Thu hồi KM = xoá bớt khoản phải hoàn, ghi vào TK chiết khấu (521) như lúc giảm.
		# Trên PHIẾU TRẢ số này phải ÂM: outstanding = grand_total − paid − write_off, với
		# grand_total âm. Gửi số dương (như hộp thoại cũ) là HĐ gốc treo công nợ âm gấp
		# đôi khoản thu hồi — khách được ghi có ảo (đo: −639.800 cho KM thu hồi 319.900).
		# Đặt thẳng vào chứng từ, không qua `data` của submit_invoice vì nhánh đó chỉ
		# nhận số dương và nuốt lỗi.
		tk = frappe.db.get_value(
			"Sales Invoice Item", {"parent": original.name, "is_free_item": 0}, "discount_account"
		) or frappe.get_cached_value("Company", original.company, "default_discount_account")
		if not tk:
			frappe.throw(
				_("Company {0} has no Default Discount Account to reclaim the promotion.").format(original.company)
			)
		tra["write_off_amount"] = -plan.thu_hoi_km
		tra["base_write_off_amount"] = -plan.thu_hoi_km
		tra["write_off_account"] = tk
		tra["write_off_cost_center"] = frappe.get_cached_value(
			"POS Profile", p.pos_profile, "write_off_cost_center"
		) or frappe.get_cached_value("Company", original.company, "cost_center")

	ket_qua_tra = submit_invoice(invoice=json.dumps(tra, default=str), data="{}")
	phieu_tra = frappe.get_doc(DOCTYPE, ket_qua_tra["name"])

	# Đổi trả đụng tiền: kiểm lại từng con số trên chứng từ đã lưu.
	if abs(abs(flt(phieu_tra.write_off_amount)) - plan.thu_hoi_km) > SAI_SO:
		frappe.throw(
			_("Could not reclaim the promotion ({0}) on the return. Check the POS Profile write-off account and limit.").format(
				frappe.format_value(plan.thu_hoi_km, {"fieldtype": "Currency"})
			)
		)
	if abs(-_tong_thanh_toan(phieu_tra) - plan.hoan_theo_dong) > SAI_SO or abs(
		-flt(phieu_tra.paid_amount) - _tong_tien(tien_hoan)
	) > SAI_SO:
		frappe.throw(
			_("Return total does not match the calculation ({0} vs {1}). Nothing was saved.").format(
				-_tong_thanh_toan(phieu_tra), plan.hoan_theo_dong
			)
		)

	if plan.diem.tien:
		_thuc_hien_thu_hoi_diem(original, phieu_tra, plan.diem)

	ket_qua = {"return_invoice": phieu_tra.name, "new_invoice": None, "summary": _tom_tat(plan)}

	# --- HĐ mới ---
	if plan.moi:
		tien_tra_them = [r for r in (p.payments or []) if flt(r.get("amount")) > 0]
		if _tong_tien(tien_tra_them) + SAI_SO < plan.khach_tra_them:
			frappe.throw(
				_("Customer still needs to pay {0}.").format(
					frappe.format_value(plan.khach_tra_them, {"fieldtype": "Currency"})
				)
			)
		moi = dict(plan.moi, posa_exchange_against=phieu_tra.name)
		moi["payments"] = [{"mode_of_payment": r["mode_of_payment"], "amount": flt(r["amount"])} for r in tien_tra_them]
		if not moi["payments"]:
			# HĐ trả hết bằng tiền trả lại. ERPNext bắt HĐ POS có ít nhất một dòng thanh
			# toán (validate_pos_paid_amount), nên thêm dòng 0đ theo hình thức mặc định.
			moi["payments"] = [{"mode_of_payment": _hinh_thuc_mac_dinh(p.pos_profile), "amount": 0}]
		ket_qua_moi = submit_invoice(invoice=json.dumps(moi, default=str), data="{}")
		hd_moi = frappe.get_doc(DOCTYPE, ket_qua_moi["name"])
		if abs(_tong_thanh_toan(hd_moi) - plan.tong_moi) > SAI_SO:
			frappe.throw(_("New invoice total does not match the calculation. Nothing was saved."))

		# Chuyển phần tiền trả lại đang treo trên HĐ gốc (công nợ âm) sang HĐ mới.
		# Gọi thẳng, KHÔNG qua customer_credit_dict của submit_invoice vì chỗ đó nuốt lỗi.
		if plan.dung_cho_hd_moi > SAI_SO:
			_validate_and_lock_invoice_credit(original.name, plan.dung_cho_hd_moi)
			_create_credit_allocation_journal_entry(hd_moi, original.name, plan.dung_cho_hd_moi)

		ket_qua["new_invoice"] = hd_moi.name

	_dat_lai_con_no_phieu_tra(phieu_tra, plan)
	return ket_qua


def _dat_lai_con_no_phieu_tra(phieu_tra, plan):
	"""Đặt `outstanding_amount` của phiếu trả về 0.

	Phiếu trả ghi công nợ vào HĐ gốc (`update_outstanding_for_self = 0`), nên ERPNext đặt
	trường này một lần lúc lưu (grand_total − đã trả) rồi không bao giờ cập nhật. Phần tiền
	còn lại của khách (nếu có, chế độ ghi vào số dư) nằm ở HĐ gốc trên sổ công nợ, và
	`credit_sales` đọc số dư theo sổ (PM-TASK-00267). Để trường này âm thì danh sách hóa đơn
	của ERPNext vẫn hiện phiếu trả như còn ghi có, dễ khiến kế toán đối chiếu nhầm.
	Đo thật (06/10, AC2610060005): đổi hàng xong sổ công nợ đã về 0, phiếu trả vẫn ghi −2.879.100.
	"""
	if abs(flt(phieu_tra.outstanding_amount)) > SAI_SO:
		phieu_tra.db_set("outstanding_amount", 0, update_modified=False)


# ---------------------------------------------------------------------------
# API cho hộp thoại Đổi / Trả hàng
# ---------------------------------------------------------------------------


def _ly_do_khong_doi_tra(row, settings, da_tra, khoa_den):
	"""Vì sao HĐ này không đổi trả được (None = đổi trả được). Dùng để làm xám dòng."""
	if row.name in da_tra:
		return _("Already returned once")
	ngay = cint(settings.return_validity_days)
	if ngay and frappe.utils.date_diff(nowdate(), row.posting_date) > ngay:
		return _("Return period expired ({0} days)").format(ngay)
	if khoa_den and getdate(row.posting_date) <= khoa_den:
		return _("Accounting period closed")
	return None


@frappe.whitelist()
def list_invoices(pos_profile, search=None, limit=50):
	"""Hóa đơn của cửa hàng để chọn đổi / trả, mới nhất trước.

	HĐ không đổi trả được vẫn trả về (kèm `blocked_reason`) để thu ngân biết vì sao.
	Tìm theo số HĐ, tên hoặc SĐT khách; có `search` thì không giới hạn ngày.

	Dùng frappe.get_list (có lọc User Permission), KHÔNG dùng truy vấn thô: `pos_profile`
	do client gửi lên, truy vấn thô thì thu ngân cửa hàng A đổi tham số là xem được danh
	sách HĐ (tên, SĐT khách, số tiền) của cửa hàng B.
	"""
	if not frappe.has_permission("POS Profile", "read", doc=pos_profile):
		frappe.throw(_("You do not have access to POS Profile {0}.").format(pos_profile), frappe.PermissionError)
	limit = min(cint(limit) or 50, 100)
	settings = _pos_settings(pos_profile)
	company = frappe.db.get_value("POS Profile", pos_profile, "company")

	or_filters = None
	if search:
		tu_khoa = f"%{search.strip()}%"
		or_filters = [
			["name", "like", tu_khoa],
			["customer_name", "like", tu_khoa],
			["contact_mobile", "like", tu_khoa],
			["customer", "like", tu_khoa],
		]
	rows = frappe.get_list(
		DOCTYPE,
		filters={"pos_profile": pos_profile, "docstatus": 1, "is_return": 0, "is_pos": 1},
		or_filters=or_filters,
		fields=["name", "customer", "customer_name", "contact_mobile", "posting_date", "grand_total", "outstanding_amount", "status"],
		order_by="posting_date desc, name desc",
		limit_page_length=limit,
	)

	ten = [r.name for r in rows]
	da_tra = set(
		frappe.get_all(
			DOCTYPE,
			filters={"return_against": ["in", ten or [""]], "is_return": 1, "docstatus": 1},
			pluck="return_against",
		)
	)
	khoa_den = _ngay_khoa_so(company) if company else None
	for r in rows:
		r["blocked_reason"] = None if cint(settings.allow_return) else _("Returns are disabled for this store.")
		r["blocked_reason"] = r["blocked_reason"] or _ly_do_khong_doi_tra(r, settings, da_tra, khoa_den)
	return rows


@frappe.whitelist()
def get_invoice(invoice_name, pos_profile):
	"""Chi tiết một HĐ để chọn hàng trả. Ném lỗi nếu HĐ không được đổi trả."""
	from pos_next.api.invoices import _compute_free_item_linkage

	original = frappe.get_doc(DOCTYPE, invoice_name)
	original.check_permission("read")
	settings = _kiem_tra_hoa_don_goc(original, pos_profile)

	ck_tong = abs(flt(original.discount_amount))
	tong = abs(flt(original.total))
	lines = []
	for r in original.items:
		phan_ck = flt(ck_tong * flt(r.amount) / tong) if ck_tong and tong else 0
		blocked = None
		if not cint(frappe.get_cached_value("Item", r.item_code, "is_stock_item")) and not frappe.db.exists(
			"Product Bundle", {"new_item_code": r.item_code, "disabled": 0}
		):
			blocked = _("Service item, not refundable")
		lines.append(
			{
				"name": r.name,
				# [mobile] _compute_free_item_linkage nối hàng tặng ↔ hàng mua qua khoá này; thiếu thì
				# free_item_row_ids / paired_paid_item_row_id không bao giờ được điền.
				"sales_invoice_item": r.name,
				"item_code": r.item_code,
				"item_name": r.item_name,
				# [mobile] Món mẹ của biến thể: app RN mở thẳng hộp chọn màu / size của món đó khi đổi hàng
				"variant_of": frappe.get_cached_value("Item", r.item_code, "variant_of"),
				# [mobile] Serial đã bán trên dòng — app cho chọn đúng máy khách trả (F2)
				"serial_nos": _serial_cua_dong(r),
				"qty": flt(r.qty),
				"uom": r.uom,
				"whole_number": cint(frappe.get_cached_value("UOM", r.uom, "must_be_whole_number")),
				"price_list_rate": flt(r.price_list_rate),
				"rate": flt(r.rate),
				# Khách thực trả cho 1 đơn vị: đã trừ phần KM tổng đơn phân bổ cho dòng
				"paid_rate": flt(r.rate) - (phan_ck / flt(r.qty) if flt(r.qty) else 0),
				"promotion_share": phan_ck,
				"is_free_item": cint(r.is_free_item),
				"pricing_rules": r.pricing_rules,
				"blocked_reason": blocked,
			}
		)
	_compute_free_item_linkage(lines, original.name)

	return {
		"name": original.name,
		"customer": original.customer,
		"customer_name": original.customer_name,
		"posting_date": original.posting_date,
		"grand_total": flt(original.grand_total),
		"outstanding_amount": flt(original.outstanding_amount),
		"discount_amount": ck_tong,
		"lines": lines,
		"reasons": frappe.get_all(
			"POS Return Reason",
			filters={"disabled": 0},
			fields=["name", "stock_destination"],
			order_by="creation asc",
		),
		# [mobile] Có thuế cộng ngoài giá không: `paid_rate` của dòng là giá trước thuế đó, còn tiền hoàn
		# máy chủ tính đã gồm thuế — app ghi "chưa thuế" bên giá dòng. Thuế đã gồm trong giá thì không.
		"tax_excluded_from_rate": any(
			not cint(t.included_in_print_rate) and abs(flt(t.tax_amount)) > 0 for t in original.taxes or []
		),
		"has_defective_warehouse": bool(
			frappe.db.get_value("POS Profile", pos_profile, "posa_defective_warehouse")
		),
		"settings": {
			"exchange_negative_difference": settings.exchange_negative_difference or "Refund",
			"can_use_customer_credit": _co_the_ghi_co(settings),
		},
	}
