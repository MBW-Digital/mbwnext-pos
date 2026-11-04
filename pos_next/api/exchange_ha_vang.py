# Copyright (c) 2026, MBW and contributors
# For license information, please see license.txt

"""Đổi hàng tại quầy POS — Hạ Vàng (PM-FEAT-00044).

Spec + các lần chốt: `apps/mbwnext_gosumo/docs/features/tinh-nang-oi-hang.md`.
Nhánh `develop` có bản đổi hàng dùng chung (PM-FEAT-00060, `api/exchange.py`) với
luật tiền khác hẳn (giỏ gộp, hoàn tiền thừa). Hạ Vàng chốt luật riêng nên nhánh này
có module riêng, chỉ dùng lại phần khung giao dịch.

Luật tiền đã chốt (anh Thắng, anh Hưng, chị Tường Vân):

- Mỗi món trả đổi lấy đúng MỘT món mới (cặp đổi). Khách lấy thêm món thì bán riêng
  bằng đơn thường, theo giá và KM đang chạy.
- Món mới hưởng **cách giảm của món trả lúc mua**: giảm % thì giảm đúng %, giảm số tiền
  thì giảm đúng số tiền (không quy ra %). KM đang chạy hôm nay KHÔNG áp cho món mới.
- KM tổng hoá đơn: phần KM đã phân bổ cho món trả đi theo sang hoá đơn mới, giữ
  nguyên số tiền (không tính lại mốc).
- Hệ thống không xác định được món trả được giảm theo cách nào (giá sửa tay, KM đã
  xoá…) thì thu ngân nhập tay cách giảm cho món mới.
- Đổi sang hàng rẻ hơn: KHÔNG trả tiền thừa. Phần thừa ghi TK 711, không tách thuế.
- Chỉ xuất âm món đổi, các món khác giữ nguyên trên hoá đơn cũ (cách A).
- Mỗi hoá đơn đổi một lần, đúng cửa hàng đã bán, bắt buộc có mạng.
- Quá số ngày được đổi: cần một người trong danh sách duyệt của cửa hàng duyệt
  (DocType `POS Exchange Approval`). 0 ngày = không giới hạn.

Chứng từ, tạo trong CÙNG một transaction (lỗi bước nào Frappe rollback cả request):

1. Phiếu trả (`is_return`, `return_against` = HĐ gốc), chỉ dòng món đổi, mang phần KM
   tổng đơn của dòng đó. Không có dòng thanh toán: tiền hoàn không trả ra quầy mà
   nằm lại thành số dư (công nợ âm) trên HĐ gốc.
2. HĐ mới, `ignore_pricing_rule` = 1 để ERPNext không áp KM hôm nay.
3. Bút toán chuyển số dư HĐ gốc sang HĐ mới (Nợ 131 HĐ gốc / Có 131 HĐ mới).
4. Tiền chênh khách không lấy lại: Nợ 131 HĐ gốc / Có 711.
Khách bù thêm thì thu trên chính HĐ mới. Xong việc, công nợ của HĐ gốc, phiếu trả
và HĐ mới đều về 0 — kiểm lại ngay trên sổ trước khi trả kết quả.
"""

from __future__ import annotations

import json

import frappe
from frappe import _
from frappe.utils import cint, date_diff, flt, getdate, nowdate

from pos_next.pos_next.doctype.pos_exchange_approval.pos_exchange_approval import nguoi_duyet_cua_cua_hang

DOCTYPE = "Sales Invoice"
# Sai số làm tròn cho phép khi so số tiền dự tính với số ERPNext tính thật (VND)
SAI_SO = 1.0
SO_NGAY_MAC_DINH = 15
CACH_GIAM_HOP_LE = ("pct", "amt")


# ---------------------------------------------------------------------------
# Cấu hình & kiểm tra HĐ gốc
# ---------------------------------------------------------------------------


def so_ngay_duoc_doi(pos_profile):
	"""Số ngày được đổi của cửa hàng. 0 = không giới hạn.

	Cửa hàng tick "Store-specific Exchange Period" thì dùng số của cửa hàng, không thì
	dùng số chung ở Selling Settings. Đọc thẳng bảng Singles: số chung chưa từng được
	lưu thì là mặc định 15 (anh Hưng chốt), không phải 0 = không giới hạn.
	"""
	rieng = frappe.db.get_value(
		"POS Profile", pos_profile, ["custom_pos_exchange_own_days", "custom_pos_exchange_days"], as_dict=True
	)
	if rieng and cint(rieng.custom_pos_exchange_own_days):
		return cint(rieng.custom_pos_exchange_days)
	chung = frappe.db.sql(
		"select value from `tabSingles` where doctype='Selling Settings' and field='custom_pos_exchange_days'"
	)
	return SO_NGAY_MAC_DINH if not chung or chung[0][0] in (None, "") else cint(chung[0][0])


def _han_doi(posting_date, pos_profile):
	so_ngay = so_ngay_duoc_doi(pos_profile)
	da_qua = date_diff(nowdate(), getdate(posting_date))
	return frappe._dict(allowed_days=so_ngay, days=da_qua, late=bool(so_ngay) and da_qua > so_ngay)


def _ky_da_khoa_so(company, posting_date):
	"""Ngày khoá sổ muộn nhất nếu `posting_date` rơi vào kỳ đã khoá."""
	posting_date = getdate(posting_date)
	frozen = frappe.db.get_single_value("Accounts Settings", "acc_frozen_upto")
	if frozen and posting_date <= getdate(frozen):
		return getdate(frozen)
	pcv = frappe.db.get_value(
		"Period Closing Voucher", {"company": company, "docstatus": 1}, "max(period_end_date)"
	)
	if pcv and posting_date <= getdate(pcv):
		return getdate(pcv)
	return None


def _ly_do_khong_doi(original, pos_profile):
	"""Vì sao HĐ này không đổi được (None = đổi được). Không tính chuyện quá hạn —
	quá hạn vẫn đổi được nếu có duyệt."""
	if original.docstatus != 1 or cint(original.is_return) or not cint(original.is_pos):
		return _("Only submitted POS sales invoices can be exchanged.")
	if original.pos_profile != pos_profile:
		return _("Sold at another store ({0}). Exchanges are only accepted at the store that sold it.").format(
			original.pos_profile
		)
	da_tra = frappe.db.get_value(
		DOCTYPE,
		{"return_against": original.name, "is_return": 1, "docstatus": 1},
		["name", "posting_date", "posa_is_exchange"],
		as_dict=True,
	)
	if da_tra:
		return _("Already {0} on {1} ({2}). Each invoice can only be exchanged once.").format(
			_("exchanged") if cint(da_tra.posa_is_exchange) else _("returned"),
			frappe.format_value(da_tra.posting_date, {"fieldtype": "Date"}),
			da_tra.name,
		)
	if flt(original.outstanding_amount) > SAI_SO:
		return _("The invoice is not fully paid (outstanding {0}).").format(
			frappe.format_value(original.outstanding_amount, {"fieldtype": "Currency"})
		)
	khoa = _ky_da_khoa_so(original.company, original.posting_date)
	if khoa:
		return _("The invoice belongs to a closed accounting period (up to {0}).").format(
			frappe.format_value(khoa, {"fieldtype": "Date"})
		)
	return None


def _lay_hd_goc(invoice_name, pos_profile, lock=False):
	if lock:
		# Hai quầy cùng đổi một HĐ: quầy sau phải chờ quầy trước xong rồi mới kiểm.
		frappe.db.sql(f"select name from `tab{DOCTYPE}` where name=%s for update", invoice_name)
	original = frappe.get_doc(DOCTYPE, invoice_name)
	original.check_permission("read")
	ly_do = _ly_do_khong_doi(original, pos_profile)
	if ly_do:
		frappe.throw(_("Invoice {0} cannot be exchanged: {1}").format(original.name, ly_do))
	return original


def _kiem_quyen_cua_hang(pos_profile):
	if not pos_profile or not frappe.has_permission("POS Profile", "read", doc=pos_profile):
		frappe.throw(_("You do not have access to POS Profile {0}.").format(pos_profile), frappe.PermissionError)


# ---------------------------------------------------------------------------
# Cách giảm của món trả lúc mua
# ---------------------------------------------------------------------------


def _ten_rule(pricing_rules):
	if not pricing_rules:
		return []
	if isinstance(pricing_rules, str) and pricing_rules.strip().startswith("["):
		try:
			return [r for r in json.loads(pricing_rules) if r]
		except ValueError:
			return []
	return [r.strip() for r in str(pricing_rules).split(",") if r.strip()]


def cach_giam_luc_mua(row):
	"""Món trả được giảm theo cách nào lúc bán.

	Trả về {type, value, label}:
	- none: không giảm.
	- pct:  giảm %, `value` = số %.
	- amt:  giảm số tiền trên MỘT đơn vị, `value` = số tiền.
	- unknown: không xác định được; `value` = số tiền khách đã được giảm / đơn vị
	  (gợi ý cho thu ngân nhập tay).

	Mức giảm luôn đọc từ chính dòng hoá đơn (giá niêm yết − đơn giá đã bán), KHÔNG từ
	Pricing Rule hiện tại: 94% Pricing Rule của Hạ Vàng đã bị tắt hoặc sửa sau khi tạo
	và không lưu lịch sử. Pricing Rule chỉ dùng để biết KIỂU giảm (% hay số tiền) — đo
	trên dữ liệu thật: POS lưu mọi dòng giảm theo KM dưới dạng `discount_amount`, kể cả
	KM giảm % (3.620/3.621 dòng), nên nhìn riêng dòng hoá đơn không phân biệt được.
	"""
	plr = flt(row.price_list_rate)
	rate = flt(row.rate)
	giam = flt(plr - rate)
	if plr <= 0 or giam < 0.5:
		return {"type": "none", "value": 0, "label": _("No discount")}

	rules = _ten_rule(row.pricing_rules)
	if len(rules) == 1:
		rule = frappe.db.get_value("Pricing Rule", rules[0], ["rate_or_discount", "title"], as_dict=True)
		ten = (rule.title if rule else None) or rules[0]
		if rule and rule.rate_or_discount == "Discount Percentage":
			return {"type": "pct", "value": flt(giam * 100 / plr, 4), "label": ten}
		if rule and rule.rate_or_discount == "Discount Amount":
			return {"type": "amt", "value": giam, "label": ten}
	elif not rules and flt(row.discount_percentage) > 0:
		# Thu ngân gõ % giảm trên dòng. Lấy đúng số % đã gõ nếu khớp đơn giá đã bán.
		pct = flt(row.discount_percentage)
		if abs(plr * (1 - pct / 100) - rate) > SAI_SO:
			pct = flt(giam * 100 / plr, 4)
		return {"type": "pct", "value": pct, "label": _("Manual discount")}

	if rules:
		ly_do = _("Price set by a promotion that no longer exists or sets a fixed price")
	else:
		ly_do = _("Price changed by hand at sale ({0})").format(frappe.format_value(rate, {"fieldtype": "Currency"}))
	return {"type": "unknown", "value": giam, "label": ly_do}


def _giam_cho_mon_moi(cach, gia_moi):
	"""Số tiền giảm trên MỘT đơn vị món mới theo cách giảm `cach` {type, value}."""
	if cach["type"] == "pct":
		return flt(gia_moi * flt(cach["value"]) / 100)
	if cach["type"] == "amt":
		return min(flt(cach["value"]), gia_moi)
	return 0.0


# ---------------------------------------------------------------------------
# Món mới
# ---------------------------------------------------------------------------


def _ho_so(pos_profile):
	return frappe.get_cached_doc("POS Profile", pos_profile)


def _gia_niem_yet(item_code, ho_so, customer, uom):
	from erpnext.stock.get_item_details import get_price_list_rate_for

	args = frappe._dict(
		price_list=ho_so.selling_price_list,
		customer=customer,
		uom=uom,
		transaction_date=nowdate(),
		qty=1,
	)
	return flt(get_price_list_rate_for(args, item_code))


def _ton(item_code, warehouse):
	return flt(frappe.db.get_value("Bin", {"item_code": item_code, "warehouse": warehouse}, "actual_qty"))


def _mon_moi(item_code, ho_so, customer):
	item = frappe.db.get_value(
		"Item",
		item_code,
		["name", "item_name", "stock_uom", "disabled", "is_sales_item", "has_variants", "is_stock_item"],
		as_dict=True,
	)
	if not item or cint(item.disabled) or not cint(item.is_sales_item) or cint(item.has_variants):
		frappe.throw(_("Item {0} cannot be sold.").format(item_code))
	if not cint(item.is_stock_item):
		frappe.throw(_("{0} is not a stock item and cannot be taken in an exchange.").format(item.item_name))
	gia = _gia_niem_yet(item.name, ho_so, customer, item.stock_uom)
	if gia <= 0:
		frappe.throw(_("{0} has no price in price list {1}.").format(item.item_name, ho_so.selling_price_list))
	item.price_list_rate = gia
	item.actual_qty = _ton(item.name, ho_so.warehouse)
	return item


# ---------------------------------------------------------------------------
# Dựng chứng từ trong bộ nhớ để tính tiền (không lưu)
# ---------------------------------------------------------------------------


def _dung_tam(data):
	"""Dựng Sales Invoice trong bộ nhớ, tính thuế và tổng như lúc lưu thật nhưng KHÔNG lưu
	(lưu nháp sẽ bắn sự kiện realtime "có hoá đơn mới" tới các quầy)."""
	from pos_next.api.sales_invoice_hooks import capture_pos_authoritative_discounts
	from pos_next.controllers.python.sales_invoice import apply_selling_item_tax_templates

	doc = frappe.get_doc(dict(data, doctype=DOCTYPE))
	doc.is_pos = 1
	doc.update_stock = 1
	doc.posting_date = nowdate()
	disable_rounded = frappe.db.get_value("POS Profile", doc.pos_profile, "disable_rounded_total")
	doc.disable_rounded_total = cint(disable_rounded) if disable_rounded is not None else 1
	capture_pos_authoritative_discounts(doc)
	doc.set_missing_values()
	# set_missing_values() chép ignore_pricing_rule từ POS Profile, đè giá trị đã đặt
	doc.ignore_pricing_rule = 1
	apply_selling_item_tax_templates(doc)
	doc.calculate_taxes_and_totals()
	# Số đúng (thuế gồm trong giá + KM tổng đơn) chỉ có sau validate đầy đủ (đo ở 00060:
	# chỉ tính một lần ra 3.135.020 thay vì 2.879.100).
	doc.flags.ignore_permissions = True
	doc.run_method("validate")
	return doc


def _tong(doc):
	return flt(doc.rounded_total or doc.grand_total) if not cint(doc.disable_rounded_total) else flt(doc.grand_total)


def _chuan_hoa(payload):
	if isinstance(payload, str):
		payload = json.loads(payload)
	return frappe._dict(payload or {})


def _ly_do_hop_le(reason):
	if not reason or not frappe.db.exists("POS Return Reason", {"name": reason, "disabled": 0}):
		frappe.throw(_("Please select the exchange reason."))
	return reason


def _duyet_hop_le(original, pos_profile, approval):
	"""HĐ quá hạn: phải có yêu cầu đã duyệt, của đúng HĐ + cửa hàng, chưa dùng lần nào."""
	if not approval:
		frappe.throw(_("Invoice {0} is past the exchange period and needs approval.").format(original.name))
	yc = frappe.db.get_value(
		"POS Exchange Approval",
		approval,
		["name", "sales_invoice", "pos_profile", "status", "used_in_return"],
		as_dict=True,
	)
	if not yc or yc.sales_invoice != original.name or yc.pos_profile != pos_profile:
		frappe.throw(_("Approval {0} is not for invoice {1}.").format(approval, original.name))
	if yc.status != "Approved":
		frappe.throw(_("Approval {0} is {1}, not approved.").format(approval, _(yc.status)))
	if yc.used_in_return:
		frappe.throw(_("Approval {0} was already used for return {1}.").format(approval, yc.used_in_return))
	return yc.name


def _lap_ke_hoach(original, p):
	"""Tính toàn bộ số tiền của một lần đổi. Dùng chung cho xem trước và lưu thật.

	p.pairs: [{sales_invoice_item, qty, new_item_code, manual_type, manual_value}]
	"""
	ho_so = _ho_so(p.pos_profile)
	han = _han_doi(original.posting_date, p.pos_profile)
	duyet = _duyet_hop_le(original, p.pos_profile, p.approval) if han.late else None
	ly_do = _ly_do_hop_le(p.return_reason)

	if not p.pairs:
		frappe.throw(_("Select at least one item to exchange."))

	theo_dong = {r.name: r for r in original.items}
	tong_dong_goc = sum(flt(r.amount) for r in original.items)
	ck_tong = flt(original.discount_amount)
	da_chon = set()
	cap = []
	for x in p.pairs:
		x = frappe._dict(x)
		goc = theo_dong.get(x.sales_invoice_item)
		if not goc or x.sales_invoice_item in da_chon:
			frappe.throw(_("Invalid exchange line."))
		da_chon.add(x.sales_invoice_item)
		qty = flt(x.qty) or flt(goc.qty)
		if qty <= 0 or qty > flt(goc.qty) + 1e-9 or qty != int(qty):
			frappe.throw(_("Invalid quantity to exchange for {0}.").format(goc.item_name))
		if cint(goc.is_free_item):
			frappe.throw(_("{0} is a free item and cannot be exchanged.").format(goc.item_name))
		if not x.new_item_code:
			frappe.throw(_("Pick the new item for {0}.").format(goc.item_name))

		cach_goc = cach_giam_luc_mua(goc)
		cach = cach_goc
		if cach_goc["type"] == "unknown":
			if x.manual_type not in CACH_GIAM_HOP_LE or flt(x.manual_value) < 0:
				frappe.throw(_("Enter the discount for the new item replacing {0}.").format(goc.item_name))
			if x.manual_type == "pct" and flt(x.manual_value) > 100:
				frappe.throw(_("Discount cannot exceed 100%."))
			cach = {"type": x.manual_type, "value": flt(x.manual_value), "label": _("Entered by cashier")}

		moi = _mon_moi(x.new_item_code, ho_so, original.customer)
		giam_dv = _giam_cho_mon_moi(cach, moi.price_list_rate)
		rate_moi = flt(round(moi.price_list_rate - giam_dv))
		# Phần KM tổng đơn đã phân bổ cho số lượng trả của dòng này
		phan_ck = flt(ck_tong * flt(goc.rate) * qty / tong_dong_goc) if ck_tong and tong_dong_goc else 0.0
		cap.append(
			frappe._dict(
				goc=goc,
				qty=qty,
				cach_goc=cach_goc,
				cach=cach,
				moi=moi,
				rate_moi=rate_moi,
				phan_ck=phan_ck,
			)
		)

	ck_chuyen = flt(round(sum(c.phan_ck for c in cap)))
	gia_tri_moi = sum(c.rate_moi * c.qty for c in cap)
	# KM không quy ra tiền: phần KM mang sang không vượt giá trị hàng mới.
	ck_moi = min(ck_chuyen, gia_tri_moi)

	chung = {
		"customer": original.customer,
		"company": original.company,
		"pos_profile": p.pos_profile,
		"posa_pos_opening_shift": p.pos_opening_shift,
		"selling_price_list": original.selling_price_list,
		"currency": original.currency,
		"posa_is_exchange": 1,
		"ignore_pricing_rule": 1,
	}
	tra = dict(
		chung,
		is_return=1,
		return_against=original.name,
		update_outstanding_for_self=0,
		posa_return_reason=ly_do,
		posa_exchange_approval=duyet,
		remarks="\n".join(
			x for x in (_("Exchange against {0}").format(original.name), (p.note or "").strip()) if x
		),
		items=[
			{
				"item_code": c.goc.item_code,
				"item_name": c.goc.item_name,
				"qty": -c.qty,
				"rate": c.goc.rate,
				"price_list_rate": c.goc.price_list_rate,
				"discount_percentage": c.goc.discount_percentage,
				"discount_amount": c.goc.discount_amount,
				"item_tax_template": c.goc.item_tax_template,
				"warehouse": c.goc.warehouse,
				"uom": c.goc.uom,
				"conversion_factor": c.goc.conversion_factor or 1,
				"sales_invoice_item": c.goc.name,
				"batch_no": c.goc.get("batch_no"),
				"serial_no": c.goc.get("serial_no"),
			}
			for c in cap
		],
	)
	if ck_chuyen:
		tra["apply_discount_on"] = original.apply_discount_on or "Grand Total"
		tra["discount_amount"] = -ck_chuyen

	ghi_chu_tay = [
		_("{0}: discount {1} entered by {2}").format(
			c.moi.name,
			f"{flt(c.cach['value'])}%" if c.cach["type"] == "pct" else frappe.format_value(c.cach["value"], {"fieldtype": "Currency"}),
			frappe.utils.get_fullname(frappe.session.user),
		)
		for c in cap
		if c.cach_goc["type"] == "unknown"
	]
	moi = dict(
		chung,
		remarks="\n".join([_("Exchange for {0}").format(original.name), *ghi_chu_tay]),
		items=[
			{
				"item_code": c.moi.name,
				"item_name": c.moi.item_name,
				"qty": c.qty,
				"uom": c.moi.stock_uom,
				"conversion_factor": 1,
				"warehouse": ho_so.warehouse,
				"price_list_rate": c.moi.price_list_rate,
				"rate": c.rate_moi,
				"discount_percentage": flt(c.cach["value"]) if c.cach["type"] == "pct" else 0,
				"discount_amount": flt(c.moi.price_list_rate - c.rate_moi),
			}
			for c in cap
		],
	)
	if ck_moi:
		moi["apply_discount_on"] = "Grand Total"
		moi["discount_amount"] = ck_moi

	tra_tam = _dung_tam(tra)
	moi_tam = _dung_tam(moi)
	hoan = -_tong(tra_tam)
	tong_moi = _tong(moi_tam)
	chenh = flt(tong_moi - hoan)

	return frappe._dict(
		original=original,
		ho_so=ho_so,
		han=han,
		duyet=duyet,
		cap=cap,
		tra=tra,
		moi=moi,
		ck_chuyen=ck_chuyen,
		hoan=hoan,
		tong_moi=tong_moi,
		chenh=chenh,
		khach_tra_them=chenh if chenh > SAI_SO else 0.0,
		tien_thua=-chenh if chenh < -SAI_SO else 0.0,
		tru_vao_hd_moi=min(hoan, tong_moi),
	)


def _tom_tat(plan):
	"""Phần trả về cho màn hình POS."""
	return {
		"lines": [
			{
				"sales_invoice_item": c.goc.name,
				"item_code": c.goc.item_code,
				"item_name": c.goc.item_name,
				"qty": c.qty,
				"returned_rate": flt(c.goc.rate),
				"returned_price_list_rate": flt(c.goc.price_list_rate),
				"discount_at_sale": c.cach_goc,
				"discount_applied": c.cach,
				"promotion_share": flt(c.phan_ck),
				"new_item_code": c.moi.name,
				"new_item_name": c.moi.item_name,
				"new_price_list_rate": c.moi.price_list_rate,
				"new_rate": c.rate_moi,
				"new_actual_qty": c.moi.actual_qty,
			}
			for c in plan.cap
		],
		"promotion_moved": plan.ck_chuyen,
		"return_value": plan.hoan,
		"new_invoice_total": plan.tong_moi,
		"difference": plan.chenh,
		"customer_pays": plan.khach_tra_them,
		"not_refunded": plan.tien_thua,
		"is_late": plan.han.late,
		"days_since_sale": plan.han.days,
		"allowed_days": plan.han.allowed_days,
	}


# ---------------------------------------------------------------------------
# Ghi sổ
# ---------------------------------------------------------------------------


def _tk_711(company):
	"""TK 711 - Thu nhập khác của công ty (chị Tường Vân chốt 21/10)."""
	tk = frappe.db.get_value(
		"Account", {"company": company, "account_number": "711", "is_group": 0, "disabled": 0}, "name"
	) or frappe.db.get_value(
		"Account", {"company": company, "name": ["like", "711 %"], "is_group": 0, "disabled": 0}, "name"
	)
	if not tk:
		frappe.throw(_("Company {0} has no account 711 (Other Income) to record the amount not refunded.").format(company))
	return tk


def _tieu_de_but_toan(phieu_tra):
	"""Tiêu đề chung của các bút toán thuộc một lần đổi — dùng để tìm lại khi huỷ.

	KHÔNG dịch: người huỷ có thể dùng ngôn ngữ khác người đổi, dịch thì tìm hụt bút
	toán và huỷ dở dang.
	"""
	return f"Đổi hàng {phieu_tra}"


def _but_toan(original, phieu_tra, dong_co, so_tien, ghi_chu):
	"""Nợ 131 (khách, gắn HĐ gốc) / Có `dong_co`."""
	cost_center = original.cost_center or frappe.get_cached_value("Company", original.company, "cost_center")
	je = frappe.get_doc(
		{
			"doctype": "Journal Entry",
			"voucher_type": "Journal Entry",
			"posting_date": nowdate(),
			"company": original.company,
			"user_remark": ghi_chu,
			"accounts": [
				{
					"account": original.debit_to,
					"party_type": "Customer",
					"party": original.customer,
					"reference_type": DOCTYPE,
					"reference_name": original.name,
					"debit_in_account_currency": so_tien,
					"cost_center": cost_center,
				},
				dict(dong_co, credit_in_account_currency=so_tien, cost_center=cost_center),
			],
		}
	)
	je.flags.ignore_permissions = True
	je.insert()
	je.submit()
	# JournalEntry.validate() tự đặt tiêu đề cho chứng từ mới, nên đặt sau khi lưu.
	je.db_set("title", _tieu_de_but_toan(phieu_tra.name), update_modified=False)
	return je.name


def _diem_cua_hd(invoice_name):
	return flt(
		frappe.db.get_value(
			"Loyalty Point Entry",
			{"invoice_type": DOCTYPE, "invoice": invoice_name, "loyalty_points": [">", 0]},
			"sum(loyalty_points)",
		)
	)


def _thu_lai_diem(original, phieu_tra, diem_truoc):
	"""Điểm của món trả đã quy ra tiền ví lúc bán (POS Settings `loyalty_to_wallet`).

	Phiếu trả làm ERPNext tính lại điểm HĐ gốc (ít đi), nhưng tiền ví đã cộng thì không
	ai thu lại, còn HĐ mới lại được tích điểm lần nữa: khách được điểm hai lần cho cùng
	một món. Ở đây trừ ví đúng phần điểm mất đi. Ví chỉ là sổ theo dõi (PM-TASK-00106),
	không có bút toán. Ví không còn đủ (khách đã tiêu) thì trừ hết phần còn lại và báo
	thu ngân phần không thu được.
	"""
	from pos_next.pos_next.doctype.wallet.wallet import tinh_so_du_vi

	rong = {"points_before": diem_truoc, "points_after": diem_truoc, "reclaimed": 0.0, "not_reclaimed": 0.0}
	if not diem_truoc:
		return rong
	da_cong_vi = flt(
		frappe.db.get_value(
			"Wallet Transaction",
			{"reference_doctype": DOCTYPE, "reference_name": original.name, "transaction_type": "Loyalty Credit", "docstatus": 1},
			"sum(amount)",
		)
	)
	diem_sau = _diem_cua_hd(original.name)
	rong["points_after"] = diem_sau
	if not da_cong_vi or diem_sau >= diem_truoc:
		return rong

	he_so = flt(frappe.db.get_value("Loyalty Program", original.loyalty_program, "conversion_factor")) or 1.0
	can_thu = min(da_cong_vi, flt((diem_truoc - diem_sau) * he_so))
	vi = frappe.db.get_value("Wallet", {"customer": original.customer, "company": original.company, "status": "Active"}, "name")
	so_du = max(0.0, flt(tinh_so_du_vi(original.customer, original.company))) if vi else 0.0
	thu = min(so_du, can_thu)
	if thu > SAI_SO:
		gd = frappe.get_doc(
			{
				"doctype": "Wallet Transaction",
				"transaction_type": "Debit",
				"wallet": vi,
				"company": original.company,
				"posting_date": nowdate(),
				"amount": thu,
				"source_type": "Loyalty Program",
				"reference_doctype": DOCTYPE,
				"reference_name": phieu_tra.name,
				"remarks": _("Reclaim loyalty credit of exchanged items: {0} ({1} → {2} points)").format(
					original.name, diem_truoc, diem_sau
				),
			}
		)
		gd.flags.ignore_permissions = True
		gd.insert()
		gd.submit()
	rong.update(reclaimed=thu, not_reclaimed=flt(can_thu - thu))
	return rong


def _con_no(invoice_name):
	return flt(frappe.db.get_value(DOCTYPE, invoice_name, "outstanding_amount"))


# ---------------------------------------------------------------------------
# API cho màn hình Đổi hàng
# ---------------------------------------------------------------------------


@frappe.whitelist()
def list_invoices(pos_profile, search=None, limit=30):
	"""HĐ POS của cửa hàng để chọn đổi, mới nhất trước.

	HĐ không đổi được vẫn trả về kèm `blocked_reason` để thu ngân biết vì sao; HĐ quá
	hạn trả về `is_late` (vẫn đổi được nếu có duyệt). Dùng frappe.get_list (có lọc User
	Permission): `pos_profile` do client gửi, truy vấn thô thì thu ngân shop A đổi tham số
	là xem được HĐ (tên, SĐT khách) của shop B.
	"""
	_kiem_quyen_cua_hang(pos_profile)
	limit = min(cint(limit) or 30, 100)
	or_filters = None
	if search and search.strip():
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
		fields=["name", "customer", "customer_name", "contact_mobile", "posting_date", "grand_total", "outstanding_amount", "company"],
		order_by="posting_date desc, creation desc",
		limit_page_length=limit,
	)
	ten = [r.name for r in rows] or [""]
	da_tra = {
		r.return_against: r
		for r in frappe.get_all(
			DOCTYPE,
			filters={"return_against": ["in", ten], "is_return": 1, "docstatus": 1},
			fields=["return_against", "posa_is_exchange"],
		)
	}
	so_dong = {
		r.parent: r.n
		for r in frappe.get_all(
			"Sales Invoice Item", filters={"parent": ["in", ten]}, fields=["parent", "count(name) as n"], group_by="parent"
		)
	}
	so_ngay = so_ngay_duoc_doi(pos_profile)
	for r in rows:
		r.item_count = so_dong.get(r.name, 0)
		r.days_since_sale = date_diff(nowdate(), r.posting_date)
		r.allowed_days = so_ngay
		r.is_late = bool(so_ngay) and r.days_since_sale > so_ngay
		r.blocked_reason = None
		if r.name in da_tra:
			r.blocked_reason = _("Exchanged once") if cint(da_tra[r.name].posa_is_exchange) else _("Already returned")
		elif flt(r.outstanding_amount) > SAI_SO:
			r.blocked_reason = _("Not fully paid")
	return {"invoices": rows, "allowed_days": so_ngay}


@frappe.whitelist()
def get_invoice(invoice_name, pos_profile):
	"""Chi tiết một HĐ để chọn món đổi. Ném lỗi nếu HĐ không đổi được."""
	_kiem_quyen_cua_hang(pos_profile)
	original = _lay_hd_goc(invoice_name, pos_profile)
	han = _han_doi(original.posting_date, pos_profile)
	ck_tong = flt(original.discount_amount)
	tong = sum(flt(r.amount) for r in original.items)
	lines = []
	for r in original.items:
		phan_ck = flt(ck_tong * flt(r.amount) / tong) if ck_tong and tong else 0.0
		blocked = None
		if cint(r.is_free_item):
			blocked = _("Free item")
		elif not cint(frappe.get_cached_value("Item", r.item_code, "is_stock_item")):
			blocked = _("Service item")
		lines.append(
			{
				"name": r.name,
				"item_code": r.item_code,
				"item_name": r.item_name,
				"qty": flt(r.qty),
				"uom": r.uom,
				"price_list_rate": flt(r.price_list_rate),
				"rate": flt(r.rate),
				"amount": flt(r.amount),
				"promotion_share": phan_ck,
				# Khách thực trả cho cả dòng: đã trừ phần KM tổng đơn phân bổ cho dòng
				"paid_amount": flt(r.amount) - phan_ck,
				"discount_at_sale": cach_giam_luc_mua(r),
				"blocked_reason": blocked,
			}
		)
	return {
		"name": original.name,
		"customer": original.customer,
		"customer_name": original.customer_name,
		"contact_mobile": original.contact_mobile,
		"posting_date": original.posting_date,
		"grand_total": flt(original.grand_total),
		"discount_amount": ck_tong,
		"promotion_label": original.get("posa_transaction_pricing_rule") or original.get("coupon_code"),
		"lines": lines,
		"is_late": han.late,
		"days_since_sale": han.days,
		"allowed_days": han.allowed_days,
		"approval": _yeu_cau_gan_nhat(original.name, pos_profile) if han.late else None,
		"approvers": [
			{"user": u, "full_name": frappe.utils.get_fullname(u)} for u in nguoi_duyet_cua_cua_hang(pos_profile)
		],
		"reasons": frappe.get_all("POS Return Reason", filters={"disabled": 0}, pluck="name", order_by="creation asc"),
		"payment_methods": [
			{"mode_of_payment": r.mode_of_payment, "default": cint(r.default)} for r in _ho_so(pos_profile).payments
		],
	}


@frappe.whitelist()
def search_new_items(pos_profile, search):
	"""Tìm món khách muốn lấy: quét mã vạch, mã hàng hoặc tên. Kèm giá niêm yết và tồn
	tại kho cửa hàng (món hết hàng vẫn trả về để thu ngân thấy, nhưng không chọn được)."""
	_kiem_quyen_cua_hang(pos_profile)
	search = (search or "").strip()
	if len(search) < 2:
		return []
	ho_so = _ho_so(pos_profile)
	item = frappe.qb.DocType("Item")
	dieu_kien = (item.disabled == 0) & (item.is_sales_item == 1) & (item.has_variants == 0) & (item.is_stock_item == 1)
	if frappe.get_meta("Item").has_field("custom_company"):
		dieu_kien &= (item.custom_company == ho_so.company) | (item.custom_company.isnull()) | (item.custom_company == "")

	ma_vach = frappe.db.get_value("Item Barcode", {"barcode": search}, "parent")
	if ma_vach:
		ten = [ma_vach]
	else:
		tu_khoa = f"%{search}%"
		ten = (
			frappe.qb.from_(item)
			.select(item.name)
			.where(dieu_kien & ((item.name.like(tu_khoa)) | (item.item_name.like(tu_khoa))))
			.orderby(item.name)
			.limit(20)
		).run(pluck=True)
	ket_qua = []
	for code in ten:
		row = frappe.db.get_value("Item", code, ["name", "item_name", "stock_uom", "image"], as_dict=True)
		if not row:
			continue
		ket_qua.append(
			{
				"item_code": row.name,
				"item_name": row.item_name,
				"uom": row.stock_uom,
				"image": row.image,
				"price_list_rate": _gia_niem_yet(row.name, ho_so, None, row.stock_uom),
				"actual_qty": _ton(row.name, ho_so.warehouse),
			}
		)
	return ket_qua


@frappe.whitelist()
def calculate_exchange(payload):
	"""Xem trước số tiền của một lần đổi. Không lưu gì.

	payload: {invoice_name, pos_profile, pos_opening_shift, return_reason, approval,
	          pairs: [{sales_invoice_item, qty, new_item_code, manual_type, manual_value}]}
	"""
	p = _chuan_hoa(payload)
	_kiem_quyen_cua_hang(p.pos_profile)
	original = _lay_hd_goc(p.invoice_name, p.pos_profile)
	return _tom_tat(_lap_ke_hoach(original, p))


@frappe.whitelist(methods=["POST"])
def submit_exchange(payload):
	"""Lưu một lần đổi: phiếu trả + HĐ mới + bút toán bù trừ, trong một transaction.

	Ngoài các khoá của calculate_exchange, payload có thêm:
	    payments:            [{mode_of_payment, amount}] khách bù thêm (khi chênh > 0)
	    customer_agreed:     1 — khách đã đồng ý không nhận lại tiền thừa (khi chênh < 0)
	    expected_difference: chênh lệch màn hình đã hiện; server tính khác thì dừng
	"""
	frappe.flags.pos_next_dang_doi_hang = True
	try:
		return _submit_exchange(_chuan_hoa(payload))
	finally:
		frappe.flags.pos_next_dang_doi_hang = False


def _submit_exchange(p):
	from pos_next.api.credit_sales import _create_credit_allocation_journal_entry
	from pos_next.api.invoices import submit_invoice

	_kiem_quyen_cua_hang(p.pos_profile)
	ca = frappe.db.get_value(
		"POS Opening Shift", p.pos_opening_shift or "", ["status", "pos_profile", "docstatus"], as_dict=True
	)
	if not ca or ca.status != "Open" or ca.docstatus != 1 or ca.pos_profile != p.pos_profile:
		frappe.throw(_("Please open a shift at this store before exchanging items."))

	original = _lay_hd_goc(p.invoice_name, p.pos_profile, lock=True)
	plan = _lap_ke_hoach(original, p)

	if p.get("expected_difference") is not None and abs(flt(p.expected_difference) - plan.chenh) > SAI_SO:
		frappe.throw(
			_("The amounts changed while you were working (expected {0}, now {1}). Please review and try again.").format(
				frappe.format_value(p.expected_difference, {"fieldtype": "Currency"}),
				frappe.format_value(plan.chenh, {"fieldtype": "Currency"}),
			)
		)
	if plan.tien_thua and not cint(p.customer_agreed):
		frappe.throw(_("Confirm that the customer agreed not to get the difference back."))

	tien_bu = [
		{"mode_of_payment": r.get("mode_of_payment"), "amount": flt(r.get("amount"))}
		for r in (p.payments or [])
		if flt(r.get("amount")) > 0 and r.get("mode_of_payment")
	]
	da_bu = sum(r["amount"] for r in tien_bu)
	if abs(da_bu - plan.khach_tra_them) > SAI_SO:
		frappe.throw(
			_("The customer must pay exactly {0} (entered {1}).").format(
				frappe.format_value(plan.khach_tra_them, {"fieldtype": "Currency"}),
				frappe.format_value(da_bu, {"fieldtype": "Currency"}),
			)
		)
	hinh_thuc_quay = {r.mode_of_payment for r in plan.ho_so.payments}
	for r in tien_bu:
		if r["mode_of_payment"] not in hinh_thuc_quay:
			frappe.throw(_("Payment method {0} is not set up for this store.").format(r["mode_of_payment"]))

	diem_truoc = _diem_cua_hd(original.name)

	# --- 1. Phiếu trả: không có dòng thanh toán, tiền hoàn nằm lại trên HĐ gốc ---
	tra = dict(plan.tra, payments=[])
	phieu_tra = frappe.get_doc(DOCTYPE, submit_invoice(invoice=json.dumps(tra, default=str), data="{}")["name"])
	if abs(-_tong(phieu_tra) - plan.hoan) > SAI_SO:
		frappe.throw(
			_("Return total does not match the calculation ({0} vs {1}). Nothing was saved.").format(
				-_tong(phieu_tra), plan.hoan
			)
		)

	# --- 2. HĐ mới ---
	moi = dict(plan.moi, posa_exchange_against=phieu_tra.name)
	moi["payments"] = tien_bu or [
		# ERPNext bắt HĐ POS có ít nhất một dòng thanh toán (validate_pos_paid_amount)
		{"mode_of_payment": _hinh_thuc_mac_dinh(plan.ho_so), "amount": 0}
	]
	hd_moi = frappe.get_doc(DOCTYPE, submit_invoice(invoice=json.dumps(moi, default=str), data="{}")["name"])
	if abs(_tong(hd_moi) - plan.tong_moi) > SAI_SO:
		frappe.throw(
			_("New invoice total does not match the calculation ({0} vs {1}). Nothing was saved.").format(
				_tong(hd_moi), plan.tong_moi
			)
		)

	# --- 3. Chuyển số dư HĐ gốc sang HĐ mới ---
	but_toan = []
	if plan.tru_vao_hd_moi > SAI_SO:
		ten_je = _create_credit_allocation_journal_entry(hd_moi, original.name, plan.tru_vao_hd_moi)
		frappe.db.set_value("Journal Entry", ten_je, "title", _tieu_de_but_toan(phieu_tra.name), update_modified=False)
		but_toan.append(ten_je)

	# --- 4. Tiền chênh khách không lấy lại → 711, không tách thuế ---
	if plan.tien_thua:
		but_toan.append(
			_but_toan(
				original,
				phieu_tra,
				{"account": _tk_711(original.company)},
				plan.tien_thua,
				_("Exchange {0} → {1}: difference not refunded to the customer (original invoice {2})").format(
					phieu_tra.name, hd_moi.name, original.name
				),
			)
		)

	# Phiếu trả ghi công nợ vào HĐ gốc (update_outstanding_for_self = 0), ERPNext đặt
	# outstanding của chính phiếu trả một lần lúc lưu rồi không cập nhật. Để âm thì danh
	# sách hoá đơn vẫn hiện phiếu trả như còn ghi có (00060 đo: AC2610060005).
	if abs(flt(phieu_tra.outstanding_amount)) > SAI_SO:
		phieu_tra.db_set("outstanding_amount", 0, update_modified=False)

	# Kiểm trên sổ: đổi xong không ai còn nợ ai. Lệch là có bước tính sai, không lưu gì.
	for ten in (original.name, hd_moi.name):
		if abs(_con_no(ten)) > SAI_SO:
			frappe.throw(
				_("Invoice {0} would be left with outstanding {1} after the exchange. Nothing was saved.").format(
					ten, _con_no(ten)
				)
			)

	if plan.duyet:
		frappe.db.set_value("POS Exchange Approval", plan.duyet, "used_in_return", phieu_tra.name, update_modified=False)

	diem = (
		_thu_lai_diem(original, phieu_tra, diem_truoc)
		if original.loyalty_program
		else {"reclaimed": 0.0, "not_reclaimed": 0.0}
	)

	return {
		"return_invoice": phieu_tra.name,
		"new_invoice": hd_moi.name,
		"journal_entries": but_toan,
		"loyalty": diem,
		"summary": _tom_tat(plan),
	}


def _hinh_thuc_mac_dinh(ho_so):
	mac_dinh = [r.mode_of_payment for r in ho_so.payments if cint(r.default)]
	if mac_dinh:
		return mac_dinh[0]
	if ho_so.payments:
		return ho_so.payments[0].mode_of_payment
	frappe.throw(_("POS Profile {0} has no payment methods.").format(ho_so.name))


# ---------------------------------------------------------------------------
# Huỷ một lần đổi (trong ca)
# ---------------------------------------------------------------------------


@frappe.whitelist(methods=["POST"])
def cancel_exchange(return_invoice):
	"""Huỷ cả lần đổi: bút toán bù trừ, HĐ mới, phiếu trả — một lần, đúng thứ tự.

	Chỉ trong ca đã đổi (ca còn mở). Sau đó phải nhờ kế toán (System Manager / Accounts
	Manager huỷ được từ form) — vì hàng đổi có thể đã bán tiếp, tiền đã nộp.
	"""
	tra = frappe.get_doc(DOCTYPE, return_invoice)
	if not (cint(tra.is_return) and cint(tra.posa_is_exchange)) or tra.docstatus != 1:
		frappe.throw(_("{0} is not a submitted exchange return.").format(return_invoice))
	_kiem_quyen_cua_hang(tra.pos_profile)
	quan_ly = {"System Manager", "Accounts Manager"} & set(frappe.get_roles())
	if not quan_ly:
		if tra.owner != frappe.session.user:
			frappe.throw(_("Only the cashier who made the exchange can cancel it."), frappe.PermissionError)
		ca = tra.get("posa_pos_opening_shift")
		if not ca or frappe.db.get_value("POS Opening Shift", ca, "status") != "Open":
			frappe.throw(_("The shift of this exchange is closed. Ask the accountant to cancel it."))

	frappe.flags.pos_next_huy_doi_hang = True
	try:
		for ten in frappe.get_all(
			"Journal Entry", filters={"title": _tieu_de_but_toan(tra.name), "docstatus": 1}, pluck="name"
		):
			je = frappe.get_doc("Journal Entry", ten)
			je.flags.ignore_permissions = True
			je.cancel()
		for ten in frappe.get_all(
			DOCTYPE, filters={"posa_exchange_against": tra.name, "docstatus": 1}, pluck="name"
		):
			hd = frappe.get_doc(DOCTYPE, ten)
			hd.flags.ignore_permissions = True
			hd.cancel()
		tra.flags.ignore_permissions = True
		tra.cancel()
		if tra.posa_exchange_approval:
			# Cho dùng lại yêu cầu đã duyệt nếu thu ngân làm lại lần đổi
			frappe.db.set_value(
				"POS Exchange Approval", tra.posa_exchange_approval, "used_in_return", None, update_modified=False
			)
	finally:
		frappe.flags.pos_next_huy_doi_hang = False
	return {"cancelled": tra.name}


def chan_huy_le(doc, method=None):
	"""Sales Invoice before_cancel: chứng từ đổi hàng phải huỷ cả bộ qua cancel_exchange.

	Huỷ lẻ phiếu trả mà để nguyên HĐ mới thì HĐ mới treo công nợ đúng bằng tiền hàng
	trả (bút toán bù trừ trỏ về HĐ gốc), không ai thấy. Kế toán vẫn huỷ lẻ được nếu cần
	xử lý tay (System Manager / Accounts Manager).
	"""
	if not cint(doc.get("posa_is_exchange")) or frappe.flags.get("pos_next_huy_doi_hang"):
		return
	if {"System Manager", "Accounts Manager"} & set(frappe.get_roles()):
		return
	frappe.throw(_("{0} is part of a POS exchange. Use the Cancel Exchange button to cancel the whole exchange.").format(doc.name))


# ---------------------------------------------------------------------------
# Duyệt đổi quá hạn
# ---------------------------------------------------------------------------


def _yeu_cau_gan_nhat(invoice_name, pos_profile):
	ten = frappe.db.get_value(
		"POS Exchange Approval",
		{"sales_invoice": invoice_name, "pos_profile": pos_profile, "status": ["!=", "Cancelled"], "used_in_return": ["is", "not set"]},
		"name",
		order_by="creation desc",
	)
	return frappe.get_doc("POS Exchange Approval", ten).ket_qua() if ten else None


@frappe.whitelist(methods=["POST"])
def request_approval(invoice_name, pos_profile, reason):
	"""Thu ngân gửi yêu cầu duyệt đổi quá hạn. Đang có yêu cầu chờ thì trả lại yêu cầu đó."""
	_kiem_quyen_cua_hang(pos_profile)
	original = _lay_hd_goc(invoice_name, pos_profile)
	han = _han_doi(original.posting_date, pos_profile)
	if not han.late:
		frappe.throw(_("Invoice {0} is still within the exchange period. No approval needed.").format(invoice_name))
	if not nguoi_duyet_cua_cua_hang(pos_profile):
		frappe.throw(
			_("Store {0} has no late exchange approvers. Ask the manager to add them on the POS Profile.").format(
				pos_profile
			)
		)
	if not (reason or "").strip():
		frappe.throw(_("Please enter the reason for the late exchange."))

	dang_cho = frappe.db.get_value(
		"POS Exchange Approval",
		{"sales_invoice": invoice_name, "pos_profile": pos_profile, "status": "Pending"},
		"name",
	)
	if dang_cho:
		return frappe.get_doc("POS Exchange Approval", dang_cho).ket_qua()

	yc = frappe.get_doc(
		{
			"doctype": "POS Exchange Approval",
			"sales_invoice": original.name,
			"pos_profile": pos_profile,
			"customer": original.customer,
			"customer_name": original.customer_name,
			"invoice_date": original.posting_date,
			"grand_total": original.grand_total,
			"currency": original.currency,
			"days_since_sale": han.days,
			"allowed_days": han.allowed_days,
			"requested_by": frappe.session.user,
			"reason": reason.strip(),
		}
	)
	yc.insert(ignore_permissions=True)
	return yc.ket_qua()


def _yeu_cau_cho_phep_xem(name):
	yc = frappe.get_doc("POS Exchange Approval", name)
	if yc.requested_by != frappe.session.user and not yc.la_nguoi_duyet() and not frappe.has_permission(
		"POS Exchange Approval", "read", doc=yc
	):
		frappe.throw(_("Not permitted"), frappe.PermissionError)
	return yc


@frappe.whitelist()
def get_approval(name):
	"""POS hỏi lại trạng thái (dự phòng khi mất realtime — mỗi 10 giây)."""
	return _yeu_cau_cho_phep_xem(name).ket_qua()


@frappe.whitelist(methods=["POST"])
def cancel_approval(name):
	yc = _yeu_cau_cho_phep_xem(name)
	if yc.requested_by != frappe.session.user:
		frappe.throw(_("Only the cashier who sent the request can withdraw it."), frappe.PermissionError)
	yc.huy()
	return yc.ket_qua()


@frappe.whitelist(methods=["POST"])
def decide_approval(name, approve, note=None):
	"""Người duyệt bấm Duyệt / Từ chối (form POS Exchange Approval)."""
	yc = frappe.get_doc("POS Exchange Approval", name)
	yc.quyet_dinh(bool(cint(approve)), note)
	return yc.ket_qua()
