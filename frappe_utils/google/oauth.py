import json
import frappe
from google.oauth2.credentials import Credentials
from googleapiclient.discovery import build
from requests import post
from frappe.utils import get_request_site_address

CALLBACK_METHOD = "/api/method/frappe_utils.google.doctype.google_drive_credentials.google_drive_credentials.callback"
_SCOPES = {
    "drive": "https://www.googleapis.com/auth/drive",
}
_SERVICES = {
    "drive": ("drive", "v3"),
}

class GoogleOAuth:
    OAUTH_URL = "https://oauth2.googleapis.com/token"

    def __init__(self, domain: str, client_id: str, client_secret: str, validate: bool = True):
        self.domain = domain.lower()
        self.client_id = client_id
        self.client_secret = client_secret
        self.scopes = _SCOPES.get(self.domain)
        if validate:
            self.validate_credentials()

    def validate_credentials(self):
        if not self.client_id or not self.client_secret:
            raise ValueError("Client ID and Client Secret must be provided.")

    def authorize(self, oauth_code: str) -> dict:
        data = {
            "code": oauth_code,
            "client_id": self.client_id,
            "client_secret": self.client_secret,
            "grant_type": "authorization_code",
            "scope": self.scopes,
            "redirect_uri": get_request_site_address(True) + CALLBACK_METHOD,
        }
        response = post(self.OAUTH_URL, data=data).json()
        if "error" in response:
            raise Exception(f"Google OAuth Error: {response.get('error_description', 'Unknown error')}")
        return response

    def refresh_access_token(self, refresh_token: str) -> dict:
        data = {
            "client_id": self.client_id,
            "client_secret": self.client_secret,
            "refresh_token": refresh_token,
            "grant_type": "refresh_token",
            "scope": self.scopes,
        }
        response = post(self.OAUTH_URL, data=data).json()
        if "error" in response:
            raise Exception(f"Google OAuth Refresh Error: {response.get('error_description', 'Unknown error')}")
        return response

    def get_authentication_url(self, state: dict) -> dict:
        state.update({"domain": self.domain})
        state = json.dumps(state)
        callback_url = get_request_site_address(True) + CALLBACK_METHOD
        auth_url = (
            f"https://accounts.google.com/o/oauth2/v2/auth?"
            f"access_type=offline&response_type=code&prompt=consent&include_granted_scopes=true&"
            f"client_id={self.client_id}&scope={self.scopes}&redirect_uri={callback_url}&state={state}"
        )
        return {"url": auth_url}

    def get_google_service_object(self, access_token: str, refresh_token: str):
        credentials = Credentials(
            token=access_token,
            refresh_token=refresh_token,
            token_uri=self.OAUTH_URL,
            client_id=self.client_id,
            client_secret=self.client_secret,
            scopes=[self.scopes],
        )
        return build(
            serviceName=_SERVICES[self.domain][0],
            version=_SERVICES[self.domain][1],
            credentials=credentials,
            static_discovery=False,
        )
