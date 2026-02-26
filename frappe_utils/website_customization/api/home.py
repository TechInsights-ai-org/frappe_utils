import frappe 
import json
from frappe_utils.api import get_products_with_stock

def get_sections():
	sections = frappe.db.sql(
		"""
		SELECT section_name, `order`
		FROM `tabHome Page Section`
		WHERE is_active = 1
		ORDER BY `order` ASC
		""",
		as_dict=True
	)
	return sections

@frappe.whitelist(allow_guest=True)
def get_products_by_section():
	sections_data = get_sections()
	if not sections_data:
		return {}

	active_section_names = [s["section_name"] for s in sections_data]

	# Fetch Website Item names that have at least one active section reference
	wi_names_with_section = frappe.db.get_all(
		"Section reference",
		filters={"section": ["in", active_section_names]},
		fields=["parent"],
		pluck="parent"
	)

	if not wi_names_with_section:
		community_link = frappe.get_doc("Website Customization Settings").community_link
		return {}, {"whatsapp_community_link": community_link}

	# Get item_codes for those Website Items so get_products_with_stock can filter
	wi_item_codes = frappe.db.get_all(
		"Website Item",
		filters={"name": ["in", wi_names_with_section]},
		pluck="item_code"
	)

	product_data = get_products_with_stock(
		query_args={"field_filters": {"item_code": wi_item_codes}},
		home_page=1
	)

	# Group items by section, fanning out items that belong to multiple sections
	result = {s["section_name"]: [] for s in sections_data}

	for item in product_data.get("items", []) or []:
		for sec in item.get("sections", []):
			section_name = sec.get("section")
			if section_name in result:
				# Clone item dict so each section gets its own copy with the correct order
				item_copy = dict(item)
				item_copy["section_order"] = sec.get("order") or 0
				result[section_name].append(item_copy)

	# Sort items within each section by their section-specific order
	for items in result.values():
		items.sort(key=lambda x: x.get("section_order") or 0)

	community_link = frappe.get_doc("Website Customization Settings").community_link

	return result, {"whatsapp_community_link": community_link}


@frappe.whitelist(allow_guest=True)
def get_shop_by_category():
	
	filter_field = frappe.get_doc("Website Customization Settings").website_item_field
	
	if not filter_field:
		return {}

	filter_filed = filter_field.split(" ")[0]
	
	query = """
	SELECT display_name,value,thumbnail 
	FROM `tabShop By Category` 
	WHERE 
	parent = 'Website Customization Settings'
	ORDER BY `order` ASC
	"""
	data = frappe.db.sql(query, as_dict=True)
	return {"shop_by_category": data,"filter_field":filter_filed}

