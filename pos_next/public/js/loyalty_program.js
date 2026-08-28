// Copyright (c) 2026, BrainWise and contributors
// For license information, please see license.txt

frappe.provide("pos_next.loyalty_program");

(function patch_loyalty_exclusion_item_line_query() {
	const dimensions = erpnext.accounts?.dimensions;
	if (!dimensions || dimensions._pos_next_loyalty_exclusion_patched) {
		return;
	}

	dimensions._pos_next_loyalty_exclusion_patched = true;
	const originalSetupFilters = dimensions.setup_filters.bind(dimensions);

	dimensions.setup_filters = function (frm, doctype) {
		originalSetupFilters(frm, doctype);
		if (doctype === "Loyalty Program") {
			pos_next.loyalty_program.clear_excluded_item_line_company_filter(frm);
		}
	};
})();

pos_next.loyalty_program.clear_excluded_item_line_company_filter = function (frm) {
	// Item Line is an accounting dimension; ERPNext filters by company on fields named
	// "item_line". Loyalty exclusion config should list all item lines, not company-scoped.
	frm.set_query("item_line", "loyalty_excluded_item_lines", function () {
		return {};
	});
};

frappe.ui.form.on("Loyalty Program", {
	refresh(frm) {
		pos_next.loyalty_program.clear_excluded_item_line_company_filter(frm);
	},
});
