
import frappe
import json
from frappe_utils.api import get_product_info

def execute():
    # Fetch a random website item to test
    items = frappe.get_all("Website Item", limit=1)
    if not items:
        print("No Website Items found.")
        return

    item_code = frappe.db.get_value("Website Item", items[0].name, "item_code")
    print(f"Testing get_product_info with Item Code: {item_code}")

    data = get_product_info(item_code)
    
    print("--- API Response Keys ---")
    print(data.keys())
    print("\n--- Key Values ---")
    for k in ["web_item_name", "item_name", "web_long_description", "stock_qty", "stock_status"]:
        print(f"{k}: {data.get(k)}")

    if data.get("item_code") == item_code:
        print("\nSUCCESS: Item code matches.")
    else:
        print("\nFAILURE: Item code mismatch or empty response.")
