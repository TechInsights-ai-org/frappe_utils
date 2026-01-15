import frappe
from frappe_utils.api import get_products_with_stock
@frappe.whitelist()
def create(item_code):
    from webshop.webshop.doctype.wishlist.wishlist import add_to_wishlist
    add_to_wishlist(item_code)
    frappe.db.commit()

@frappe.whitelist()
def remove(item_code):
    from webshop.webshop.doctype.wishlist.wishlist import remove_from_wishlist
    remove_from_wishlist(item_code)
    frappe.db.commit()  


@frappe.whitelist()
def get_wishlist(user, page=1, limit=10):
    """Get paginated wishlist items with stock information for a user."""
    page = int(page)
    limit = int(limit)  
    offset = (page - 1) * limit
    query = """
        SELECT item_code
        FROM `tabWishlist Item`
        WHERE parent = %s
        ORDER BY idx DESC
        LIMIT %s OFFSET %s
    """
    result = frappe.db.sql(query, (user, limit, offset), as_dict=True)
    names = [d.item_code for d in result]
    
    if not names:
        return []
    
    # Pass names as field_filters with 'item_code' field
    data = get_products_with_stock(query_args={"field_filters": {"item_code": names}})
    return data.get("items", [])
