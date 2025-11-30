frappe.provide("webshop.webshop.wishlist");
const wishlist = webshop.webshop.wishlist;

frappe.provide("webshop.webshop.shopping_cart");
const shopping_cart = webshop.webshop.shopping_cart;

// Constants
const ANIMATION_TIMEOUT_MS = 500;

// Guest kullanıcı kontrolü ve login yönlendirme
const redirectGuest = () => {
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

$.extend(wishlist, {
	set_wishlist_count(animate = false) {
		let wish_count = frappe.get_cookie("wish_count");
		if (frappe.session.user === "Guest") {
			wish_count = 0;
		}

		const wishCount = parseInt(wish_count) || 0;

		if (wishCount > 0) {
			$(".wishlist").toggleClass('hidden', false);
		}

		const $wishlist = $('.wishlist-icon');
		const $badge = $wishlist.find("#wish-count");

		if (wishCount === 0) {
			$wishlist.css("display", "none");
		} else {
			$wishlist.css("display", "inline");
		}

		if (wishCount > 0) {
			$badge.html(wishCount);
			if (animate) {
				$wishlist.addClass('cart-animate');
				setTimeout(() => {
					$wishlist.removeClass('cart-animate');
				}, ANIMATION_TIMEOUT_MS);
			}
		} else {
			$badge.remove();
		}
	},

	bind_move_to_cart_action() {
		$('.page_content').on("click", ".btn-add-to-cart", (e) => {
			const $move_to_cart_btn = $(e.currentTarget);
			const item_code = $move_to_cart_btn.data("item-code");

			if (!item_code) {
				console.error("Item code not found");
				return;
			}

			shopping_cart.shopping_cart_update({
				item_code,
				qty: 1,
				cart_dropdown: true
			});

			const success_action = () => {
				const $card_wrapper = $move_to_cart_btn.closest(".wishlist-card");
				$card_wrapper.addClass("wish-removed");
			};
			const args = { item_code };
			this.add_remove_from_wishlist("remove", args, success_action, null, true);
		});
	},

	bind_remove_action() {
		$('.page_content').on("click", ".remove-wish", (e) => {
			const $remove_wish_btn = $(e.currentTarget);
			const item_code = $remove_wish_btn.data("item-code");

			if (!item_code) {
				console.error("Item code not found");
				return;
			}

			const success_action = () => {
				const $card_wrapper = $remove_wish_btn.closest(".wishlist-card");
				$card_wrapper.addClass("wish-removed");
				if (parseInt(frappe.get_cookie("wish_count")) === 0) {
					$(".page_content").empty();
					this.render_empty_state();
				}
			};
			const args = { item_code };
			this.add_remove_from_wishlist("remove", args, success_action);
		});
	},

	bind_wishlist_action() {
		$('.page_content').on('click', '.like-action, .like-action-list', (e) => {
			const $btn = $(e.currentTarget);
			this.wishlist_action($btn);
		});
	},

	wishlist_action(btn) {
		const $wish_icon = btn.find('.wish-icon');

		if (frappe.session.user === "Guest") {
			redirectGuest();
			return;
		}

		const success_action = () => {
			webshop.webshop.wishlist.set_wishlist_count(true);
		};

		const item_code = btn.data('item-code');
		if (!item_code) {
			console.error("Item code not found");
			return;
		}

		if ($wish_icon.hasClass('wished')) {
			btn.removeClass("like-animate");
			btn.addClass("like-action-wished");
			this.toggle_button_class($wish_icon, 'wished', 'not-wished');

			const args = { item_code };
			const failure_action = () => {
				this.toggle_button_class($wish_icon, 'not-wished', 'wished');
			};
			this.add_remove_from_wishlist("remove", args, success_action, failure_action);
		} else {
			btn.addClass("like-animate");
			btn.addClass("like-action-wished");
			this.toggle_button_class($wish_icon, 'not-wished', 'wished');

			const args = { item_code };
			const failure_action = () => {
				this.toggle_button_class($wish_icon, 'wished', 'not-wished');
			};
			this.add_remove_from_wishlist("add", args, success_action, failure_action);
		}
	},

	toggle_button_class(button, remove, add) {
		button.removeClass(remove);
		button.addClass(add);
	},

	add_remove_from_wishlist(action, args, success_action, failure_action, async = false) {
		if (frappe.session.user === "Guest") {
			redirectGuest();
			return;
		}

		const method = action === "remove"
			? "webshop.webshop.doctype.wishlist.wishlist.remove_from_wishlist"
			: "webshop.webshop.doctype.wishlist.wishlist.add_to_wishlist";

		frappe.call({
			async: async,
			type: "POST",
			method: method,
			args: args,
			callback: (r) => {
				try {
					if (r?.exc) {
						if (failure_action && typeof failure_action === 'function') {
							failure_action();
						}
						frappe.msgprint({
							message: __("Sorry, something went wrong. Please refresh."),
							indicator: "red",
							title: __("Note")
						});
					} else if (success_action && typeof success_action === 'function') {
						success_action();
					}
				} catch (error) {
					console.error("Error in add_remove_from_wishlist callback:", error);
					if (failure_action && typeof failure_action === 'function') {
						failure_action();
					}
				}
			}
		});
	},

	redirect_guest() {
		redirectGuest();
	},

	render_empty_state() {
		$(".page_content").append(`
			<div class="cart-empty frappe-card">
				<div class="cart-empty-state">
					<img src="/assets/webshop/images/cart-empty-state.png" alt="Empty Wishlist" loading="lazy">
				</div>
				<div class="cart-empty-message mt-4">${__('Wishlist is empty !')}</div>
			</div>
		`);
	}

});

frappe.ready(() => {
	if (window.location.pathname !== "/wishlist") {
		$(".wishlist").toggleClass('hidden', true);
		wishlist.set_wishlist_count();
	} else {
		wishlist.bind_move_to_cart_action();
		wishlist.bind_remove_action();
	}
});
