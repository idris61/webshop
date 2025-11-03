webshop.ProductList = class extends webshop.ProductCardBase {
	constructor(options) {
		super();
		Object.assign(this, options);

		if (this.preference !== "List View") {
			this.products_section.addClass("hidden");
		}

		this.products_section.empty();
		this.make();
	}

	make() {
		let html = ``;

		this.items.forEach(item => {
			let title = item.web_item_name || item.item_name || item.item_code || "";
			title = title.length > 200 ? title.substr(0, 200) + "..." : title;

			html += `<div class='row list-row w-100 mb-4'>`;
			html += this.get_image_html(item, title, this.settings);
			html += this.get_row_body_html(item, title, this.settings);
			html += `</div>`;
		});

		this.products_section.append(html);
	}

	get_image_html(item, title, settings) {
		let image = item.website_image;
		let wishlist_enabled = !item.has_variants && settings.enable_wishlist;
		let image_html = ``;

		if (image) {
			image_html += `
				<div class="col-2 border text-center rounded list-image">
					<a class="product-link product-list-link" href="/${ item.route || '#' }">
						<img itemprop="image" class="website-image h-100 w-100" alt="${ title }"
							src="${ image }">
					</a>
					${ wishlist_enabled ? this.get_wishlist_icon(item): '' }
				</div>
			`;
		} else {
			image_html += `
				<div class="col-2 border text-center rounded list-image">
					<a class="product-link product-list-link" href="/${ item.route || '#' }"
						style="text-decoration: none">
						<div class="card-img-top no-image-list">
							${ frappe.get_abbr(title) }
						</div>
					</a>
					${ wishlist_enabled ? this.get_wishlist_icon(item): '' }
				</div>
			`;
		}

		return image_html;
	}

	get_row_body_html(item, title, settings) {
		let body_html = `<div class='col-10 text-left'>`;
		body_html += this.get_title_html(item, title, settings);
		body_html += this.get_item_details(item, settings);
		body_html += `</div>`;
		return body_html;
	}

	get_title_html(item, title, settings) {
		let title_html = `<div style="display: flex; margin-left: -15px;">`;
		title_html += `
			<div class="col-8" style="margin-right: -15px;">
				<a class="" href="/${ item.route || '#' }"
					style="color: var(--gray-800); font-weight: 500;">
					${ title }
				</a>
			</div>
		`;

		if (settings.enabled) {
			title_html += `<div class="col-4 cart-action-container ${item.in_cart ? 'd-flex' : ''}">`;
			title_html += this.get_primary_button(item, settings);
			title_html += `</div>`;
		}
		title_html += `</div>`;

		return title_html;
	}

	get_item_details(item, settings) {
		let details = `
			<p class="product-code">
				${ item.item_group } | ${ __('Item Code') } : ${ item.item_code }
			</p>
			<div class="mt-2" style="color: var(--gray-600) !important; font-size: 13px;">
				${ item.custom_short_description || item.short_description || '' }
			</div>
			<div class="product-price" itemprop="offers" itemscope itemtype="https://schema.org/AggregateOffer">
				${ item.formatted_price || '' }
		`;

		if (item.formatted_mrp) {
			details += `
				<small class="striked-price">
					<s>${ item.formatted_mrp ? item.formatted_mrp.replace(/ +/g, "") : "" }</s>
				</small>
				<small class="ml-1 product-info-green">
					${ item.discount } ${ __("OFF") }
				</small>
			`;
		}

		details += this.get_stock_availability(item, settings);
		details += `</div>`;

		return details;
	}

	get_wishlist_icon(item) {
		return super.get_wishlist_icon(item, "like-action-list");
	}

	get_stock_availability(item, settings) {
		let stock_html = super.get_stock_availability(item, settings);
		return stock_html ? `<br>${stock_html}` : '';
	}

	get_primary_button(item, settings) {
		if (item.has_variants) {
			return this.get_explore_button(item);
		} else if (settings.enabled && (settings.allow_items_not_in_stock || item.in_stock)) {
			return `
				<div id="${ item.name }" class="btn btn-sm btn-primary btn-add-to-cart-list mb-0 ${ item.in_cart ? 'hidden' : '' }"
					data-item-code="${ item.item_code }"
					style="margin-top: 0px !important; max-height: 30px; float: right; padding: 0.25rem 1rem; min-width: 135px;">
					<span class="mr-2">
						<svg class="icon icon-md">
							<use href="#icon-assets"></use>
						</svg>
					</span>
					${ this.get_cart_button_text(settings) }
				</div>
				<div class="cart-indicator list-indicator ${item.in_cart ? '' : 'hidden'}">${ item.qty || 1 }</div>
				<a href="/cart">
					<div id="${ item.name }" class="btn btn-sm btn-primary btn-add-to-cart-list ml-4 go-to-cart mb-0 mt-0 ${ item.in_cart ? '' : 'hidden' }"
						data-item-code="${ item.item_code }"
						style="padding: 0.25rem 1rem; min-width: 135px;">
						${ this.get_goto_cart_text(settings) }
					</div>
				</a>
			`;
		}
		return ``;
	}

};
