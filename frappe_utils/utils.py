
import frappe

def should_be_published(item_code, stock_qty=0, is_discontinued=0):
	"""
	Determines if an item should be published on the website.
	Rules:
	- Discontinued + Stock=0 + No Active Work Order -> Published=0
	- Otherwise -> Published=1 (or keeps existing state, but logic here determines if it forces hidden)
	
	Returns: True if it CAN be published/visible, False if it must be HIDDEN.
	"""
	if not is_discontinued:
		return True

	if stock_qty > 0:
		return True

	if has_active_work_order(item_code):
		return True

	return False

def has_active_work_order(item_code):
	"""
	Checks if there is an active Work Order for the item.
	Active = Not Completed and Not Cancelled.
	"""
	return frappe.db.exists(
		"Work Order",
		{
			"production_item": item_code,
			"status": ["not in", ["Completed", "Cancelled"]], 
			"docstatus": ["in", [1, 0]],
		}
	)
