// Ô "Print Format" của POS Profile: cho chọn cả mẫu khai Sales Invoice.
//
// ERPNext lọc cứng danh sách theo `Doc Type = POS Invoice`. Nhưng POS của app
// này bán ra Sales Invoice chứ không phải POS Invoice, nên mẫu in của app
// (POS Next Receipt, POS Retail Receipt) khai Sales Invoice — và vì thế biến
// mất khỏi ô chọn, cửa hàng không khai được mẫu nào.
//
// Nới bộ lọc cho nhận cả hai doctype. Không đụng gì tới mẫu POS Invoice sẵn có.
frappe.ui.form.on("POS Profile", {
	setup: function (frm) {
		frm.set_query("print_format", function () {
			return {
				filters: {
					doc_type: ["in", ["Sales Invoice", "POS Invoice"]],
					disabled: 0,
				},
			};
		});

		// Ô "SePay Mode of Payment": chỉ cho chọn hình thức có trong bảng Payment Methods của chính
		// điểm bán (máy chủ cũng kiểm lúc lưu — sepay.validate_pos_profile_sepay).
		frm.set_query("sepay_mode_of_payment", function (doc) {
			const modes = (doc.payments || []).map((row) => row.mode_of_payment).filter(Boolean);
			return { filters: { name: ["in", modes] } };
		});
	},
});
