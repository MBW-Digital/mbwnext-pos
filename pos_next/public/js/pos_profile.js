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
	},
});
