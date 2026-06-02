import frappe


@frappe.whitelist()
def get_customer(email):
	result = frappe.get_list(
		"Portal User",
		filters={"user": email},
		fields=["parent"],
		limit=1
	)
	if result:
		return result[0].parent
	return None
