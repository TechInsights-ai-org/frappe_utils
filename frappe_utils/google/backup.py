import os
from datetime import datetime
import frappe
from frappe.integrations.offsite_backup_utils import get_latest_backup_file, send_email, validate_file_size
from frappe.utils.backups import new_backup
from frappe.utils import now_datetime, get_backups_path, get_bench_path
from apiclient.http import MediaFileUpload
from googleapiclient.errors import HttpError
from frappe_utils.google.oauth import GoogleOAuth

def get_absolute_path(filename):
	"""Return absolute path for a backup file"""
	file_path = os.path.join(get_backups_path()[2:], os.path.basename(filename))
	return f"{get_bench_path()}/sites/{file_path}"

@frappe.whitelist()
def enqueue_backup(account):
	try:
		upload_backup_for_account(account.name)
	except Exception as e:
		frappe.log_error(title=f"[Google Drive Backup Failed] {account.name}", message=frappe.get_traceback())
		if account.send_email_notification:
			send_email(False, "Google Drive", "Google Drive Credentials", account.notification_mail, error_status=e)


@frappe.whitelist()
def upload_all_enabled_google_drive_backups(accounts:list = []):
	"""Iterate through all enabled Google Drive accounts and upload backups"""
	if not accounts:
		accounts = frappe.get_all(
			"Google Drive Credentials",
			filters={"enable_backup": 1},
			fields=["name",'send_email_notification','email']
		)

	for account in accounts:
		frappe.enqueue(
			method="frappe_utils.google.backup.enqueue_backup",
			account=account,
			queue="long",
			timeout=3600,
			job_name=f'Backup to {account.name}-{account.email}'
		)


def upload_backup_for_account(docname):
	"""Upload latest or newly created backup to a specific Google account"""
	doc = frappe.get_doc("Google Drive Credentials", docname)

	if not doc.refresh_token:
		frappe.throw(f"Refresh token missing for {doc.email}")

	# Step 1: Initialize OAuth
	oauth = GoogleOAuth("drive", client_id=doc.get_password('client_id'), client_secret=doc.get_password('client_secret'))
	tokens = oauth.refresh_access_token(doc.get_password("refresh_token"))
	service = oauth.get_google_service_object(tokens["access_token"], doc.get_password("refresh_token"))

	# Step 2: Ensure main backup folder exists
	if not doc.backup_folder_id:
		main_folder_id = create_or_find_folder(service, doc.backup_folder_name)
		frappe.db.set_value(doc.doctype, doc.name, "backup_folder_id", main_folder_id)
		doc.reload()

	# Step 3: Create date-based subfolder
	date_folder_id = create_date_subfolder(service, doc.backup_folder_id)

	# Step 4: Validate and create/get backup
	validate_file_size()
	if getattr(frappe.flags, "create_new_backup", False):
		backup = new_backup()
		backup_files = [backup.backup_path_db, backup.backup_path_conf]
		if doc.file_backup:  # same as frappe default
			backup_files.append(backup.backup_path_files)
			backup_files.append(backup.backup_path_private_files)
	else:
		backup_files = get_latest_backup_file(with_files=doc.file_backup)

	# Step 5: Upload files
	for file_path in backup_files:
		if not file_path:
			continue
		media = MediaFileUpload(get_absolute_path(file_path), mimetype="application/gzip", resumable=True)
		metadata = {"name": os.path.basename(file_path), "parents": [date_folder_id]}
		try:
			service.files().create(body=metadata, media_body=media, fields="id").execute()
		except HttpError as e:
			frappe.log_error(title="[Google Drive Upload Error]", message=str(e))

	# Step 6: Update timestamp and notify
	frappe.db.set_value(doc.doctype, doc.name, "last_backup_on", now_datetime())
	if doc.send_email_notification == 1:
		send_email(True, "Google Drive", "Google Drive Credentials", doc.notification_mail)


def create_or_find_folder(service, folder_name):
	"""Check if folder exists; create if not"""
	query = f"name='{folder_name}' and mimeType='application/vnd.google-apps.folder' and trashed=false"
	resp = service.files().list(q=query, spaces='drive', fields='files(id, name)').execute()
	folders = resp.get('files', [])
	if folders:
		return folders[0]['id']

	folder_metadata = {'name': folder_name, 'mimeType': 'application/vnd.google-apps.folder'}
	folder = service.files().create(body=folder_metadata, fields='id').execute()
	return folder.get('id')


def create_date_subfolder(service, parent_folder_id):
	"""Create a folder for today's date under the main backup folder"""
	now_str = now_datetime().strftime("%Y-%m-%d_%H-%M-%S")
	metadata = {
		'name': now_str,
		'mimeType': 'application/vnd.google-apps.folder',
		'parents': [parent_folder_id]
	}
	folder = service.files().create(body=metadata, fields='id').execute()
	return folder['id']
