
import frappe
from frappe_utils.utils import should_be_published
from webshop.webshop.utils.product import get_web_item_qty_in_stock

def daily_unpublish_job():
	"""
	Scans all Discontinued Website Items.
	- If out of stock and no active WO -> Set published = 0
	- If has stock or active WO -> Set published = 1 (Ensure visible)
	"""
	if "webshop" not in frappe.get_installed_apps():
		return

	items = frappe.get_all(
		"Website Item",
		filters={"discontinued": 1},
		fields=["name", "item_code", "published", "website_warehouse"]
	)

	for item in items:
		stock_data = get_web_item_qty_in_stock(item.item_code, "website_warehouse", item.website_warehouse)
		stock_qty = stock_data.get("stock_qty", 0.0)

		is_visible = should_be_published(item.item_code, stock_qty, is_discontinued=1)

		if not is_visible:
			if item.published:
				frappe.db.set_value("Website Item", item.name, "published", 0)
				frappe.db.commit()
		else:
			if not item.published:
				frappe.db.set_value("Website Item", item.name, "published", 1)
				frappe.db.commit()
