if (!window.webshop) window.webshop = {}
if (!frappe.boot) frappe.boot = {}

// Fix for file_uploader.bundle.js missing in assets_json
// upload.js in frappe-web.bundle tries to load this but mapping is missing in web context
if (!frappe.boot.assets_json) frappe.boot.assets_json = {};

// Dynamically find the file_uploader bundle if not mapped
if (!frappe.boot.assets_json['file_uploader.bundle.js']) {
	// Try to find it from other bundles' pattern
	var frappeJsPath = '/assets/frappe/dist/js/';
	// Search for any existing file_uploader bundle in the page
	var scripts = document.querySelectorAll('script[src*="file_uploader.bundle"]');
	if (scripts.length > 0) {
		frappe.boot.assets_json['file_uploader.bundle.js'] = scripts[0].src;
	} else {
		// Fallback: use a path that will gracefully fail without breaking the page
		frappe.boot.assets_json['file_uploader.bundle.js'] = frappeJsPath + 'file_uploader.bundle.H6A6HD5S.js';
	}
}
