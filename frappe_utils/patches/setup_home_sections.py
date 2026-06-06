import frappe


def execute():
	"""Seed Website Sections and configure the home page so products appear."""
	_create_sections()
	_configure_settings()
	_assign_items_to_sections()


def _create_sections():
	sections = ["Featured Products", "New Arrivals"]
	for name in sections:
		if not frappe.db.exists("Website Section", name):
			frappe.get_doc({"doctype": "Website Section", "section_name": name}).insert(
				ignore_permissions=True
			)


def _configure_settings():
	settings = frappe.get_doc("Website Customization Settings")
	existing = {row.section_name for row in settings.get("section_setting", [])}

	for order, name in enumerate(["Featured Products", "New Arrivals"], start=1):
		if name not in existing:
			settings.append("section_setting", {"section_name": name, "order": order, "is_active": 1})

	settings.save(ignore_permissions=True)


def _assign_items_to_sections():
	items = frappe.db.get_all(
		"Website Item",
		filters={"custom_section": ("is", "not set")},
		fields=["name"],
		order_by="creation asc",
	)

	section_cycle = ["Featured Products", "New Arrivals"]
	for i, item in enumerate(items):
		section = section_cycle[i % len(section_cycle)]
		frappe.db.set_value(
			"Website Item",
			item.name,
			{"custom_section": section, "custom_section_order": (i // len(section_cycle)) + 1},
		)
