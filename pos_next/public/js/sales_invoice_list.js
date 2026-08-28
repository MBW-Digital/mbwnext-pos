// POS Next — Sales Invoice List: nút phát hành hóa đơn bảng kê (Điều 6.5 TT78)
frappe.listview_settings["Sales Invoice"] = frappe.listview_settings["Sales Invoice"] || {};

(function () {
	var _orig_onload = frappe.listview_settings["Sales Invoice"].onload;

	frappe.listview_settings["Sales Invoice"].onload = function (listview) {
		if (_orig_onload) _orig_onload(listview);

		if (!frappe.listview_settings["Sales Invoice"]._pos_next_consolidated_rt) {
			frappe.listview_settings["Sales Invoice"]._pos_next_consolidated_rt = true;
			if (frappe.realtime && frappe.realtime.on) {
				frappe.realtime.on("consolidated_einvoice_done", function (data) {
					if (!data) return;
					if (data.ok) {
						frappe.show_alert({
							message: __("Phát hành HĐ bảng kê xong: <b>{0}</b> ({1} hóa đơn).", [
								data.einvoice_no || data.fkey || "—",
								String(data.si_count || ""),
							]),
							indicator: "green",
						}, 12);
					} else {
						frappe.msgprint({
							title: __("Lỗi HĐ bảng kê (job nền)"),
							message: data.error || __("Xem Error Log để biết chi tiết."),
							indicator: "red",
						});
					}
					if (
						frappe.get_route_str &&
						frappe.get_route_str() === "List/Sales Invoice" &&
						cur_list &&
						cur_list.doctype === "Sales Invoice"
					) {
						cur_list.refresh();
					}
				});
			}
		}

		listview.page.add_action_item(__("Phát hành HĐ bảng kê (cuối ngày)"), function () {
			var selected = listview.get_checked_items();
			if (!selected || !selected.length) {
				frappe.msgprint(__("Vui lòng chọn ít nhất một hóa đơn."));
				return;
			}

			var si_names = selected.map(function (r) { return r.name; });

			// Xác nhận trước khi phát hành
			var msg = __("Bạn đang chọn <b>{0}</b> hóa đơn để gộp thành <b>1 hóa đơn bảng kê</b>.<br><br>"
				+ "Yêu cầu: Cùng ngày, cùng công ty, chưa có HĐĐT.<br>"
				+ "Trên HĐĐT gửi VNPT: Các dòng <b>cùng SKU (mã hàng) và cùng đơn giá</b> được gộp một dòng.<br><br>"
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
							if (m.queued) {
								frappe.show_alert({
									message: __(
										"Đã đưa <b>{0}</b> hóa đơn vào job nền (queue long). Bạn sẽ nhận thông báo khi xong; danh sách tự làm mới nếu đang mở.",
										[m.si_count]
									),
									indicator: "orange",
								}, 12);
								return;
							}
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
