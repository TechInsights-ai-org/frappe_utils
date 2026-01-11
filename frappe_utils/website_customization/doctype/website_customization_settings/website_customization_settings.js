frappe.ui.form.on("Website Customization Settings", {
    refresh(frm) {
        frm.trigger("setup_website_item_fields");
        frm.trigger("set_category_options");
    },

    setup_website_item_fields(frm) {
        frappe.model.with_doctype("Website Item", () => {
            let meta = frappe.get_meta("Website Item");
            let options = meta.fields
                .filter((df) => {
                    return !["Section Break", "Column Break", "Tab Break", "Table"].includes(df.fieldtype);
                })
                .map((df) => ({ label: df.label + ` (${df.fieldname})`, value: df.fieldname }));

            if (frm.fields_dict.website_item_field.set_data) {
                frm.fields_dict.website_item_field.set_data(options);
            }
        });
    },

    website_item_field(frm) {
        frm.trigger("set_category_options");
    },

    set_category_options(frm) {
        let fieldname = frm.doc.website_item_field;
        if (!fieldname) return;

        frappe.model.with_doctype("Website Item", () => {
            let meta = frappe.get_meta("Website Item");
            let df = meta.fields.find((field) => field.fieldname === fieldname);

            const update_options = (options) => {
                frm.fields_dict.category.grid.update_docfield_property("value", "options", options);
                // Explicitly update the field in the grid's docfields list to ensure inline editing picks it up
                let grid_df = frm.fields_dict.category.grid.docfields.find((d) => d.fieldname === "value");
                if (grid_df) {
                    grid_df.options = options;
                }
                frm.fields_dict.category.grid.refresh();
            };

            if (df && df.fieldtype === "Link" && df.options) {
                frappe.db.get_list(df.options, { pluck: "name", limit: 500 }).then((data) => {
                    update_options(data);
                });
            } else if (df && df.fieldtype === "Select" && df.options) {
                let options = df.options.split("\n");
                update_options(options);
            } else {
                update_options([]);
            }
        });
    },
});
