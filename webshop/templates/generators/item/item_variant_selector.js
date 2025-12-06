frappe.ready(function() {
	if (!window.variant_info || !window.attributes) {
		return;
	}

	let selectedAttributes = {};
	let currentVariant = null;

	$(document).on('click', '.variant-attribute-btn', function() {
		const $btn = $(this);
		const attribute = $btn.data('attribute');
		const value = $btn.data('value');

		if ($btn.hasClass('variant-attribute-selected')) {
			$btn.removeClass('variant-attribute-selected').addClass('variant-attribute-unselected');
			$btn.css({
				'background-color': 'white',
				'border-color': '#dee2e6',
				'color': '#495057'
			});
			delete selectedAttributes[attribute];
		} else {
			$(`.variant-attribute-btn[data-attribute="${attribute}"]`).removeClass('variant-attribute-selected').addClass('variant-attribute-unselected');
			$(`.variant-attribute-btn[data-attribute="${attribute}"]`).css({
				'background-color': 'white',
				'border-color': '#dee2e6',
				'color': '#495057'
			});

			// Yeni seçimi yap
			$btn.removeClass('variant-attribute-unselected').addClass('variant-attribute-selected');
			$btn.css({
				'background-color': '#ff6b35',
				'border-color': '#ff6b35',
				'color': 'white'
			});
			selectedAttributes[attribute] = value;
		}

		updateAttributeLabel(attribute, value);
		checkVariantMatch();
	});

	function updateAttributeLabel(attribute, value) {
		const $label = $(`.variant-attribute-label:contains("${attribute}")`);
		if (value) {
			$label.find('span').remove();
			$label.append(`<span class="text-primary" style="font-weight: 600;">${value}</span>`);
		} else {
			$label.find('span').remove();
		}
	}

	function checkVariantMatch() {
		const allAttributesSelected = window.attributes.every(attr => selectedAttributes[attr.attribute]);

		if (!allAttributesSelected) {
			filterAvailableVariants();
			hideVariantInfo();
			return;
		}

		currentVariant = findMatchingVariant(selectedAttributes);

		if (currentVariant) {
			showVariantInfo(currentVariant);
			loadVariantDetails(currentVariant.name);
		} else {
			hideVariantInfo();
		}
	}

	function filterAvailableVariants() {
		const availableVariants = getAvailableVariants(selectedAttributes);

		window.attributes.forEach(attr => {
			const availableValues = new Set();
			
			availableVariants.forEach(variant => {
				variant.attributes.forEach(variantAttr => {
					if (variantAttr.attribute === attr.attribute) {
						availableValues.add(variantAttr.attribute_value);
					}
				});
			});

			$(`.variant-attribute-btn[data-attribute="${attr.attribute}"]`).each(function() {
				const $btn = $(this);
				const value = $btn.data('value');
				const isSelected = $btn.hasClass('variant-attribute-selected');

				if (availableValues.has(value) || isSelected) {
					$btn.prop('disabled', false);
					$btn.css('opacity', '1');
				} else {
					$btn.prop('disabled', true);
					$btn.css('opacity', '0.5');
				}
			});
		});
	}

	function getAvailableVariants(selectedAttrs) {
		return window.variant_info.filter(variant => {
			return Object.keys(selectedAttrs).every(attrName => {
				const selectedValue = String(selectedAttrs[attrName]).trim();
				return variant.attributes.some(variantAttr => {
					const variantValue = String(variantAttr.attribute_value).trim();
					return variantAttr.attribute === attrName && variantValue === selectedValue;
				});
			});
		});
	}

	function findMatchingVariant(selectedAttrs) {
		return window.variant_info.find(variant => {
			if (variant.attributes.length !== Object.keys(selectedAttrs).length) {
				return false;
			}

			return Object.keys(selectedAttrs).every(attrName => {
				const selectedValue = String(selectedAttrs[attrName]).trim();
				return variant.attributes.some(variantAttr => {
					const variantValue = String(variantAttr.attribute_value).trim();
					return variantAttr.attribute === attrName && variantValue === selectedValue;
				});
			});
		});
	}

	function showVariantInfo(variant) {
		if (!variant || !variant.name) {
			return;
		}
		
		$('#selected-variant-info').slideDown(300);
		$('#selected-variant-name').text(variant.name);
		$('#selected-variant-price').html('<span class="text-muted"><i class="fa fa-spinner fa-spin"></i> Fiyat yükleniyor...</span>');

		$('#variant-add-to-cart').slideDown(300);
	}

	function hideVariantInfo() {
		$('#selected-variant-info').slideUp(200);
		$('#variant-add-to-cart').slideUp(200);
		currentVariant = null;
	}

	function loadVariantDetails(itemCode) {
		if (!itemCode) {
			return;
		}
		
		frappe.call({
			method: "webshop.webshop.shopping_cart.product_info.get_product_info_for_website",
			args: {
				item_code: itemCode
			},
			callback: function(r) {
				if (r.message && r.message.product_info) {
					const productInfo = r.message.product_info;
					const cartSettings = r.message.cart_settings;

					if (productInfo.price && cartSettings.show_price) {
						const formattedPrice = productInfo.price.formatted_price_sales_uom || 
						                       productInfo.price.formatted_price || 
						                       (productInfo.price.price_list_rate ? `€ ${productInfo.price.price_list_rate.toFixed(2).replace('.', ',')}` : 'Fiyat yok');
						$('#selected-variant-price').html(
							`<span class="text-success font-weight-bold" style="font-size: 20px;">${formattedPrice}</span>`
						);
					} else if (cartSettings.show_price) {
						const templatePrice = window.template_price || '';
						if (templatePrice) {
							$('#selected-variant-price').html(
								`<span class="text-success font-weight-bold" style="font-size: 20px;">${templatePrice}</span>`
							);
						} else {
							$('#selected-variant-price').html('<span class="text-muted">Fiyat bilgisi yok</span>');
						}
					} else {
						$('#selected-variant-price').html('<span class="text-muted">Fiyat bilgisi yok</span>');
					}

					if (cartSettings.show_stock_availability) {
						let stockHtml = '';
						if (productInfo.in_stock === 0) {
							stockHtml = '<span class="badge badge-danger" style="font-size: 13px; padding: 8px 12px;"><i class="fa fa-times-circle"></i> Stokta Yok</span>';
						} else if (productInfo.in_stock === 1) {
							let stockText = 'Stokta Var';
							if (productInfo.show_stock_qty) {
								stockText += ` (${productInfo.stock_qty})`;
							}
							stockHtml = `<span class="badge badge-success" style="font-size: 13px; padding: 8px 12px;"><i class="fa fa-check-circle"></i> ${stockText}</span>`;
						}
						$('#selected-variant-stock').html(stockHtml);
					}

					updateVariantImage(itemCode);
					updateAddToCartButton(itemCode, productInfo, cartSettings);
				} else {
					$('#selected-variant-price').html('<span class="text-danger">Fiyat yüklenemedi</span>');
				}
			},
			error: function(r) {
				$('#selected-variant-price').html('<span class="text-danger">Fiyat yüklenemedi</span>');
			}
		});
	}

	function updateVariantImage(itemCode) {
		frappe.call({
			method: "frappe.client.get",
			args: {
				doctype: "Website Item",
				filters: {
					item_code: itemCode
				},
				fields: ["website_image", "thumbnail"]
			},
			callback: function(r) {
				if (r.message) {
					let imageUrl = null;
					
					if (r.message.thumbnail) {
						if (r.message.thumbnail.startsWith('http://') || r.message.thumbnail.startsWith('https://')) {
							imageUrl = r.message.thumbnail;
						} else {
							var baseUrl = frappe.base_url || window.location.origin;
							imageUrl = r.message.thumbnail.startsWith('/') 
								? baseUrl + r.message.thumbnail 
								: baseUrl + '/' + r.message.thumbnail;
						}
					} else if (r.message.website_image) {
						if (r.message.website_image.startsWith('http://') || r.message.website_image.startsWith('https://')) {
							imageUrl = r.message.website_image;
						} else {
							var baseUrl = frappe.base_url || window.location.origin;
							imageUrl = r.message.website_image.startsWith('/') 
								? baseUrl + r.message.website_image 
								: baseUrl + '/' + r.message.website_image;
						}
					}
					
					if (imageUrl) {
						$('.item-image img').attr('src', imageUrl);
						$('.item-image img').attr('data-src', imageUrl);
					}
				}
			}
		});
	}

	function updateAddToCartButton(itemCode, productInfo, cartSettings) {
		const $addToCart = $('#variant-add-to-cart');
		
		if (cartSettings.enabled) {
			let hasPrice = !!productInfo.price;
			if (!hasPrice && cartSettings.show_price && window.template_price) {
				hasPrice = true;
			}
			
			// UOM seçenekleri varsa da buton gösterilmeli
			const hasUOMOptions = productInfo.uom_options && productInfo.uom_options.length > 0;
			
			// Buton gösterilmeli: fiyat varsa VEYA UOM seçenekleri varsa VEYA stok kontrolü kapalıysa
			const shouldShowButton = hasPrice || hasUOMOptions || !cartSettings.show_price;
			const canAddToCart = shouldShowButton && 
				(productInfo.in_stock !== false || cartSettings.allow_items_not_in_stock || productInfo.in_stock === undefined);
			
			// item-cart div'ini her zaman göster (hide class'ını kaldır)
			$addToCart.find('.item-cart').removeClass('hide').show();
			$addToCart.find('.item-price').toggleClass('hide', !cartSettings.show_price);
			$addToCart.find('.item-stock').toggleClass('hide', !cartSettings.show_stock_availability);

			$addToCart.find('[data-variant-item-code]').attr('data-variant-item-code', itemCode);
			$addToCart.find('[data-item-code]').attr('data-item-code', itemCode);
			$addToCart.find('.cart-qty').attr('data-item-code', itemCode);
			
			// Butonları göster/gizle (qty kontrolüne göre)
			const inCart = productInfo.qty && productInfo.qty > 0;
			
			// Buton container'ını göster ve butonları kontrol et
			let $buttonContainer = $addToCart.find('.mb-4.d-flex');
			
			// Eğer buton container yoksa veya içinde buton yoksa oluştur
			if (!$buttonContainer.length || !$buttonContainer.find('.btn-add-to-cart, .btn-view-in-cart').length) {
				const addToCartText = cartSettings.enable_checkout ? __('Sepete Ekle') : __('Teklif Oluştur');
				const viewInCartText = cartSettings.enable_checkout ? __('Sepette Görüntüle') : __('Teklifte Görüntüle');
				const buttonHtml = `
					<div class="mb-4 d-flex">
						<button class="btn btn-primary btn-add-to-cart mr-2 w-30-40" data-item-code="${itemCode}">
							<span class="mr-2">
								<svg class="icon icon-md">
									<use href="#icon-assets"></use>
								</svg>
							</span>
							${addToCartText}
						</button>
						<button class="btn btn-primary btn-view-in-cart hidden mr-2 font-md" data-item-code="${itemCode}">
							${viewInCartText}
						</button>
					</div>
				`;
				// Eski container'ı kaldır
				$buttonContainer.remove();
				
				// UOM seçicisinden sonra veya item-cart'ın sonuna ekle
				const $uomWrapper = $addToCart.find('.nm-uom-select-wrapper');
				const $itemCartCol = $addToCart.find('.item-cart .col-md-12');
				
				if ($uomWrapper.length) {
					$uomWrapper.after(buttonHtml);
				} else if ($itemCartCol.length) {
					$itemCartCol.append(buttonHtml);
				} else {
					// item-cart div'ine direkt ekle
					$addToCart.find('.item-cart').append(buttonHtml);
				}
				$buttonContainer = $addToCart.find('.mb-4.d-flex').last();
			}
			
			// Varyant seçildiğinde butonları her zaman göster (template koşulunu bypass et)
			if ($buttonContainer.length) {
				$buttonContainer.show().removeClass('hidden').css('display', 'flex');
				
				// Butonları göster/gizle (qty kontrolüne göre)
				if (inCart) {
					$addToCart.find('.btn-add-to-cart').addClass('hidden');
					$addToCart.find('.btn-view-in-cart').removeClass('hidden');
				} else {
					$addToCart.find('.btn-add-to-cart').removeClass('hidden');
					$addToCart.find('.btn-view-in-cart').addClass('hidden');
				}
			} else {
				console.error('Button container not found after creation attempt');
			}
			
			// Add to Cart butonuna click event'i ekle (eğer yoksa)
			$addToCart.find('.btn-add-to-cart').off('click').on('click', function(e) {
				e.preventDefault();
				const $btn = $(this);
				const itemCode = $btn.data('item-code');
				const qty = $addToCart.find('.cart-qty').val() || 1;
				const uom = window.nm_get_selected_uom ? window.nm_get_selected_uom(itemCode) : null;
				
				if (itemCode) {
					shopping_cart.update_cart({
						item_code: itemCode,
						qty: qty,
						uom: uom,
						callback: function(r) {
							if (!r.exc) {
								// Butonları güncelle
								$addToCart.find('.btn-add-to-cart').addClass('hidden');
								$addToCart.find('.btn-view-in-cart').removeClass('hidden');
								shopping_cart.set_cart_count(true);
							}
						}
					});
				}
			});
			
			// Önce tüm mevcut UOM ve quantity selector'ları temizle (duplicate'leri önlemek için)
			const $itemCart = $addToCart.find('.item-cart');
			// Tüm "Satış Birimi" label'larını içeren div'leri kaldır
			$itemCart.find('.mt-3.mb-3, .mb-3').each(function() {
				const $el = $(this);
				if ($el.find('.nm-uom-select, .nm-uom-select-wrapper').length > 0 || 
				    $el.find('label').text().includes('Satış Birimi') || 
				    $el.hasClass('nm-uom-wrapper')) {
					$el.remove();
				}
			});
			// Tüm quantity selector'ları kaldır
			$itemCart.find('#item-detail-spinner, .number-spinner, .cart-qty').closest('.mb-3, .mb-4').remove();
			
			// UOM seçimini dinamik olarak ekle/güncelle
			updateUOMSelector(itemCode, productInfo, cartSettings);
			
			// Miktar seçicisini ekle/güncelle
			updateQuantitySelector(itemCode, productInfo, cartSettings);
		}

		const currentUrl = new URL(window.location.href);
		currentUrl.searchParams.set('variant', itemCode);
		window.history.pushState({variant: itemCode}, '', currentUrl.toString());
	}
	
	function updateUOMSelector(itemCode, productInfo, cartSettings) {
		const $addToCart = $('#variant-add-to-cart');
		const $itemCart = $addToCart.find('.item-cart');
		
		// Tüm mevcut UOM seçicilerini kaldır (duplicate'leri önlemek için)
		// Hem .nm-uom-select-wrapper hem de .nm-uom-wrapper ve tüm "Satış Birimi" label'larını içeren div'leri kaldır
		$itemCart.find('.mt-3.mb-3, .mb-3').each(function() {
			const $el = $(this);
			if ($el.find('.nm-uom-select, .nm-uom-select-wrapper').length > 0 || 
			    $el.find('label').text().includes('Satış Birimi') || 
			    $el.hasClass('nm-uom-wrapper')) {
				$el.remove();
			}
		});
		
		// UOM seçenekleri varsa seçiciyi ekle (1'den fazla seçenek varsa göster)
		if (productInfo.uom_options && productInfo.uom_options.length > 0) {
			let uomHtml = `
				<div class="nm-uom-select-wrapper mb-4" style="margin-top: 0;">
					<label class="font-weight-bold mb-2" style="font-size: 14px; color: #2c3e50; display: block; margin-bottom: 8px;">${__('Satış Birimi')}:</label>
					<select class="form-control nm-uom-select" data-item-code="${itemCode}" style="max-width: 300px; padding: 10px 15px !important; border: 1px solid #dee2e6; border-radius: 6px; font-size: 14px !important; display: block !important; visibility: visible !important; opacity: 1 !important; height: 40px !important; min-height: 40px !important; line-height: 20px !important; box-sizing: border-box !important;">
			`;
			
			productInfo.uom_options.forEach(function(opt) {
				const selected = opt.is_default ? 'selected' : '';
				uomHtml += `
					<option value="${opt.uom}" data-price="${opt.formatted_price || ''}" ${selected}>
						${opt.uom}${opt.formatted_price ? ' – ' + opt.formatted_price : ''}
					</option>
				`;
			});
			
			uomHtml += `
					</select>
				</div>
			`;
			
			// Fiyat gösteriminden sonra UOM seçicisini ekle
			const $priceDiv = $itemCart.find('.product-price');
			if ($priceDiv.length) {
				$priceDiv.after(uomHtml);
			} else {
				// Fiyat yoksa, item-cart'ın başına ekle
				$itemCart.prepend(uomHtml);
			}
			
			// UOM selector'ı başlat
			const $uomSelect = $itemCart.find('.nm-uom-select');
			if ($uomSelect.length) {
				// CSS ayarlarını zorunlu kıl
				$uomSelect.css({
					'display': 'block',
					'visibility': 'visible',
					'opacity': '1',
					'height': '40px',
					'min-height': '40px',
					'line-height': '20px',
					'padding': '10px 15px',
					'font-size': '14px',
					'box-sizing': 'border-box'
				});
				
				// Default seçili değeri kontrol et
				if (!$uomSelect.val() || $uomSelect.val() === '') {
					const $firstOption = $uomSelect.find('option').first();
					if ($firstOption.length) {
						$uomSelect.val($firstOption.val());
						$uomSelect[0].selectedIndex = 0;
					}
				}
			}
			
			// UOM değiştiğinde fiyatı güncelle
			$uomSelect.off('change').on('change', function() {
				const $select = $(this);
				const formattedPrice = $select.find('option:selected').data('price');
				if (formattedPrice) {
					$('#selected-variant-price').html(
						`<span class="text-success font-weight-bold" style="font-size: 20px;">${formattedPrice}</span>`
					);
				}
				// Global fiyat güncelleme fonksiyonunu da çağır
				if (window.nm_update_price_for_uom) {
					window.nm_update_price_for_uom(itemCode);
				}
			});
		}
	}
	
	function updateQuantitySelector(itemCode, productInfo, cartSettings) {
		const $addToCart = $('#variant-add-to-cart');
		const $itemCart = $addToCart.find('.item-cart');
		
		// Tüm mevcut quantity selector'ları kaldır (duplicate'leri önlemek için)
		$itemCart.find('#item-detail-spinner, .number-spinner, .cart-qty').closest('.mb-3, .mb-4').remove();
		
		// Quantity selector'ı ekle
		const quantityHtml = `
			<div class="mb-4" style="margin-top: 0;">
				<label class="font-weight-bold mb-2" style="font-size: 14px; color: #2c3e50; display: block; margin-bottom: 8px;">${__('Miktar')}:</label>
				<div class="input-group number-spinner" id="item-detail-spinner" style="max-width: 180px;">
					<span class="input-group-prepend">
						<button class="btn btn-outline-secondary" data-dir="dwn" type="button" style="width: 40px; height: 40px; padding: 0; display: flex; align-items: center; justify-content: center; font-size: 18px; font-weight: bold; border: 1px solid #dee2e6; border-radius: 6px 0 0 6px;">
							−
						</button>
					</span>
					<input class="form-control text-center cart-qty" type="text" 
						value="${productInfo.qty || 1}" data-item-code="${itemCode}" 
						inputmode="numeric" pattern="[0-9]*" style="height: 40px; text-align: center; font-size: 16px; font-weight: 600; border: 1px solid #dee2e6; border-left: none; border-right: none;">
					<span class="input-group-append">
						<button class="btn btn-outline-secondary" data-dir="up" type="button" style="width: 40px; height: 40px; padding: 0; display: flex; align-items: center; justify-content: center; font-size: 18px; font-weight: bold; border: 1px solid #dee2e6; border-radius: 0 6px 6px 0;">
							+
						</button>
					</span>
				</div>
			</div>
		`;
		
		// UOM seçicisinden sonra ekle (tutarlı spacing için)
		const $uomWrapper = $itemCart.find('.nm-uom-select-wrapper');
		const $buttonContainer = $itemCart.find('.mb-4.d-flex');
		
		if ($uomWrapper.length) {
			// UOM wrapper'dan sonra ekle, aralarında tutarlı boşluk olsun
			$uomWrapper.after(quantityHtml);
		} else if ($buttonContainer.length) {
			$buttonContainer.before(quantityHtml);
		} else {
			// item-cart içindeki col-md-12'ye ekle
			const $col = $itemCart.find('.col-md-12');
			if ($col.length) {
				$col.append(quantityHtml);
			} else {
				$itemCart.append(quantityHtml);
			}
		}
		
		// Quantity selector event handler'larını ekle
		const $qtyInput = $itemCart.find('#item-detail-spinner .cart-qty');
		const $spinner = $itemCart.find('#item-detail-spinner');
		
		// +/- butonları
		$spinner.find('button[data-dir]').off('click').on('click', function() {
			const $btn = $(this);
			const dir = $btn.data('dir');
			let currentQty = parseInt($qtyInput.val()) || 1;
			
			if (dir === 'up') {
				currentQty += 1;
			} else if (dir === 'dwn') {
				if (currentQty > 1) {
					currentQty -= 1;
				} else {
					return;
				}
			}
			
			$qtyInput.val(currentQty);
		});
		
		// Input validation
		$qtyInput.off('input change blur').on('input change blur', function() {
			let rawVal = $(this).val().toString().replace(/[^0-9]/g, '');
			let qty = parseInt(rawVal) || 1;
			if (qty < 1) qty = 1;
			$(this).val(qty);
		});
	}

	function formatPrice(price) {
		return new Intl.NumberFormat('tr-TR', {
			style: 'currency',
			currency: 'EUR'
		}).format(price);
	}

	if (window.selected_attributes && Object.keys(window.selected_attributes).length > 0) {
		selectedAttributes = window.selected_attributes;
		
		Object.keys(selectedAttributes).forEach(attr => {
			const value = selectedAttributes[attr];
			const $btn = $(`.variant-attribute-btn[data-attribute="${attr}"][data-value="${value}"]`);
			$btn.removeClass('variant-attribute-unselected').addClass('variant-attribute-selected');
			$btn.css({
				'background-color': '#ff6b35',
				'border-color': '#ff6b35',
				'color': 'white'
			});
			updateAttributeLabel(attr, value);
		});

		checkVariantMatch();
	}
});

