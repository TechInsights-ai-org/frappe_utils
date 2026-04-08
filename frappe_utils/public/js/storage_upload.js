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

			// Try to intercept upload for valid doctypes
			this.initialize();
		}

		async initialize() {
			const enabled = await this.check_direct_upload();
			if (enabled) {
				this.show_direct_uploader();
			} else {
				// Fall back to the default Vue Uploader
				this.uploader = new OriginalFileUploader(this.options);
			}
		}

		async check_direct_upload() {
			const doctype = this.options.doctype;
			if (!doctype) return false;

			try {
				const status = await frappe.xcall(
					"frappe_utils.api.upload.check_external_storage_status",
					{ doctype: doctype }
				);
				return status.enabled && status.direct_upload;
			} catch (e) {
				console.warn("Wasabi direct upload check failed:", e);
				return false;
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
								<input type="file" id="direct-s3-file-input" style="max-width: 100%;" />
								<div class="progress mt-4" style="display: none; height: 10px;" id="direct-s3-progress-container">
									<div class="progress-bar progress-bar-success" id="direct-s3-progress" style="width: 0%; background-color: var(--green-500);"></div>
								</div>
								<div id="direct-s3-status" class="mt-2 text-muted" style="display:none;font-size:12px;"></div>
							</div>
						`
					}
				],
				primary_action_label: __("Upload securely to Wasabi"),
				primary_action: () => {
					const input = document.getElementById("direct-s3-file-input");
					if (input.files.length > 0) {
						this.upload_file(input.files[0]);
					} else {
						frappe.show_alert({ message: __("Please select a file first"), indicator: "orange" });
					}
				}
			});

			this.dialog.show();
		}

		async upload_file(file) {
			const doctype = this.options.doctype;
			const docname = this.options.docname;
			const filename = file.name;
			const content_type = file.type || "application/octet-stream";
			const file_size = file.size;
			const is_private = this.options.is_private ? 1 : 0;

			// UI Elements
			const upload_btn = this.dialog.get_primary_btn();
			const progress_container = document.getElementById("direct-s3-progress-container");
			const progress_bar = document.getElementById("direct-s3-progress");
			const status_text = document.getElementById("direct-s3-status");

			upload_btn.prop("disabled", true);
			progress_container.style.display = "flex";
			status_text.style.display = "block";

			try {
				status_text.innerText = "Requesting secure upload URL...";

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
					}
				);

				status_text.innerText = "Uploading directly to object storage...";

				// Step 2: Upload file directly to S3/Wasabi
				await this._upload_to_presigned_url(
					presigned.upload_url,
					file,
					presigned.content_type,
					is_private,
					(percent) => {
						progress_bar.style.width = percent + "%";
						status_text.innerText = `Uploading... ${percent}%`;
					}
				);

				status_text.innerText = "Confirming upload...";

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
				upload_btn.prop("disabled", false);
				progress_bar.classList.add("progress-bar-danger");
				status_text.innerText = "Upload failed.";
				status_text.style.color = "var(--red-500)";

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

				// Critical headers. Adding these correctly is required by S3/Wasabi.
				xhr.setRequestHeader("Content-Type", content_type);

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
					reject(new Error("Network error during file upload. Check Wasabi bucket CORS policy."));
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
