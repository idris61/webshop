webshop.ProductCardBase = class {
	get_stock_availability(item, settings) {
		if (settings.show_stock_availability && !item.has_variants) {
			if (item.on_backorder) {
				return `<span class="out-of-stock mt-2" style="color: var(--primary-color)">${ __("Available on backorder") }</span>`;
			} else if (!item.in_stock) {
				return `<span class="out-of-stock mt-2">${ __("Out of stock") }</span>`;
			} else if (item.is_stock) {
				return `<span class="in-stock in-green has-stock mt-2" style="font-size: 14px;">${ __("In stock") }</span>`;
			}
		}
		return ``;
	}

	get_wishlist_icon(item, css_class = "like-action") {
		let icon_class = item.wished ? "wished" : "not-wished";
		return `
			<div class="${css_class} ${ item.wished ? "like-action-wished" : ''}" data-item-code="${ item.item_code }">
				<svg class="icon sm">
					<use class="${ icon_class } wish-icon" href="#icon-heart"></use>
				</svg>
			</div>
		`;
	}

	get_price_html(item) {
		let price_html = `
			<div class="product-price" itemprop="offers" itemscope itemtype="https://schema.org/AggregateOffer">
				${ item.formatted_price || '' }
		`;

		if (item.formatted_mrp) {
			price_html += `
				<small class="striked-price">
					<s>${ item.formatted_mrp ? item.formatted_mrp.replace(/ +/g, "") : "" }</s>
				</small>
				<small class="ml-1 product-info-green">
					${ item.discount } ${ __("OFF") }
				</small>
			`;
		}
		price_html += `</div>`;
		return price_html;
	}

	get_explore_button(item) {
		if (!item.has_variants) return '';
		
		return `
			<a href="/${ item.route || '#' }">
				<div class="btn btn-sm btn-explore-variants btn mb-0 mt-0">
					${ __("Explore") }
				</div>
			</a>
		`;
	}

	get_cart_button_text(settings) {
		return settings.enable_checkout ? __("Add to Cart") : __("Add to Quote");
	}

	get_goto_cart_text(settings) {
		return settings.enable_checkout ? __("Go to Cart") : __("Go to Quote");
	}
};

