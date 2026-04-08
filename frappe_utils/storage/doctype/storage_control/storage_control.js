// Copyright (c) 2026, TechInsights-AI and contributors
// For license information, please see license.txt

frappe.ui.form.on("Storage Control", {
	refresh(frm) {
		if (frm.doc.enable_external_storage && frm.doc.access_key && frm.doc.bucket_name) {
			frm.add_custom_button(__("Test Connection"), () => {
				frm.call("test_connection");
			});
		}
	},
});
