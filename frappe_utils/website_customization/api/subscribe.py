import frappe 

@frappe.whitelist(allow_guest=True)
def email(email):
    website_customization_settings = frappe.get_doc("Website Customization Settings")
    if website_customization_settings.mail_enabled == 0:
        return {"message": "Email Subscription is not enabled at the moment", "status": "error"}
        
    email_group = website_customization_settings.email_group_name 
    if not email_group:
        frappe.log_error(title="Website Customization Settings", message="Email Group is not set")
        return {"message": "Email Service temporarily unavaiable", "status": "error"}

    email_member = frappe.db.get_value("Email Group Member", {"email_group": email_group, "email": email,"unsubscribed": 0})
    if email_member:
        return {"message": "You are already subscribed to our newsletter", "status": "error"}

    try:
        doc = frappe.new_doc("Email Group Member")
        doc.email_group = email_group
        doc.email = email
        doc.save(ignore_permissions=True)
        frappe.db.commit()
        return {"message": "You have been successfully subscribed to our newsletter", "status": "success"}
    except Exception as e:
        frappe.log_error(title="Website Customization Settings", message=str(e))
        return {"message": "Email Service temporarily unavaiable", "status": "error"}

