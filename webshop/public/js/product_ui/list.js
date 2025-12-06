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
		const MAX_TITLE_LENGTH = 200;
		let html = ``;

		this.items.forEach(item => {
			let title = item.web_item_name || item.item_name || item.item_code || "";
			title = title.length > MAX_TITLE_LENGTH ? title.slice(0, MAX_TITLE_LENGTH) + "..." : title;

			html += `<div class='row list-row w-100 mb-4'>`;
			html += this.get_image_html(item, title, this.settings);
			html += this.get_row_body_html(item, title, this.settings);
			html += `</div>`;
		});

		this.products_section.append(html);
	}

	get_image_html(item, title, settings) {
		// Backend'den gelen resim bilgisini kullan (zaten set edilmiş olmalı)
		const image = item.website_image || item.thumbnail;
		const wishlist_enabled = !item.has_variants && settings?.enable_wishlist;
		const route = item.route || '#';
		const wishlistIcon = wishlist_enabled ? this.get_wishlist_icon(item) : '';
		
		const imageHtml = image
			? `<img itemprop="image" class="website-image h-100 w-100" alt="${title}" src="${image}" loading="lazy">`
			: `<div class="card-img-top no-image-list">${frappe.get_abbr(title)}</div>`;

		return `
			<div class="col-2 border text-center rounded list-image">
				<a class="product-link product-list-link" href="/${route}" style="text-decoration: none">
					${imageHtml}
				</a>
				${wishlistIcon}
			</div>
		`;
	}

	get_row_body_html(item, title, settings) {
		return `
			<div class='col-10 text-left'>
				${this.get_title_html(item, title, settings)}
				${this.get_item_details(item, settings)}
			</div>
		`;
	}

	get_title_html(item, title, settings) {
		const route = item.route || '#';
		const cartActionContainer = settings?.enabled 
			? `<div class="col-4 cart-action-container ${item.in_cart ? 'd-flex' : ''}">
					${this.get_primary_button(item, settings)}
				</div>`
			: '';

		return `
			<div style="display: flex; margin-left: -15px;">
				<div class="col-8" style="margin-right: -15px;">
					<a href="/${route}" style="color: var(--gray-800); font-weight: 500;">
						${title}
					</a>
				</div>
				${cartActionContainer}
			</div>
		`;
	}

	get_item_details(item, settings) {
		let details = `
			<p class="product-code">
				${item.item_group} | ${__('Item Code')}: ${item.item_code}
			</p>
			<div class="mt-2" style="color: var(--gray-600) !important; font-size: 13px;">
				${item.short_description || ''}
			</div>
		`;
		
		details += this.get_categories_html(item);
		details += this.get_badges_html(item);
		
		details += `
			<div class="product-price" itemprop="offers" itemscope itemtype="https://schema.org/AggregateOffer">
		`;

		if (item.has_variants) {
			details += item.formatted_price_range || item.formatted_price || '';
		} else {
			details += item.formatted_price || '';
		}

		if (item.formatted_mrp) {
			const mrp = item.formatted_mrp.replace(/\s+/g, '');
			details += `
				<small class="striked-price">
					<s>${mrp}</s>
				</small>
				<small class="ml-1 product-info-green">
					${item.discount} ${__("OFF")}
				</small>
			`;
		}

		details += this.get_stock_availability(item, settings);
		details += `</div>`;

		return details;
	}

	get_categories_html(item) {
		if (!item.product_categories?.length) {
			return '';
		}

		const MAX_CATEGORIES = 3;
		const categoriesToShow = item.product_categories.slice(0, MAX_CATEGORIES);
		let html = `<div class="product-categories mt-2" style="font-size: 11px; color: #7f8c8d;">`;
		
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

	get_wishlist_icon(item) {
		return super.get_wishlist_icon(item, "like-action-list");
	}

	get_stock_availability(item, settings) {
		const stock_html = super.get_stock_availability(item, settings);
		return stock_html ? `<br>${stock_html}` : '';
	}

	get_primary_button(item, settings) {
		if (item.has_variants) {
			return this.get_explore_button(item);
		}
		
		if (!settings?.enabled) {
			return '';
		}

		if (settings.allow_items_not_in_stock === false && item.in_stock === false) {
			return '';
		}

		const inCart = item.in_cart === true;
		const addToCartHidden = inCart ? 'hidden' : '';
		const goToCartHidden = inCart ? '' : 'hidden';
		const qty = item.qty || 1;
		
		return `
			<div id="${item.name}" class="btn btn-sm btn-primary btn-add-to-cart-list mb-0 ${addToCartHidden}"
				data-item-code="${item.item_code}"
				style="margin-top: 0px !important; max-height: 30px; float: right; padding: 0.25rem 1rem; min-width: 135px;">
				<span class="mr-2">
					<svg class="icon icon-md">
						<use href="#icon-assets"></use>
					</svg>
				</span>
				${this.get_cart_button_text(settings)}
			</div>
			<div class="cart-indicator list-indicator ${inCart ? '' : 'hidden'}">${qty}</div>
			<a href="/cart" style="text-decoration: none !important; border-bottom: none !important;">
				<div id="${item.name}" class="btn btn-sm btn-primary btn-add-to-cart-list ml-4 go-to-cart mb-0 mt-0 ${goToCartHidden}"
					data-item-code="${item.item_code}"
					style="padding: 0.25rem 1rem; min-width: 135px; text-decoration: none !important; border-bottom: none !important;">
					${this.get_goto_cart_text(settings)}
				</div>
			</a>
		`;
	}

};
