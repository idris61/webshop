webshop.ProductGrid = class extends webshop.ProductCardBase {
	constructor(options) {
		super();
		Object.assign(this, options);

		if (this.preference !== "Grid View") {
			this.products_section.addClass("hidden");
		}

		this.products_section.empty();
		this.make();
	}

	make() {
		let me = this;
		let html = ``;

		this.items.forEach(item => {
			let title = item.web_item_name || item.item_name || item.item_code || "";
			title =  title.length > 90 ? title.substr(0, 90) + "..." : title;

			html += `<div class="col-sm-4 item-card"><div class="card text-left">`;
			html += me.get_image_html(item, title);
			html += me.get_card_body_html(item, title, me.settings);
			html += `</div></div>`;
		});

		let $product_wrapper = this.products_section;
		$product_wrapper.append(html);
	}

	get_image_html(item, title) {
		let image = item.website_image;

		if (image) {
			return `
				<div class="card-img-container">
					<a href="/${ item.route || '#' }" style="text-decoration: none;">
						<img itemprop="image" class="card-img" src="${ image }" alt="${ title }">
					</a>
				</div>
			`;
		} else {
			return `
				<div class="card-img-container">
					<a href="/${ item.route || '#' }" style="text-decoration: none;">
						<div class="card-img-top no-image">
							${ frappe.get_abbr(title) }
						</div>
					</a>
				</div>
			`;
		}
	}

	get_card_body_html(item, title, settings) {
		let body_html = `
			<div class="card-body text-left card-body-flex" style="width:100%">
				<div style="margin-top: 1rem; display: flex;">
		`;
		body_html += this.get_title(item, title);

		if (!item.has_variants) {
			if (settings.enable_wishlist) {
				body_html += this.get_wishlist_icon(item);
			}
			if (settings.enabled) {
				body_html += this.get_cart_indicator(item);
			}
		}

		body_html += `</div>`;
		body_html += `<div class="product-category" itemprop="name">${ item.item_group || '' }</div>`;
		
		if (item.custom_short_description) {
			body_html += `<div class="product-short-description text-muted" style="font-size: 12px; margin-top: 4px; line-height: 1.4; text-align: justify;">${ item.custom_short_description }</div>`;
		}

		if (item.formatted_price) {
			body_html += this.get_price_html(item);
		}

		body_html += this.get_stock_availability(item, settings);
		body_html += this.get_primary_button(item, settings);
		body_html += `</div>`;

		return body_html;
	}

	get_title(item, title) {
		let title_html = `
			<a href="/${ item.route || '#' }">
				<div class="product-title" itemprop="name">
					${ title || '' }
				</div>
			</a>
		`;
		return title_html;
	}

	get_cart_indicator(item) {
		return `
			<div class="cart-indicator ${item.in_cart ? '' : 'hidden'}" data-item-code="${ item.item_code }">
				1
			</div>
		`;
	}

	get_primary_button(item, settings) {
		if (item.has_variants) {
			return `
				<a href="/${ item.route || '#' }">
					<div class="btn btn-sm btn-explore-variants w-100 mt-4">
						${ __("Explore") }
					</div>
				</a>
			`;
		} else if (settings.enabled && (settings.allow_items_not_in_stock || item.in_stock)) {
			return `
				<div id="${ item.name }" class="btn btn-sm btn-primary btn-add-to-cart-list w-100 mt-2 ${ item.in_cart ? 'hidden' : '' }"
					data-item-code="${ item.item_code }">
					<span class="mr-2">
						<svg class="icon icon-md">
							<use href="#icon-assets"></use>
						</svg>
					</span>
					${ this.get_cart_button_text(settings) }
				</div>
				<a href="/cart">
					<div id="${ item.name }" class="btn btn-sm btn-primary btn-add-to-cart-list w-100 mt-4 go-to-cart-grid ${ item.in_cart ? '' : 'hidden' }"
						data-item-code="${ item.item_code }">
						${ this.get_goto_cart_text(settings) }
					</div>
				</a>
			`;
		}
		return ``;
	}
};
