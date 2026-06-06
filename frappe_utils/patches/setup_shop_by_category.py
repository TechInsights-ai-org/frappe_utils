import frappe


def execute():
	"""Set website_item_field and seed Shop By Category rows from existing Website Item groups."""
	_set_website_item_field()
	_seed_categories()


def _set_website_item_field():
	existing = frappe.db.get_single_value("Website Customization Settings", "website_item_field")
	if not existing:
		frappe.db.set_single_value("Website Customization Settings", "website_item_field", "item_group")


def _seed_categories():
	existing_values = {
		row.value
		for row in frappe.db.get_all(
			"Shop By Category",
			filters={"parent": "Website Customization Settings"},
			fields=["value"],
		)
	}
	if existing_values:
		return

	groups = frappe.db.get_all(
		"Website Item",
		fields=["item_group"],
		group_by="item_group",
		order_by="item_group asc",
	)

	settings = frappe.get_doc("Website Customization Settings")
	for order, row in enumerate(groups, start=1):
		group = row.item_group
		if not group or group in existing_values:
			continue
		settings.append(
			"category",
			{
				"display_name": group,
				"value": group,
				"thumbnail": None,
				"order": order,
			},
		)
	settings.save(ignore_permissions=True)
