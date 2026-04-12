/**
 * secure_files.js
 * 
 * Helper library for dynamically resolving strictly private 
 * S3 secure files in Frappe.
 */

(function () {
	"use strict";

	frappe.provide("frappe_utils");

	// Simple in-memory cache to prevent repeatedly resolving the same URL on the same page
	const resolved_url_cache = {};

	/**
	 * Resolve an https://s3.private/ virtual URL to a time-limited GET presigned URL.
	 * If the URL is an actual standard http/https link, it returns it directly.
	 * 
	 * @param {string} file_url - The original file URL from the database
	 * @returns {Promise<string>} The resolve downloadable URL
	 */
	frappe_utils.get_secure_url = async function(file_url) {
		if (!file_url) return "";

		// If it's a standard URL or local file, return it as is.
		if (!file_url.startsWith("https://s3.private/")) {
			return file_url;
		}

		// Return from cache if we already resolved it recently
		if (resolved_url_cache[file_url]) {
			return resolved_url_cache[file_url];
		}

		try {
			const secure_url = await frappe.xcall("frappe_utils.api.upload.get_download_url", {
				file_url: file_url
			});
			
			resolved_url_cache[file_url] = secure_url;
			return secure_url;
		} catch (error) {
			console.error("Failed to fetch secure URL for " + file_url, error);
			// You could handle UI error states here
			return file_url;
		}
	};

	/**
	 * Automatically scan a container for secure images, videos, or links
	 * and resolve them asynchronously.
	 * 
	 * Usage Example:
	 *   frappe_utils.resolve_secure_elements(document.getElementById('gallery'));
	 */
	frappe_utils.resolve_secure_elements = function(container = document) {
		// Example: Resolve Images
		const images = container.querySelectorAll("img[data-secure-src]");
		images.forEach(async (img) => {
			const s3_url = img.getAttribute("data-secure-src");
			const real_url = await frappe_utils.get_secure_url(s3_url);
			img.src = real_url;
			img.removeAttribute("data-secure-src");
		});

		// Example: Resolve Videos
		const videos = container.querySelectorAll("video[data-secure-src]");
		videos.forEach(async (video) => {
			const s3_url = video.getAttribute("data-secure-src");
			const real_url = await frappe_utils.get_secure_url(s3_url);
			video.src = real_url;
			video.removeAttribute("data-secure-src");
		});

		// Example: Resolve Links
		const links = container.querySelectorAll("a[data-secure-href]");
		links.forEach(async (a) => {
			const s3_url = a.getAttribute("data-secure-href");
			const real_url = await frappe_utils.get_secure_url(s3_url);
			a.href = real_url;
			a.removeAttribute("data-secure-href");
		});
	};

})();
