// Copyright (c) 2025, TechInsights-AI and contributors
// For license information, please see license.txt

// frappe.ui.form.on("Google Drive Credentials", {
// 	refresh(frm) {

// 	},
// });
frappe.ui.form.on('Google Drive Credentials', {
    authorize: function(frm) {
        frappe.call({
            method: "frappe_utils.google.doctype.google_drive_credentials.google_drive_credentials.authorize_access",
            args: {
                name: frm.doc.name,
                reauthorize: frm.doc.refresh_token ? 1 : 0
            },
            callback: function(r) {
                console.log(r.message.url)
                if (!r.exc && r.message && r.message.url) {
                    // Open the Google OAuth consent page
                    window.open(r.message.url);
                }
            }
        });
    }
});