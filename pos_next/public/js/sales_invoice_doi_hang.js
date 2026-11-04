// Nút "Huỷ đổi hàng" trên chứng từ đổi hàng tại quầy (PM-FEAT-00044, Hạ Vàng).
// Phiếu trả + HĐ mới + bút toán bù trừ phải huỷ CẢ BỘ, đúng thứ tự — huỷ lẻ bị chặn
// (exchange_ha_vang.chan_huy_le). Thu ngân chỉ huỷ được trong ca; kế toán huỷ lúc nào cũng được.
frappe.ui.form.on("Sales Invoice", {
	refresh(frm) {
		if (frm.doc.docstatus !== 1 || !frm.doc.posa_is_exchange) return;
		const phieu_tra = frm.doc.is_return ? frm.doc.name : frm.doc.posa_exchange_against;
		if (!phieu_tra) return;
		frm.add_custom_button(__("Cancel Exchange"), () => {
			frappe.confirm(
				__("Cancel the whole exchange {0}: the return, the new invoice and their journal entries?", [phieu_tra]),
				() =>
					frappe.call({
						method: "pos_next.api.exchange_ha_vang.cancel_exchange",
						args: { return_invoice: phieu_tra },
						freeze: true,
						callback: () => frm.reload_doc(),
					})
			);
		});
	},
});
