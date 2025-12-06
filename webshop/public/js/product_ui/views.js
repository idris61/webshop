webshop.ProductView = class {
	constructor(options) {
		Object.assign(this, options);
		// Default to Grid View if not specified
		this.preference = this.view_type === "grid" ? "Grid View" : (this.view_type === "list" ? "List View" : "Grid View");
		this.make();
	}

	make(from_filters=false) {
		// Optimize: Only clear products area, not toolbar
		if (from_filters) {
			// For filter changes, only clear products area
			$("#products-grid-area, #products-list-area").empty();
			this.show_loading_state();
		} else {
			// For initial load, clear everything
			this.products_section.empty();
			this.prepare_toolbar();
		}
		this.get_item_filter_data(from_filters);
	}

	prepare_toolbar() {
		this.products_section.append(`
			<div class="toolbar d-flex">
			</div>
		`);
		this.prepare_search();
		this.prepare_sort_by();
		this.prepare_show_dropdown();
		this.prepare_product_count();
		this.prepare_view_toggler();

		// Initialize ProductSearch for dropdown and autocomplete
		this.productSearch = new webshop.ProductSearch();
		
		// Also bind search to filter products on the page
		this.bind_search_filter();
	}

	prepare_view_toggler() {

		if (!$("#list").length || !$("#image-view").length) {
			this.render_view_toggler();
			this.bind_view_toggler_actions();
			this.set_view_state();
		}
	}

	get_item_filter_data(from_filters = false) {
		this.from_filters = from_filters;
		const args = this.get_query_filters();

		this.disable_view_toggler(true);
		
		// Show loading indicator during filter/data load
		if (!$('.product-filter-loading').length && from_filters) {
			$('.products-section').prepend('<div class="product-filter-loading text-center py-3"><i class="fa fa-spinner fa-spin"></i> Yükleniyor...</div>');
		}

		frappe.call({
			method: "webshop.webshop.api.get_product_filter_data",
			args: {
				query_args: args
			},
			callback: (result) => {
				try {
					this.hide_loading_state();
					$('.product-filter-loading').remove(); // Remove loading indicator
					
					if (!result || result.exc || !result.message || result.message.exc) {
						this.render_no_products_section(true);
						return;
					}

					const { items, settings, sub_categories, filters } = result.message;

					if (this.item_group && sub_categories?.length) {
						this.render_item_sub_categories(sub_categories);
					}

					if (!items?.length) {
						this.render_no_products_section();
					} else {
						this.re_render_discount_filters(filters?.discount_filters);
						this.render_list_view(items, settings);
						this.render_grid_view(items, settings);
						
						this.products = items;
						this.product_count = result.message.items_count || 0;
						
						// Set initial view state after rendering
						if (!from_filters) {
							this.set_view_state();
						} else {
							// For filter changes, maintain current view state
							this.set_view_state();
						}
					}

					if (!from_filters) {
						this.bind_filters();
						this.restore_filters_state();
					}

					// Filtre sayılarını her zaman güncelle (sayfa yüklendiğinde ve filtre değiştiğinde)
					// restore_filters_state'ten SONRA çağrılmalı ki checkbox'lar işaretlendikten sonra sayılar güncellensin
					if (filters) {
						this.update_filter_counts(filters);
					}

					this.add_paging_section(settings);
				} catch (error) {
					console.error("Product filter data error:", error);
					this.hide_loading_state();
					this.render_no_products_section(true);
				} finally {
					this.disable_view_toggler(false);
					// Re-enable items per page dropdown
					$("#items-per-page-select").prop('disabled', false);
				}
			},
			error: () => {
				this.hide_loading_state();
				$('.product-filter-loading').remove(); // Remove loading indicator on error
				this.disable_view_toggler(false);
				// Re-enable items per page dropdown on error
				$("#items-per-page-select").prop('disabled', false);
			}
		});
	}

	disable_view_toggler(disable=false) {
		$('#list').prop('disabled', disable);
		$('#image-view').prop('disabled', disable);
	}

	render_grid_view(items, settings) {
		// Only create wrapper if it doesn't exist (optimize for filter changes)
		if (!$("#products-grid-area").length) {
			this.prepare_product_area_wrapper("grid");
		} else {
			$("#products-grid-area").empty();
		}

		new webshop.ProductGrid({
			items: items,
			products_section: $("#products-grid-area"),
			settings: settings,
			preference: this.preference
		});
		
		// Ensure grid is visible if it's the default view
		if (this.preference === "Grid View" || !this.preference) {
			$("#products-grid-area").removeClass("hidden");
		}
	}

	render_list_view(items, settings) {
		// Only create wrapper if it doesn't exist (optimize for filter changes)
		if (!$("#products-list-area").length) {
			this.prepare_product_area_wrapper("list");
		} else {
			$("#products-list-area").empty();
		}

		new webshop.ProductList({
			items: items,
			products_section: $("#products-list-area"),
			settings: settings,
			preference: this.preference
		});
		
		// Ensure list is hidden if grid is default
		if (this.preference !== "List View") {
			$("#products-list-area").addClass("hidden");
		}
	}

	prepare_product_area_wrapper(view) {
		let left_margin = view == "list" ? "ml-2" : "";
		let top_margin = view == "list" ? "mt-6" : "mt-minus-1";
		return this.products_section.append(`
			<br>
			<div id="products-${view}-area" class="row products-list ${ top_margin } ${ left_margin }" itemscope itemtype="https://schema.org/Product"></div>
		`);
	}

	get_query_filters() {
		const filters = frappe.utils.get_query_params();
		let {field_filters, attribute_filters, search} = filters;

		field_filters = field_filters ? JSON.parse(field_filters) : {};
		attribute_filters = attribute_filters ? JSON.parse(attribute_filters) : {};

		return {
			field_filters: field_filters,
			attribute_filters: attribute_filters,
			item_group: this.item_group,
			start: filters.start || null,
			from_filters: this.from_filters || false,
			sort_by: filters.sort_by || null,
			items_per_page: filters.items_per_page || null,
			price_min: filters.price_min || null,
			price_max: filters.price_max || null,
			search: search || null
		};
	}

	add_paging_section(settings) {
		$(".product-paging-area").remove();

		if (!this.products || this.product_count === undefined) {
			return;
		}

		const DEFAULT_PAGE_LENGTH = 6;
		const MAX_VISIBLE_PAGES = 7;
		const PAGES_AROUND_CURRENT = 3;

		const query_params = frappe.utils.get_query_params();
		const start = query_params.start ? cint(query_params.start) : 0;
		
		let page_length = query_params.items_per_page ? cint(query_params.items_per_page) : (settings?.products_per_page || DEFAULT_PAGE_LENGTH);
		
		if (page_length === 0) {
			page_length = DEFAULT_PAGE_LENGTH;
		}
		
		let current_page = Math.max(1, Math.floor(start / page_length) + 1);
		const total_pages = Math.max(1, Math.ceil(this.product_count / page_length));
		
		const items_on_page = this.products.length;
		const display_count = this.product_count || 0;
		$('#product-count-text').text(`${items_on_page}/${display_count}`);
		
		let paging_html = `
			<div class="row product-paging-area mt-5">
				<div class="col-12 text-center">
		`;

		if (current_page > 1) {
			const prev_start = Math.max(0, (current_page - 2) * page_length);
			paging_html += `
				<button class="btn btn-sm btn-default btn-page-nav" data-start="${prev_start}">
					${__("Prev")}
				</button>`;
		}
		
		const start_page = Math.max(1, current_page - PAGES_AROUND_CURRENT);
		const end_page = Math.min(total_pages, current_page + PAGES_AROUND_CURRENT);
		
		if (start_page > 1) {
			paging_html += `
				<button class="btn btn-sm btn-outline-secondary btn-page-nav ml-1" data-start="0">
					1
				</button>`;
			if (start_page > 2) {
				paging_html += `<span class="btn btn-sm btn-outline-secondary ml-1" style="border: none; cursor: default;">...</span>`;
			}
		}
		
		for (let page = start_page; page <= end_page; page++) {
			const active_class = page === current_page ? 'btn-primary' : 'btn-outline-secondary';
			paging_html += `
				<button class="btn btn-sm ${active_class} btn-page-nav ml-1" data-start="${(page - 1) * page_length}">
					${page}
				</button>`;
		}

		if (end_page < total_pages) {
			if (end_page < total_pages - 1) {
				paging_html += `<span class="btn btn-sm btn-outline-secondary ml-1" style="border: none; cursor: default;">...</span>`;
			}
			paging_html += `
				<button class="btn btn-sm btn-outline-secondary btn-page-nav ml-1" data-start="${(total_pages - 1) * page_length}">
					${total_pages}
				</button>`;
		}

		if (current_page < total_pages) {
			const next_start = current_page * page_length;
			paging_html += `
				<button class="btn btn-sm btn-default btn-page-nav ml-1" data-start="${next_start}">
					${__("Next")}
				</button>`;
		}

		paging_html += `</div></div>`;

		$(".page_content").append(paging_html);
		this.bind_paging_action();
	}

	prepare_search() {
		const query_params = frappe.utils.get_query_params();
		const current_search = query_params.search || "";
		
		$(".toolbar").append(`
			<div class="input-group search-bar">
				<div class="dropdown w-100" id="dropdownMenuSearch">
					<input type="search" name="query" id="search-box" class="form-control font-md"
						placeholder="${__("Search for Products")}"
						value="${current_search}"
						aria-label="Product" aria-describedby="button-addon2">
					<div class="search-icon">
						<svg xmlns="http://www.w3.org/2000/svg" width="16" height="16" viewBox="0 0 24 24"
							fill="none"
							stroke="currentColor" stroke-width="2" stroke-linecap="round"
							stroke-linejoin="round"
							class="feather feather-search">
							<circle cx="11" cy="11" r="8"></circle>
							<line x1="21" y1="21" x2="16.65" y2="16.65"></line>
						</svg>
					</div>
				</div>
			</div>
		`);
	}

	bind_search_filter() {
		// This handles filtering products on the current page dynamically as user types
		// ProductSearch handles the dropdown autocomplete separately
		const performFilter = frappe.utils.debounce((query) => {
			const query_params = frappe.utils.get_query_params();
			
			if (query && query.trim().length > 0) {
				query_params.search = query.trim();
			} else {
				delete query_params.search;
			}
			
			query_params.start = 0;
			const path = `${window.location.pathname}?${frappe.utils.get_url_from_dict(query_params)}`;
			window.history.pushState({}, '', path);
			this.from_filters = false;
			this.make(true);
		}, 150); // Hızlı yanıt için debounce azaltıldı

		// Dinamik filtreleme - her karakter için otomatik filtrele
		$("#search-box").on("input", (e) => {
			const query = $(e.target).val().trim();
			
			// Boş ise hemen temizle
			if (query.length === 0) {
				performFilter('');
				return;
			}
			
			// Her karakter için filtreleme yap (minimum karakter limiti yok)
			performFilter(query);
		});

		// Enter tuşu için de filtrele (dropdown'ı kapat)
		$("#search-box").on("keypress", (e) => {
			if (e.which === 13) {
				e.preventDefault();
				const query = $(e.target).val().trim();
				if (query && query.length > 0) {
					performFilter(query);
					// Hide the dropdown
					if (this.productSearch && this.productSearch.search_dropdown) {
						this.productSearch.search_dropdown.addClass("hidden");
					}
					// Input focus'u kaldır
					$(e.target).blur();
				}
			}
		});
	}

	prepare_sort_by() {
		const query_params = frappe.utils.get_query_params();
		const current_sort = query_params.sort_by || "default";
		
		const sort_options = [
			{ value: "default", label: __("Default") },
			{ value: "name_asc", label: __("Name: A to Z") },
			{ value: "name_desc", label: __("Name: Z to A") },
			{ value: "price_asc", label: __("Price: Low to High") },
			{ value: "price_desc", label: __("Price: High to Low") },
			{ value: "new", label: __("Newest First") }
		];

		const current_label = sort_options.find(opt => opt.value === current_sort)?.label || __("Default");

		$(".toolbar").append(`
			<div class="toolbar-control-group sort-by-group">
				<label class="toolbar-label">${__("Sort By")}</label>
				<select class="toolbar-select sort-by-select" id="sort-by-select">
					${sort_options.map(opt => `
						<option value="${opt.value}" ${opt.value === current_sort ? 'selected' : ''}>
							${opt.label}
						</option>
					`).join('')}
				</select>
			</div>
		`);

		// Önceki handler'ları temizle (duplicate önlemek için)
		$("#sort-by-select").off('change').on('change', (e) => {
			const sort_value = $(e.target).val();
			const query_params = frappe.utils.get_query_params();
			
			if (sort_value === "default") {
				delete query_params.sort_by;
			} else {
				query_params.sort_by = sort_value;
			}
			
			query_params.start = 0;
			const path = `${window.location.pathname}?${frappe.utils.get_url_from_dict(query_params)}`;
			window.history.pushState({}, '', path);
			
			// Show loading indicator for better UX
			if (!$('.product-filter-loading').length) {
				$('.products-section').prepend('<div class="product-filter-loading text-center py-3"><i class="fa fa-spinner fa-spin"></i> Sıralanıyor...</div>');
			}
			
			// Disable dropdown during load
			$("#sort-by-select").prop('disabled', true);
			
			this.from_filters = false;
			this.make(true);
		});
	}

	prepare_show_dropdown() {
		const query_params = frappe.utils.get_query_params();
		const current_items_per_page = query_params.items_per_page ? cint(query_params.items_per_page) : 6;
		
		const show_options = [6, 12, 24, 48];

		$(".toolbar").append(`
			<div class="toolbar-control-group show-group">
				<label class="toolbar-label">${__("Show")}</label>
				<select class="toolbar-select items-per-page-select" id="items-per-page-select">
					${show_options.map(opt => `
						<option value="${opt}" ${opt === current_items_per_page ? 'selected' : ''}>
							${opt}
						</option>
					`).join('')}
				</select>
			</div>
		`);

		// Optimize: Hızlı items per page değişimi - debounce kaldırıldı, anında çalışıyor
		const performItemsPerPageChange = (items_per_page) => {
			const query_params = frappe.utils.get_query_params();
			
			query_params.items_per_page = items_per_page;
			query_params.start = 0; // İlk sayfaya dön
			const path = `${window.location.pathname}?${frappe.utils.get_url_from_dict(query_params)}`;
			window.history.pushState({}, '', path);
			
			// Show loading indicator
			if (!$('.product-filter-loading').length) {
				$('.products-section').prepend('<div class="product-filter-loading text-center py-3"><i class="fa fa-spinner fa-spin"></i> Yükleniyor...</div>');
			}
			
			// Disable dropdown during load
			$("#items-per-page-select").prop('disabled', true);
			
			this.from_filters = false;
			// Sadece ürün verilerini yeniden yükle, toolbar'ı yeniden oluşturma
			this.get_item_filter_data(false);
		};

		// Önceki handler'ları temizle (duplicate önlemek için)
		$("#items-per-page-select").off('change').on('change', (e) => {
			const items_per_page = $(e.target).val();
			performItemsPerPageChange(items_per_page);
		});
	}

	prepare_product_count() {
		$(".toolbar").append(`
			<div class="product-count-display" id="product-count-display">
				<span id="product-count-text">0/0</span>
			</div>
		`);
	}

	render_view_toggler() {
		$(".toolbar").append(`<div class="view-toggler"></div>`);

		// List view button
		$(".view-toggler").append(`
			<button id="list" class="btn btn-list-view" title="${__('List View')}">
				<svg xmlns="http://www.w3.org/2000/svg" width="16" height="16" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2" stroke-linecap="round" stroke-linejoin="round">
					<line x1="8" y1="6" x2="21" y2="6"></line>
					<line x1="8" y1="12" x2="21" y2="12"></line>
					<line x1="8" y1="18" x2="21" y2="18"></line>
					<line x1="3" y1="6" x2="3.01" y2="6"></line>
					<line x1="3" y1="12" x2="3.01" y2="12"></line>
					<line x1="3" y1="18" x2="3.01" y2="18"></line>
				</svg>
			</button>
		`);

		// Grid view button
		$(".view-toggler").append(`
			<button id="image-view" class="btn btn-grid-view" title="${__('Grid View')}">
				<svg xmlns="http://www.w3.org/2000/svg" width="16" height="16" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2" stroke-linecap="round" stroke-linejoin="round">
					<rect x="3" y="3" width="7" height="7"></rect>
					<rect x="14" y="3" width="7" height="7"></rect>
					<rect x="14" y="14" width="7" height="7"></rect>
					<rect x="3" y="14" width="7" height="7"></rect>
				</svg>
			</button>
		`);
	}

	bind_view_toggler_actions() {
		// Önceki handler'ları temizle (duplicate önlemek için)
		$("#list").off('click').on('click', () => {
			$("#list").addClass('btn-primary');
			$(".btn-grid-view").removeClass('btn-primary');

			$("#products-grid-area").addClass("hidden");
			$("#products-list-area").removeClass("hidden");
			localStorage.setItem("product_view", "List View");
		});

		// Önceki handler'ları temizle (duplicate önlemek için)
		$("#image-view").off('click').on('click', () => {
			$("#image-view").addClass('btn-primary');
			$(".btn-list-view").removeClass('btn-primary');

			$("#products-list-area").addClass("hidden");
			$("#products-grid-area").removeClass("hidden");
			localStorage.setItem("product_view", "Grid View");
		});
	}

	set_view_state() {
		if (this.preference === "List View") {
			$("#list").addClass('btn-primary');
			$("#image-view").removeClass('btn-primary');
			$("#products-grid-area").addClass("hidden");
			$("#products-list-area").removeClass("hidden");
		} else {
			// Default to Grid View
			$("#image-view").addClass('btn-primary');
			$("#list").removeClass('btn-primary');
			$("#products-list-area").addClass("hidden");
			$("#products-grid-area").removeClass("hidden");
		}
	}

	bind_paging_action() {
		$(document).on('click', '.btn-page-nav', (e) => {
			e.preventDefault();
			const $btn = $(e.currentTarget);
			this.from_filters = false;

			$('.btn-page-nav').prop('disabled', true);
			
			const start = $btn.data('start');

			const query_params = frappe.utils.get_query_params();
			query_params.start = start;
			
			const path = `${window.location.pathname}?${frappe.utils.get_url_from_dict(query_params)}`;
			window.history.pushState({}, '', path);
			
			this.make(true);
		});
	}

	update_filter_counts(filters) {
		if (!filters) {
			return;
		}
		
		// Item Group filtrelerinin sayılarını güncelle
		if (filters.item_group_filters && Array.isArray(filters.item_group_filters)) {
			filters.item_group_filters.forEach(group => {
				// Hem parent hem de children için güncelle
				if (group.children && Array.isArray(group.children)) {
					group.children.forEach(child => {
						const $checkbox = $(`input[data-filter-name="item_group"][data-filter-value="${child.name}"]`);
						if ($checkbox.length) {
							const $countSpan = $checkbox.closest('.filter-lookup-wrapper').find('.text-muted');
							if ($countSpan.length) {
								$countSpan.text(`(${child.count || 0})`);
							}
						}
					});
				}
				
				// Parent grup için de güncelle
				const $checkbox = $(`input[data-filter-name="item_group"][data-filter-value="${group.name}"]`);
				if ($checkbox.length) {
					const $countSpan = $checkbox.closest('.filter-lookup-wrapper').find('.text-muted');
					if ($countSpan.length) {
						$countSpan.text(`(${group.count || 0})`);
					}
				}
			});
		}

		// Product Category filtrelerinin sayılarını güncelle
		if (filters.product_category_filters && Array.isArray(filters.product_category_filters)) {
			filters.product_category_filters.forEach(category => {
				const $checkbox = $(`input[data-filter-name="product_category"][data-filter-value="${category.name}"]`);
				if ($checkbox.length) {
					const $countSpan = $checkbox.closest('.filter-lookup-wrapper').find('.text-muted');
					if ($countSpan.length) {
						$countSpan.text(`(${category.count || 0})`);
					}
				}
			});
		}
		
		// Debug: Güncellenen filtre sayılarını logla
		const itemGroupDetails = filters.item_group_filters?.map(g => ({
			name: g.name, 
			count: g.count,
			is_group: g.is_group,
			children: g.children?.map(c => ({name: c.name, count: c.count})) || []
		})) || [];
		
		console.log('=== FILTER COUNTS DEBUG ===');
		console.log('Item Groups:', filters.item_group_filters?.length || 0);
		console.log('Categories:', filters.product_category_filters?.length || 0);
		
		// Her item group için detaylı log
		itemGroupDetails.forEach((group, index) => {
			console.log(`Group ${index + 1}:`, group.name, '-> Count:', group.count, '| Is Group:', group.is_group);
			if (group.children && group.children.length > 0) {
				group.children.forEach((child, childIndex) => {
					console.log(`  Child ${childIndex + 1}:`, child.name, '-> Count:', child.count);
				});
			}
		});
		
		console.log('Full Item Group Details Array:', JSON.stringify(itemGroupDetails, null, 2));
		console.log('===========================');
	}

	re_render_discount_filters(filter_data) {
		this.get_discount_filter_html(filter_data);
		if (this.from_filters) {
			this.bind_discount_filter_action();
		}
		this.restore_discount_filter();
	}

	get_discount_filter_html(filter_data) {
		$("#discount-filters").remove();
		if (filter_data) {
			$("#product-filters").append(`
				<div id="discount-filters" class="mb-4 filter-block pb-5">
					<div class="filter-label mb-3">${ __("Discounts") }</div>
				</div>
			`);

			let html = `<div class="filter-options">`;
			filter_data.forEach(filter => {
				html += `
					<div class="checkbox">
						<label data-value="${ filter[0] }">
							<input type="radio"
								class="product-filter discount-filter"
								name="discount" id="${ filter[0] }"
								data-filter-name="discount"
								data-filter-value="${ filter[0] }"
								style="width: 14px !important"
							>
								<span class="label-area" for="${ filter[0] }">
									${ filter[1] }
								</span>
						</label>
					</div>
				`;
			});
			html += `</div>`;

			$("#discount-filters").append(html);
		}
	}

	restore_discount_filter() {
		const filters = frappe.utils.get_query_params();
		let field_filters = filters.field_filters;
		if (!field_filters) return;

		field_filters = JSON.parse(field_filters);

		if (field_filters && field_filters["discount"]) {
			const values = field_filters["discount"];
			const selector = values.map(value => {
				return `input[data-filter-name="discount"][data-filter-value="${value}"]`;
			}).join(',');
			$(selector).prop('checked', true);
			this.field_filters = field_filters;
		}
	}

	bind_discount_filter_action() {
		let me = this;
		$('.discount-filter').on('change', (e) => {
			const $checkbox = $(e.target);
			const is_checked = $checkbox.is(':checked');
			const { filterValue: filter_value } = $checkbox.data();

			delete this.field_filters["discount"];

			if (is_checked) {
				this.field_filters["discount"] = [filter_value];
			}

			me.change_route_with_filters();
		});
	}

	bind_filters() {
		this.field_filters = {};
		this.attribute_filters = {};

		// Önceki handler'ları temizle (duplicate önlemek için)
		$('.product-filter').off('change').on('change', (e) => {
			this.from_filters = true;

			const $checkbox = $(e.target);
			const is_checked = $checkbox.is(':checked');

			if ($checkbox.is('.attribute-filter')) {
				const {
					attributeName: attribute_name,
					attributeValue: attribute_value
				} = $checkbox.data();

				if (!this.attribute_filters[attribute_name]) {
					this.attribute_filters[attribute_name] = [];
				}

				if (is_checked) {
					if (!this.attribute_filters[attribute_name].includes(attribute_value)) {
						this.attribute_filters[attribute_name].push(attribute_value);
					}
				} else {
					this.attribute_filters[attribute_name] = this.attribute_filters[attribute_name].filter(v => v !== attribute_value);
				}

				if (this.attribute_filters[attribute_name].length === 0) {
					delete this.attribute_filters[attribute_name];
				}
			} else if ($checkbox.is('.field-filter') || $checkbox.is('.discount-filter')) {
				const { filterName: filter_name, filterValue: filter_value } = $checkbox.data();

				if ($checkbox.is('.discount-filter')) {
					delete this.field_filters["discount"];
				}
				
				if (!this.field_filters[filter_name]) {
					this.field_filters[filter_name] = [];
				}
				
				if (is_checked) {
					if (!this.field_filters[filter_name].includes(filter_value)) {
						this.field_filters[filter_name].push(filter_value);
					}
				} else {
					this.field_filters[filter_name] = this.field_filters[filter_name].filter(v => v !== filter_value);
				}

				if (this.field_filters[filter_name].length === 0) {
					delete this.field_filters[filter_name];
				}
			}

			// Anında filtreleme - debounce kaldırıldı
			this.change_route_with_filters();
		});

		// Filtre arama input'u - anında çalışıyor (sadece görsel filtreleme, API çağrısı yok)
		$(document).off('keyup input', '.filter-lookup-input').on('keyup input', '.filter-lookup-input', (e) => {
			const $input = $(e.target);
			const keyword = ($input.val() || '').toLowerCase();
			const $filter_options = $input.next('.filter-options');

			if (!$filter_options.length) {
				return;
			}

			$filter_options.find('.filter-lookup-wrapper').each((i, el) => {
				const $el = $(el);
				const value = ($el.data('value') || '').toLowerCase();
				if (keyword && !value.includes(keyword)) {
					$el.hide();
				} else {
					$el.show();
				}
			});
		});
	}

	change_route_with_filters() {
		const route_params = frappe.utils.get_query_params();
		const start = this.from_filters ? 0 : (this.if_key_exists(route_params.start) || 0);

		const query_params = {
			start: start,
			field_filters: JSON.stringify(this.if_key_exists(this.field_filters) || {}),
			attribute_filters: JSON.stringify(this.if_key_exists(this.attribute_filters) || {}),
		};

		if (route_params.sort_by) query_params.sort_by = route_params.sort_by;
		if (route_params.items_per_page) query_params.items_per_page = route_params.items_per_page;
		if (route_params.search) query_params.search = route_params.search;
		if (route_params.price_min) query_params.price_min = route_params.price_min;
		if (route_params.price_max) query_params.price_max = route_params.price_max;

		const query_string = this.get_query_string(query_params);
		
		window.history.pushState('filters', '', `${location.pathname}?${query_string}`);

		// Show loading indicator for better UX
		if (!$('.product-filter-loading').length) {
			$('.products-section').prepend('<div class="product-filter-loading text-center py-3"><i class="fa fa-spinner fa-spin"></i> Filtreleniyor...</div>');
		}

		// Optimize: Only disable filter inputs, not all inputs
		$('.product-filter').prop('disabled', true);
		this.make(true);
		
		// Re-enable filters after a short delay (will be re-enabled in callback, but this is a safety)
		setTimeout(() => {
			$('.product-filter').prop('disabled', false);
			$('.product-filter-loading').remove();
		}, 100);
	}

	restore_filters_state() {
		const filters = frappe.utils.get_query_params();
		const {field_filters, attribute_filters} = filters;

		if (field_filters) {
			try {
				const parsed = JSON.parse(field_filters);
				for (const fieldname in parsed) {
					const values = parsed[fieldname];
					const selector = values.map(value => 
						`input[data-filter-name="${fieldname}"][data-filter-value="${value}"]`
					).join(',');
					$(selector).prop('checked', true);
				}
				this.field_filters = parsed;
			} catch (error) {
				console.error("Error parsing field_filters:", error);
			}
		}
		
		if (attribute_filters) {
			try {
				const parsed = JSON.parse(attribute_filters);
				for (const attribute in parsed) {
					const values = parsed[attribute];
					const selector = values.map(value => 
						`input[data-attribute-name="${attribute}"][data-attribute-value="${value}"]`
					).join(',');
					$(selector).prop('checked', true);
				}
				this.attribute_filters = parsed;
			} catch (error) {
				console.error("Error parsing attribute_filters:", error);
			}
		}
	}

	show_loading_state() {
		// Remove existing loading state if any
		$("#products-loading-state").remove();
		
		// Show loading skeleton
		const loadingHtml = `
			<div id="products-loading-state" class="row products-list mt-4">
				${Array(6).fill(0).map(() => `
					<div class="col-md-4 mb-4">
						<div class="card" style="height: 400px; background: #f8f9fa; border-radius: 8px;">
							<div class="card-body">
								<div class="skeleton-loader" style="height: 200px; background: linear-gradient(90deg, #f0f0f0 25%, #e0e0e0 50%, #f0f0f0 75%); background-size: 200% 100%; animation: loading 1.5s infinite;"></div>
								<div class="mt-3">
									<div class="skeleton-loader" style="height: 20px; width: 80%; margin-bottom: 10px; background: linear-gradient(90deg, #f0f0f0 25%, #e0e0e0 50%, #f0f0f0 75%); background-size: 200% 100%; animation: loading 1.5s infinite;"></div>
									<div class="skeleton-loader" style="height: 16px; width: 60%; background: linear-gradient(90deg, #f0f0f0 25%, #e0e0e0 50%, #f0f0f0 75%); background-size: 200% 100%; animation: loading 1.5s infinite;"></div>
								</div>
							</div>
						</div>
					</div>
				`).join('')}
			</div>
		`;
		
		$("#products-grid-area, #products-list-area").first().parent().append(loadingHtml);
	}

	hide_loading_state() {
		$("#products-loading-state").remove();
	}

	render_no_products_section(error = false) {
		const error_section = `
			<div class="mt-4 w-100 alert alert-error font-md">
				${__("Something went wrong. Please refresh or contact us.")}
			</div>
		`;
		const no_results_section = `
			<div class="cart-empty frappe-card mt-4">
				<div class="cart-empty-state">
					<img src="/assets/webshop/images/cart-empty-state.png" alt="Empty Cart" loading="lazy">
				</div>
				<div class="cart-empty-message mt-4">${__("No products found")}</div>
			</div>
		`;

		this.products_section.append(error ? error_section : no_results_section);
	}

	render_item_sub_categories(categories) {
		if (!categories?.length) {
			return;
		}

		let sub_group_html = `<div class="sub-category-container scroll-categories">`;

		categories.forEach(category => {
			const route = category.route || '#';
			sub_group_html += `
				<a href="/${route}" style="text-decoration: none;">
					<div class="category-pill">
						${category.name}
					</div>
				</a>
			`;
		});
		
		sub_group_html += `</div>`;
		$("#product-listing").prepend(sub_group_html);
	}

	get_query_string(object) {
		const url = new URLSearchParams();
		for (const key in object) {
			const value = object[key];
			if (value) {
				url.append(key, value);
			}
		}
		return url.toString();
	}

	if_key_exists(obj) {
		if (!obj || typeof obj !== 'object') {
			return undefined;
		}
		
		for (const key in obj) {
			if (Object.prototype.hasOwnProperty.call(obj, key) && obj[key]) {
				return obj;
			}
		}
		return undefined;
	}
};
