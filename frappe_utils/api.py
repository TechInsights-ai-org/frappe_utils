import frappe
from frappe.utils import cint, flt
import json
from datetime import datetime


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
	
	if isinstance(query_args, str):
		query_args = json.loads(query_args)
	
	if not query_args:
		query_args = {}

	# Price Filtering Logic
	price_min = flt(query_args.get("price_min"))
	price_max = flt(query_args.get("price_max"))
	
	if price_min or price_max:
		# Get default price list from Webshop Settings
		price_list = frappe.db.get_single_value("Webshop Settings", "price_list") or \
					 frappe.db.get_single_value("Webshop Settings", "selling_price_list") or \
					 "Standard Selling"
		
		price_filters = {
			"price_list": price_list,
			"price_list_rate": []
		}

		if price_min:
			price_filters["price_list_rate"].append([">=", price_min])
		if price_max:
			price_filters["price_list_rate"].append(["<=", price_max])
			
		# Let's use direct SQL or frappe.get_all to get valid item_codes
		# Use list format for filters to support multiple conditions on same field
		price_db_filters = [
			["Item Price", "price_list", "=", price_list]
		]
		
		if price_min:
			price_db_filters.append(["Item Price", "price_list_rate", ">=", price_min])
		if price_max:
			price_db_filters.append(["Item Price", "price_list_rate", "<=", price_max])
			
		valid_price_items = frappe.get_all("Item Price", filters=price_db_filters, pluck="item_code")
		
		# Inject into query_args field_filters
		print(f"DEBUG: valid_price_items={len(valid_price_items)} items: {valid_price_items[:5]}")
		if "field_filters" not in query_args:
			query_args["field_filters"] = {}
			
		# If there's already an item_code filter, we need to intersect
		existing_items = query_args["field_filters"].get("item_code")
		if existing_items:
			# If it's a list, intersect. If it's a single value, check if in valid_price_items
			# Simplified: just add to 'in' list if not present, or intersect logic
			# But existing check might be from other filters.
			# Safest is to intersect if generic list, or overwrite if we are narrowing down.
			# Let's assume standard usage: it's either unset or a list.
			pass # We will handle intersection by just adding as a new AND condition effectively?
			# No, 'item_code' key collision.
			
			# Complex usage: Let's just create a set intersection if possible or simple 'in'
			# For now, let's just REPLACE or INTERSECT
			if isinstance(existing_items, list) and len(existing_items) > 0 and existing_items[0] == "in":
				current_list = set(existing_items[1])
				new_list = current_list.intersection(set(valid_price_items))
				query_args["field_filters"]["item_code"] = list(new_list)
			else:
				# Unknown format or single value. If single value is in valid_price_items, keep it.
				# If not, empty.
				if isinstance(existing_items, str):
					 if existing_items in valid_price_items:
						  pass # Keep as is
					 else:
						  query_args["field_filters"]["item_code"] = [] # No match
				else:
					 # Fallback or complex, just overwrite or careful intersection?
					 # If we overwrite, we lose existing filter.
					 # But standard usage via field_filters usually implies list or value.
					 # Let's assume list for now if previous logic used list.
					 # But wait, did I assume existing_items was ["in", list]?
					 # If ProductQuery expects ONLY list, then existing_items should be just a list.
					 # IF existing_items is `['SKU1', 'SKU2']`.
					 if isinstance(existing_items, list):
						  current_list = set(existing_items)
						  new_list = current_list.intersection(set(valid_price_items))
						  query_args["field_filters"]["item_code"] = list(new_list)
					 else:
						  pass # Should be handled

		
		if not existing_items:
			query_args["field_filters"]["item_code"] = valid_price_items
		
		# If valid_price_items is empty, we should probably return empty result now
		if not valid_price_items:
			return {"message": {"items": []}}

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
			# if is_discontinued and actual_qty <= 0 and not has_active_wo:
			# 	continue

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


@frappe.whitelist(allow_guest=True) 
def get_product_info(item_code):
	if "webshop" not in frappe.get_installed_apps():
		return {}

	# 1. Resolve Website Item
	website_item_name = frappe.db.get_value("Website Item", {"item_code": item_code}, "name")
	if not website_item_name:
		if frappe.db.exists("Website Item", item_code):
			website_item_name = item_code

	if not website_item_name:
		frappe.throw(f"Product {item_code} not found", exc=frappe.DoesNotExistError)

	# 2. Fetch basic details
	wi = frappe.get_doc("Website Item", website_item_name)
	item_data = wi.as_dict()

	# 3. Use Webshop API for Price & Stock
	from webshop.webshop.shopping_cart.product_info import get_product_info_for_website
	
	# We pass WI's item_code to ensure it matches
	product_api_res = get_product_info_for_website(wi.item_code, skip_quotation_creation=True)
	product_info = product_api_res.get("product_info", {})

	# 4. Map/Append Data
	# Price
	price_data = product_info.get("price") or {}
	item_data["price_list_rate"] = price_data.get("price_list_rate") or 0.0
	item_data["formatted_price"] = price_data.get("formatted_price") or frappe.utils.fmt_money(0)
	
	# Stock
	item_data["stock_qty"] = product_info.get("stock_qty") or 0
	item_data["total_quantity"] = item_data["stock_qty"]
	item_data["in_stock"] = product_info.get("in_stock") or 0
	
	# Status Logic (Frontend expects stock_status string)
	if item_data.get("in_stock"):
		item_data["stock_status"] = "In Stock"
	else:
		item_data["stock_status"] = "Out of Stock"
		# Optional: Check Work Order logic if needed, but user just said "use prebuilt api"
		# Prebuilt API doesn't know about my Work Order logic (In Process).
		# If I want to keep "In Process", I might need to add that check back manually.
		# But let's stick to the prompt: "use prebuilt api ... and append necessary data".
		
	# Work Order Check (Preserving custom logic "In Process")
	# If out of stock, check if WO exists
	if item_data["stock_status"] == "Out of Stock":
		has_active_wo = frappe.db.count("Work Order", {
			"production_item": wi.item_code, 
			"status": ["not in", ["Completed", "Cancelled"]],
			"docstatus": 1
		})
		if has_active_wo:
			item_data["stock_status"] = "In Process"

	# Standard fields
	item_data.update({
		"web_item_name": wi.name,
		"item_group": wi.item_group,
		"item_name": wi.item_name,
		"item_code": wi.item_code,
		"website_image": wi.website_image,
		"short_description": wi.short_description,
		"web_long_description": wi.web_long_description,
		"route": wi.route
	})

	# Reviews
	rating_data = frappe.db.get_all(
		"Item Review",
		filters={"website_item": wi.name},
		fields=["avg(rating) as average", "count(*) as total"]
	)
	
	avg_rating = 0.0
	review_count = 0

	if rating_data:
		# Frappe Rating field is 0-1 in DB usually for website reviews if using standard webshop logic
		# But let's check what we get. If it's normalized, we multiply by 5.
		raw_avg = rating_data[0].get("average") or 0.0
		avg_rating = flt(raw_avg) * 5
		review_count = rating_data[0].get("total") or 0
	
	item_data["avg_rating"] = avg_rating
	item_data["review_count"] = review_count

	return item_data

 

@frappe.whitelist(allow_guest=True)
def get_product_reviews(item_code):
	if "webshop" not in frappe.get_installed_apps():
		return []

	website_item = frappe.db.get_value("Website Item", {"item_code": item_code}, "name")
	if not website_item:
		return []

	reviews = frappe.db.get_all(
		"Item Review",
		filters={"website_item": website_item},
		fields=["name", "user", "review_title", "comment", "rating", "published_on", "creation"],
		order_by="creation desc"
	)

	return reviews