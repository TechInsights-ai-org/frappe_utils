/**
 * Storage Upload Override
 *
 * Intercepts Frappe's file upload to support direct-to-S3 uploads
 * via pre-signed URLs when external storage with direct upload is enabled.
 */
(function () {
	"use strict";

	if (!frappe.ui || !frappe.ui.FileUploader) return;

	const OriginalFileUploader = frappe.ui.FileUploader;

	frappe.ui.FileUploader = class DirectStorageUploader {
		constructor(options) {
			this.options = options;
			this.uid = frappe.utils.get_random(10);

			// Try to intercept upload for valid doctypes
			this.initialize();
		}

		async initialize() {
			const status = await this.check_direct_upload();
			if (status && status.enabled && status.direct_upload) {
				this.show_direct_uploader(status);
			} else {
				// Fall back to the default Vue Uploader with limited options
				this.options.disable_file_browser = true;
				this.options.allow_take_photo = false;
				this.options.allow_link = false;
				
				this.uploader = new OriginalFileUploader(this.options);
			}
		}

		async check_direct_upload() {
			const doctype = this.options.doctype;
			if (!doctype) return null;

			const cache_key = this.options.fieldname ? `${doctype}:${this.options.fieldname}` : doctype;

			frappe._direct_upload_cache = frappe._direct_upload_cache || {};
			if (frappe._direct_upload_cache[cache_key] !== undefined) {
				return frappe._direct_upload_cache[cache_key];
			}

			try {
				const status = await frappe.xcall(
					"frappe_utils.api.upload.check_external_storage_status",
					{ 
						doctype: doctype,
						fieldname: this.options.fieldname
					}
				);
				frappe._direct_upload_cache[cache_key] = status;
				return status;
			} catch (e) {
				console.warn("Direct upload check failed:", e);
				frappe._direct_upload_cache[cache_key] = null;
				return null;
			}
		}

		show_direct_uploader() {
			this.dialog = new frappe.ui.Dialog({
				title: __("Direct Upload to Storage"),
				fields: [
					{
						fieldtype: "HTML",
						fieldname: "file_html",
						options: `
							<div style="padding: 20px; border: 2px dashed var(--border-color); border-radius: 8px; text-align: center; background: var(--control-bg);">
								<input type="file" class="direct-storage-file-input" style="max-width: 100%;" />
								<div class="progress mt-4 direct-storage-progress-container" style="display: none; height: 10px;">
									<div class="progress-bar progress-bar-success direct-storage-progress" style="width: 0%; background-color: var(--green-500);"></div>
								</div>
								<div class="mt-2 text-muted direct-storage-status" style="display:none;font-size:12px;"></div>
							</div>
						`
					}
				],
				primary_action_label: __("Upload securely to Storage"),
				primary_action: () => {
					const input = this.dialog.$wrapper.find('.direct-storage-file-input').get(0);
					if (input && input.files && input.files.length > 0) {
						this.upload_file(input.files[0]);
					} else {
						frappe.show_alert({ message: __("Please select a file first"), indicator: "orange" });
					}
				}
			});

			this.dialog.onhide = () => {
				setTimeout(() => {
					if (this.dialog && this.dialog.$wrapper) {
						this.dialog.$wrapper.remove();
					}
				}, 400);
			};

			this.dialog.show();
		}

		async upload_file(file) {
			const doctype = this.options.doctype;
			const docname = this.options.docname;
			const filename = file.name;
			const content_type = file.type || "application/octet-stream";
			const file_size = file.size;
			
			const is_private = 0; // All external storage files are public for now

			// UI Elements
			const upload_btn = this.dialog.get_primary_btn();
			const progress_container = this.dialog.$wrapper.find('.direct-storage-progress-container').get(0);
			const progress_bar = this.dialog.$wrapper.find('.direct-storage-progress').get(0);
			const status_text = this.dialog.$wrapper.find('.direct-storage-status').get(0);

			if (upload_btn) upload_btn.prop("disabled", true);
			if (progress_container) progress_container.style.display = "flex";
			if (status_text) status_text.style.display = "block";

			try {
				if (status_text) status_text.innerText = "Requesting secure upload URL...";

				// Step 1: Get pre-signed upload URL
				const presigned = await frappe.xcall(
					"frappe_utils.api.upload.get_presigned_upload_url",
					{
						doctype,
						docname,
						filename,
						content_type,
						is_private,
						file_size,
						fieldname: this.options.fieldname
					}
				);

				if (status_text) status_text.innerText = "Uploading directly to object storage...";

				// Step 2: Upload file directly
				await this._upload_to_presigned_url(
					presigned.upload_url,
					file,
					presigned.content_type,
					is_private,
					(percent) => {
						if (progress_bar) progress_bar.style.width = percent + "%";
						if (status_text) status_text.innerText = `Uploading... ${percent}%`;
					}
				);

				if (status_text) status_text.innerText = "Confirming upload...";

				// Step 3: Confirm upload and create File doc
				const result = await frappe.xcall(
					"frappe_utils.api.upload.confirm_direct_upload",
					{
						object_key: presigned.object_key,
						doctype,
						docname,
						filename,
						is_private,
					}
				);

				frappe.show_alert({ message: __("Successfully uploaded to remote storage"), indicator: "green" });

				this.dialog.hide();

				if (this.options.on_success) {
					this.options.on_success(result);
				}

			} catch (error) {
				if (upload_btn) upload_btn.prop("disabled", false);
				if (progress_bar) progress_bar.classList.add("progress-bar-danger");
				if (status_text) {
					status_text.innerText = "Upload failed.";
					status_text.style.color = "var(--red-500)";
				}

				frappe.msgprint({
					title: __("Remote Upload Failed"),
					message: error.message || __("Failed to upload file to external storage. Please check CORS settings."),
					indicator: "red",
				});
			}
		}

		_upload_to_presigned_url(upload_url, file_obj, content_type, is_private, on_progress) {
			return new Promise((resolve, reject) => {
				const xhr = new XMLHttpRequest();

				xhr.open("PUT", upload_url, true);

				// Critical headers. Adding these correctly is required by S3 providers.
				xhr.setRequestHeader("Content-Type", content_type);
				if (!is_private) {
					xhr.setRequestHeader("x-amz-acl", "public-read");
				}

				xhr.upload.onprogress = (e) => {
					if (e.lengthComputable) {
						let percent = Math.round((e.loaded / e.total) * 100);
						on_progress(percent);
					}
				};

				xhr.onload = () => {
					if (xhr.status >= 200 && xhr.status < 300) {
						resolve();
					} else {
						reject(new Error(`Storage Provider returned status ${xhr.status}: ${xhr.statusText}`));
					}
				};

				xhr.onerror = () => {
					reject(new Error("Network error during file upload. Check storage bucket CORS policy."));
				};

				xhr.ontimeout = () => {
					reject(new Error("Upload timed out"));
				};

				xhr.timeout = 600000; // 10 minute
				xhr.send(file_obj);
			});
		}
	};
})();
