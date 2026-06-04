import frappe
from frappe_utils.api import _get_customer_from_user


@frappe.whitelist()
def get_payments(from_date=None, to_date=None, page_length=20, start=0):
	"""Return the current customer's Payment Entries."""
	customer = _get_customer_from_user()
	filters = [
		["party_type", "=", "Customer"],
		["party", "=", customer],
		["docstatus", "=", 1],
	]
	if from_date:
		filters.append(["posting_date", ">=", from_date])
	if to_date:
		filters.append(["posting_date", "<=", to_date])

	return frappe.get_all(
		"Payment Entry",
		filters=filters,
		fields=["name", "posting_date", "paid_amount", "unallocated_amount", "status", "mode_of_payment"],
		order_by="posting_date desc",
		limit=int(page_length),
		start=int(start),
	)
