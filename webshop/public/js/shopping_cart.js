// Copyright (c) 2015, Frappe Technologies Pvt. Ltd. and Contributors
// License: GNU General Public License v3. See license.txt

// shopping cart
frappe.provide("webshop.webshop.shopping_cart");
const shopping_cart = webshop.webshop.shopping_cart;

// Constants
const ANIMATION_TIMEOUT_MS = 500;
const COOKIE_EXPIRY_MINUTES = 30;
const FREEZE_DELAY_MS = 1;

// Cookie expiry hesaplama (30 dakika)
const getCookieExpiry = () => {
	const d = new Date();
	d.setTime(d.getTime() + (COOKIE_EXPIRY_MINUTES * 60 * 1000));
	return `expires=${d.toUTCString()}`;
};

// URL parametrelerini parse et (modern URL API kullanarak)
const getParams = (url) => {
	try {
		const urlObj = new URL(url, window.location.origin);
		const params = {};
		urlObj.searchParams.forEach((value, key) => {
			params[key] = value;
		});
		return params;
	} catch (error) {
		console.error("Error parsing URL params:", error);
		return {};
	}
};

// Guest kullanıcı kontrolü ve login yönlendirme
const handleGuestUser = () => {
	if (localStorage) {
		localStorage.setItem("last_visited", window.location.pathname);
	}
	return frappe.call('webshop.webshop.api.get_guest_redirect_on_action')
		.then((res) => {
			window.location.href = res?.message || "/login";
		})
		.catch((error) => {
			console.error("Error redirecting guest user:", error);
			window.location.href = "/login";
		});
};

frappe.ready(() => {
	const full_name = frappe.session?.user_fullname;
	
	if (full_name) {
		$('.navbar li[data-label="User"] a')
			.html(`<i class="fa fa-fixed-width fa fa-user"></i> ${full_name}`);
	}
	
	// URL'den coupon code ve sales partner code'u al ve cookie'ye kaydet
	const url_args = getParams(window.location.href);
	const referral_coupon_code = url_args.cc;
	const referral_sales_partner = url_args.sp;
	const expires = getCookieExpiry();

	if (referral_coupon_code) {
		document.cookie = `referral_coupon_code=${referral_coupon_code};${expires};path=/`;
	}
	if (referral_sales_partner) {
		document.cookie = `referral_sales_partner=${referral_sales_partner};${expires};path=/`;
	}

	const saved_coupon_code = frappe.get_cookie("referral_coupon_code");
	const saved_sales_partner = frappe.get_cookie("referral_sales_partner");

	if (saved_coupon_code && $(".tot_quotation_discount").val() === undefined) {
		$(".txtcoupon").val(saved_coupon_code);
	}
	if (saved_sales_partner) {
		$(".txtreferral_sales_partner").val(saved_sales_partner);
	}

	shopping_cart.show_shoppingcart_dropdown();
	shopping_cart.set_cart_count();
	shopping_cart.show_cart_navbar();
	shopping_cart.bind_place_order();
	shopping_cart.bind_add_to_cart_action();
	shopping_cart.bind_remove_from_cart_action();
	shopping_cart.bind_cart_quantity_handlers();
});

$.extend(shopping_cart, {
	show_shoppingcart_dropdown() {
		$(".shopping-cart").on('shown.bs.dropdown', () => {
			if (!$('.shopping-cart-menu .cart-container').length) {
				return frappe.call({
					method: 'webshop.webshop.shopping_cart.cart.get_shopping_cart_menu',
					callback: (r) => {
						try {
							if (r?.message) {
								$('.shopping-cart-menu').html(r.message);
							}
						} catch (error) {
							console.error("Error loading shopping cart menu:", error);
						}
					}
				});
			}
		});
	},

	update_cart(opts) {
		if (frappe.session.user === "Guest") {
			handleGuestUser();
			return;
		}

		shopping_cart.freeze();
		return frappe.call({
			type: "POST",
			method: "webshop.webshop.shopping_cart.cart.update_cart",
			args: {
				item_code: opts.item_code,
				qty: opts.qty,
				uom: opts.uom,
				additional_notes: opts.additional_notes !== undefined ? opts.additional_notes : undefined,
				with_items: opts.with_items || 0
			},
			btn: opts.btn,
			callback: (r) => {
				try {
					shopping_cart.unfreeze();
					shopping_cart.set_cart_count(true);
					if (opts.callback && typeof opts.callback === 'function') {
						opts.callback(r);
					}
				} catch (error) {
					console.error("Error in update_cart callback:", error);
					shopping_cart.unfreeze();
				}
			}
		});
	},

	set_cart_count(animate = false) {
		$(".intermediate-empty-cart").remove();

		let cart_count = frappe.get_cookie("cart_count");
		if (frappe.session.user === "Guest") {
			cart_count = 0;
		}

		const cartCount = parseInt(cart_count) || 0;

		if (cartCount > 0) {
			$(".shopping-cart").toggleClass('hidden', false);
		}

		const $cart = $('.cart-icon');
		const $badge = $cart.find("#cart-count");

		if (cartCount === 0) {
			$cart.css("display", "none");
			$(".cart-tax-items").hide();
			$(".btn-place-order").hide();
			$(".cart-payment-addresses").hide();

			const intermediate_empty_cart_msg = `
				<div class="text-center w-100 intermediate-empty-cart mt-4 mb-4 text-muted">
					${__("Cart is Empty")}
				</div>
			`;
			$(".cart-table").after(intermediate_empty_cart_msg);
		} else {
			$cart.css("display", "inline");
			$("#cart-count").text(cartCount);
		}

		if (cartCount > 0) {
			$badge.html(cartCount);

			if (animate) {
				$cart.addClass("cart-animate");
				setTimeout(() => {
					$cart.removeClass("cart-animate");
				}, ANIMATION_TIMEOUT_MS);
			}
		} else {
			$badge.remove();
		}
	},

	shopping_cart_update({item_code, qty, cart_dropdown, additional_notes}) {
		shopping_cart.update_cart({
			item_code,
			qty,
			additional_notes,
			with_items: 1,
			btn: this,
			callback: (r) => {
				try {
					if (!r?.exc && r?.message) {
						$(".cart-items").html(r.message.items);
						$(".cart-tax-items").html(r.message.total);
						$(".payment-summary").html(r.message.taxes_and_totals);
						shopping_cart.set_cart_count();

						if (cart_dropdown !== true) {
							$(".cart-icon").hide();
						}
					}
				} catch (error) {
					console.error("Error in shopping_cart_update callback:", error);
				}
			},
		});
	},

	show_cart_navbar() {
		frappe.call({
			method: "webshop.webshop.doctype.webshop_settings.webshop_settings.is_cart_enabled",
			callback: (r) => {
				try {
					$(".shopping-cart").toggleClass('hidden', !r?.message);
				} catch (error) {
					console.error("Error checking cart enabled status:", error);
				}
			}
		});
	},

	toggle_button_class(button, remove, add) {
		button.removeClass(remove);
		button.addClass(add);
	},

	bind_add_to_cart_action() {
		$('.page_content').on('click', '.btn-add-to-cart-list', (e) => {
			const $btn = $(e.currentTarget);
			$btn.prop('disabled', true);

			if (frappe.session.user === "Guest") {
				handleGuestUser();
				return;
			}

			const item_code = $btn.data('item-code');
			if (!item_code) {
				console.error("Item code not found");
				$btn.prop('disabled', false);
				return;
			}

			frappe.call({
				method: "webshop.webshop.shopping_cart.product_info.get_product_info_for_website",
				args: {
					item_code: item_code
				},
				callback: (r) => {
					try {
						const current_qty = r?.message?.product_info?.qty || 0;
						const new_qty = current_qty + 1;

						$btn.addClass('hidden');
						$btn.closest('.cart-action-container').addClass('d-flex');
						$btn.parent().find('.go-to-cart').removeClass('hidden');
						$btn.parent().find('.go-to-cart-grid').removeClass('hidden');

						webshop.webshop.shopping_cart.update_cart({
							item_code,
							qty: new_qty,
							callback: (r) => {
								try {
									if (!r?.exc) {
										$(`.cart-quantity-selector-overlay[data-item-code="${item_code}"]`).removeClass('hidden');
										$(`.cart-quantity-selector-overlay[data-item-code="${item_code}"] .cart-qty-display`).text(new_qty);
									}
								} catch (error) {
									console.error("Error updating cart quantity display:", error);
								}
							}
						});
					} catch (error) {
						console.error("Error getting product info:", error);
						$btn.prop('disabled', false);
					}
				}
			});
		});
	},

	bind_remove_from_cart_action() {
		$('.page_content').on('click', '.remove-cart-item', (e) => {
			e.preventDefault();
			const $btn = $(e.currentTarget);
			const item_code = $btn.data('item-code');
			if (!item_code) {
				console.error("remove-cart-item: item_code bulunamadı");
				return;
			}

			webshop.webshop.shopping_cart.update_cart({
				item_code,
				qty: 0,
				callback: (r) => {
					if (r && !r.exc) {
						$btn.closest('tr[data-name]').remove();
						shopping_cart.set_cart_count(true);
					}
				}
			});
		});
	},

	bind_cart_quantity_handlers() {
		// Cart sayfasındaki quantity butonları için
		$('.page_content').on('click', '.cart-btn[data-dir]', function(e) {
			e.preventDefault();
			const $btn = $(this);
			const $spinner = $btn.closest('.number-spinner');
			const $input = $spinner.find('.cart-qty');
			const item_code = $input.data('item-code');
			const dir = $btn.data('dir');
			
			if (!item_code) {
				console.error("cart-btn: item_code bulunamadı");
				return;
			}
			
			if ($btn.prop('disabled') || $input.prop('disabled')) {
				return;
			}
			
			let currentQty = parseInt($input.val()) || 1;
			let newQty = currentQty;
			
			if (dir === 'up') {
				newQty = currentQty + 1;
			} else if (dir === 'dwn') {
				if (currentQty > 1) {
					newQty = currentQty - 1;
				} else {
					return;
				}
			}
			
			if (newQty !== currentQty) {
				$btn.prop('disabled', true);
				shopping_cart.shopping_cart_update({
					item_code,
					qty: newQty
				});
			}
		});
		
		// Product card üzerindeki quantity selector için
		$('.page_content').on('click', '.btn-qty-increase, .btn-qty-decrease', function(e) {
			e.preventDefault();
			e.stopPropagation();
			const $btn = $(this);
			const item_code = $btn.data('item-code');
			const $overlay = $btn.closest('.cart-quantity-selector-overlay');
			const $qtyDisplay = $overlay.find('.cart-qty-display');
			const $increaseBtn = $overlay.find('.btn-qty-increase');
			const $decreaseBtn = $overlay.find('.btn-qty-decrease');
			
			if (!item_code) {
				console.error("btn-qty: item_code bulunamadı");
				return;
			}
			
			if ($btn.prop('disabled')) {
				return;
			}
			
			let currentQty = parseInt($qtyDisplay.text()) || 1;
			let newQty = currentQty;
			
			if ($btn.hasClass('btn-qty-increase')) {
				newQty = currentQty + 1;
			} else if ($btn.hasClass('btn-qty-decrease')) {
				if (currentQty > 1) {
					newQty = currentQty - 1;
				} else {
					return;
				}
			}
			
			if (newQty !== currentQty) {
				// Tüm butonları disable et
				$increaseBtn.prop('disabled', true);
				$decreaseBtn.prop('disabled', true);
				
				// Optimistic update
				$qtyDisplay.text(newQty);
				
				shopping_cart.update_cart({
					item_code,
					qty: newQty,
					callback: (r) => {
						// Her durumda butonları tekrar enable et
						setTimeout(() => {
							$increaseBtn.prop('disabled', false);
							$decreaseBtn.prop('disabled', false);
						}, 100);
						
						if (!r?.exc) {
							// Başarılı - miktarı güncelle
							$qtyDisplay.text(newQty);
							shopping_cart.set_cart_count(true);
						} else {
							// Hata durumunda eski değere geri dön
							$qtyDisplay.text(currentQty);
							console.error("Quantity update error:", r?.exc);
						}
					}
				}).fail(() => {
					// Hata durumunda da butonları enable et
					$increaseBtn.prop('disabled', false);
					$decreaseBtn.prop('disabled', false);
					$qtyDisplay.text(currentQty);
				});
			}
		});
		
		let qtyChangeTimeout;
		$('.page_content').on('change blur', '.cart-qty', function() {
			const $input = $(this);
			const item_code = $input.data('item-code');
			
			if (!item_code || $input.prop('disabled')) {
				return;
			}
			
			let rawVal = $input.val().toString().replace(/[^0-9]/g, '');
			let qty = parseInt(rawVal) || 1;
			if (qty < 1) qty = 1;
			
			if (qty !== parseInt($input.data('last-qty') || $input.val() || 1)) {
				clearTimeout(qtyChangeTimeout);
				$input.data('last-qty', qty);
				$input.val(qty);
				
				qtyChangeTimeout = setTimeout(() => {
					shopping_cart.shopping_cart_update({
						item_code,
						qty: qty
					});
				}, 500);
			}
		});
	},

	freeze() {
		if (window.location.pathname !== "/cart") {
			return;
		}

		if (!$('#freeze').length) {
			const freeze = $('<div id="freeze" class="modal-backdrop fade"></div>')
				.appendTo("body");

			setTimeout(() => {
				freeze.addClass("show");
			}, FREEZE_DELAY_MS);
		} else {
			$("#freeze").addClass("show");
		}
	},

	unfreeze() {
		const $freeze = $('#freeze');
		if ($freeze.length) {
			$freeze.removeClass("show");
			setTimeout(() => {
				$freeze.remove();
			}, FREEZE_DELAY_MS);
		}
	},

	bind_place_order() {
		$('.page_content').on('click', '.btn-place-order', (e) => {
			e.preventDefault();
			const $btn = $(e.currentTarget);
			$btn.prop('disabled', true);

			if (frappe.session.user === "Guest") {
				handleGuestUser();
				$btn.prop('disabled', false);
				return;
			}

			shopping_cart.freeze();

			frappe.call({
				method: "webshop.webshop.shopping_cart.cart.place_order",
				callback: (r) => {
					shopping_cart.unfreeze();
					$btn.prop('disabled', false);

					if (r.exc) {
						frappe.show_alert({
							message: r.exc || __("Sipariş oluşturulurken bir hata oluştu"),
							indicator: 'red'
						}, 5);
						console.error("Place order error:", r.exc);
					} else if (r.message) {
						frappe.show_alert({
							message: __("Sipariş başarıyla oluşturuldu"),
							indicator: 'green'
						}, 3);
						
						setTimeout(() => {
							window.location.href = `/order?doctype=Sales Order&name=${r.message}`;
						}, 1000);
					}
				}
			});
		});

		$('.page_content').on('click', '.btn-request-for-quotation', (e) => {
			e.preventDefault();
			const $btn = $(e.currentTarget);
			$btn.prop('disabled', true);

			if (frappe.session.user === "Guest") {
				handleGuestUser();
				$btn.prop('disabled', false);
				return;
			}

			shopping_cart.freeze();

			frappe.call({
				method: "webshop.webshop.shopping_cart.cart.request_for_quotation",
				callback: (r) => {
					shopping_cart.unfreeze();
					$btn.prop('disabled', false);

					if (r.exc) {
						frappe.show_alert({
							message: r.exc || __("Teklif isteği oluşturulurken bir hata oluştu"),
							indicator: 'red'
						}, 5);
						console.error("Request for quotation error:", r.exc);
					} else if (r.message) {
						frappe.show_alert({
							message: __("Teklif isteği başarıyla oluşturuldu"),
							indicator: 'green'
						}, 3);
						
						setTimeout(() => {
							window.location.href = `/order?doctype=Quotation&name=${r.message}`;
						}, 1000);
					}
				}
			});
		});
	}
});
