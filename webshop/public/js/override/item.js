frappe.ui.form.on("Item", {
	refresh: function(frm) {
		if (frm.doc.__islocal) {
			return;
		}

		if (!frm.doc.published_in_website) {
			frm.add_custom_button(__("Publish in Website"), () => {
				frappe.call({
					method: "webshop.webshop.doctype.website_item.website_item.make_website_item",
					args: {
						doc: frm.doc,
					},
					freeze: true,
					freeze_message: __("Publishing Item ..."),
					callback: (result) => {
						if (result.message && result.message[0]) {
							const [website_item_name, item_name] = result.message;
							const encoded_name = encodeURIComponent(website_item_name);
							const link = `/app/website-item/${encoded_name}`;
							
							frappe.msgprint({
								message: __("Website Item {0} has been created.", [
									`<a href="${link}" class="strong">${item_name}</a>`
								]),
								title: __("Published"),
								indicator: "green"
							});
							
							frm.reload_doc();
						}
					}
				});
			}, __('Actions'));
		} else {
			frm.add_custom_button(__("View Website Item"), () => {
				frappe.db.get_value("Website Item", {item_code: frm.doc.name}, "name")
					.then((r) => {
						if (!r.name) {
							frappe.throw(__("Website Item not found"));
						}
						frappe.set_route("Form", "Website Item", r.name);
					});
			}, __('Actions'));
		}
	}
});
