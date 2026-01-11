import frappe
from frappe import _

@frappe.whitelist(allow_guest=True)
def register(businessName, contactName, email, phone, password, gst=None, acceptTerms=None):
	"""
	Registers a new user and creates/links a Customer.
	Payload matches frontend: businessName, gst, contactName, email, phone, password.
	"""
	if frappe.db.exists("User", email):
		return {"status": "error", "message": _("User with this email already exists")}

	try:
		# 1. Create User
		user = frappe.new_doc("User")
		user.email = email
		
		# Split Contact Name
		if contactName:
			if " " in contactName:
				parts = contactName.strip().split(" ", 1)
				user.first_name = parts[0]
				user.last_name = parts[1] if len(parts) > 1 else ""
			else:
				user.first_name = contactName.strip()
				user.last_name = ""
		
		user.enabled = 1
		user.send_welcome_email = 0
		user.new_password = password
		user.mobile_no = phone
		user.user_type = "Website User"
		
		user.save(ignore_permissions=True)
		
		# Add Customer Role
		if frappe.db.exists("Role", "Customer"):
			user.add_roles("Customer")

		# 2. Link to Customer
		customer_name = frappe.db.get_value("Customer", {"email_id": email}, "name")
		
		if customer_name:
			customer = frappe.get_doc("Customer", customer_name)
		else:
			customer = frappe.new_doc("Customer")
			customer.customer_name = businessName
			customer.customer_type = "Company"
			customer.tax_id = gst
			customer.email_id = email
			customer.mobile_no = phone
			
			customer.customer_group = frappe.db.get_single_value("Selling Settings", "customer_group") or "All Customer Groups"
				
			if not customer.territory:
				customer.territory = frappe.db.get_single_value("Selling Settings", "territory") or "All Territories"
			
			customer.save(ignore_permissions=True)
		
		# Link User in Portal Users
		user_linked = False
		for pu in customer.portal_users:
			if pu.user == user.name:
				user_linked = True
				break
		
		if not user_linked:
			customer.append("portal_users", {
				"user": user.name
			})
			customer.save(ignore_permissions=True)

		frappe.db.commit()
		
		return {
			"status": "success", 
			"message": _("Registration successful"),
			"user": user.name,
			"customer": customer.name
		}

	except Exception as e:
		frappe.log_error(f"Registration Error: {str(e)}")
		return {"status": "error", "message": _("Registration failed. Please try again or contact support.")}
