
import frappe
from frappe_utils.api import get_products_with_stock
import json

def execute():
    # Test Case 1: Filter Price > 100
    print("\n--- Test Case 1: Price > 100 ---")
    query_args = {"price_min": 100}
    try:
        data = get_products_with_stock(query_args=json.dumps(query_args))
        items = data.get("message", {}).get("items", []) if isinstance(data, dict) and "message" in data else data.get("items", [])
        
        print(f"Found {len(items)} items")
        for item in items[:5]:
            print(f"Item: {item.item_code}, Price: {item.price_list_rate}")
            if item.price_list_rate < 100:
                print("FAILURE: Found item with price < 100")
    except Exception as e:
        print(f"Error: {e}")

    # Test Case 2: Filter Price < 500
    print("\n--- Test Case 2: Price < 500 ---")
    query_args = {"price_max": 500}
    try:
        data = get_products_with_stock(query_args=json.dumps(query_args))
        items = data.get("message", {}).get("items", []) if isinstance(data, dict) and "message" in data else data.get("items", [])
        
        print(f"Found {len(items)} items")
        for item in items[:5]:
            print(f"Item: {item.item_code}, Price: {item.price_list_rate}")
            if item.price_list_rate > 500:
                print("FAILURE: Found item with price > 500")
    except Exception as e:
        print(f"Error: {e}")

    # Test Case 3: Price Range 100 - 500
    print("\n--- Test Case 3: Price 100 - 500 ---")
    query_args = {"price_min": 100, "price_max": 500}
    try:
        data = get_products_with_stock(query_args=json.dumps(query_args))
        items = data.get("message", {}).get("items", []) if isinstance(data, dict) and "message" in data else data.get("items", [])
        
        print(f"Found {len(items)} items")
        for item in items[:5]:
            print(f"Item: {item.item_code}, Price: {item.price_list_rate}")
            if item.price_list_rate < 100 or item.price_list_rate > 500:
                 print("FAILURE: Found item outside range")
    except Exception as e:
        print(f"Error: {e}")
