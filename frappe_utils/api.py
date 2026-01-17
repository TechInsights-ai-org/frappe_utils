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

	# Parse query_args if string
	if isinstance(query_args, str):
		try:
			args_dict = json.loads(query_args)
		except ValueError:
			args_dict = {}
	else:
		args_dict = query_args or {}

	# Extract price filters
	price_min = flt(args_dict.get("price_min")) if args_dict.get("price_min") else None
	price_max = flt(args_dict.get("price_max")) if args_dict.get("price_max") else None

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

			# Price Filtering
			# We use price_list_rate as the base price.
			# In different contexts "website_item_price" or "formatted_mrp" might be used,
			# but price_list_rate is the standard raw float value for sorting/filtering.
			item_price = item.get("price_list_rate") or 0.0
			if price_min is not None and item_price < price_min:
				continue
			if price_max is not None and item_price > price_max:
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


@frappe.whitelist(allow_guest=True)
def get_product_info(item_code):
	"""
	Get detailed info for a single product.
	'item_code' argument here is expected to be the Website Item Name (primary key).
	"""
	if "webshop" not in frappe.get_installed_apps():
		return {}

	from webshop.webshop.utils.product import get_web_item_qty_in_stock

	# Fetch Website Item
	# We lookup by NAME (Primary Key) as per requirement.
	# The argument 'item_code' is treated as the Website Item Name.
	ws_item = frappe.db.get_value("Website Item",
		item_code,
		["name", "web_item_name", "item_name", "item_code", "website_image",
		 "web_long_description", "short_description", "ranking",
		 "on_backorder", "item_group", "route"],
		as_dict=True
	)

	if not ws_item:
		return {}

	# Create a dict with keys compatible with what frontend expects
	item = ws_item
	
	# The actual Item Code for linking to Price, Stock, etc.
	real_item_code = ws_item.item_code

	# Fetch Price
	# Try to get price from Item Price
	# Ideally we use the default price list from Webshop Settings
	price_list = frappe.db.get_single_value("Webshop Settings", "price_list") or "Standard Selling"
	price_args = {"item_code": real_item_code, "price_list": price_list}
	
	price_doc = frappe.db.get_value("Item Price", price_args, ["price_list_rate", "currency"], as_dict=True)
	
	if price_doc:
		item["price_list_rate"] = price_doc.price_list_rate
		item["currency"] = price_doc.currency
	else:
		item["price_list_rate"] = 0.0
		item["currency"] = frappe.db.get_value("Price List", price_list, "currency") or "INR"

	# Fetch Stock
	stock_data = get_web_item_qty_in_stock(real_item_code, "website_warehouse")
	if stock_data:
		item.update(stock_data)

	# Stock Status Logic
	actual_qty = item.get("stock_qty", 0.0)
	is_stock_item = item.get("is_stock_item", 0)

	# Check for active Work Order using real_item_code
	has_active_wo = False
	if frappe.db.exists("Work Order", {
		"production_item": real_item_code,
		"status": ["not in", ["Completed", "Cancelled"]],
		"docstatus": ["in", [1, 0]]
	}):
		has_active_wo = True

	stock_status = "Out of Stock"
	if not is_stock_item:
		stock_status = "In Stock"
	elif actual_qty > 0:
		stock_status = "In Stock"
	elif has_active_wo:
		stock_status = "In Process"

	item["total_quantity"] = actual_qty
	item["stock_status"] = stock_status

	# Fetch Ratings
	# Review Logic: Rating is 0-1 in DB, convert to 0-5
	rating_data = frappe.db.get_all("Item Review",
		filters={"website_item": item_code}, # item_code is the name here as per new logic
		fields=["avg(rating) as avg_rating", "count(name) as total"],
		as_list=False, ignore_permissions=True
	)

	if rating_data:
		db_rating = rating_data[0].get("avg_rating") or 0.0
		item["avg_rating"] = db_rating * 5 # Convert 0-1 to 0-5
		item["review_count"] = rating_data[0].get("total") or 0
	else:
		item["avg_rating"] = 0.0
		item["review_count"] = 0

	# Add discount info if needed (placeholder)
	item["discount_percent"] = 0

	# Check if wished
	item["wished"] = 0
	if frappe.session.user and frappe.session.user != "Guest":
		# Wishlist is stored in "Wishlist" doctype, with "Wishlist Item" as child table
		# The parent of Wishlist Item is the user (name of Wishlist doc is usually the user)
		if frappe.db.exists("Wishlist Item", {"parent": frappe.session.user, "item_code": real_item_code}):
			item["wished"] = 1

	return item

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