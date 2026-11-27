"""Gỡ các trường VNPost Pay còn sót trên POS Profile (PM-TASK-00446).

Tích hợp VNPost Pay đã bị gỡ khỏi code ở commit 37b68e0 (12/06), thay bằng
SePay, nhưng 11 Custom Field của nó vẫn nằm trong database: sync fixtures chỉ
thêm/sửa chứ không xoá trường đã bỏ. Chúng hiện ngay dưới các ô SePay (cùng
điều kiện hiển thị enable_bank_transfer_check) nên người thiết lập dễ điền nhầm.

Tệ hơn: hai ô "VNPost API username / password" nằm trong form nên trình duyệt
tự điền email + mật khẩu đăng nhập đã lưu của người đang thao tác, và bị lưu
theo khi bấm Lưu POS Profile. Trên dev đã thấy 42 mật khẩu như vậy trong
__Auth và email nhân viên trong ô username.

Patch xoá Custom Field, mật khẩu đã lưu và cột dữ liệu. Site không dính thì
chạy qua không làm gì. Chạy lại lần nữa vô hại.
"""

from __future__ import annotations

import frappe

DOCTYPE = "POS Profile"
TRUONG_VNPOST = (
	"vnpost_api_base_url",
	"vnpost_username",
	"vnpost_password",
	"vnpost_service_code",
	"vnpost_partner_code",
	"vnpost_partner_acc_no",
	"vnpost_pocode",
	"vnpost_rsa_private_key",
	"vnpost_vnpd_public_key",
	"vnpost_sdk_ui_url",
	"vnpost_sdk_show_pttt",
)


def execute():
	for fieldname in TRUONG_VNPOST:
		name = frappe.db.get_value("Custom Field", {"dt": DOCTYPE, "fieldname": fieldname})
		if name:
			frappe.delete_doc("Custom Field", name, ignore_permissions=True, force=True)

	frappe.db.delete("__Auth", {"doctype": DOCTYPE, "fieldname": ["in", TRUONG_VNPOST]})

	# Đọc thẳng cấu trúc bảng: frappe.db.has_column() trả lời theo cache, cột đã
	# xoá rồi vẫn báo là còn (chạy lại lần hai sẽ lỗi DROP COLUMN).
	cot_con = frappe.db.sql(
		"""SELECT column_name FROM information_schema.columns
		WHERE table_schema = DATABASE() AND table_name = 'tabPOS Profile'
			AND column_name IN %s""",
		(TRUONG_VNPOST,),
		pluck=True,
	)
	if cot_con:
		frappe.db.sql_ddl(
			"ALTER TABLE `tabPOS Profile` " + ", ".join(f"DROP COLUMN `{f}`" for f in cot_con)
		)

	frappe.clear_cache(doctype=DOCTYPE)
