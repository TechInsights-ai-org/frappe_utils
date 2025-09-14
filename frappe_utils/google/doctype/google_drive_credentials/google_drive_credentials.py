# Copyright (c) 2025, TechInsights-AI and contributors
# For license information, please see license.txt
import frappe
from frappe.model.document import Document
import json
from frappe_utils.google.oauth import GoogleOAuth
from hrms.hr.doctype.travel_itinerary.travel_itinerary import TravelItinerary


class GoogleDriveCredentials(Document):
	pass


@frappe.whitelist()
def authorize_access(name, reauthorize: int = 0):
	doc = frappe.get_doc("Google Drive Credentials", name)
	oauth = GoogleOAuth("drive", client_id=doc.get_password('client_id'),
						client_secret=doc.get_password('client_secret'))
	auth_url = oauth.get_authentication_url({"state": name})
	return auth_url



@frappe.whitelist()
def callback(state: str, code: str = None, error: str = None):
	if error:
		frappe.throw(f"Google OAuth error: {error}")
	if not code:
		frappe.throw("No authorization code returned.")
	if isinstance(state, str):
		state = json.loads(state)
	doc = frappe.get_doc("Google Drive Credentials", state["state"])
	oauth = GoogleOAuth("drive", client_id=doc.get_password('client_id'),
						client_secret=doc.get_password('client_secret'))
	token_data = oauth.authorize(code)
	doc = frappe.get_doc("Google Drive Credentials", state["state"])
	doc.refresh_token = token_data["refresh_token"]
	doc.authorization_code = code
	doc.status = 'Authorized'
	doc.save()
	frappe.db.commit()
	frappe.local.response["type"] = "redirect"
	frappe.local.response["location"] = f"/app/Form/Google Drive Credentials/{state['state']}"

