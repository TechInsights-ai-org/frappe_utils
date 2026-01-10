// Copyright (c) 2026, TechInsights-AI and contributors
// For license information, please see license.txt

frappe.ui.form.on("Website Section", {
    refresh(frm) {
        frappe.model.with_doctype("Website Item", () => {
            let meta = frappe.get_meta("Website Item");
            let options = meta.fields
                .filter(df => !['Section Break', 'Column Break', 'Tab Break', 'HTML', 'Button', 'Image'].includes(df.fieldtype))
                .map(df => df.label)
                .filter(f => f);
            if (frm.fields_dict.filter_field.set_data) {
                frm.fields_dict.filter_field.set_data(options);
            }
        });
    },
});
