webshop.ProductSearch = class {
	constructor(opts) {
		$.extend(this, opts);
		this.MAX_RECENT_SEARCHES = 4;
		this.MIN_SEARCH_LENGTH = 1; // Her karakter için anında arama
		this.SEARCH_DEBOUNCE_MS = 100; // Daha hızlı yanıt için debounce azaltıldı
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
		this.searchBox.on("focus", () => {
			this.search_dropdown.removeClass("hidden");
		});

		$("body").on("click", (e) => {
			const searchEvent = $(e.target).closest(this.search_box_id).length;
			const resultsEvent = $(e.target).closest('#search-results-container').length;
			const isResultHidden = this.search_dropdown.hasClass("hidden");

			if (!searchEvent && !resultsEvent && !isResultHidden) {
				this.search_dropdown.addClass("hidden");
			}
		});

		const performSearch = frappe.utils.debounce((query) => {
			if (!query || query.length === 0) {
				this.populateResults(null);
				this.populateCategoriesList(null);
				return;
			}

			frappe.call({
				method: "webshop.templates.pages.product_search.search",
				args: { query: query },
				callback: (data) => {
					try {
						const product_results = data?.message?.product_results || null;
						const category_results = data?.message?.category_results || null;

						this.populateResults(product_results);

						if (this.category_container) {
							this.populateCategoriesList(category_results);
						}

						if (product_results?.length || category_results?.length) {
							this.setRecentSearches(query);
						}
					} catch (error) {
						console.error("Search error:", error);
					}
				}
			});
		}, this.SEARCH_DEBOUNCE_MS);

		this.searchBox.on("input", (e) => {
			const query = e.target.value.trim();

			if (query.length === 0) {
				this.populateResults(null);
				this.populateCategoriesList(null);
				this.search_dropdown.removeClass("hidden"); // Recent searches'ı göster
				return;
			}

			// Her karakter için anında arama yap
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
		const $recents_section = this.search_dropdown.append(`
			<div class="mb-2 mt-2 recent-searches">
				<div>
					<b>${__("Recent")}</b>
				</div>
			</div>
		`).find(".recent-searches");

		this.recents_container = $recents_section.append(`
			<div id="recents" style="padding: .25rem 0 1rem 0;">
			</div>
		`).find("#recents");
	}

	getRecentSearches() {
		try {
			return JSON.parse(localStorage.getItem("recent_searches") || "[]");
		} catch (error) {
			console.error("Error parsing recent searches:", error);
			return [];
		}
	}

	attachEventListenersToChips() {
		const chips = $(".recent-search");

		chips.on('click', (e) => {
			const chip = e.currentTarget;
			this.searchBox[0].value = chip.innerText.trim();
			this.searchBox.trigger("input");
			this.searchBox.focus();
		});
	}

	setRecentSearches(query) {
		const recents = this.getRecentSearches();
		
		if (recents.length >= this.MAX_RECENT_SEARCHES) {
			recents.shift();
		}

		if (recents.includes(query)) {
			return;
		}

		recents.push(query);
		try {
			localStorage.setItem("recent_searches", JSON.stringify(recents));
			this.populateRecentSearches();
		} catch (error) {
			console.error("Error saving recent searches:", error);
		}
	}

	populateRecentSearches() {
		const recents = this.getRecentSearches();

		if (!recents.length) {
			this.recents_container.html(`<span class="text-muted">${__("No searches yet.")}</span>`);
			return;
		}

		let html = "";
		recents.forEach((key) => {
			html += `
				<div class="recent-search mr-1" style="font-size: 13px; cursor: pointer;">
					<span class="mr-2">
						<svg width="20" height="20" viewBox="0 0 16 16" fill="none" xmlns="http://www.w3.org/2000/svg">
							<path d="M8 14C11.3137 14 14 11.3137 14 8C14 4.68629 11.3137 2 8 2C4.68629 2 2 4.68629 2 8C2 11.3137 4.68629 14 8 14Z" stroke="var(--gray-500)" stroke-miterlimit="10" stroke-linecap="round" stroke-linejoin="round"/>
							<path d="M8.00027 5.20947V8.00017L10 10" stroke="var(--gray-500)" stroke-miterlimit="10" stroke-linecap="round" stroke-linejoin="round"/>
						</svg>
					</span>
					${key}
				</div>
			`;
		});

		this.recents_container.html(html);
		this.attachEventListenersToChips();
	}

	populateResults(product_results) {
		if (!product_results?.length) {
			this.products_container.html('');
			return;
		}

		let html = "";

		product_results.forEach((res) => {
			const thumbnail = res.thumbnail || res.website_image || '/assets/webshop/images/cart-empty-state.png';
			const route = res.route || '#';
			const brandLine = res.brand ? `by ${res.brand}` : '';
			const itemCode = res.item_code || '';
			
			html += `
				<div class="dropdown-item">
					<img class="item-thumb" src="${thumbnail}" alt="${res.web_item_name || ''}" loading="lazy" />
					<div>
						<a href="/${route}">${res.web_item_name || res.item_name || ''}</a>
						${itemCode ? `<div class="text-muted small">${itemCode}</div>` : ''}
						${brandLine ? `<span class="brand-line">${brandLine}</span>` : ''}
					</div>
				</div>
			`;
		});

		this.products_container.html(html);
	}

	populateCategoriesList(category_results) {
		if (!category_results?.length) {
			this.category_container.html('');
			return;
		}

		let html = `<div class="mb-2"><b>${__("Categories")}</b></div>`;

		category_results.forEach((category) => {
			const route = category.route || '#';
			html += `
				<a href="/${route}" class="btn btn-sm category-chip mr-2 mb-2" 
					style="font-size: 13px" role="button">
					${category.name || ''}
				</a>
			`;
		});

		this.category_container.html(html);
	}
};
