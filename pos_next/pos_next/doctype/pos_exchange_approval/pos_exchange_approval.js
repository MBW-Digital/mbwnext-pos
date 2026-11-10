// Copyright (c) 2026, MBW and contributors
// For license information, please see license.txt

// Người duyệt mở yêu cầu từ chuông / email rồi bấm Duyệt hoặc Từ chối ngay trên form
// (PM-FEAT-00044). Server tự kiểm người bấm có trong danh sách duyệt của cửa hàng.
frappe.ui.form.on("POS Exchange Approval", {
	refresh(frm) {
		const mau = { Pending: "orange", Approved: "green", Rejected: "red", Cancelled: "gray" };
		frm.page.set_indicator(__(frm.doc.status), mau[frm.doc.status] || "gray");
		if (frm.doc.status !== "Pending") return;

		frm.add_custom_button(__("Approve"), () => quyet_dinh(frm, 1)).addClass("btn-primary");
		frm.add_custom_button(__("Reject"), () => {
			frappe.prompt(
				{ fieldname: "note", fieldtype: "Small Text", label: __("Reason for rejecting"), reqd: 1 },
				(v) => quyet_dinh(frm, 0, v.note),
				__("Reject Late Exchange"),
				__("Reject")
			);
		});
	},
});

function quyet_dinh(frm, duyet, note) {
	frappe.call({
		method: "pos_next.api.exchange_ha_vang.decide_approval",
		args: { name: frm.doc.name, approve: duyet, note: note || null },
		freeze: true,
		callback: () => frm.reload_doc(),
	});
}
