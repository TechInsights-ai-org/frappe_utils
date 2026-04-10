# Copyright (c) 2026, TechInsights-AI and contributors
# For license information, please see license.txt

"""Central upload orchestrator.

Handles the decision logic for routing uploads to external storage
or falling back to default Frappe storage. Contains the hook handlers
for `write_file` and `delete_file_data_content`.
"""

import hashlib
import mimetypes
import re
import uuid

import frappe
from frappe import _

from frappe_utils.services.validation import (
	validate_file_size,
	validate_file_type,
	validate_user_permission,
)

# ---------------------------------------------------------------------------
# Settings & Provider Helpers
# ---------------------------------------------------------------------------

_PROVIDER_MAP = {
	"S3": "frappe_utils.storage.s3.S3Storage",
}


def get_storage_settings():
	"""Fetch the Storage Control singleton settings.

	Returns cached settings doc, or None if not configured.
	"""
	try:
		return frappe.get_cached_doc("Storage Control")
	except Exception:
		return None


def is_external_storage_enabled(doctype: str = None, fieldname: str = None) -> bool:
	"""Check if external storage is enabled for the given doctype and fieldname.

	Args:
		doctype: The DocType to check. If None, only checks master toggle.
		fieldname: Optional. Field name to check against explicit exclusion rules.

	Returns:
		True if external storage should be used for this doctype.
	"""
	# Hardcoded exclusions for Candidate Profile (requested by user)
	if doctype == "Candidate Profile" and fieldname in ["qr", "profile_photo"]:
		return False

	settings = get_storage_settings()
	if not settings or not settings.enable_external_storage:
		return False

	# Check explicit field exclusions
	if settings.exclusion_list and doctype and fieldname:
		for rule in settings.exclusion_list:
			if rule.doctype_name == doctype and rule.field_name == fieldname:
				frappe.log_error("Storage Config Check", f"Field explicitly excluded from external storage: {doctype}.{fieldname}")
				return False

	# If no target doctypes specified, apply to all
	if not settings.target_doctypes:
		frappe.log_error("Storage Config Check", "No target doctypes, enabled for all")
		return True

	# Check if this doctype is in the target list
	if doctype:
		target_list = [row.doctype_name for row in settings.target_doctypes]
		is_target = doctype in target_list
		frappe.log_error("Storage Config Check", f"Target DocTypes: {target_list}, Checked: {doctype}, Result: {is_target}")
		return is_target

	return True


def get_storage_provider():
	"""Instantiate and return the configured storage provider.

	Returns:
		An instance of the storage provider class (e.g., S3Storage).

	Raises:
		frappe.ValidationError: If provider is not configured or unknown.
	"""
	settings = get_storage_settings()
	if not settings:
		frappe.throw(_("Storage Control is not configured"))

	provider_class_path = _PROVIDER_MAP.get(settings.storage_provider)
	if not provider_class_path:
		frappe.throw(
			_("Unknown storage provider: {0}").format(settings.storage_provider)
		)

	provider_class = frappe.get_attr(provider_class_path)
	return provider_class(settings)


# ---------------------------------------------------------------------------
# Object Key Generation
# ---------------------------------------------------------------------------

def generate_object_key(doctype: str, docname: str, filename: str) -> str:
	"""Generate a structured storage key for the file.

	Format: <doctype>/<docname>/<short_hash>_<sanitized_filename>

	Args:
		doctype: The DocType the file is attached to.
		docname: The document name.
		filename: Original filename.

	Returns:
		A unique, structured object key string.
	"""
	# Sanitize components for safe storage paths
	safe_doctype = _sanitize_path_component(doctype) if doctype else "unlinked"
	safe_docname = _sanitize_path_component(docname) if docname else "general"
	safe_filename = _sanitize_path_component(filename)

	# Generate a short unique hash to prevent collisions
	unique_hash = hashlib.md5(
		f"{uuid.uuid4().hex}{filename}".encode(), usedforsecurity=False
	).hexdigest()[:8]

	return f"{safe_doctype}/{safe_docname}/{unique_hash}_{safe_filename}"


def _sanitize_path_component(value: str) -> str:
	"""Sanitize a string for use as a path component."""
	# Replace spaces and unsafe chars with underscores, keep alphanumerics, dots, dashes
	return re.sub(r"[^\w.\-]", "_", str(value))


def _extract_object_key_from_url(file_url: str, settings=None) -> str | None:
	"""Extract the object key from an external file URL.

	Args:
		file_url: The full URL of the file.
		settings: Optional Storage Control settings.

	Returns:
		The object key if URL matches external storage, else None.
	"""
	if file_url and "download_secure?key=" in file_url:
		return file_url.split("download_secure?key=")[-1]
		
	if file_url and file_url.startswith("https://s3.private/"):
		return file_url[len("https://s3.private/"):]

	if not settings:
		settings = get_storage_settings()

	if not settings:
		return None

	endpoint = settings.endpoint_url.rstrip("/")
	bucket = settings.bucket_name
	prefix = f"{endpoint}/{bucket}/"

	if file_url and file_url.startswith(prefix):
		return file_url[len(prefix):]

	return None


# ---------------------------------------------------------------------------
# Server Upload (write_file hook)
# ---------------------------------------------------------------------------

def handle_write_file(file_doc) -> dict | None:
	"""Frappe `write_file` hook handler.

	Called by Frappe's File.save_file() when the write_file hook is registered.
	Decides whether to upload to external storage or fall back to filesystem.

	Args:
		file_doc: The Frappe File document being saved.

	Returns:
		dict with file_name and file_url if handled externally, else None
		(which causes Frappe to fall back to save_file_on_filesystem).
	"""
	doctype = file_doc.attached_to_doctype
	docname = file_doc.attached_to_name
	fieldname = file_doc.attached_to_field
	
	frappe.log_error("Storage Hook Triggered", f"handle_write_file called for file={file_doc.file_name}, doctype={doctype}, docname={docname}, fieldname={fieldname}")

	# Check if external storage should handle this upload
	if not is_external_storage_enabled(doctype, fieldname):
		frappe.log_error("Storage Hook Action", f"External storage disabled for {doctype}, using local filesystem")
		return file_doc.save_file_on_filesystem()

	frappe.log_error("Storage Hook Action", f"External storage enabled for {doctype}, initiating S3 upload")
	settings = get_storage_settings()

	# Run validations
	if file_doc._content:
		validate_file_size(len(file_doc._content), settings)
	validate_file_type(file_doc.file_name, settings)

	# Generate object key and upload
	object_key = generate_object_key(doctype, docname, file_doc.file_name)
	content_type = mimetypes.guess_type(file_doc.file_name)[0]

	try:
		storage = get_storage_provider()
		is_private = False # Force all external uploads to be public
		file_doc.is_private = 0
		file_url = storage.upload_file(object_key, file_doc._content, content_type, is_private=is_private)

		# For private files, store a virtual URL containing the object key.
		if is_private:
			from frappe.utils import get_url
			file_url = get_url(f"/api/method/frappe_utils.api.upload.download_secure?key={object_key}")
		file_doc.file_url = file_url

		return {
			"file_name": file_doc.file_name,
			"file_url": file_url,
		}
	except Exception as e:
		frappe.log_error(
			title="External Storage Upload Failed",
			message=f"Failed to upload {file_doc.file_name}: {str(e)}",
		)
		frappe.throw(
			_("Failed to upload file to external storage: {0}").format(str(e))
		)


# ---------------------------------------------------------------------------
# File Deletion (delete_file_data_content hook)
# ---------------------------------------------------------------------------

def handle_delete_file(file_doc, only_thumbnail=False) -> None:
	"""Frappe `delete_file_data_content` hook handler.

	Called when a File document is being deleted. Handles cleanup of
	external storage files.

	Args:
		file_doc: The Frappe File document being deleted.
		only_thumbnail: If True, only delete thumbnail.
	"""
	settings = get_storage_settings()
	object_key = _extract_object_key_from_url(file_doc.file_url, settings)

	if object_key:
		# Direct uploads lack a content_hash, making Frappe pass only_thumbnail=True
		# to protect against deduplication. External files are always unique per doc.
		try:
			storage = get_storage_provider()
			storage.delete_file(object_key)
		except Exception as e:
			frappe.log_error(
				title="External Storage Delete Failed",
				message=f"Failed to delete {object_key}: {str(e)}",
			)
	else:
		# Not an external file — use default filesystem deletion
		if only_thumbnail:
			file_doc.delete_file_from_filesystem(only_thumbnail=True)
			return
			
		file_doc.delete_file_from_filesystem(only_thumbnail=False)


# ---------------------------------------------------------------------------
# Direct Upload (Pre-signed URL flow)
# ---------------------------------------------------------------------------

def handle_direct_upload_request(
	doctype: str,
	docname: str,
	filename: str,
	content_type: str = None,
	is_private: int = 0,
	file_size: int = 0,
	fieldname: str = None,
) -> dict:
	"""Generate a pre-signed upload URL for direct client upload.

	Args:
		doctype: Target DocType.
		docname: Target document name.
		filename: Original filename.
		content_type: MIME type of the file.
		is_private: Whether the file is private.
		file_size: File size in bytes (for validation).

	Returns:
		dict with upload_url, object_key, and file_url.
	"""
	settings = get_storage_settings()
	if not settings or not settings.enable_external_storage or not settings.enable_direct_upload:
		frappe.throw(_("Direct upload is not enabled"))

	if not is_external_storage_enabled(doctype, fieldname):
		frappe.throw(_("External storage is not enabled for {0} field {1}").format(doctype, fieldname or ''))

	# Validate
	if file_size:
		validate_file_size(file_size, settings)
	validate_file_type(filename, settings)
	validate_user_permission(doctype, docname)

	# Generate key and pre-signed URL
	if not content_type:
		content_type = mimetypes.guess_type(filename)[0] or "application/octet-stream"

	is_private = 0 # force all external uploads to be public
	object_key = generate_object_key(doctype, docname, filename)
	storage = get_storage_provider()

	upload_url = storage.generate_upload_url(
		object_key, 
		content_type, 
		expires_in=3600, 
		is_private=bool(is_private)
	)
	
	if is_private:
		from frappe.utils import get_url
		file_url = get_url(f"/api/method/frappe_utils.api.upload.download_secure?key={object_key}")
	else:
		file_url = storage.get_file_url(object_key)

	return {
		"upload_url": upload_url,
		"object_key": object_key,
		"file_url": file_url,
		"content_type": content_type,
	}


def confirm_upload(
	object_key: str,
	doctype: str,
	docname: str,
	filename: str,
	is_private: int = 0,
) -> dict:
	"""Confirm that a direct upload completed successfully.

	Verifies the file exists in storage, then creates the File document.

	Args:
		object_key: The storage object key.
		doctype: Target DocType.
		docname: Target document name.
		filename: Original filename.
		is_private: Whether the file is private.

	Returns:
		dict with the created File document data.
	"""
	validate_user_permission(doctype, docname)

	storage = get_storage_provider()

	# Verify file exists in storage
	if not storage.check_file_exists(object_key):
		frappe.throw(_("Upload verification failed: file not found in storage"))

	file_url = storage.get_file_url(object_key)

	# For private files, use virtual URL (consistent with handle_write_file)
	if int(is_private):
		from frappe.utils import get_url
		file_url = get_url(f"/api/method/frappe_utils.api.upload.download_secure?key={object_key}")

	# Determine folder
	folder = f"Home/{doctype}" if doctype else "Home"

	# Ensure folder exists
	if not frappe.db.exists("File", folder):
		folder = "Home"

	# Create File document
	try:
		file_doc = frappe.get_doc(
			{
				"doctype": "File",
				"file_name": filename,
				"file_url": file_url,
				"attached_to_doctype": doctype,
				"attached_to_name": docname,
				"is_private": int(is_private),
				"folder": folder,
			}
		)
		file_doc.flags.ignore_file_validate = True
		file_doc.insert(ignore_permissions=False)

		result = file_doc.as_dict()
		if int(is_private):
			result["file_url"] = storage.generate_download_url(object_key, expires_in=3600)
		return result
	except frappe.DuplicateEntryError:
		frappe.clear_messages()
		# File doc already exists, find and return it
		existing = frappe.get_value(
			"File",
			{"file_url": file_url, "attached_to_doctype": doctype, "attached_to_name": docname},
			"name",
		)
		if existing:
			existing_doc = frappe.get_doc("File", existing)
			result = existing_doc.as_dict()
			if int(is_private):
				result["file_url"] = storage.generate_download_url(object_key, expires_in=3600)
			return result
		frappe.throw(_("File already exists"))
	except Exception as e:
		# Metadata creation failed — attempt to clean up the uploaded file
		frappe.log_error(
			title="Storage Metadata Creation Failed",
			message=f"File uploaded to {object_key} but metadata creation failed: {str(e)}",
		)
		try:
			storage.delete_file(object_key)
		except Exception:
			frappe.log_error(
				title="Storage Cleanup Failed",
				message=f"Failed to clean up {object_key} after metadata failure",
			)
		raise

def get_download_url_for_file(file_url: str) -> str:
	"""Generate a secure proxy URL after verifying permissions.
	
	This hides S3 credentials from the caller and provides a stable
	endpoint that never expires for authorized users.
	"""
	if not file_url:
		return file_url

	settings = get_storage_settings()
	object_key = _extract_object_key_from_url(file_url, settings)
	
	if not object_key:
		return file_url # Local or non-external file

	# Permission check
	file_names = frappe.get_all("File", filters={"file_url": file_url}, fields=["name", "attached_to_doctype", "attached_to_name"], limit=1)
	if not file_names:
		frappe.throw(_("File not found globally"), frappe.DoesNotExistError)
		
	target = file_names[0]
	if target.attached_to_doctype and target.attached_to_name:
		if not frappe.has_permission(target.attached_to_doctype, "read", target.attached_to_name):
			frappe.throw(_("No permission to access this file"), frappe.PermissionError)
			
	from frappe.utils import get_url
	return get_url(f"/api/method/frappe_utils.api.upload.download_secure?key={object_key}")


def resolve_external_url(file_url: str, expires_in: int = 3600) -> str:
	"""Resolve an external storage URL to a time-limited pre-signed download URL.

	Used for server-side URL resolution when rendering guest-facing pages
	(e.g. candidate profiles via Jinja). Generates a fresh pre-signed S3 URL
	that works for the duration of a typical page visit.

	Handles:
	- Secure proxy URLs (/api/.../download_secure?key=<key>)
	- Private virtual URLs (https://s3.private/<key>)
	- Direct endpoint URLs (https://<endpoint>/<bucket>/<key>)
	- Local/non-external URLs → returned as-is

	Args:
		file_url: The file URL stored in the database.
		expires_in: Pre-signed URL expiry in seconds (default 3600 = 1 hour).

	Returns:
		A working, time-limited download URL string.
	"""
	if not file_url:
		return file_url

	object_key = None

	# Case 1: Secure proxy URL — extract the key
	if "download_secure?key=" in file_url:
		object_key = file_url.split("download_secure?key=")[-1]

	# Case 2: Private virtual URL
	elif file_url.startswith("https://s3.private/"):
		object_key = file_url[len("https://s3.private/"):]

	# Case 3: Direct external storage endpoint URL
	else:
		settings = get_storage_settings()
		if settings:
			object_key = _extract_object_key_from_url(file_url, settings)

	if object_key:
		try:
			storage = get_storage_provider()
			return storage.generate_download_url(object_key, expires_in=expires_in)
		except Exception:
			return file_url

	# Case 4: Local or unrecognised URL — return as-is
	return file_url



