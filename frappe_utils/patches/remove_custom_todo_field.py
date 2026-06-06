import frappe


def execute():
	"""Remove the test custom_todo field from filter config and from the schema."""
	# Remove from Webshop Settings filter list
	frappe.db.delete("Website Filter Field", {"parent": "Webshop Settings", "fieldname": "custom_todo"})

	# Delete the Custom Field definitions (bench migrate will drop the columns)
	for name in ("Item-custom_todo", "Website Item-custom_todo"):
		if frappe.db.exists("Custom Field", name):
			frappe.delete_doc("Custom Field", name, ignore_permissions=True, force=True)

	frappe.db.commit()
