// Ô chọn tài khoản của hình thức thanh toán bằng ví (PM-TASK-00106).
//
// ERPNext gốc chỉ cho chọn tài khoản loại Bank / Cash / Receivable. Hợp lý với
// tiền mặt hay quẹt thẻ, nhưng sai với ví điểm thưởng: kế toán chốt điểm chỉ ghi
// sổ khi khách TIÊU, và lúc đó ghi thẳng vào 6418 - Chi phí bán hàng. Tài khoản
// chi phí không nằm trong ba loại kia nên gõ mãi không ra, kế toán tưởng hệ
// thống thiếu tài khoản.
//
// Nới bộ lọc đúng cho hình thức đã đánh dấu "Is Wallet Payment", các hình thức
// khác giữ nguyên như ERPNext.
frappe.ui.form.on("Mode of Payment", {
	setup: function (frm) {
		frm.set_query("default_account", "accounts", function (doc, cdt, cdn) {
			const dong = locals[cdt][cdn];
			const dieu_kien = [
				["Account", "is_group", "=", 0],
				["Account", "company", "=", dong.company],
			];

			if (!doc.is_wallet_payment) {
				dieu_kien.push(["Account", "account_type", "in", "Bank, Cash, Receivable"]);
			}

			return { filters: dieu_kien };
		});
	},
});
