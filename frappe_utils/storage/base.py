# Copyright (c) 2026, TechInsights-AI and contributors
# For license information, please see license.txt

"""Abstract base class for storage providers.

All storage providers must implement this interface.
The system depends only on this base class, making it easy
to add new providers (e.g., GCS, Azure Blob) in the future.
"""

from abc import ABC, abstractmethod


class BaseStorage(ABC):
	"""Abstract interface for external file storage providers."""

	@abstractmethod
	def upload_file(self, object_key: str, file_content: bytes, content_type: str = None) -> str:
		"""Upload file content to external storage.

		Args:
			object_key: The storage path/key for the file.
			file_content: Raw bytes of the file.
			content_type: MIME type of the file.

		Returns:
			The public or accessible URL of the uploaded file.
		"""
		...

	@abstractmethod
	def generate_upload_url(self, object_key: str, content_type: str = None, expires_in: int = 3600) -> str:
		"""Generate a pre-signed URL for direct client upload.

		Args:
			object_key: The storage path/key for the file.
			content_type: MIME type of the file (used for Content-Type validation).
			expires_in: URL expiry time in seconds.

		Returns:
			A pre-signed URL that allows direct PUT upload.
		"""
		...

	@abstractmethod
	def generate_download_url(self, object_key: str, expires_in: int = 3600) -> str:
		"""Generate a pre-signed URL for downloading a file.

		Args:
			object_key: The storage path/key for the file.
			expires_in: URL expiry time in seconds.

		Returns:
			A pre-signed GET URL.
		"""
		...

	@abstractmethod
	def check_file_exists(self, object_key: str) -> bool:
		"""Check if a file exists in storage.

		Args:
			object_key: The storage path/key for the file.

		Returns:
			True if the file exists, False otherwise.
		"""
		...

	@abstractmethod
	def delete_file(self, object_key: str) -> None:
		"""Delete a file from external storage.

		Args:
			object_key: The storage path/key for the file.
		"""
		...

	@abstractmethod
	def get_file_url(self, object_key: str) -> str:
		"""Get the permanent/public URL for a file.

		Args:
			object_key: The storage path/key for the file.

		Returns:
			The URL to access the file.
		"""
		...
