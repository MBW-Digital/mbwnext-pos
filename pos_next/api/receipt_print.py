# Copyright (c) 2026, POS Next contributors
"""Shared receipt metadata and Vietnamese amount formatting for print templates."""

from __future__ import annotations

import base64
import mimetypes
import os
from typing import Any
from urllib.parse import quote

import frappe
from frappe.utils import cint, flt, fmt_money, format_datetime, now_datetime


def format_receipt_amount(value, precision: int = 0) -> str:
	"""Format số theo Number Format trong System Settings (không kèm ký hiệu tiền tệ)."""
	return fmt_money(value, precision=int(precision or 0))


def format_vn_amount(value, decimals: int = 0) -> str:
	"""Format number Việt Nam: thousands `.`, decimal `,` (vd. 27.685,19)."""
	v = flt(value)
	decimals = int(decimals or 0)
	if decimals <= 0:
		n = int(round(abs(v)))
		int_part = f"{n:,}".replace(",", ".")
		return f"-{int_part}" if v < 0 else int_part
	sign = "-" if v < 0 else ""
	v = abs(v)
	whole = int(v)
	frac = round((v - whole) * (10**decimals))
	if frac >= 10**decimals:
		whole += 1
		frac = 0
	int_part = f"{whole:,}".replace(",", ".")
	frac_str = str(int(frac)).zfill(decimals)
	return f"{sign}{int_part},{frac_str}"


def primary_tax_rate_percent(doc) -> float | None:
	"""Lấy % thuế dòng đầu có rate > 0 (Sales Taxes and Charges)."""
	rows = getattr(doc, "taxes", None) or []
	for row in rows:
		rate = flt(getattr(row, "rate", None) or 0)
		if rate > 0:
			return rate
	return None


def receipt_vat_amount_for_print(doc) -> float:
	"""Tiền thuế hiển thị phiếu: total_taxes_and_charges hoặc cộng tax_amount các dòng (tax-inclusive)."""
	base = flt(getattr(doc, "total_taxes_and_charges", None) or 0)
	if base > 0:
		return base
	s = 0.0
	for row in getattr(doc, "taxes", None) or []:
		s += flt(getattr(row, "tax_amount", None) or 0)
	return flt(s)


def receipt_invoice_discount_for_print(doc) -> float:
	"""Chiết khấu cấp hóa đơn — luôn hiển thị như số dương."""
	return abs(flt(getattr(doc, "discount_amount", None) or 0))


def receipt_vat_label_for_print(doc, vat_amt: float) -> str:
	rate = primary_tax_rate_percent(doc)
	if rate is not None:
		if rate == int(rate):
			return f"VAT {int(rate)}%"
		return f"VAT {rate:g}%"
	if flt(vat_amt) > 0:
		return "Thuế GTGT"
	return "VAT 0%"


def receipt_totals_aux_for_print(doc):
	"""Meta cho khối tổng kết phiếu in (Chiết khấu / VAT)."""
	vat_amt = receipt_vat_amount_for_print(doc)
	disc = receipt_invoice_discount_for_print(doc)
	vat_lbl = receipt_vat_label_for_print(doc, vat_amt)
	return frappe._dict(vat_amt=vat_amt, disc=disc, vat_lbl=vat_lbl)


def receipt_payments_for_invoice(inv) -> list[dict[str, Any]]:
	"""All payment lines for receipt: POS rows + Payment Entry allocations (e.g. VNPost bank transfer)."""
	rows: list[dict[str, Any]] = []
	seen_pe: set[str] = set()

	for row in getattr(inv, "payments", None) or inv.get("payments") or []:
		amount = flt(getattr(row, "amount", None) if not isinstance(row, dict) else row.get("amount"))
		if amount <= 0:
			continue
		mop = getattr(row, "mode_of_payment", None) if not isinstance(row, dict) else row.get("mode_of_payment")
		rows.append({"mode_of_payment": mop or "", "amount": amount})

	inv_name = getattr(inv, "name", None) or inv.get("name")
	if not inv_name or not frappe.db.table_exists("Payment Entry Reference"):
		return rows

	pe_rows = frappe.db.sql(
		"""
		SELECT pe.mode_of_payment, per.allocated_amount AS amount
		FROM `tabPayment Entry Reference` per
		INNER JOIN `tabPayment Entry` pe ON pe.name = per.parent AND pe.docstatus = 1
		WHERE per.reference_doctype = 'Sales Invoice'
		  AND per.reference_name = %(inv)s
		ORDER BY pe.creation ASC
		""",
		{"inv": inv_name},
		as_dict=True,
	)
	for pe in pe_rows or []:
		amount = flt(pe.get("amount"))
		if amount <= 0:
			continue
		key = f"{pe.get('mode_of_payment')}|{amount}"
		if key in seen_pe:
			continue
		seen_pe.add(key)
		rows.append({"mode_of_payment": pe.get("mode_of_payment") or "", "amount": amount})

	return rows


def receipt_total_paid_for_invoice(inv) -> float:
	"""Total collected on receipt — includes Payment Entry bank transfers not on SI Payment child table."""
	grand = flt(getattr(inv, "grand_total", None) if not isinstance(inv, dict) else inv.get("grand_total"))
	outstanding = flt(
		getattr(inv, "outstanding_amount", None) if not isinstance(inv, dict) else inv.get("outstanding_amount")
	)
	if grand > 0 and outstanding >= 0:
		paid = flt(grand - outstanding)
		if paid > 0:
			return paid

	payments = receipt_payments_for_invoice(inv)
	total_from_rows = flt(sum(flt(p.get("amount")) for p in payments))
	paid_field = flt(getattr(inv, "paid_amount", None) if not isinstance(inv, dict) else inv.get("paid_amount"))
	return max(paid_field, total_from_rows)


def receipt_payments_for_jinja(doc):
	"""Print Format (Jinja): payment block with Payment Entry rows included."""
	return frappe._dict(
		payments=receipt_payments_for_invoice(doc),
		total_paid=receipt_total_paid_for_invoice(doc),
	)


def receipt_loyalty_earned_for_invoice(inv) -> float:
	"""Points earned on this invoice (positive entries only)."""
	inv_name = getattr(inv, "name", None) or inv.get("name")
	if not inv_name or not frappe.db.table_exists("Loyalty Point Entry"):
		return 0.0
	res = frappe.db.sql(
		"""
		select coalesce(sum(loyalty_points), 0)
		from `tabLoyalty Point Entry`
		where invoice = %(inv)s and invoice_type = %(dt)s and loyalty_points > 0
		""",
		{"inv": inv_name, "dt": "Sales Invoice"},
	)
	return flt(res[0][0]) if res else 0.0


def receipt_loyalty_balance_for_invoice(inv) -> float:
	"""Số điểm khách TIÊU ĐƯỢC sau hoá đơn này — lấy từ ví (PM-TASK-00120).

	Trước đây số này cộng từ `Loyalty Point Entry` và lọc `expiry_date >= today`.
	Sai ở hai đầu, và sai ngược chiều nhau:

	  - Chương trình NEW-2026 đặt hạn dùng 0 ngày, mà ERPNext tính
	    `add_days(posting_date, 0)` chứ không coi 0 là vô hạn, nên điểm hết hạn
	    ngay cuối ngày. Phiếu in ra 0 trong khi ví khách còn 2.283 điểm.
	  - Ngược lại, tiêu điểm KHÔNG sinh dòng âm bên `Loyalty Point Entry` (khách
	    tiêu bằng hình thức thanh toán ví, không qua đường redeem của ERPNext).
	    Nên chỉ cần khách bắt đầu tiêu là sổ điểm cao hơn số tiêu được.

	Đặt lại hạn dùng chỉ chữa được vế đầu. Số duy nhất luôn đúng với câu hỏi
	"khách còn tiêu được bao nhiêu" là số dư ví, nên phiếu đọc thẳng từ đó.
	"""
	cust = getattr(inv, "customer", None) if not isinstance(inv, dict) else inv.get("customer")
	company = getattr(inv, "company", None) if not isinstance(inv, dict) else inv.get("company")
	if not cust or not company or not frappe.db.table_exists("Wallet Transaction"):
		return 0.0

	from pos_next.pos_next.doctype.wallet.wallet import tinh_so_du_vi

	try:
		return flt(tinh_so_du_vi(cust, company))
	except Exception:
		# Phiếu in không được chết vì một con số phụ. Ghi log rồi in 0.
		frappe.log_error(frappe.get_traceback(), "Receipt wallet balance error")
		return 0.0


def enrich_invoice_dict_for_print(inv: dict[str, Any]) -> dict[str, Any]:
	"""Các key bổ sung cho phiếu in (HTML fallback POS + có thể dùng API)."""
	out: dict[str, Any] = {}
	out["receipt_print_datetime"] = format_datetime(now_datetime(), "dd/MM/yyyy HH:mm")
	company = inv.get("company") or ""
	if company:
		row = frappe.db.get_value(
			"Company",
			company,
			["company_name", "phone_no"],
			as_dict=True,
		)
		out["receipt_company_display_name"] = (row or {}).get("company_name") or company
		out["receipt_company_phone"] = (row or {}).get("phone_no") or ""
	else:
		out["receipt_company_display_name"] = company
		out["receipt_company_phone"] = ""
	out["receipt_company_address"] = (inv.get("company_address_display") or "").strip()
	pp = inv.get("pos_profile")
	if pp and frappe.get_meta("POS Profile").has_field("custom_print_in_duplicate"):
		out["print_in_duplicate"] = cint(
			frappe.db.get_value("POS Profile", pp, "custom_print_in_duplicate")
		)
	out["is_reprint"] = bool(inv.get("posa_is_printed"))
	wh = frappe.db.get_value("POS Profile", pp, "warehouse") if pp else None
	out["receipt_branch_label"] = (
		frappe.db.get_value("Warehouse", wh, "warehouse_name") if wh else (pp or "")
	)
	owner = inv.get("owner")
	out["receipt_salesperson"] = (
		frappe.db.get_value("User", owner, "full_name") if owner else ""
	) or (owner or "")
	out["receipt_customer_phone"] = (
		(inv.get("contact_mobile") or "").strip()
		or (inv.get("mobile_no") or "").strip()
		or (inv.get("pos_einvoice_buyer_phone") or "").strip()
	)
	out["receipt_msch"] = ""

	out["receipt_loyalty_earned"] = receipt_loyalty_earned_for_invoice(inv)
	out["receipt_loyalty_balance"] = receipt_loyalty_balance_for_invoice(inv)
	out["receipt_payments"] = receipt_payments_for_invoice(inv)
	out["receipt_total_paid"] = receipt_total_paid_for_invoice(inv)
	return out


def _is_cash_mode_of_payment(mode_of_payment: str | None) -> bool:
	label = (mode_of_payment or "").strip().lower()
	return label in {"cash", "tiền mặt", "tien mat", "tiền mặt vnđ"} or "cash" in label


def _la_hinh_thuc_vi(mode_of_payment: str | None) -> bool:
	"""Hình thức thanh toán bằng ví điểm thưởng (PM-TASK-00120).

	Đọc cờ `is_wallet_payment` chứ không đoán theo tên, vì đó là tín hiệu cả
	phần còn lại của POS đang dùng (PaymentDialog loại hình thức ví ra trước khi
	xét loại tài khoản). Đoán theo tên thì hình thức tên "đổi điểm" rơi vào rổ
	"còn lại" và in ra thành Chuyển khoản; đọc theo `type` cũng sai, vì hình
	thức đó khai type = Cash nên sẽ in thành Tiền mặt.
	"""
	if not mode_of_payment:
		return False
	return bool(
		cint(frappe.db.get_value("Mode of Payment", mode_of_payment, "is_wallet_payment"))
	)


def _payment_totals_by_type(doc) -> dict[str, float]:
	cash_paid = 0.0
	bank_paid = 0.0
	wallet_paid = 0.0
	for row in receipt_payments_for_invoice(doc):
		amount = flt(row.get("amount"))
		if amount <= 0:
			continue
		mode = row.get("mode_of_payment")
		if _la_hinh_thuc_vi(mode):
			wallet_paid += amount
		elif _is_cash_mode_of_payment(mode):
			cash_paid += amount
		else:
			bank_paid += amount
	return {"cash_paid": cash_paid, "bank_paid": bank_paid, "wallet_paid": wallet_paid}


def _pos_profile_store_fields(pos_profile: str | None) -> dict[str, Any]:
	if not pos_profile:
		return {}
	meta = frappe.get_meta("POS Profile")
	fields = [
		fname
		for fname in (
			"custom_shop_code",
			"custom_store_name_2",
			"custom_address",
			"custom_phone",
			"custom_pos_logo",
			"custom_store_hours",
			"tc_name",
		)
		if meta.has_field(fname)
	]
	if not fields:
		return {}
	return frappe.db.get_value("POS Profile", pos_profile, fields, as_dict=True) or {}


def _receipt_policy_text(tc_name: str | None) -> str:
	"""Dòng chính sách in cuối phiếu, lấy từ POS Profile > Terms and Conditions.

	Trước đây câu "Hàng mua rồi miễn đổi trả..." được gắn cứng trong mẫu in và
	trong cả hai nhánh in nhiệt — đó là chính sách của MỘT chuỗi cửa hàng, in
	lên phiếu của mọi khách, và mâu thuẫn với chính tính năng trả hàng của app.
	Cửa hàng nào cần thì khai vào ô Terms and Conditions của POS Profile; không
	khai thì phiếu không in dòng nào.

	Terms and Conditions là Text Editor (HTML) nên phải bóc thẻ: máy in nhiệt in
	thẳng chuỗi, để nguyên HTML là ra đầy thẻ trên giấy.
	"""
	if not tc_name:
		return ""
	terms = frappe.db.get_value("Terms and Conditions", tc_name, "terms")
	if not terms:
		return ""
	return " ".join(frappe.utils.strip_html(terms).split())


def _nhan_ca(inv: dict[str, Any]) -> str:
	"""Nhãn ca của phiếu: "Ca N" theo THỨ TỰ ca trong ngày của cửa hàng đó.

	Trước đây gắn cứng "Ca 1" cho mọi phiếu — cửa hàng mở ca thứ hai trong ngày
	vẫn in ra "Ca 1", tức phiếu ghi sai ca.
	"""
	ca = inv.get("posa_pos_opening_shift")
	if not ca:
		return ""

	thong_tin = frappe.db.get_value(
		"POS Opening Shift", ca, ["pos_profile", "period_start_date"], as_dict=True
	)
	if not thong_tin or not thong_tin.period_start_date:
		return ""

	truoc_do = frappe.db.count(
		"POS Opening Shift",
		{
			"pos_profile": thong_tin.pos_profile,
			"docstatus": 1,
			"period_start_date": [
				"between",
				[
					frappe.utils.get_datetime(thong_tin.period_start_date).date(),
					thong_tin.period_start_date,
				],
			],
		},
	)
	return f"Ca {max(truoc_do, 1)}"


def attach_image_url_for_print(file_path: str | None) -> str:
	"""Absolute URL cho Attach Image (fallback khi không embed base64)."""
	if not file_path:
		return ""
	from frappe.utils import get_url

	path = str(file_path).strip()
	if path.startswith("http://") or path.startswith("https://"):
		return path
	if not path.startswith("/"):
		path = f"/{path}"
	encoded = "/" + "/".join(quote(part, safe="") for part in path.split("/") if part)
	return get_url(encoded)


def _resize_receipt_logo_bytes(raw: bytes, disk_path: str, max_px: int = 512) -> tuple[bytes, str]:
	"""Thu nhỏ logo (ảnh dọc/ngang) trước khi embed — phiếu in gọn hơn.

	⚠ Ngưỡng này tính theo ĐIỂM IN của máy in nhiệt, không phải điểm màn hình.
	Giấy 80mm in được 576 điểm ngang, mẫu in đặt logo rộng 68mm ≈ 490 điểm. Đặt
	96px như trước là ảnh bị phóng gấp 5 lần khi in — chữ trong logo nhoè hẳn.
	512 đủ nét cho cả giấy 58mm lẫn 80mm mà file nhúng vẫn nhỏ (PM-TASK-00116).
	"""
	try:
		import io

		from PIL import Image

		img = Image.open(io.BytesIO(raw))
		if img.mode not in ("RGB", "L"):
			img = img.convert("RGB")
		img.thumbnail((max_px, max_px), Image.Resampling.LANCZOS)
		out = io.BytesIO()
		img.save(out, format="JPEG", quality=88, optimize=True)
		return out.getvalue(), "image/jpeg"
	except Exception:
		mime = mimetypes.guess_type(disk_path)[0] or "image/png"
		return raw, mime


def attach_image_src_for_print(file_path: str | None, max_bytes: int = 2 * 1024 * 1024) -> str:
	"""
	Src cho <img> phiếu in: embed base64 (private file, tên có khoảng trắng).
	Fallback URL nếu không đọc được file.
	"""
	if not file_path:
		return ""

	path = str(file_path).strip()
	if path.startswith("http://") or path.startswith("https://"):
		return path

	try:
		from frappe.utils.file_manager import get_file_path

		disk_path = get_file_path(path)
		if not disk_path or not os.path.isfile(disk_path):
			return attach_image_url_for_print(path)

		if os.path.getsize(disk_path) > max_bytes:
			return attach_image_url_for_print(path)

		with open(disk_path, "rb") as image_file:
			raw = image_file.read()

		raw, mime = _resize_receipt_logo_bytes(raw, disk_path)
		b64 = base64.b64encode(raw).decode("ascii")
		return f"data:{mime};base64,{b64}"
	except Exception:
		frappe.log_error(
			title="POS receipt logo embed failed",
			message=frappe.get_traceback(),
		)
		return attach_image_url_for_print(path)


def item_barcode_for_receipt(item) -> str:
	"""Barcode / mã vạch dòng hàng cho phiếu bán lẻ."""
	barcode = getattr(item, "barcode", None)
	if barcode is None and isinstance(item, dict):
		barcode = item.get("barcode")
	if barcode:
		return str(barcode)

	item_code = getattr(item, "item_code", None) or (item.get("item_code") if isinstance(item, dict) else None)
	if not item_code:
		return ""

	# ERPNext stores barcodes in Item Barcode child table (Item has no barcode column).
	if frappe.db.table_exists("Item Barcode"):
		row_barcode = frappe.db.get_value(
			"Item Barcode",
			{"parent": item_code},
			"barcode",
			order_by="idx asc",
		)
		if row_barcode:
			return str(row_barcode)

	return str(item_code)


def item_gross_amount_for_receipt(item) -> float:
	qty = flt(getattr(item, "qty", None) if not isinstance(item, dict) else item.get("qty"))
	rate = flt(
		getattr(item, "price_list_rate", None)
		if not isinstance(item, dict)
		else item.get("price_list_rate")
	)
	if not rate:
		rate = flt(getattr(item, "rate", None) if not isinstance(item, dict) else item.get("rate"))
	return flt(rate * qty)


def _item_field(item, field):
	return getattr(item, field, None) if not isinstance(item, dict) else item.get(field)


def item_discount_percent_for_receipt(item) -> float:
	"""% chiết khấu dòng hàng cho phiếu in.

	Ưu tiên `discount_percentage`. Nếu = 0 (khuyến mãi qua Pricing Rule bị POS
	quy về số tiền + rate tròn, xem sales_invoice_hooks.restore_pos_authoritative_discounts)
	thì quy đổi lại % từ giá gốc: (price_list_rate - rate) / price_list_rate * 100,
	hoặc từ discount_amount khi thiếu rate. Trả 0 nếu không có chiết khấu.
	"""
	pct = flt(_item_field(item, "discount_percentage"))
	if pct > 0:
		return pct

	price_list_rate = flt(_item_field(item, "price_list_rate"))
	if price_list_rate <= 0:
		return 0.0

	rate = flt(_item_field(item, "rate"))
	if rate > 0 and rate < price_list_rate:
		return (price_list_rate - rate) / price_list_rate * 100

	qty = flt(_item_field(item, "qty"))
	discount_amount = flt(_item_field(item, "discount_amount"))
	if discount_amount > 0 and qty > 0:
		per_unit = discount_amount / qty
		if per_unit < price_list_rate:
			return per_unit / price_list_rate * 100

	return 0.0


def retail_receipt_meta_for_jinja(doc):
	"""Metadata cho Print Format POS Retail Receipt."""
	inv = doc.as_dict()
	base = enrich_invoice_dict_for_print(inv)
	profile = _pos_profile_store_fields(inv.get("pos_profile"))
	pay = _payment_totals_by_type(doc)

	gross_total = 0.0
	item_discount_total = 0.0
	for row in getattr(doc, "items", None) or []:
		gross_total += item_gross_amount_for_receipt(row)
		item_discount_total += flt(getattr(row, "discount_amount", None) or 0)

	posting_date = ""
	if doc.posting_date:
		posting_date = format_datetime(doc.posting_date, "dd/MM/yyyy")
	posting_time = ""
	if doc.posting_time:
		posting_time = str(doc.posting_time).split(".")[0][:8]

	now = now_datetime()
	owner = inv.get("owner") or ""
	salesperson = (
		frappe.db.get_value("User", owner, "full_name") if owner else ""
	) or owner

	pos_logo_url = attach_image_src_for_print(profile.get("custom_pos_logo"))

	return frappe._dict(
		**base,
		pos_logo_url=pos_logo_url,
		shop_code=profile.get("custom_shop_code") or "",
		store_display_name=profile.get("custom_store_name_2") or base.get("receipt_branch_label") or "",
		store_address=profile.get("custom_address") or base.get("receipt_company_address") or "",
		store_phone=profile.get("custom_phone") or base.get("receipt_company_phone") or "",
		posting_date=posting_date,
		posting_time=posting_time,
		print_date=format_datetime(now, "dd/MM/yyyy"),
		print_time=format_datetime(now, "HH:mm:ss"),
		shift_label=_nhan_ca(inv),
		gross_total=gross_total,
		item_discount_total=item_discount_total,
		invoice_discount_total=abs(
			flt(inv.get("custom_invoice_discount_amount") or inv.get("discount_amount") or 0)
		),
		cash_paid=pay["cash_paid"],
		bank_paid=pay["bank_paid"],
		wallet_paid=pay["wallet_paid"],
		vip_label=inv.get("customer_category") or "",
		store_hours=profile.get("custom_store_hours") or "",
		receipt_policy=_receipt_policy_text(profile.get("tc_name")),
		salesperson=salesperson,
	)


def receipt_logo_url_for_print(doc=None) -> str:
	"""Logo phiếu in, lấy theo TỪNG CỬA HÀNG (POS Profile > Logo POS).

	Bản cũ trả về một đường dẫn GẮN CỨNG logo của một dự án cụ thể, nên mọi khách
	khác in ra logo của khách đó (PM-TASK-00116). Giờ đọc ô `custom_pos_logo` của
	POS Profile trên hoá đơn. Cửa hàng chưa tải logo lên thì phiếu không có logo
	— đúng hơn là in nhầm logo người khác.
	"""
	pos_profile = None
	if doc is not None:
		pos_profile = getattr(doc, "pos_profile", None)
		if not pos_profile and isinstance(doc, dict):
			pos_profile = doc.get("pos_profile")
	if not pos_profile:
		return ""

	logo = frappe.db.get_value("POS Profile", pos_profile, "custom_pos_logo")
	return attach_image_src_for_print(logo) if logo else ""


def invoice_meta_for_jinja(doc):
	"""Print Format (Jinja): invoice_meta_for_jinja(doc) — registered via pos_next hooks jinja.methods."""
	return enrich_invoice_dict_for_print(doc.as_dict())


def einvoice_qr_payload_for_jinja(invoice_name: str) -> dict[str, Any]:
	from pos_next.api.einvoice_self_service import get_self_service_qr_payload

	return get_self_service_qr_payload(invoice_name or "") or {}
