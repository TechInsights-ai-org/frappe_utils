# Copyright (c) 2026, TechInsights-AI and contributors
# For license information, please see license.txt

"""S3-compatible storage provider implementation.

Works with any S3-compatible service: AWS S3, Wasabi, MinIO, etc.
Uses boto3 for all operations.
"""

import boto3
from botocore.config import Config as BotoConfig

from frappe_utils.storage.base import BaseStorage


class S3Storage(BaseStorage):
	"""S3-compatible storage provider using boto3."""

	def __init__(self, settings):
		"""Initialize S3 client from Storage Control settings.

		Args:
			settings: Storage Control document or dict-like object with
				access_key, secret_key, endpoint_url, region, bucket_name.
		"""
		self.bucket_name = settings.bucket_name
		self.endpoint_url = settings.endpoint_url.rstrip("/")
		self.region = settings.region or "us-east-1"

		self.client = boto3.client(
			"s3",
			aws_access_key_id=settings.access_key,
			aws_secret_access_key=settings.get_password("secret_key"),
			endpoint_url=self.endpoint_url,
			region_name=self.region,
			config=BotoConfig(
				signature_version="s3v4",
				s3={"addressing_style": "path"},
			),
		)

	def upload_file(self, object_key: str, file_content: bytes, content_type: str = None, is_private: bool = False) -> str:
		extra_args = {}
		if content_type:
			extra_args["ContentType"] = content_type
		if not is_private:
			extra_args["ACL"] = "public-read"

		self.client.put_object(
			Bucket=self.bucket_name,
			Key=object_key,
			Body=file_content,
			**extra_args,
		)

		return self.get_file_url(object_key)

	def generate_upload_url(self, object_key: str, content_type: str = None, expires_in: int = 3600, is_private: bool = False) -> str:
		params = {
			"Bucket": self.bucket_name,
			"Key": object_key,
		}
		if content_type:
			params["ContentType"] = content_type
		if not is_private:
			params["ACL"] = "public-read"

		return self.client.generate_presigned_url(
			"put_object",
			Params=params,
			ExpiresIn=expires_in,
		)

	def generate_download_url(self, object_key: str, expires_in: int = 3600) -> str:
		return self.client.generate_presigned_url(
			"get_object",
			Params={
				"Bucket": self.bucket_name,
				"Key": object_key,
			},
			ExpiresIn=expires_in,
		)

	def check_file_exists(self, object_key: str) -> bool:
		try:
			self.client.head_object(Bucket=self.bucket_name, Key=object_key)
			return True
		except self.client.exceptions.ClientError:
			return False

	def delete_file(self, object_key: str) -> None:
		self.client.delete_object(Bucket=self.bucket_name, Key=object_key)

	def get_file_url(self, object_key: str) -> str:
		return f"{self.endpoint_url}/{self.bucket_name}/{object_key}"
