frappe.ui.form.on('Material Request', {
    refresh: function(frm) {
        frm.set_query("pos_profile", () => {
            return {
                filters: {
                    company: frm.doc.company,
                }
            }
        });
    }
});