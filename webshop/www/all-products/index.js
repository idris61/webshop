frappe.ready(() => {
	const initProductView = () => {
		if (typeof webshop === 'undefined' || typeof webshop.ProductView === 'undefined') {
			setTimeout(initProductView, 100);
			return;
		}
		
		const query_params = frappe.utils.get_query_params();
		let item_group = query_params.item_group || null;
		
		if (!item_group && $('.item-group-content').length) {
			item_group = $('.item-group-content').data('item-group') || null;
		}
		
		if ($("#product-listing").length) {
			try {
				new webshop.ProductView({
					products_section: $("#product-listing"),
					item_group: item_group,
					view_type: "grid"
				});
			} catch (error) {
				console.error("Error initializing ProductView:", error);
			}
		} else {
			console.error("Product listing container (#product-listing) not found");
		}
	};
	
	initProductView();
});
