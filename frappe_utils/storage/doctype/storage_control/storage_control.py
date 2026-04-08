# Copyright (c) 2026, TechInsights-AI and contributors
# For license information, please see license.txt

import frappe
from frappe.model.document import Document


class StorageControl(Document):
	def validate(self):
		if self.enable_external_storage:
			self._validate_required_fields()
			self._validate_endpoint_url()

	def _validate_required_fields(self):
		required = ["access_key", "secret_key", "bucket_name", "endpoint_url"]
		for field in required:
			if not self.get(field):
				frappe.throw(
					frappe._("{0} is required when external storage is enabled").format(
						frappe.bold(self.meta.get_label(field))
					)
				)

	def _validate_endpoint_url(self):
		if self.endpoint_url and not self.endpoint_url.startswith(("http://", "https://")):
			frappe.throw(frappe._("Endpoint URL must start with http:// or https://"))

	@frappe.whitelist()
	def test_connection(self):
		"""Test the connection to the storage provider."""
		from frappe_utils.storage.s3 import S3Storage

		try:
			storage = S3Storage(self)
			storage.client.head_bucket(Bucket=self.bucket_name)
			frappe.msgprint(
				frappe._("Successfully connected to {0}").format(frappe.bold(self.bucket_name)),
				title=frappe._("Connection Successful"),
				indicator="green",
			)
		except Exception as e:
			frappe.throw(
				frappe._("Failed to connect: {0}").format(str(e)),
				title=frappe._("Connection Failed"),
			)
