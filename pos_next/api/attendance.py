# -*- coding: utf-8 -*-
# Copyright (c) 2024, POS Next and contributors
# For license information, please see license.txt

from __future__ import unicode_literals

import base64
import re

import frappe
from frappe import _
from frappe.utils import nowdate, now_datetime

from hrms.hr.doctype.attendance.attendance import (
	DuplicateAttendanceError,
	OverlappingShiftAttendanceError,
)


def _get_employee_for_current_user(pos_profile=None, user=None):
	"""Xác định Employee tương ứng với user POS cấu hình trên POS Profile.

	Logic:
	- Nếu có truyền POS Profile thì ưu tiên dùng bảng Applicable for Users:
	  - Ưu tiên dòng có Default = 1, lấy trường User.
	  - Nếu không có, lấy dòng User đầu tiên của profile đó.
	- Nếu không có POS Profile (hoặc không tìm được dòng), fallback về user
	  truyền vào hoặc user của phiên hiện tại.
	- Cuối cùng map User này sang Employee qua Employee.user_id.
	"""
	session_user = frappe.session.user

	# Nếu không truyền user thì mặc định lấy user của session hiện tại
	if not user:
		user = session_user

	# Nếu có POS Profile thì cố gắng xác định POS user từ bảng Applicable for Users
	pos_profile_user = None
	if pos_profile:
		# Ưu tiên dòng được tick Default
		pos_profile_user = frappe.db.get_value(
			"POS Profile User",
			{"parent": pos_profile, "default": 1},
			"user",
		)

		if not pos_profile_user:
			pos_profile_user = frappe.db.get_value(
				"POS Profile User",
				{"parent": pos_profile},
				"user",
			)

	# Khi không truyền profile, thử suy ra từ Applicable for Users
	# của user (truyền vào hoặc session), nhưng vẫn map Employee qua user_id.
	if not pos_profile:
		pos_profile = frappe.db.get_value(
			"POS Profile User",
			{"user": user, "default": 1},
			"parent",
		) or frappe.db.get_value("POS Profile User", {"user": user}, "parent")

	effective_user = pos_profile_user or user

	employee = frappe.db.get_value("Employee", {"user_id": effective_user}, "name")

	if not employee:
		frappe.throw(
			_(
				"No Employee linked to POS user {0}. Please set Employee for this user."
			).format(frappe.bold(effective_user))
		)

	return employee, pos_profile


def _get_today_attendance(employee):
	"""Trả về bản ghi Attendance hôm nay của employee (dict) nếu có."""
	today = nowdate()
	records = frappe.get_all(
		"Attendance",
		filters={
			"employee": employee,
			"attendance_date": today,
			"docstatus": ["<", 2],
		},
		fields=["name", "status", "attendance_date", "in_time", "out_time"],
		limit_page_length=1,
		order_by="creation desc",
	)
	return records[0] if records else None


def _build_status(employee, attendance_row):
	"""Chuẩn hoá trạng thái chấm công trả về cho frontend."""
	today = nowdate()

	if not attendance_row:
		return {
			"state": "not_marked",
			"employee": employee,
			"attendance_name": None,
			"attendance_date": today,
			"status": None,
			"in_time": None,
			"out_time": None,
		}

	state = "checked_in"
	if attendance_row.get("out_time"):
		state = "checked_out"

	return {
		"state": state,
		"employee": employee,
		"attendance_name": attendance_row.get("name"),
		"attendance_date": attendance_row.get("attendance_date") or today,
		"status": attendance_row.get("status"),
		"in_time": attendance_row.get("in_time"),
		"out_time": attendance_row.get("out_time"),
	}


@frappe.whitelist()
def get_today_status(pos_profile=None):
	"""Lấy trạng thái chấm công hôm nay cho user POS hiện tại."""
	employee, _ = _get_employee_for_current_user(pos_profile=pos_profile)
	attendance_row = _get_today_attendance(employee)
	return _build_status(employee, attendance_row)


@frappe.whitelist()
def check_in(pos_profile=None, shift=None):
	"""Đánh dấu check-in Attendance hôm nay cho user POS hiện tại."""
	employee, _ = _get_employee_for_current_user(pos_profile=pos_profile)
	today = nowdate()

	attendance_row = _get_today_attendance(employee)

	# Nếu có truyền ca làm việc thì kiểm tra tồn tại
	if shift and not frappe.db.exists("Shift Type", shift):
		frappe.throw(
			_("Ca làm việc {0} không tồn tại.").format(frappe.bold(shift))
		)

	# Nếu đã có bản ghi chấm công cho hôm nay thì không sửa nữa (tránh lỗi update sau submit),
	# chỉ trả về trạng thái hiện tại.
	if attendance_row:
		attendance = frappe.get_doc("Attendance", attendance_row.get("name"))

		# Dù đã có giờ ra hay chưa, coi như hôm nay đã được chấm công,
		# không tạo thêm Attendance mới, chỉ trả về trạng thái hiện tại.
		return _build_status(employee, attendance.as_dict())

	# Không có Attendance cho hôm nay → tạo mới ở trạng thái draft với in_time
	attendance = frappe.new_doc("Attendance")
	doc = {
		"employee": employee,
		"attendance_date": today,
		"status": "Present",
		"in_time": now_datetime(),
	}
	if shift:
		doc["shift"] = shift

	attendance.update(doc)
	attendance.insert()  # để docstatus = 0, sẽ submit khi check-out

	return _build_status(employee, attendance.as_dict())


@frappe.whitelist()
def check_out(pos_profile=None):
	"""Đánh dấu check-out Attendance hôm nay cho user POS hiện tại."""
	employee, _ = _get_employee_for_current_user(pos_profile=pos_profile)
	today = nowdate()

	attendance_row = _get_today_attendance(employee)

	if not attendance_row:
		frappe.throw(
			_("No Attendance found for employee {0} on {1}. Please check in first.").format(
				frappe.bold(employee), frappe.bold(today)
			)
		)

	attendance = frappe.get_doc("Attendance", attendance_row.get("name"))

	# Nếu đã có giờ ra thì coi như đã check-out, trả lại trạng thái hiện tại
	if attendance.out_time:
		return _build_status(employee, attendance.as_dict())

	# Nếu bản ghi đã submit (docstatus = 1) nhưng chưa có out_time, không được phép sửa
	# qua flow chuẩn, nên báo lỗi rõ ràng.
	if attendance.docstatus == 1 and not attendance.out_time:
		frappe.throw(
			_(
				"Bảng chấm công hôm nay của nhân viên {0} đã được gửi, "
				"không thể cập nhật giờ ra từ POS."
			).format(frappe.bold(employee))
		)

	# Trường hợp bình thường: bản ghi đang ở trạng thái draft (docstatus = 0),
	# set giờ ra và submit để hoàn tất.
	attendance.out_time = now_datetime()

	if attendance.in_time and attendance.out_time:
		delta = attendance.out_time - attendance.in_time
		attendance.working_hours = round(delta.total_seconds() / 3600.0, 1)

	if attendance.docstatus == 0:
		attendance.submit()
	else:
		attendance.save()

	return _build_status(employee, attendance.as_dict())


@frappe.whitelist()
def get_shift_types():
	"""Lấy danh sách ca làm việc (Shift Type) khả dụng."""
	shifts = frappe.get_all(
		"Shift Type",
		filters={},
		fields=["name", "start_time", "end_time"],
		order_by="name asc",
		ignore_permissions=True,
	)
	return shifts


def _decode_base64_image(image_base64):
	"""Chuẩn hoá base64 từ data URL hoặc raw base64, trả về (bytes, ext)."""
	if not image_base64:
		frappe.throw(_("Không có dữ liệu ảnh."))
	data = image_base64.strip()
	# Data URL: data:image/jpeg;base64,xxxx
	if "," in data:
		data = data.split(",", 1)[1]
	# Chỉ lấy ký tự base64
	data = re.sub(r"\s+", "", data)
	raw = base64.b64decode(data, validate=True)
	if len(raw) > 10 * 1024 * 1024:  # 10 MB
		frappe.throw(_("Kích thước ảnh vượt quá 10 MB."))
	ext = "jpg"
	if raw[:8] == b"\x89PNG\r\n\x1a\n":
		ext = "png"
	elif raw[:2] in (b"\xff\xd8",):
		ext = "jpg"
	return raw, ext


@frappe.whitelist()
def upload_attendance_photo(attendance_name, image_base64, photo_type="check_in"):
	"""Đính kèm ảnh chấm công vào bản ghi Attendance (lưu thành File)."""
	if not attendance_name:
		frappe.throw(_("Thiếu tên bản ghi Attendance."))
	if not frappe.db.exists("Attendance", attendance_name):
		frappe.throw(_("Không tìm thấy bản ghi Attendance {0}.").format(frappe.bold(attendance_name)))
	attendance = frappe.get_doc("Attendance", attendance_name)
	# Kiểm tra quyền: chỉ user thuộc employee của attendance hoặc có quyền Attendance
	if attendance.employee:
		emp_user = frappe.db.get_value("Employee", attendance.employee, "user_id")
		if emp_user != frappe.session.user and not frappe.has_permission("Attendance", "write"):
			frappe.throw(_("Bạn không có quyền đính kèm ảnh cho bản ghi này."))
	content, ext = _decode_base64_image(image_base64)
	suffix = now_datetime().strftime("%Y-%m-%d_%H%M%S")
	file_name = "attendance_{0}_{1}.{2}".format(photo_type, suffix, ext)
	file_doc = frappe.get_doc(
		{
			"doctype": "File",
			"attached_to_doctype": "Attendance",
			"attached_to_name": attendance_name,
			"file_name": file_name,
			"content": content,
			"decode": False,
		}
	)
	file_doc.save(ignore_permissions=False)
	return {"file_name": file_doc.file_name, "file_url": file_doc.file_url}

