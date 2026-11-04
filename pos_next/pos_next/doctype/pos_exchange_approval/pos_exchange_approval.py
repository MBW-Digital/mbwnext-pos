# Copyright (c) 2026, MBW and contributors
# For license information, please see license.txt

"""Yêu cầu duyệt đổi hàng quá hạn (PM-FEAT-00044, Hạ Vàng).

Hoá đơn quá số ngày được đổi thì POS không tự đổi được. Thu ngân gửi yêu cầu kèm lý
do; MỌI người trong danh sách "người duyệt đổi quá hạn" của cửa hàng (POS Profile)
nhận chuông + email, ai bấm Duyệt hoặc Từ chối trước thì yêu cầu đóng lại (anh Hưng
chốt 04/11: "1 trong các USER đó OK thì hoàn tất"). Không nhập mật khẩu người duyệt
trên máy POS — người duyệt quyết trên máy của họ (anh Thắng chốt 30/10).

Thứ tự trạng thái: Pending → Approved | Rejected | Cancelled. Một yêu cầu đã duyệt
chỉ dùng được cho MỘT lần đổi (`used_in_return`), và chỉ cho đúng hoá đơn + cửa hàng
đã xin.

Mọi trường đều chỉ đọc trên form: trạng thái chỉ đổi qua `quyet_dinh()` / `huy()`,
để không ai sửa tay "Approved" mà không qua kiểm tra người duyệt.
"""

import frappe
from frappe import _
from frappe.model.document import Document
from frappe.utils import get_url_to_form, now_datetime

SU_KIEN_REALTIME = "pos_exchange_approval"


def nguoi_duyet_cua_cua_hang(pos_profile):
	"""Danh sách user được duyệt đổi quá hạn của cửa hàng, theo thứ tự khai."""
	if not frappe.get_meta("POS Profile").has_field("custom_pos_exchange_approvers"):
		return []
	return frappe.get_all(
		"POS Exchange Approver",
		filters={"parent": pos_profile, "parenttype": "POS Profile", "parentfield": "custom_pos_exchange_approvers"},
		order_by="idx asc",
		pluck="user",
	)


class POSExchangeApproval(Document):
	def validate(self):
		if not (self.reason or "").strip():
			frappe.throw(_("Please enter the reason for the late exchange."))
		if not self.requested_by:
			self.requested_by = frappe.session.user

	def after_insert(self):
		nguoi_duyet = nguoi_duyet_cua_cua_hang(self.pos_profile)
		# Người duyệt có thể không có vai trò đọc DocType này (quản lý cửa hàng): chia sẻ
		# để họ mở được yêu cầu từ chuông / email.
		for user in nguoi_duyet:
			frappe.share.add_docshare(
				self.doctype, self.name, user, read=1, write=0, share=0, flags={"ignore_share_permission": True}, notify=0
			)
		self._bao(
			nguoi_duyet,
			_("Late exchange request: {0} ({1}, {2} days)").format(
				self.sales_invoice, self.customer_name or self.customer, self.days_since_sale
			),
		)

	# ------------------------------------------------------------------
	def la_nguoi_duyet(self, user=None):
		user = user or frappe.session.user
		return user == "Administrator" or user in nguoi_duyet_cua_cua_hang(self.pos_profile)

	def quyet_dinh(self, duyet, ghi_chu=None):
		"""Người duyệt bấm Duyệt (duyet=True) hoặc Từ chối. Ai bấm trước thì thắng."""
		# Khoá dòng: hai người duyệt bấm cùng lúc thì người sau thấy yêu cầu đã đóng.
		frappe.db.sql("select name from `tabPOS Exchange Approval` where name=%s for update", self.name)
		self.reload()
		if not self.la_nguoi_duyet():
			frappe.throw(
				_("You are not an approver for late exchanges at {0}.").format(self.pos_profile), frappe.PermissionError
			)
		if self.status != "Pending":
			frappe.throw(
				_("This request was already {0} by {1}.").format(
					_(self.status).lower(), frappe.utils.get_fullname(self.decided_by) if self.decided_by else "-"
				)
			)
		if not duyet and not (ghi_chu or "").strip():
			frappe.throw(_("Please enter the reason for rejecting."))

		self.db_set(
			{
				"status": "Approved" if duyet else "Rejected",
				"decided_by": frappe.session.user,
				"decided_on": now_datetime(),
				"decision_note": (ghi_chu or "").strip() or None,
			}
		)
		self.add_comment("Info", _("{0}: {1}").format(_(self.status), self.decision_note or ""))
		self._bao_thu_ngan()
		# Báo những người duyệt còn lại để họ khỏi mở một yêu cầu đã đóng.
		con_lai = [u for u in nguoi_duyet_cua_cua_hang(self.pos_profile) if u != frappe.session.user]
		self._bao(
			con_lai,
			_("Late exchange request {0} was {1} by {2}").format(
				self.name, _(self.status).lower(), frappe.utils.get_fullname(frappe.session.user)
			),
			gui_email=False,
		)

	def huy(self):
		"""Thu ngân rút yêu cầu khi khách không đổi nữa."""
		if self.status != "Pending":
			return
		self.db_set({"status": "Cancelled", "decided_on": now_datetime()})
		self._bao_thu_ngan()

	# ------------------------------------------------------------------
	def ket_qua(self):
		"""Phần POS cần biết về yêu cầu (không lộ gì ngoài yêu cầu này)."""
		return {
			"name": self.name,
			"sales_invoice": self.sales_invoice,
			"status": self.status,
			"reason": self.reason,
			"requested_by": self.requested_by,
			"decided_by": self.decided_by,
			"decided_by_name": frappe.utils.get_fullname(self.decided_by) if self.decided_by else None,
			"decided_on": self.decided_on,
			"decision_note": self.decision_note,
			"used_in_return": self.used_in_return,
		}

	def _bao_thu_ngan(self):
		frappe.publish_realtime(SU_KIEN_REALTIME, self.ket_qua(), user=self.requested_by, after_commit=True)
		if self.requested_by and self.requested_by != frappe.session.user:
			self._bao(
				[self.requested_by],
				_("Late exchange {0}: {1}").format(self.sales_invoice, _(self.status)),
				gui_email=False,
			)

	def _bao(self, users, tieu_de, gui_email=True):
		"""Chuông ERP + email (anh Thắng chốt 04/11: chỉ ERP và email, không Zalo).

		Thông báo loại "Alert" của Frappe không tự gửi email, nên email gửi riêng.
		"""
		users = [u for u in users if u and u != frappe.session.user]
		if not users:
			return
		from frappe.desk.doctype.notification_log.notification_log import enqueue_create_notification

		thong_bao = {
			"type": "Alert",
			"document_type": self.doctype,
			"document_name": self.name,
			"subject": tieu_de,
			"from_user": frappe.session.user,
		}
		# enqueue_create_notification() đẩy job NGAY, kể cả khi giao dịch sau đó rollback:
		# người duyệt sẽ nhận chuông cho một yêu cầu không tồn tại. Chờ commit rồi mới đẩy.
		frappe.db.after_commit.add(lambda: enqueue_create_notification(users, thong_bao))
		if not gui_email:
			return
		emails = [e for e in frappe.get_all("User", filters={"name": ["in", users], "enabled": 1}, pluck="email") if e]
		if not emails:
			return
		# Email chỉ là kênh báo thêm: site chưa khai email gửi đi thì vẫn phải gửi được
		# yêu cầu (người duyệt còn chuông ERP), không để thu ngân kẹt ở quầy.
		try:
			frappe.sendmail(
				recipients=emails,
				subject=tieu_de,
				message=_(
					"<p>{0} asks to exchange items on invoice <b>{1}</b> ({2}) at {3}.</p>"
					"<p>Purchased on {4}, {5} days ago (exchange period: {6} days).</p>"
					"<p>Reason: {7}</p>"
					'<p><a href="{8}">Open the request to approve or reject</a></p>'
				).format(
					frappe.utils.get_fullname(self.requested_by),
					self.sales_invoice,
					self.customer_name or self.customer,
					self.pos_profile,
					frappe.format_value(self.invoice_date, {"fieldtype": "Date"}),
					self.days_since_sale,
					self.allowed_days,
					frappe.utils.escape_html(self.reason),
					get_url_to_form(self.doctype, self.name),
				),
				reference_doctype=self.doctype,
				reference_name=self.name,
				now=False,
			)
		except Exception:
			frappe.log_error(title="POS Exchange Approval email", reference_doctype=self.doctype, reference_name=self.name)
