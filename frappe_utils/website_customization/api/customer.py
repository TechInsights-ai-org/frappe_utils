import frappe 


@frappe.whitelist()
def get_customer(email):
    query = """
        SELECT parent from `tabPortal User` where user = %s
    """
    result = frappe.db.sql(query, (email,), as_dict=True)
    if result:
        return result[0]["parent"]
    return None 