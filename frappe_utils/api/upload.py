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
) -> dict:
	"""Generate a pre-signed URL for direct client-side upload.

	Args:
		doctype: Target DocType for the file attachment.
		docname: Target document name.
		filename: Original filename.
		content_type: MIME type of the file.
		is_private: Whether the file should be private (1) or public (0).
		file_size: File size in bytes for validation.

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
def check_external_storage_status(doctype: str = None) -> dict:
	"""Check if external storage is enabled and configured.

	Args:
		doctype: Optional DocType to check specific routing.

	Returns:
		dict with enabled status and direct_upload flag.
	"""
	from frappe_utils.services.upload_service import (
		get_storage_settings,
		is_external_storage_enabled,
	)

	settings = get_storage_settings()
	enabled = is_external_storage_enabled(doctype)

	return {
		"enabled": enabled,
		"direct_upload": bool(settings and settings.enable_direct_upload) if enabled else False,
		"storage_provider": settings.storage_provider if settings else None,
	}

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

