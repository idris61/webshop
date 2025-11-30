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
		const MAX_TITLE_LENGTH = 90;
		let html = ``;

		this.items.forEach(item => {
			let title = item.web_item_name || item.item_name || item.item_code || "";
			title = title.length > MAX_TITLE_LENGTH ? title.slice(0, MAX_TITLE_LENGTH) + "..." : title;

			html += `<div class="col-sm-4 item-card"><div class="card text-left">`;
			html += this.get_image_html(item, title, this.settings);
			html += this.get_card_body_html(item, title, this.settings);
			html += `</div></div>`;
		});

		this.products_section.append(html);
	}

	get_image_html(item, title, settings) {
		// Backend'den gelen resim bilgisini kullan (zaten set edilmiş olmalı)
		let image = item.website_image || item.thumbnail;
		
		const qty = item.qty || 1;
		const qty_selector = (!item.has_variants && settings?.enabled) ? `
			<div class="cart-quantity-selector-overlay ${item.in_cart ? '' : 'hidden'}" data-item-code="${item.item_code}">
				<button class="btn-qty-decrease" data-item-code="${item.item_code}" aria-label="Decrease quantity" title="Azalt">−</button>
				<span class="cart-qty-display">${qty}</span>
				<button class="btn-qty-increase" data-item-code="${item.item_code}" aria-label="Increase quantity" title="Artır">+</button>
			</div>
		` : '';

		const route = item.route || '#';
		const imageHtml = image 
			? `<img itemprop="image" class="card-img" src="${image}" alt="${title}" loading="lazy">`
			: `<div class="card-img-top no-image">${frappe.get_abbr(title)}</div>`;

		return `
			<div class="card-img-container">
				<a href="/${route}" style="text-decoration: none;">
					${imageHtml}
				</a>
				${qty_selector}
			</div>
		`;
	}

	get_card_body_html(item, title, settings) {
		let body_html = `
			<div class="card-body text-left card-body-flex" style="width:100%">
				<div style="margin-top: 1rem; display: flex;">
		`;
		body_html += this.get_title(item, title);

		if (!item.has_variants && settings?.enable_wishlist) {
			body_html += this.get_wishlist_icon(item);
		}

		body_html += `</div>`;
		body_html += `<div class="product-category" itemprop="name">${item.item_group || ''}</div>`;
		
		if (item.short_description) {
			body_html += `<div class="product-short-description text-muted" style="font-size: 12px; margin-top: 4px; line-height: 1.4;">${item.short_description}</div>`;
		}
		
		body_html += this.get_categories_html(item);
		body_html += this.get_badges_html(item);
	
		if (item.has_variants) {
			if (item.formatted_price_range || item.formatted_price) {
				body_html += this.get_price_html(item);
			}
		} else if (item.formatted_price) {
			body_html += this.get_price_html(item);
		}

		body_html += this.get_stock_availability(item, settings);
		body_html += this.get_primary_button(item, settings);
		body_html += `</div>`;

		return body_html;
	}

	get_categories_html(item) {
		if (!item.product_categories?.length) {
			return '';
		}

		const MAX_CATEGORIES = 3;
		const categoriesToShow = item.product_categories.slice(0, MAX_CATEGORIES);
		let html = `<div class="product-categories" style="font-size: 11px; color: #7f8c8d; margin-top: 4px;">`;
		
		categoriesToShow.forEach(category => {
			html += `<span class="badge badge-secondary mr-1" style="background-color: #ecf0f1; color: #34495e; padding: 2px 6px;">${category}</span>`;
		});
		
		if (item.product_categories.length > MAX_CATEGORIES) {
			html += `<span class="text-muted">+${item.product_categories.length - MAX_CATEGORIES}</span>`;
		}
		
		html += `</div>`;
		return html;
	}

	get_badges_html(item) {
		if (!item.product_badges?.length) {
			return '';
		}

		const MAX_BADGES = 3;
		const badgesToShow = item.product_badges.slice(0, MAX_BADGES);
		let html = `<div class="product-badges mt-2 d-flex align-items-center flex-wrap" style="gap: 4px;">`;
		
		badgesToShow.forEach(badge => {
			if (badge.badge_image) {
				const altText = badge.badge_alt_text || badge.badge_name || '';
				const badgeImg = `<img src="${badge.badge_image}" alt="${altText}" style="max-height: 24px; max-width: 60px; object-fit: contain;" loading="lazy">`;
				
				if (badge.badge_link) {
					html += `<a href="${badge.badge_link}" target="_blank" rel="noopener noreferrer">${badgeImg}</a>`;
				} else {
					html += badgeImg;
				}
			}
		});
		
		html += `</div>`;
		return html;
	}

	get_title(item, title) {
		const route = item.route || '#';
		return `
			<a href="/${route}">
				<div class="product-title" itemprop="name">
					${title || ''}
				</div>
			</a>
		`;
	}

	get_primary_button(item, settings) {
		if (item.has_variants) {
			const route = item.route || '#';
			return `
				<a href="/${route}" style="text-decoration: none !important; border-bottom: none !important;">
					<div class="btn btn-sm btn-explore-variants w-100 mt-4">
						${(__("Explore") || "EXPLORE").toUpperCase()}
					</div>
				</a>
			`;
		}
		
		if (!settings) {
			return '';
		}

		if (!settings.enabled) {
			return '';
		}

		if (settings.allow_items_not_in_stock === false && item.in_stock === false) {
			return '';
		}

		const inCart = item.in_cart === true;
		const addToCartHidden = inCart ? 'hidden' : '';
		const goToCartHidden = inCart ? '' : 'hidden';
		
		return `
			<div id="${item.name}" class="btn btn-sm btn-primary btn-add-to-cart-list w-100 mt-2 ${addToCartHidden}"
				data-item-code="${item.item_code}">
				<span class="mr-2">
					<svg class="icon icon-md">
						<use href="#icon-assets"></use>
					</svg>
				</span>
				${this.get_cart_button_text(settings)}
			</div>
			<a href="/cart" style="text-decoration: none !important; border-bottom: none !important;">
				<div id="${item.name}" class="btn btn-sm btn-primary btn-add-to-cart-list w-100 mt-4 go-to-cart-grid ${goToCartHidden}"
					data-item-code="${item.item_code}">
					${this.get_goto_cart_text(settings)}
				</div>
			</a>
		`;
	}
};

