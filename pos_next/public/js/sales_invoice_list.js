// POS Next — Sales Invoice List: nút phát hành hóa đơn bảng kê (Điều 6.5 TT78)
frappe.listview_settings["Sales Invoice"] = frappe.listview_settings["Sales Invoice"] || {};

(function () {
	var _orig_onload = frappe.listview_settings["Sales Invoice"].onload;

	frappe.listview_settings["Sales Invoice"].onload = function (listview) {
		if (_orig_onload) _orig_onload(listview);

		listview.page.add_action_item(__("Phát hành HĐ bảng kê (cuối ngày)"), function () {
			var selected = listview.get_checked_items();
			if (!selected || !selected.length) {
				frappe.msgprint(__("Vui lòng chọn ít nhất một hóa đơn."));
				return;
			}

			var si_names = selected.map(function (r) { return r.name; });

			// Xác nhận trước khi phát hành
			var msg = __("Bạn đang chọn <b>{0}</b> hóa đơn để gộp thành <b>1 hóa đơn bảng kê</b>.<br><br>"
				+ "Yêu cầu: cùng ngày, cùng công ty, chưa có HĐDT.<br><br>"
				+ "Tiếp tục?", [si_names.length]);

			frappe.confirm(msg, function () {
				frappe.dom.freeze(__("Đang phát hành hóa đơn bảng kê…"));

				frappe.call({
					method: "pos_next.api.einvoice_batch.issue_consolidated_einvoice",
					args: { si_names: JSON.stringify(si_names) },
					freeze: false,
					callback: function (r) {
						frappe.dom.unfreeze();
						if (r && r.message && r.message.ok) {
							var m = r.message;
							frappe.show_alert({
								message: __("Đã phát hành HĐ bảng kê: <b>{0}</b> — {1} hóa đơn.", [m.einvoice_no || m.fkey, m.si_count]),
								indicator: "green",
							}, 8);
							listview.refresh();
						}
					},
					error: function () {
						frappe.dom.unfreeze();
					},
				});
			});
		});
	};
})();
