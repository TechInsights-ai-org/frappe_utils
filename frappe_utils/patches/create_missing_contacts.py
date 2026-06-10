import frappe


def execute():
	"""
	Create Contact records for Website Users who have a Customer (via portal_users)
	but no Contact. Without a Contact, _get_customer_from_user() throws for every
	cart, checkout, and address API call.
	"""
	users = frappe.db.sql("""
		SELECT u.name AS user, u.first_name, u.last_name, u.email, u.mobile_no,
		       pu.parent AS customer
		FROM `tabUser` u
		JOIN `tabPortal User` pu ON pu.user = u.name
		WHERE u.user_type = 'Website User'
		  AND u.name != 'Guest'
		  AND NOT EXISTS (
		      SELECT 1 FROM `tabContact` c WHERE c.user = u.name
		  )
	""", as_dict=True)

	for row in users:
		customer_name = frappe.db.get_value(
			"Dynamic Link",
			{"link_doctype": "Customer", "link_name": row.customer, "parenttype": "Contact"},
			"parent"
		)
		# Skip if a Contact already links to this customer under a different user field
		if customer_name:
			frappe.db.set_value("Contact", customer_name, "user", row.user)
			continue

		contact = frappe.new_doc("Contact")
		contact.first_name = row.first_name or row.user.split("@")[0]
		contact.last_name = row.last_name or ""
		contact.user = row.user
		contact.company_name = frappe.db.get_value("Customer", row.customer, "customer_name") or ""

		contact.append("email_ids", {"email_id": row.email or row.user, "is_primary": 1})

		if row.mobile_no:
			contact.append("phone_nos", {"phone": row.mobile_no, "is_primary_mobile_no": 1})

		contact.append("links", {"link_doctype": "Customer", "link_name": row.customer})

		contact.save(ignore_permissions=True)

	if users:
		frappe.db.commit()
