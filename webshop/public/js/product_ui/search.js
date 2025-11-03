webshop.ProductSearch = class {
	constructor(opts) {
		$.extend(this, opts);
		this.MAX_RECENT_SEARCHES = 4;
		this.search_box_id = this.search_box_id || "#search-box";
		this.searchBox = $(this.search_box_id);

		this.setupSearchDropDown();
		this.bindSearchAction();
	}

	setupSearchDropDown() {
		this.search_area = $("#dropdownMenuSearch");
		this.setupSearchResultContainer();
		this.populateRecentSearches();
	}

	bindSearchAction() {
		let me = this;

		this.searchBox.on("focus", () => {
			this.search_dropdown.removeClass("hidden");
		});

		$("body").on("click", (e) => {
			let searchEvent = $(e.target).closest(this.search_box_id).length;
			let resultsEvent = $(e.target).closest('#search-results-container').length;
			let isResultHidden = this.search_dropdown.hasClass("hidden");

			if (!searchEvent && !resultsEvent && !isResultHidden) {
				this.search_dropdown.addClass("hidden");
			}
		});

		const performSearch = frappe.utils.debounce((query) => {
			if (query.length < 3 || !query.length) return;

			frappe.call({
				method: "webshop.templates.pages.product_search.search",
				args: { query: query },
				callback: (data) => {
					let product_results = data.message ? data.message.product_results : null;
					let category_results = data.message ? data.message.category_results : null;

					me.populateResults(product_results);

					if (me.category_container) {
						me.populateCategoriesList(category_results);
					}

					if (!$.isEmptyObject(product_results) || !$.isEmptyObject(category_results)) {
						me.setRecentSearches(query);
					}
				}
			});
		}, 200);

		this.searchBox.on("input", (e) => {
			let query = e.target.value;

			if (query.length == 0) {
				me.populateResults(null);
				me.populateCategoriesList(null);
				return;
			}

			if (query.length < 3) return;

			performSearch(query);
			this.search_dropdown.removeClass("hidden");
		});
	}

	setupSearchResultContainer() {
		this.search_dropdown = this.search_area.append(`
			<div class="overflow-hidden shadow dropdown-menu w-100 hidden"
				id="search-results-container"
				aria-labelledby="dropdownMenuSearch"
				style="display: flex; flex-direction: column;">
			</div>
		`).find("#search-results-container");

		this.setupCategoryContainer();
		this.setupProductsContainer();
		this.setupRecentsContainer();
	}

	setupProductsContainer() {
		this.products_container = this.search_dropdown.append(`
			<div id="product-results mt-2">
				<div id="product-scroll" style="overflow: scroll; max-height: 300px">
				</div>
			</div>
		`).find("#product-scroll");
	}

	setupCategoryContainer() {
		this.category_container = this.search_dropdown.append(`
			<div class="category-container mt-2 mb-1">
				<div class="category-chips">
				</div>
			</div>
		`).find(".category-chips");
	}

	setupRecentsContainer() {
		let $recents_section = this.search_dropdown.append(`
			<div class="mb-2 mt-2 recent-searches">
				<div>
					<b>${ __("Recent") }</b>
				</div>
			</div>
		`).find(".recent-searches");

		this.recents_container = $recents_section.append(`
			<div id="recents" style="padding: .25rem 0 1rem 0;">
			</div>
		`).find("#recents");
	}

	getRecentSearches() {
		return JSON.parse(localStorage.getItem("recent_searches") || "[]");
	}

	attachEventListenersToChips() {
		let me = this;
		const chips = $(".recent-search");

		for (let chip of chips) {
			chip.addEventListener("click", () => {
				me.searchBox[0].value = chip.innerText.trim();
				me.searchBox.trigger("input");
				me.searchBox.focus();
			});
		}
	}

	setRecentSearches(query) {
		let recents = this.getRecentSearches();
		
		if (recents.length >= this.MAX_RECENT_SEARCHES) {
			recents.splice(0, 1);
		}

		if (recents.indexOf(query) >= 0) {
			return;
		}

		recents.push(query);
		localStorage.setItem("recent_searches", JSON.stringify(recents));
		this.populateRecentSearches();
	}

	populateRecentSearches() {
		let recents = this.getRecentSearches();

		if (!recents.length) {
			this.recents_container.html(`<span class=""text-muted">${ __("No searches yet.") }</span>`);
			return;
		}

		let html = "";
		recents.forEach((key) => {
			html += `
				<div class="recent-search mr-1" style="font-size: 13px">
					<span class="mr-2">
						<svg width="20" height="20" viewBox="0 0 16 16" fill="none" xmlns="http://www.w3.org/2000/svg">
							<path d="M8 14C11.3137 14 14 11.3137 14 8C14 4.68629 11.3137 2 8 2C4.68629 2 2 4.68629 2 8C2 11.3137 4.68629 14 8 14Z" stroke="var(--gray-500)"" stroke-miterlimit="10" stroke-linecap="round" stroke-linejoin="round"/>
							<path d="M8.00027 5.20947V8.00017L10 10" stroke="var(--gray-500)" stroke-miterlimit="10" stroke-linecap="round" stroke-linejoin="round"/>
						</svg>
					</span>
					${ key }
				</div>
			`;
		});

		this.recents_container.html(html);
		this.attachEventListenersToChips();
	}

	populateResults(product_results) {
		if (!product_results || product_results.length === 0) {
			this.products_container.html('');
			return;
		}

		let html = "";

		product_results.forEach((res) => {
			let thumbnail = res.thumbnail || res.website_image || '/assets/webshop/images/cart-empty-state.png';
			html += `
				<div class="dropdown-item">
					<img class="item-thumb" src="${thumbnail}" alt="${res.web_item_name}" loading="lazy" />
					<div>
						<a href="/${res.route}">${res.web_item_name}</a>
						<span class="brand-line">${res.brand ? "by " + res.brand : ""}</span>
					</div>
				</div>
			`;
		});

		this.products_container.html(html);
	}

	populateCategoriesList(category_results) {
		if (!category_results || category_results.length === 0) {
			this.category_container.html(`
				<div class="category-container mt-2">
					<div class="category-chips"></div>
				</div>
			`);
			return;
		}

		let html = `<div class="mb-2"><b>${ __("Categories") }</b></div>`;

		category_results.forEach((category) => {
			html += `
				<a href="/${category.route}" class="btn btn-sm category-chip mr-2 mb-2" 
					style="font-size: 13px" role="button">
					${ category.name }
				</a>
			`;
		});

		this.category_container.html(html);
	}
};
