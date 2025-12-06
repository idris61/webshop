$(() => {
	class CustomerReviews {
		constructor() {
			this.start = 0;
			this.PAGE_LENGTH = 10;
			this.MAX_RATING = 5;
			this.bind_button_actions();
		}

		bind_button_actions() {
			this.write_review();
			this.view_more();
		}

		write_review() {
			$('.page_content').on('click', '.btn-write-review', (e) => {
				const $btn = $(e.currentTarget);
				const web_item = $btn.attr('data-web-item');

				if (!web_item) {
					console.error("Web item not found");
					return;
				}

				const d = new frappe.ui.Dialog({
					title: __("Write a Review"),
					fields: [
						{fieldname: "title", fieldtype: "Data", label: "Headline", reqd: 1},
						{fieldname: "rating", fieldtype: "Rating", label: "Overall Rating", reqd: 1},
						{fieldtype: "Section Break"},
						{fieldname: "comment", fieldtype: "Small Text", label: "Your Review"}
					],
					primary_action: () => {
						const data = d.get_values();
						if (!data.title || !data.rating) {
							frappe.msgprint({
								message: __("Please fill in all required fields"),
								indicator: "orange",
								title: __("Required Fields")
							});
							return;
						}

						frappe.call({
							method: "webshop.webshop.doctype.item_review.item_review.add_item_review",
							args: {
								web_item: web_item,
								title: data.title,
								rating: data.rating,
								comment: data.comment || ''
							},
							freeze: true,
							freeze_message: __("Submitting Review ..."),
							callback: (r) => {
								try {
									if (!r?.exc) {
										frappe.msgprint({
											message: __("Thank you for submitting your review"),
											title: __("Review Submitted"),
											indicator: "green"
										});
										d.hide();
										location.reload();
									} else {
										frappe.msgprint({
											message: __("Error submitting review. Please try again."),
											indicator: "red",
											title: __("Error")
										});
									}
								} catch (error) {
									console.error("Error submitting review:", error);
									frappe.msgprint({
										message: __("Error submitting review. Please try again."),
										indicator: "red",
										title: __("Error")
									});
								}
							}
						});
					},
					primary_action_label: __("Submit")
				});
				d.show();
			});
		}

		view_more() {
			$('.page_content').on('click', '.btn-view-more', (e) => {
				const $btn = $(e.currentTarget);
				const web_item = $btn.attr('data-web-item');

				if (!web_item) {
					console.error("Web item not found");
					return;
				}

				$btn.prop('disabled', true);

				this.start += this.PAGE_LENGTH;

				frappe.call({
					method: "webshop.webshop.doctype.item_review.item_review.get_item_reviews",
					args: {
						web_item: web_item,
						start: this.start,
						end: this.PAGE_LENGTH
					},
					callback: (result) => {
						try {
							if (result?.message) {
								const res = result.message;
								this.get_user_review_html(res.reviews || []);

								$btn.prop('disabled', false);
								if (res.total_reviews <= (this.start + this.PAGE_LENGTH)) {
									$btn.hide();
								}
							} else {
								$btn.prop('disabled', false);
							}
						} catch (error) {
							console.error("Error loading more reviews:", error);
							$btn.prop('disabled', false);
						}
					}
				});
			});
		}

		get_user_review_html(reviews) {
			if (!reviews || !Array.isArray(reviews) || reviews.length === 0) {
				return;
			}

			const $content = $('.user-reviews');
			if (!$content.length) {
				console.error("User reviews container not found");
				return;
			}

			reviews.forEach((review) => {
				const review_title = this.escapeHtml(review.review_title || '');
				const comment = this.escapeHtml(review.comment || '');
				const customer = this.escapeHtml(review.customer || '');
				const published_on = this.escapeHtml(review.published_on || '');

				$content.append(`
					<div class="mb-3 review">
						<div class="d-flex">
							<p class="mr-4 user-review-title">
								<span>${review_title}</span>
							</p>
							<div class="rating">
								${this.get_review_stars(review.rating || 0)}
							</div>
						</div>

						<div class="product-description mb-4">
							<p>${comment}</p>
						</div>
						<div class="review-signature mb-2">
							<span class="reviewer">${customer}</span>
							<span class="indicator grey" style="--text-on-gray: var(--gray-300);"></span>
							<span class="reviewer">${published_on}</span>
						</div>
					</div>
				`);
			});
		}

		escapeHtml(text) {
			const div = document.createElement('div');
			div.textContent = text;
			return div.innerHTML;
		}

		get_review_stars(rating) {
			const normalizedRating = Math.max(0, Math.min(this.MAX_RATING, Math.floor(rating || 0)));
			let stars = '';

			for (let i = 1; i <= this.MAX_RATING; i++) {
				const fill_class = i <= normalizedRating ? 'star-click' : '';
				stars += `
					<svg class="icon icon-sm ${fill_class}">
						<use href="#icon-star"></use>
					</svg>
				`;
			}
			return stars;
		}
	}

	new CustomerReviews();
});
