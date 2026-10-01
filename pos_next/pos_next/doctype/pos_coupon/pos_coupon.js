// Copyright (c) 2021, Youssef Restom and contributors
// For license information, please see license.txt

frappe.ui.form.on("POS Coupon", {
	setup: function (frm) {
		frm.set_query("pos_offer", function () {
			return {
				filters: {
					company: frm.doc.company,
					coupon_based: 1,
					disable: 0,
				},
			};
		});
	},
	coupon_name: function (frm) {
		if (frm.doc.__islocal === 1) {
			frm.trigger("make_coupon_code");
		}
	},
	coupon_type: function (frm) {
		if (frm.doc.__islocal === 1) {
			frm.trigger("make_coupon_code");
		}
	},
	make_coupon_code: function (frm) {
		var coupon_name = frm.doc.coupon_name;
		var coupon_code;
		if (frm.doc.coupon_type == "Gift Card") {
			coupon_code = Math.random().toString(12).substring(2, 12).toUpperCase();
		} else if (frm.doc.coupon_type == "Promotional") {
			coupon_name = coupon_name.replace(/\s/g, "");
			coupon_code = coupon_name.toUpperCase().slice(0, 8);
		}
		frm.doc.coupon_code = coupon_code;
		frm.refresh_field("coupon_code");
	},
	refresh: function (frm) {
		// Giá trị lưu vẫn là Grand Total / Net Total; chỉ đổi nhãn cho đúng nghĩa (PM-TASK-00259).
		frm.set_df_property("apply_on", "label", __("Calculate Discount On"));
		frm.set_df_property("apply_on", "options", [
			{ label: __("List price (before promotion)"), value: "Grand Total" },
			{ label: __("Price after promotion (VAT included)"), value: "Net Total" },
		]);
		frm.set_df_property(
			"apply_on",
			"description",
			__("The amount the discount percentage is calculated on. 'Price after promotion' is what the customer would pay before this coupon; 'List price' ignores item promotions already applied.")
		);
		if (frm.doc.pricing_rule) {
			frm.add_custom_button(__("Add/Edit Coupon Conditions"), function () {
				frappe.set_route("Form", "POS Offer", frm.doc.pos_offer);
			});
		}
	},
});
