import frappe
from frappe.custom.doctype.custom_field.custom_field import create_custom_fields

@frappe.whitelist()
def execute():
	if "webshop" not in frappe.get_installed_apps():
		return

	custom_fields = {
		"Item": [
			{
				"fieldname": "discontinued",
				"label": "Discontinued",
				"fieldtype": "Check",
				"insert_after": "is_sales_item",
				"description": "If checked, this item is discontinued and will be hidden from the website when out of stock and not in production.",
				"default": 0
			}
		],
		"Website Item": [
			{
				"fieldname": "discontinued",
				"label": "Discontinued",
				"fieldtype": "Check",
				"insert_after": "published", 
				"description": "Synced from Item. If checked, this item is discontinued.",
				"default": 0,
				"read_only": 1
			}
		]
	}

	create_custom_fields(custom_fields, ignore_validate=True)
