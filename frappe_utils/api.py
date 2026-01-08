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
def get_products_with_stock(query_args=None,home_page=0):
	if "webshop" not in frappe.get_installed_apps():
		return {"message": {"items": []}}

	from webshop.webshop.api import get_product_filter_data
	from webshop.webshop.utils.product import get_web_item_qty_in_stock
	
	data = get_product_filter_data(query_args)
	
	if not data or not data.get("items"):
		return data

	item_codes = [item.item_code for item in data["items"]]
	
	# Batch query for active Work Orders
	# "active" = In Process (as per previous logic) or broad check if we want to match utils.py exactly
	# For API performance, we stick to the Requirement: "In Process" status or similar. 
	# Implementation Plan said: "API will always return items that have an active Work Order... even if discontinued."
	# User cleared "active" = not Completed/Cancelled.
	# So I should update the WO filter to match `utils.py` logic: status NOT IN ("Completed", "Cancelled")
	
	items_in_process = set()
	discontinued_map = {}
	is_home_page = int(home_page)

	if item_codes:
		# Work Orders
		work_orders = frappe.db.get_all(
			"Work Order",
			filters={
				"production_item": ["in", item_codes],
				"status": ["not in", ["Completed", "Cancelled"]], # Exclude inactive
				"docstatus": ["in", [1, 0]] 
			},
			fields=["production_item", "status"],
			distinct=True
		)
		items_in_process = {d.production_item for d in work_orders}

		# Discontinued Status & Custom Fields
		fields = ["item_code", "discontinued"]
		if is_home_page:
			fields.extend(["custom_section", "custom_section_order"])

		# Fetch from Website Item. Assuming 1-to-1 mapping or we take the first one found.
		# Note: get_product_filter_data items usually come from Website Item, so item_code is the link.
		wi_data = frappe.db.get_all(
			"Website Item",
			filters={"item_code": ["in", item_codes]},
			fields=fields
		)
		for d in wi_data:
			discontinued_map[d.item_code] = d

	valid_items = []
	for item in data["items"]:
		stock_data = get_web_item_qty_in_stock(item.item_code, "website_warehouse")
		if stock_data:
			item.update(stock_data)

			# Determine Stock Status
			wi_item_data = discontinued_map.get(item.item_code, {})
			
			actual_qty = stock_data.get("stock_qty", 0.0)
			is_stock_item = stock_data.get("is_stock_item", 0)
			is_discontinued = wi_item_data.get("discontinued", 0)
			has_active_wo = item.item_code in items_in_process

			# API Guard: Visibility Check
			# Logic: If Discontinued AND Stock <= 0 AND No Active WO -> Hide
			if is_discontinued and actual_qty <= 0 and not has_active_wo:
				continue

			stock_status = "Out of Stock"
			
			if not is_stock_item:
				stock_status = "In Stock"
			elif actual_qty > 0:
				stock_status = "In Stock"
			elif has_active_wo:
				stock_status = "In Process"
			
			if is_home_page:
				item["custom_section"] = wi_item_data.get("custom_section")
				item["custom_section_order"] = wi_item_data.get("custom_section_order")

			item["total_quantity"] = actual_qty
			item["stock_status"] = stock_status
			valid_items.append(item)

	data["items"] = valid_items
	return data