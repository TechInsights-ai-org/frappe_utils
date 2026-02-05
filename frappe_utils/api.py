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
		 "on_backorder", "item_group", "route","slideshow"],
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

	item["website_specifications"] = frappe.db.get_all(
		"Item Website Specification",
		filters={'parent': item_code},
		fields=['idx','label','custom_value']
	)
	slideshow = item.slideshow
	item['slideshow_list'] = []
	if slideshow:
		item['slideshow_list']=frappe.db.get_all(
			"Website Slideshow Item",
			filters={'parent': slideshow},
			fields=['idx', 'image', 'custom_render_video']
		)

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


# ============================================================================
# ERP Integration: Cart -> Quotation -> Sales Order
# ============================================================================

def _ensure_lead_source(source_name):
	"""Ensure Lead Source exists, create if missing."""
	if not frappe.db.exists("Lead Source", source_name):
		doc = frappe.get_doc({
			"doctype": "Lead Source",
			"source_name": source_name
		})
		doc.insert(ignore_permissions=True)
		frappe.db.commit()


def _get_customer_from_user(user=None):
	"""Get Customer linked to the current user via Contact."""
	if not user:
		user = frappe.session.user
	
	if user == "Guest":
		frappe.throw("Please login to sync cart")
	
	# Find Contact linked to this user
	contact = frappe.db.get_value("Contact", {"user": user}, "name")
	if not contact:
		frappe.throw(f"No Contact found for user {user}")
	
	# Get Customer from Dynamic Link in Contact
	customer = frappe.db.get_value(
		"Dynamic Link",
		{"link_doctype": "Customer", "parent": contact, "parenttype": "Contact"},
		"link_name"
	)
	
	if not customer:
		frappe.throw(f"No Customer linked to Contact {contact}")
	
	return customer


@frappe.whitelist()
def sync_cart_to_quotation(items):
	"""
	Sync cart items to a Quotation.
	Creates a new Quotation or updates existing Website-sourced Draft Quotation.
	
	Args:
		items: JSON string or list of cart items with structure:
			[{"item_code": "SKU001", "qty": 2, "rate": 100.0}, ...]
	
	Returns:
		dict: {"quotation": "QTN-00001", "grand_total": 1234.56, ...}
	"""
	# Parse items if string
	if isinstance(items, str):
		items = json.loads(items)
	
	# Ensure Website Lead Source exists
	_ensure_lead_source("Website")
	
	# Get Customer
	customer = _get_customer_from_user()
	
	# Find existing Website-sourced Draft Quotation for this Customer
	existing_quotation = frappe.db.get_value(
		"Quotation",
		{
			"party_name": customer,
			"docstatus": 0,  # Draft
			"source": "Website"
		},
		"name",
		order_by="modified desc"
	)
	
	if existing_quotation:
		# Update existing Quotation
		quotation = frappe.get_doc("Quotation", existing_quotation)
		# Clear existing items
		quotation.items = []
	else:
		# Create new Quotation
		quotation = frappe.get_doc({
			"doctype": "Quotation",
			"party_name": customer,
			"quotation_to": "Customer",
			"source": "Website",
			"order_type": "Sales",
			"transaction_date": frappe.utils.nowdate()
		})
	
	# Add items from cart
	for item in items:
		quotation.append("items", {
			"item_code": item.get("item_code"),
			"qty": item.get("qty", 1),
			"rate": item.get("rate", 0.0),
			"delivery_date": frappe.utils.add_days(frappe.utils.nowdate(), 7)  # Default 7 days
		})
	
	# Save
	if existing_quotation:
		quotation.save(ignore_permissions=True)
	else:
		quotation.insert(ignore_permissions=True)
	
	frappe.db.commit()
	
	return {
		"quotation": quotation.name,
		"grand_total": quotation.grand_total,
		"total_qty": sum([item.qty for item in quotation.items]),
		"message": "Cart synced successfully"
	}


	return addresses

@frappe.whitelist()
def get_cities():
	"""
	Fetch all cities for dropdown.
	"""
	return frappe.get_all("City", fields=["name", "city_name", "state", "country"])

@frappe.whitelist()
def get_customer_addresses():
	"""
	Fetch addresses linked to the current user's customer.
	"""
	customer = _get_customer_from_user()
	
	addresses = frappe.get_all(
		"Address",
		filters={
			"is_your_company_address": 0
		},
		fields=["name", "address_title", "address_line1", "address_line2", "city", "state", "pincode", "country", "phone", "email_id", "is_primary_address", "is_shipping_address"],
		or_filters={
			"name": ["in", [d.parent for d in frappe.get_all("Dynamic Link", filters={"link_doctype": "Customer", "link_name": customer, "parenttype": "Address"}, fields=["parent"])]]
		}
	)
	return addresses

@frappe.whitelist()
def create_customer_address(address_data):
	"""
	Create a new address for the current customer.
	Args:
		address_data (dict/json): Address fields
	"""
	if isinstance(address_data, str):
		address_data = frappe.parse_json(address_data)
		
	customer = _get_customer_from_user()
	
	doc = frappe.new_doc("Address")
	doc.update(address_data)
	doc.append("links", {
		"link_doctype": "Customer",
		"link_name": customer
	})
	doc.insert(ignore_permissions=True)
	
	return doc.name

@frappe.whitelist()
def update_customer_address(address_name, address_data):
	"""
	Update an existing address.
	Args:
		address_name (str): Name of address to update
		address_data (dict/json): Updated fields
	"""
	if isinstance(address_data, str):
		address_data = frappe.parse_json(address_data)
		
	# Verify ownership (via link)
	customer = _get_customer_from_user()
	if not frappe.db.exists("Dynamic Link", {"parent": address_name, "link_doctype": "Customer", "link_name": customer}):
		frappe.throw("You do not have permission to update this address")
		
	doc = frappe.get_doc("Address", address_name)
	doc.update(address_data)
	doc.save(ignore_permissions=True)
	return doc.name

@frappe.whitelist()
def delete_customer_address(address_name):
	"""
	Delete an address (if allowed).
	"""
	# Verify ownership
	customer = _get_customer_from_user()
	if not frappe.db.exists("Dynamic Link", {"parent": address_name, "link_doctype": "Customer", "link_name": customer}):
		frappe.throw("You do not have permission to delete this address")
		
	frappe.delete_doc("Address", address_name, ignore_permissions=True)
	return "Deleted"

@frappe.whitelist()
def get_current_quotation():
	"""
	Get the current Website-sourced Draft Quotation for the logged-in user.
	
	Returns:
		dict: Quotation details or None if no quotation exists
	"""
	try:
		# Get Customer
		customer = _get_customer_from_user()
		
		# Find existing Website-sourced Draft Quotation
		quotation_name = frappe.db.get_value(
			"Quotation",
			{
				"party_name": customer,
				"docstatus": 0,  # Draft
				"source": "Website"
			},
			"name",
			order_by="modified desc"
		)
		
		if not quotation_name:
			return None
		
		# Get full quotation details
		quotation = frappe.get_doc("Quotation", quotation_name)
		
		return {
			"quotation": quotation.name,
			"grand_total": quotation.grand_total,
			"net_total": quotation.net_total,
			"total_qty": sum([item.qty for item in quotation.items]),
			"created": quotation.creation,
			"modified": quotation.modified,
			"items": [{
				"item_code": item.item_code,
				"item_name": item.item_name,
				"qty": item.qty,
				"rate": item.rate,
				"amount": item.amount
			} for item in quotation.items]
		}
	except Exception as e:
		# Guest users or users without customer will fail silently
		return None



@frappe.whitelist()
@frappe.whitelist()
def place_order(quotation_name, address_name=None):
	"""
	Convert a Website-sourced Quotation to a Sales Order.
	Entire operation is atomic - both Quotation and Sales Order are committed together.
	
	Args:
		quotation_name: Name of the Quotation to convert
		address_name: Optional name of the Address to link
	
	Returns:
		dict: {"sales_order": "SO-00001", "message": "Order placed successfully"}
	"""
	# Get Quotation
	quotation = frappe.get_doc("Quotation", quotation_name)
	
	# Validate source
	if quotation.source != "Website":
		frappe.throw("Only Website quotations can be converted via this API")
	
	# Validate ownership
	customer = _get_customer_from_user()
	if quotation.party_name != customer:
		frappe.throw("You can only place orders for your own quotations")
	
	# Validate status
	if quotation.docstatus != 0:
		frappe.throw("Quotation must be in Draft status")
	
	# Single transaction: Submit Quotation + Create Sales Order
	try:
		# Step 1: Submit the Quotation (no commit yet)
		quotation.submit()
		
		# Step 2: Create Sales Order using mapper
		from frappe.model.mapper import get_mapped_doc
		
		def set_missing_values(source, target):
			target.source = "Website"
			target.delivery_date = frappe.utils.nowdate()
			target.customer = source.party_name  # Explicitly set customer
			
			if address_name:
				target.customer_address = address_name
				target.shipping_address_name = address_name
			
			# Auto-assign Warehouse with highest stock
			import erpnext.stock.dashboard.item_dashboard as item_dashboard
			
			for item in target.items:
				if not item.warehouse:
					try:
						# Get warehouse data using ERPNext's dashboard utility
						warehouse_data = item_dashboard.get_data(item_code=item.item_code)
						if warehouse_data:
							# Sort by actual_qty descending
							sorted_data = sorted(warehouse_data, key=lambda x: x.get("actual_qty", 0), reverse=True)
							if sorted_data:
								item.warehouse = sorted_data[0]["warehouse"]
					except Exception:
						pass
				
				# Fallback 1: First available non-group Warehouse
				if not item.warehouse:
					item.warehouse = frappe.db.get_value("Warehouse", {"is_group": 0}, "name")
				
				# Fallback 2: Hardcoded fallback (common in ERPNext)
				if not item.warehouse:
					item.warehouse = "Stores"
			
			target.run_method("set_missing_values")
			target.run_method("calculate_taxes_and_totals")
		
		sales_order = get_mapped_doc(
			"Quotation",
			quotation_name,
			{
				"Quotation": {
					"doctype": "Sales Order",
					"validation": {
						"docstatus": ["=", 1]  # Quotation is submitted
					}
				},
				"Quotation Item": {
					"doctype": "Sales Order Item",
					"field_map": {
						"parent": "prevdoc_docname",
						"parenttype": "prevdoc_doctype"
					}
				}
			},
			target_doc=None,
			postprocess=set_missing_values
		)
		
		# Step 3: Save Sales Order (Draft state)
		sales_order.insert(ignore_permissions=True)
		
		# Step 4: Create Sales Invoice (Draft state)
		from frappe.model.mapper import get_mapped_doc
		
		def set_invoice_missing_values(source, target):
			target.update_stock = 1
			if address_name:
				target.customer_address = address_name
				target.shipping_address_name = address_name
			target.run_method("set_missing_values")
			target.run_method("calculate_taxes_and_totals")

		sales_invoice = get_mapped_doc(
			"Sales Order",
			sales_order.name,
			{
				"Sales Order": {
					"doctype": "Sales Invoice",
					"validation": {
						"docstatus": ["=", 0]  # Allow mapping from Draft SO
					}
				},
				"Sales Order Item": {
					"doctype": "Sales Invoice Item",
					"field_map": {
						"parent": "sales_order",
					}
				}
			},
			target_doc=None,
			postprocess=set_invoice_missing_values
		)
		
		sales_invoice.insert(ignore_permissions=True)
		
		# Step 5: Commit everything together (atomic)
		frappe.db.commit()
		
		return {
			"sales_order": sales_order.name,
			"sales_invoice": sales_invoice.name,
			"grand_total": sales_order.grand_total,
			"message": "Order placed successfully"
		}
		
	except Exception as e:
		# Rollback everything - Quotation stays in Draft
		frappe.db.rollback()
		frappe.throw(f"Failed to place order: {str(e)}")