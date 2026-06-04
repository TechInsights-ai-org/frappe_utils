import frappe
from frappe_utils.api import _get_customer_from_user


@frappe.whitelist()
def get_invoices(from_date=None, to_date=None, page_length=20, start=0, outstanding_only=0):
	"""Return the current customer's Sales Invoices."""
	customer = _get_customer_from_user()
	filters = [
		["customer", "=", customer],
		["docstatus", "=", 1],
	]
	if from_date:
		filters.append(["posting_date", ">=", from_date])
	if to_date:
		filters.append(["posting_date", "<=", to_date])
	if int(outstanding_only):
		filters.append(["outstanding_amount", ">", 0])

	return frappe.get_all(
		"Sales Invoice",
		filters=filters,
		fields=["name", "posting_date", "due_date", "grand_total", "outstanding_amount", "status", "currency"],
		order_by="posting_date desc",
		limit=int(page_length),
		start=int(start),
	)


@frappe.whitelist()
def get_invoice_count(outstanding_only=0):
	"""Return the count of the current customer's Sales Invoices."""
	customer = _get_customer_from_user()
	filters = {"customer": customer, "docstatus": 1}
	if int(outstanding_only):
		filters["outstanding_amount"] = [">", 0]
	return frappe.db.count("Sales Invoice", filters)


@frappe.whitelist()
def get_order_count():
	"""Return the count of non-cancelled Sales Orders for the current customer."""
	customer = _get_customer_from_user()
	return frappe.db.count(
		"Sales Order",
		{"customer": customer, "docstatus": ["!=", 2], "status": ["!=", "Cancelled"]},
	)
