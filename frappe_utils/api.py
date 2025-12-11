import frappe
from frappe.utils import cint
import json


@frappe.whitelist(allow_guest=True)
def get_product_filters(item_group=None):
	"""
	Returns available filters (field and attribute filters) and sub-categories.
	"""
	if "webshop" not in frappe.get_installed_apps():
		return {
			"filters": {},
			"sub_categories": []
		}

	from webshop.webshop.product_data_engine.filters import ProductFiltersBuilder
	from webshop.webshop.product_data_engine.query import ProductQuery
	from webshop.webshop.doctype.override_doctype.item_group import get_child_groups_for_website

	filters = {}
	
	# If item_group is None or empty string, treat is as None
	if not item_group:
		item_group = None

	filter_engine = ProductFiltersBuilder()
	filters["field_filters"] = filter_engine.get_field_filters()
	filters["attribute_filters"] = filter_engine.get_attribute_filters()

	sub_categories = []
	if item_group:
		sub_categories = get_child_groups_for_website(item_group, immediate=True)

	return {
		"filters": filters,
		"sub_categories": sub_categories
	}


@frappe.whitelist(allow_guest=True)
def get_stock(item_code, warehouse=None):
	if "webshop" not in frappe.get_installed_apps():
		return frappe._dict({"in_stock": 0, "stock_qty": 0.0, "is_stock_item": 0})

	from webshop.webshop.utils.product import get_web_item_qty_in_stock
	return get_web_item_qty_in_stock(item_code, "website_warehouse", warehouse)


@frappe.whitelist(allow_guest=True)
def get_products_with_stock(query_args=None):
	if "webshop" not in frappe.get_installed_apps():
		return {"message": {"items": []}}

	from webshop.webshop.api import get_product_filter_data
	from webshop.webshop.utils.product import get_web_item_qty_in_stock
	
	data = get_product_filter_data(query_args)
	
	if not data or not data.get("items"):
		return data

	for item in data["items"]:
		stock_data = get_web_item_qty_in_stock(item.item_code, "website_warehouse")
		if stock_data:
			item.update(stock_data)

	return data