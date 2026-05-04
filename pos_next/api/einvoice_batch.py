# Copyright (c) 2026, BrainWise and contributors
"""Phát hành hóa đơn bảng kê (tổng hợp cuối ngày) — Điều 6.5 TT78/2021."""
from __future__ import annotations

from typing import Any, Dict, List

import frappe
from frappe import _
from frappe.utils import cint


def _consolidated_max_si_per_request() -> int:
	"""Giới hạn số SI / request để tránh timeout và XML quá lớn.

	site_config.json: consolidated_einvoice_max_si (mặc định 3000).
	"""
	m = cint(frappe.conf.get("consolidated_einvoice_max_si"))
	return m if m > 0 else 3000


def _consolidated_enqueue_min_si() -> int:
	"""Từ bao nhiêu SI trở lên thì chạy background job thay vì đồng bộ.

	site_config.json:
	  consolidated_einvoice_enqueue_min_si

	- Không khai báo: mặc định **300** (>=300 SI → enqueue).
	- **0**: luôn chạy đồng bộ (không enqueue).
	"""
	m = cint(frappe.conf.get("consolidated_einvoice_enqueue_min_si"))
	if frappe.conf.get("consolidated_einvoice_enqueue_min_si") is None:
		return 300
	return m if m > 0 else 0


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------

def _validate_si_list_for_batch(si_names: List[str]) -> Dict[str, Any]:
	"""Kiểm tra danh sách SI có hợp lệ để gộp bảng kê không.

	Yêu cầu:
	- Tất cả cùng company
	- Tất cả cùng posting_date
	- Tất cả là is_pos = 1
	- Không có SI nào đã issued (created_einvoice = 1) hoặc đã có batch_einvoice_ref
	- Tất cả đã submitted (docstatus = 1)
	"""
	if not si_names:
		frappe.throw(_("Vui lòng chọn ít nhất một Sales Invoice."))

	rows = frappe.db.get_all(
		"Sales Invoice",
		filters=[["name", "in", si_names]],
		fields=[
			"name", "company", "posting_date", "is_pos", "pos_profile",
			"docstatus", "created_einvoice", "batch_einvoice_ref",
		],
	)

	if len(rows) != len(si_names):
		found = {r.name for r in rows}
		missing = [n for n in si_names if n not in found]
		frappe.throw(_("Không tìm thấy Sales Invoice: {0}").format(", ".join(missing)))

	errors = []
	companies = {r.company for r in rows}
	dates = {str(r.posting_date) for r in rows}

	if len(companies) > 1:
		errors.append(_("Tất cả hóa đơn phải cùng một công ty. Đang có: {0}").format(", ".join(companies)))
	if len(dates) > 1:
		errors.append(_("Tất cả hóa đơn phải cùng ngày. Đang có: {0}").format(", ".join(dates)))

	for r in rows:
		if r.docstatus != 1:
			errors.append(_("{0}: Hóa đơn chưa submit.").format(r.name))
		if not r.is_pos:
			errors.append(_("{0}: Không phải hóa đơn POS.").format(r.name))
		if r.created_einvoice:
			errors.append(_("{0}: Đã có hóa đơn điện tử.").format(r.name))
		if r.batch_einvoice_ref:
			errors.append(_("{0}: Đã thuộc bảng kê {1}.").format(r.name, r.batch_einvoice_ref))

	if errors:
		frappe.throw("<br>".join(errors))

	first = rows[0]
	return {
		"company": first.company,
		"batch_date": str(first.posting_date),
		"pos_profile": first.pos_profile or "",
		"rows": rows,
	}


def _mark_si_as_batched(si_names: List[str], fkey: str, einvoice_no: str) -> None:
	"""Đánh dấu các SI đã được gộp vào hóa đơn bảng kê."""
	frappe.db.set_value(
		"Sales Invoice",
		{"name": ["in", si_names]},
		{
			"batch_einvoice_ref": fkey,
			"created_einvoice": 1,
			"einvoice_no": einvoice_no,
			# Cùng fkey XML (BATCH-…) để get_einvoice_pdf / cổng VNPT tra đúng — không chỉ số C26TTA/…
			"einvoice_uuid": fkey,
		},
	)
	frappe.db.commit()


def _execute_consolidated_issue_sync(si_names: List[str], meta: Dict[str, Any]) -> Dict[str, Any]:
	"""Gọi VNPT + đánh dấu SI (dùng cho đồng bộ và worker)."""
	from mbwnext_einvoice.integrations.vnpt.service import issue_consolidated_from_si_list

	result = issue_consolidated_from_si_list(
		si_names=si_names,
		company=meta["company"],
		batch_date=meta["batch_date"],
		pos_profile=meta["pos_profile"],
	)
	fkey = result.get("fkey") or ""
	einvoice_no = result.get("einvoice_no") or ""
	_mark_si_as_batched(si_names, fkey, einvoice_no)
	return {
		"ok": True,
		"fkey": fkey,
		"einvoice_no": einvoice_no,
		"si_count": len(si_names),
		"batch_date": meta["batch_date"],
		"provider_result": result,
	}


def _issue_consolidated_einvoice_worker(si_names: List[str], submitted_by: str) -> None:
	"""Background: phát hành bảng kê (timeout dài, không chặn HTTP)."""
	try:
		frappe.set_user(submitted_by)
	except Exception:
		pass

	try:
		meta = _validate_si_list_for_batch(si_names)
		company = meta["company"]
		provider = (frappe.db.get_value("Company", company, "provider") or "").strip()
		if provider != "VNPT":
			frappe.throw(_("Hóa đơn bảng kê hiện chỉ hỗ trợ nhà cung cấp VNPT."))

		out = _execute_consolidated_issue_sync(si_names, meta)
		frappe.publish_realtime(
			"consolidated_einvoice_done",
			{
				"ok": True,
				"einvoice_no": out.get("einvoice_no"),
				"fkey": out.get("fkey"),
				"si_count": out.get("si_count"),
			},
			user=submitted_by,
		)
	except Exception as e:
		frappe.log_error(frappe.get_traceback(), "issue_consolidated_einvoice worker failed")
		frappe.publish_realtime(
			"consolidated_einvoice_done",
			{"ok": False, "error": str(e), "si_count": len(si_names)},
			user=submitted_by,
		)


# ---------------------------------------------------------------------------
# Public API
# ---------------------------------------------------------------------------

@frappe.whitelist()
def issue_consolidated_einvoice(si_names: str | List[str]) -> Dict[str, Any]:
	"""Phát hành hóa đơn bảng kê cho danh sách SI bán lẻ.

	si_names: JSON string hoặc list tên Sales Invoice.
	"""
	import json as _json

	if isinstance(si_names, str):
		try:
			si_names = _json.loads(si_names)
		except Exception:
			si_names = [s.strip() for s in si_names.split(",") if s.strip()]

	si_names = list(si_names)

	max_si = _consolidated_max_si_per_request()
	if len(si_names) > max_si:
		frappe.throw(
			_("Quá nhiều hóa đơn ({0}). Tối đa <b>{1}</b> đơn mỗi lần. "
			  "Chia nhỏ danh sách hoặc cấu hình <code>consolidated_einvoice_max_si</code> trong site_config.")
			.format(len(si_names), max_si)
		)

	meta = _validate_si_list_for_batch(si_names)

	company = meta["company"]
	provider = (frappe.db.get_value("Company", company, "provider") or "").strip()

	if provider != "VNPT":
		frappe.throw(_("Hóa đơn bảng kê hiện chỉ hỗ trợ nhà cung cấp VNPT."))

	min_q = _consolidated_enqueue_min_si()
	if min_q > 0 and len(si_names) >= min_q:
		frappe.enqueue(
			"pos_next.api.einvoice_batch._issue_consolidated_einvoice_worker",
			queue="long",
			timeout=7200,
			si_names=si_names,
			submitted_by=frappe.session.user,
			job_name=f"consolidated_einv_{len(si_names)}",
			enqueue_after_commit=True,
		)
		frappe.msgprint(
			_("Đã đưa <b>{0}</b> hóa đơn vào hàng chờ phát hành bảng kê (job nền). "
			  "Khi xong bạn sẽ nhận thông báo; có thể làm việc khác trong lúc chờ.<br><br>"
			  "Để luôn chạy đồng bộ: đặt <code>consolidated_einvoice_enqueue_min_si</code> = 0 trong site_config.")
			.format(len(si_names)),
			title=_("Đang xử lý"),
			indicator="orange",
		)
		return {
			"ok": True,
			"queued": True,
			"si_count": len(si_names),
			"batch_date": meta["batch_date"],
		}

	try:
		out = _execute_consolidated_issue_sync(si_names, meta)
	except Exception as e:
		frappe.log_error(frappe.get_traceback(), "issue_consolidated_einvoice: VNPT error")
		frappe.throw(_("Lỗi phát hành hóa đơn bảng kê: {0}").format(str(e)))

	frappe.msgprint(
		_("Đã phát hành hóa đơn bảng kê <b>{0}</b> cho {1} hóa đơn.").format(
			out.get("einvoice_no") or out.get("fkey"), len(si_names)
		),
		title=_("Phát hành thành công"),
		indicator="green",
	)

	return out


@frappe.whitelist()
def get_unissued_retail_si(company: str, date: str, pos_profile: str = "") -> List[Dict]:
	"""Lấy danh sách SI bán lẻ chưa xuất hóa đơn trong ngày.

	Dùng cho dialog xác nhận trước khi phát hành bảng kê.
	"""
	filters: Dict = {
		"company": company,
		"posting_date": date,
		"is_pos": 1,
		"docstatus": 1,
		"created_einvoice": 0,
		"batch_einvoice_ref": ("in", ["", None]),
	}
	if pos_profile:
		filters["pos_profile"] = pos_profile

	return frappe.db.get_all(
		"Sales Invoice",
		filters=filters,
		fields=["name", "customer_name", "grand_total", "pos_profile", "posting_date"],
		order_by="name asc",
	)
