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

	# Fetch items filtered by active sections
	product_data = get_products_with_stock(
		query_args={"field_filters": {"custom_section": [s["section_name"] for s in sections_data]}}, 
		home_page=1
	)
	
	# Group items by section (preserving section order from get_sections)
	result = {s["section_name"]: [] for s in sections_data}
	
	for item in product_data.get("items", []) or []:
		if section := item.get("custom_section"):
			if section in result:
				result[section].append(item)

	# Sort items in each section by their specific order
	for items in result.values():
		items.sort(key=lambda x: x.get("custom_section_order") or 0)

	return result


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

