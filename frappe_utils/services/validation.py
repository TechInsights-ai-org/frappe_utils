# Copyright (c) 2026, TechInsights-AI and contributors
# For license information, please see license.txt

"""Pre-upload validation utilities.

Validates file size, file type, and user permissions before
allowing upload to external storage.
"""

import os

import frappe
from frappe import _


def validate_file_size(file_size_bytes: int, settings) -> None:
	"""Validate file size against configured limit.

	Args:
		file_size_bytes: Size of the file in bytes.
		settings: Storage Control settings doc.

	Raises:
		frappe.ValidationError: If file exceeds max size.
	"""
	max_mb = settings.max_file_size_mb
	if not max_mb:
		return

	max_bytes = max_mb * 1024 * 1024
	if file_size_bytes > max_bytes:
		frappe.throw(
			_("File size {0} MB exceeds the maximum allowed size of {1} MB").format(
				round(file_size_bytes / (1024 * 1024), 2),
				max_mb,
			),
			frappe.ValidationError,
		)


def validate_file_type(filename: str, settings) -> None:
	"""Validate file extension against allowed types.

	Args:
		filename: Original filename with extension.
		settings: Storage Control settings doc.

	Raises:
		frappe.ValidationError: If file type is not allowed.
	"""
	allowed = settings.allowed_file_types
	if not allowed:
		return

	allowed_types = {ext.strip().lower().lstrip(".") for ext in allowed.split(",") if ext.strip()}
	if not allowed_types:
		return

	_, ext = os.path.splitext(filename)
	file_ext = ext.lstrip(".").lower()

	if file_ext not in allowed_types:
		frappe.throw(
			_("File type '{0}' is not allowed. Allowed types: {1}").format(
				file_ext, ", ".join(sorted(allowed_types))
			),
			frappe.ValidationError,
		)


def validate_user_permission(doctype: str, docname: str) -> None:
	"""Validate that the current user has write permission on the target document.

	Args:
		doctype: Target DocType name.
		docname: Target document name.

	Raises:
		frappe.PermissionError: If user lacks write permission.
	"""
	if not doctype:
		return

	if not docname:
		frappe.has_permission(doctype, "write", throw=True)
		return

	try:
		doc = frappe.get_doc(doctype, docname)
	except frappe.DoesNotExistError:
		# Doc might not be inserted yet (new-<doctype> pattern)
		frappe.new_doc(doctype).check_permission("write")
		return

	doc.check_permission("write")
