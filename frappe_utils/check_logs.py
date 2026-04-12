import frappe
import json

def get_logs():
    logs = frappe.get_all("Error Log", fields=["name", "method", "error", "creation"], limit=10, order_by="creation desc")
    for log in logs:
        print(f"[{log.creation}] {log.method}: {log.error}")

get_logs()
