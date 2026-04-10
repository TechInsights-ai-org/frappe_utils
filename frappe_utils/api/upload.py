# Copyright (c) 2026, TechInsights-AI and contributors
# For license information, please see license.txt

"""Whitelisted API endpoints for external storage uploads.

Provides endpoints for:
- Generating pre-signed upload URLs (direct upload flow)
- Confirming direct uploads
- Checking if external storage is enabled for a doctype
"""

import frappe
from frappe import _


@frappe.whitelist()
def get_presigned_upload_url(
	doctype: str,
	docname: str,
	filename: str,
	content_type: str = None,
	is_private: int = 1,
	file_size: int = 0,
	fieldname: str = None,
) -> dict:
	"""Generate a pre-signed URL for direct client-side upload.

	Args:
		doctype: Target DocType for the file attachment.
		docname: Target document name.
		filename: Original filename.
		content_type: MIME type of the file.
		is_private: Whether the file should be private (1) or public (0).
		file_size: File size in bytes for validation.
		fieldname: Form fieldname this file is being attached to.

	Returns:
		dict with upload_url, object_key, file_url, content_type.
	"""
	from frappe_utils.services.upload_service import handle_direct_upload_request

	return handle_direct_upload_request(
		doctype=doctype,
		docname=docname,
		filename=filename,
		content_type=content_type,
		is_private=int(is_private),
		file_size=int(file_size) if file_size else 0,
		fieldname=fieldname,
	)


@frappe.whitelist()
def confirm_direct_upload(
	object_key: str,
	doctype: str,
	docname: str,
	filename: str,
	is_private: int = 1,
) -> dict:
	"""Confirm that a direct upload completed successfully.

	Verifies the file exists in external storage, then creates
	the File document in Frappe.

	Args:
		object_key: The storage object key returned by get_presigned_upload_url.
		doctype: Target DocType for the file attachment.
		docname: Target document name.
		filename: Original filename.
		is_private: Whether the file should be private (1) or public (0).

	Returns:
		dict with the created File document data.
	"""
	from frappe_utils.services.upload_service import confirm_upload

	return confirm_upload(
		object_key=object_key,
		doctype=doctype,
		docname=docname,
		filename=filename,
		is_private=int(is_private),
	)


@frappe.whitelist()
def check_external_storage_status(doctype: str = None, fieldname: str = None) -> dict:
	"""Check if external storage is enabled and configured.

	Args:
		doctype: Optional DocType to check specific routing.
		fieldname: Optional Fieldname to check against exclusion rules.

	Returns:
		dict with enabled status and direct_upload flag.
	"""
	from frappe_utils.services.upload_service import (
		get_storage_settings,
		is_external_storage_enabled,
	)

	settings = get_storage_settings()
	enabled = is_external_storage_enabled(doctype, fieldname)

	return {
		"enabled": enabled,
		"direct_upload": bool(settings and settings.enable_direct_upload) if enabled else False,
		"default_private": bool(settings and settings.default_private) if enabled else False,
		"storage_provider": settings.storage_provider if settings else None,
	}

@frappe.whitelist(allow_guest=False)
def download_secure(key: str):
	"""Proxy the file from external storage to the client.
	
	This hides S3 credentials/signatures from the browser and ensures
	permanent access to authorized users via a stable endpoint.
	"""
	# 1. Verify file exists and user has access
	# We find the File doc that has this object key in its file_url
	file_names = frappe.get_all(
		"File", 
		filters={"file_url": ["like", f"%{key}%"]}, 
		fields=["name", "file_name", "attached_to_doctype", "attached_to_name"],
		limit=1
	)
	
	if not file_names:
		frappe.throw(_("File not found or no permission"), exc=frappe.DoesNotExistError)
	
	target = file_names[0]
	
	# Check if user has permission to read the attached document
	if target.attached_to_doctype and target.attached_to_name:
		if not frappe.has_permission(target.attached_to_doctype, "read", target.attached_to_name):
			frappe.throw(_("No permission to access this file"), exc=frappe.PermissionError)

	# 2. Fetch from External Storage
	from frappe_utils.services.upload_service import get_storage_provider
	storage = get_storage_provider()
	
	try:
		# Internal fetch from S3 (Streaming)
		response = storage.client.get_object(Bucket=storage.bucket_name, Key=key)
		
		# 3. Prepare Frappe Response
		# Using the boto3 StreamingBody directly ensures we don't load large files into RAM
		frappe.local.response.filename = target.file_name
		frappe.local.response.filecontent = response["Body"]
		frappe.local.response.type = "download"
		
		# Set Content-Type and other relevant headers from S3 metadata
		if "ContentType" in response:
			frappe.local.response.content_type = response["ContentType"]
		
		# Transfer ETag and Content-Length to help browser caching/progress
		if "ETag" in response:
			frappe.local.response.headers = {
				"ETag": response["ETag"],
				"Content-Length": str(response["ContentLength"])
			}
			
	except Exception as e:
		frappe.log_error(f"Storage Proxy Error: {str(e)}", "download_secure")
		frappe.throw(_("Failed to fetch file from remote storage"))

@frappe.whitelist()
def get_download_url(file_url: str) -> str:
	"""Get a time-limited presigned download URL for a private external file.
	
	Validates that the user has permission to read the document attached to this file.
	
	Args:
		file_url: The file_url tracked in the DB.
		
	Returns:
		A secure presigned GET URL (string) or the original URL if public.
	"""
	from frappe_utils.services.upload_service import get_download_url_for_file
	return get_download_url_for_file(file_url)

# Browser cache duration for served media (seconds)
_MEDIA_CACHE_MAX_AGE = 3600  # 1 hour


@frappe.whitelist(allow_guest=True)
def serve_media(key: str):
	"""Guest-accessible media proxy — fetches from S3 and serves inline.

	Used on public-facing pages (e.g. candidate profiles) so that:
	- No S3 credentials are ever embedded in the HTML source
	- The URL never expires (the server always has valid credentials)
	- Browser caches the response via Cache-Control headers

	Args:
		key: The S3 object key for the file.
	"""
	if not key:
		frappe.throw(_("Missing file key"), exc=frappe.ValidationError)

	from frappe_utils.services.upload_service import get_storage_provider

	try:
		storage = get_storage_provider()
		response = storage.client.get_object(Bucket=storage.bucket_name, Key=key)

		frappe.local.response.filecontent = response["Body"].read()
		frappe.local.response.type = "download"

		# Serve inline (not as attachment) so images/videos render in the page
		content_type = response.get("ContentType", "application/octet-stream")
		frappe.local.response.filename = key.split("/")[-1]
		frappe.local.response.content_type = content_type

		# Let browsers cache the file to reduce repeated S3 fetches
		frappe.local.response.headers = {
			"Content-Disposition": f"inline; filename=\"{key.split('/')[-1]}\"",
			"Cache-Control": f"public, max-age={_MEDIA_CACHE_MAX_AGE}",
			"Content-Length": str(response.get("ContentLength", 0)),
		}
		if "ETag" in response:
			frappe.local.response.headers["ETag"] = response["ETag"]

	except Exception as e:
		frappe.log_error(title="serve_media Error", message=str(e))
		frappe.throw(_("Failed to fetch file from storage"))


