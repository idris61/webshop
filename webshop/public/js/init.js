if (!window.webshop) {
	window.webshop = {};
}

if (!frappe.boot) {
	frappe.boot = {};
}

if (!frappe.boot.assets_json) {
	frappe.boot.assets_json = {};
}

if (!frappe.boot.assets_json['file_uploader.bundle.js']) {
	const FRAppeJsPath = '/assets/frappe/dist/js/';
	const DEFAULT_HASH = 'ASQECIYZ';
	
	const scripts = document.querySelectorAll('script[src*="file_uploader.bundle"]');
	
	if (scripts.length > 0 && scripts[0]?.src) {
		frappe.boot.assets_json['file_uploader.bundle.js'] = scripts[0].src;
	} else {
		frappe.boot.assets_json['file_uploader.bundle.js'] = `${FRAppeJsPath}file_uploader.bundle.${DEFAULT_HASH}.js`;
	}
}
