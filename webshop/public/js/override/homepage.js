frappe.ui.form.on('Homepage', {
	setup: function(frm) {
		frm.set_query('item_code', 'products', () => {
			return {
				filters: {
					'published': 1
				}
			};
		});
	},
});

frappe.ui.form.on('Homepage Featured Product', {
	view: function(frm, cdt, cdn) {
		const child = locals[cdt][cdn];
		
		if (child.item_code && child.route) {
			const url = child.route.startsWith('/') ? child.route : `/${child.route}`;
			window.open(url, '_blank');
		} else if (child.item_code) {
			frappe.set_route("Form", "Website Item", child.item_code);
		}
	}
});
