webshop.ProductCardBase = class {
	get_stock_availability(item, settings) {
		if (!settings?.show_stock_availability || item.has_variants) {
			return '';
		}

		if (item.on_backorder) {
			return `<span class="out-of-stock mt-2" style="color: var(--primary-color)">${__("Available on backorder")}</span>`;
		}
		
		if (!item.in_stock) {
			return `<span class="out-of-stock mt-2">${__("Out of stock")}</span>`;
		}
		
		if (item.is_stock) {
			return `<span class="in-stock in-green has-stock mt-2" style="font-size: 14px;">${__("In stock")}</span>`;
		}
		
		return '';
	}

	get_wishlist_icon(item, css_class = "like-action") {
		const icon_class = item.wished ? "wished" : "not-wished";
		const wishedClass = item.wished ? "like-action-wished" : '';
		
		return `
			<div class="${css_class} ${wishedClass}" data-item-code="${item.item_code}">
				<svg class="icon sm">
					<use class="${icon_class} wish-icon" href="#icon-heart"></use>
				</svg>
			</div>
		`;
	}

	get_price_html(item) {
		let price_html = `
			<div class="product-price" itemprop="offers" itemscope itemtype="https://schema.org/AggregateOffer">
		`;

		if (item.has_variants) {
			price_html += item.formatted_price_range || item.formatted_price || '';
		} else {
			price_html += item.formatted_price || '';
		}

		if (item.formatted_mrp) {
			const mrp = item.formatted_mrp.replace(/\s+/g, '');
			price_html += `
				<small class="striked-price">
					<s>${mrp}</s>
				</small>
				<small class="ml-1 product-info-green">
					${item.discount} ${__("OFF")}
				</small>
			`;
		}
		
		price_html += `</div>`;
		return price_html;
	}

	get_explore_button(item) {
		if (!item.has_variants) {
			return '';
		}
		
		const route = item.route || '#';
		return `
			<a href="/${route}" style="text-decoration: none !important; border-bottom: none !important;">
				<div class="btn btn-sm btn-explore-variants btn mb-0 mt-0">
					${(__("Explore") || "EXPLORE").toUpperCase()}
				</div>
			</a>
		`;
	}

	get_cart_button_text(settings) {
		const text = settings?.enable_checkout ? __("Add to Cart") : __("Add to Quote");
		return text ? text.toUpperCase() : (settings?.enable_checkout ? "ADD TO CART" : "ADD TO QUOTE");
	}

	get_goto_cart_text(settings) {
		const text = settings?.enable_checkout ? __("View in Cart") : __("View in Quote");
		return text ? text.toUpperCase() : (settings?.enable_checkout ? "VIEW IN CART" : "VIEW IN QUOTE");
	}
};


