# -*- coding: utf-8 -*-
# Copyright (c) 2021, Frappe Technologies Pvt. Ltd. and contributors
# For license information, please see license.txt

import hashlib
import json

import frappe
from frappe.utils import cint, flt

from webshop.webshop.product_data_engine.filters import ProductFiltersBuilder
from webshop.webshop.product_data_engine.query import ProductQuery
from webshop.webshop.doctype.override_doctype.item_group import get_child_groups_for_website

SORT_OPTIONS = {
	"price_asc": ("price_list_rate", False),
	"price_desc": ("price_list_rate", True),
	"name_asc": ("web_item_name", False),
	"name_desc": ("web_item_name", True),
	"new": ("creation", True)
}


def _apply_price_filter_and_sort(items, price_min=None, price_max=None, sort_by=None):
	"""Apply price filtering and sorting in single pass - optimized for performance"""
	if not items:
		return []
	
	min_price = flt(price_min) if price_min else None
	max_price = flt(price_max) if price_max else None
	
	# Filter by price
	if min_price is not None or max_price is not None:
		filtered_items = []
		for item in items:
			price = flt(item.get("price_list_rate") or item.get("formatted_price") or 0)
			if min_price is not None and price < min_price:
				continue
			if max_price is not None and price > max_price:
				continue
			filtered_items.append(item)
		items = filtered_items
	
	# Sort
	if sort_by and sort_by in SORT_OPTIONS:
		sort_field, reverse = SORT_OPTIONS[sort_by]
		items.sort(key=lambda x: flt(x.get(sort_field) or 0), reverse=reverse)
	
	return items


@frappe.whitelist(allow_guest=True)
def get_product_group_counts():
	"""Get product counts by item group for debugging"""
	base_filters = {"published": 1}
	if frappe.db.get_single_value("Webshop Settings", "hide_variants"):
		base_filters["variant_of"] = ["is", "not set"]
	
	# Get all item groups that are shown in website
	item_groups = frappe.get_all(
		"Item Group",
		filters={"show_in_website": 1},
		fields=["name", "item_group_name", "parent_item_group", "is_group"],
		order_by="lft asc"
	)
	
	result = []
	for ig in item_groups:
		# Count via item_group field
		count_via_field = frappe.db.count(
			"Website Item",
			filters={**base_filters, "item_group": ig.name}
		)
		
		# Count via Website Item Group child table
		published_web_items = frappe.get_all(
			"Website Item",
			filters=base_filters,
			pluck="name"
		)
		
		count_via_child_table = 0
		if published_web_items:
			count_via_child_table = frappe.db.count(
				"Website Item Group",
				filters={
					"item_group": ig.name,
					"parent": ["in", published_web_items]
				}
			)
		
		# Get unique count (items that have this group via field OR child table)
		items_via_field = frappe.get_all(
			"Website Item",
			filters={**base_filters, "item_group": ig.name},
			pluck="name"
		)
		
		items_via_child_table = []
		if published_web_items:
			items_via_child_table = frappe.get_all(
				"Website Item Group",
				filters={
					"item_group": ig.name,
					"parent": ["in", published_web_items]
				},
				pluck="parent",
				distinct=True
			)
		
		unique_count = len(set(items_via_field) | set(items_via_child_table))
		
		result.append({
			"name": ig.name,
			"item_group_name": ig.item_group_name,
			"parent_item_group": ig.parent_item_group,
			"is_group": ig.is_group,
			"count_via_field": count_via_field,
			"count_via_child_table": count_via_child_table,
			"unique_count": unique_count
		})
	
	return result


@frappe.whitelist(allow_guest=True)
def get_product_filter_data(query_args=None):
	"""Returns filtered products with caching and sorting support"""
	if not query_args:
		query_args = frappe.utils.get_query_params()
	
	if isinstance(query_args, str):
		query_args = json.loads(query_args)
	
	search = query_args.get("search")
	field_filters = query_args.get("field_filters", {})
	attribute_filters = query_args.get("attribute_filters", {})
	start = 0 if query_args.get("from_filters", False) else cint(query_args.get("start", 0))
	item_group = query_args.get("item_group")
	sort_by = query_args.get("sort_by")
	items_per_page = cint(query_args.get("items_per_page", 0))
	price_min = query_args.get("price_min")
	price_max = query_args.get("price_max")

	sub_categories = []
	if item_group:
		sub_categories = get_child_groups_for_website(item_group, immediate=True)

	engine = ProductQuery()
	
	if sort_by and sort_by not in ["price_asc", "price_desc"]:
		sort_field, reverse = SORT_OPTIONS.get(sort_by, ("ranking", True))
		engine.order_by = f"{sort_field} {'desc' if reverse else 'asc'}"
	elif not sort_by:
		engine.order_by = "ranking desc"
	
	if items_per_page:
		engine.page_length = items_per_page

	try:
		result = engine.query(
			attribute_filters,
			field_filters,
			search_term=search,
			start=start,
			item_group=item_group,
		)
	except Exception as e:
		frappe.log_error(f"Product Query Error: {str(e)}", "Product Query Failed")
		return {"exc": frappe._("Unable to load products. Please try again.")}

	all_items = result.get("items", [])
	
	# Price filter'dan önceki items listesini sakla (filtre sayıları için)
	items_before_price_filter = all_items.copy() if all_items else []
	
	items = _apply_price_filter_and_sort(
		all_items,
		price_min=price_min,
		price_max=price_max,
		sort_by=sort_by
	)
	
	try:
		from webshop.webshop.utils.translation import get_translated_list
		items = get_translated_list(items)
	except Exception as e:
		frappe.log_error(f"Translation error in API: {str(e)}", "Translation Error")
	
	if price_min or price_max:
		original_count = result.get("items_count", 0)
		if len(items) < engine.page_length:
			items_count = start + len(items)
		else:
			items_count = max(original_count, start + len(items))
	else:
		items_count = result.get("items_count", 0)

	filters = {}
	discounts = result.get("discounts", [])
	if discounts:
		filter_engine = ProductFiltersBuilder()
		filters["discount_filters"] = filter_engine.get_discount_filters(discounts)
	
	# Mevcut tüm filtrelerle (search, price, attribute, field) güncellenmiş filtre sayılarını hesapla
	# Query sonuçlarına göre filtre sayılarını güncelle
	current_item_group = None
	if field_filters and "item_group" in field_filters:
		current_item_group = field_filters["item_group"]
		if isinstance(current_item_group, list) and current_item_group:
			current_item_group = current_item_group[0]
	elif item_group:
		current_item_group = item_group
	
	# Mevcut filtrelerle birlikte her filtre seçeneği için sayıları hesapla
	# Her filtre seçeneği, mevcut diğer filtrelerle birlikte seçildiğinde kaç ürün olacağını gösterir
	has_other_filters = search or price_min or price_max or attribute_filters or (field_filters and any(k != "item_group" and k != "product_category" for k in field_filters.keys()))
	has_product_category_filter = field_filters and "product_category" in field_filters
	has_item_group_filter = field_filters and "item_group" in field_filters
	
	# Tüm filtre seçeneklerini al
	if current_item_group:
		updated_filter_engine = ProductFiltersBuilder(item_group=current_item_group)
		all_item_group_filters = updated_filter_engine.get_item_group_filters()
		all_category_filters = updated_filter_engine.get_product_category_filters()
	else:
		updated_filter_engine = ProductFiltersBuilder()
		all_item_group_filters = updated_filter_engine.get_item_group_filters()
		all_category_filters = updated_filter_engine.get_product_category_filters()
	
	# Price filter'dan önceki items listesini kullan (price filter sayıları etkilemesin)
	items_for_counting = items_before_price_filter if items_before_price_filter else items
	
	# Filtreler seçili değilken ve seçiliyken sayıların tutarlı olması için
	# Mevcut items listesi zaten tüm aktif filtrelerle filtrelenmiş
	# Her filtre seçeneği için, mevcut items listesindeki ürünlerin bilgilerine bakarak sayıları hesapla
	# Bu, "bu filtreyi seçersen mevcut filtrelerle birlikte kaç ürün göreceksin" anlamına gelir
	if (has_other_filters or has_product_category_filter or has_item_group_filter) and items_for_counting:
		# Item Group filtrelerini güncelle
		# Her grup için, mevcut items listesindeki ürünlerin item_group bilgilerine bak
		if all_item_group_filters:
			for group in all_item_group_filters:
				# Mevcut items listesindeki ürünlerin item_group'larına bak
				group_items = [item for item in items_for_counting if item.get("item_group") == group.get("name")]
				
				if group.get("children"):
					for child in group.get("children", []):
						child_items = [item for item in items_for_counting if item.get("item_group") == child.get("name")]
						child["count"] = len(child_items)
				group["count"] = len(group_items)
			filters["item_group_filters"] = all_item_group_filters
		else:
			filters["item_group_filters"] = []
		
		# Product Category filtrelerini güncelle
		# Her kategori için, mevcut items listesindeki ürünlerin product_categories bilgilerine bak
		if all_category_filters:
			# Seçili kategorileri al
			selected_categories = []
			if has_product_category_filter and field_filters.get("product_category"):
				selected_categories = field_filters["product_category"] if isinstance(field_filters["product_category"], list) else [field_filters["product_category"]]
			
			for category in all_category_filters:
				category_items = []
				category_name = category.get("name")
				
				# Mevcut items listesindeki ürünlerin product_categories bilgilerine bak
				for item in items_for_counting:
					item_categories = item.get("product_categories", [])
					
					if isinstance(item_categories, list) and len(item_categories) > 0:
						for cat in item_categories:
							if isinstance(cat, dict):
								cat_name = cat.get("product_category") or cat.get("name") or str(cat)
							else:
								cat_name = str(cat) if cat else None
							
							if cat_name and cat_name == category_name:
								category_items.append(item)
								break  # Bu item'ı sadece bir kez say
					elif item_categories:
						cat_name = str(item_categories) if not isinstance(item_categories, dict) else (item_categories.get("product_category") or item_categories.get("name"))
						if cat_name == category_name:
							category_items.append(item)
				
				category["count"] = len(category_items)
			
			# Seçili kategorileri koru (count 0 olsa bile)
			filters["product_category_filters"] = [
				c for c in all_category_filters 
				if c.get("count", 0) > 0 or c.get("name") in selected_categories
			]
		else:
			filters["product_category_filters"] = []
	elif has_other_filters and items_for_counting:
		# Sadece search, price, attribute veya diğer field filtreleri varsa
		# Mevcut items listesindeki ürünlerin bilgilerine göre sayıları güncelle
		if all_item_group_filters:
			for group in all_item_group_filters:
				group_items = [item for item in items_for_counting if item.get("item_group") == group.get("name")]
				if group.get("children"):
					for child in group.get("children", []):
						child_items = [item for item in items_for_counting if item.get("item_group") == child.get("name")]
						child["count"] = len(child_items)
				group["count"] = len(group_items)
			filters["item_group_filters"] = all_item_group_filters
		else:
			filters["item_group_filters"] = []
		
		if all_category_filters:
			for category in all_category_filters:
				category_items = []
				category_name = category.get("name")
				
				for item in items_for_counting:
					item_categories = item.get("product_categories", [])
					
					if isinstance(item_categories, list) and len(item_categories) > 0:
						for cat in item_categories:
							if isinstance(cat, dict):
								cat_name = cat.get("product_category") or cat.get("name") or str(cat)
							else:
								cat_name = str(cat) if cat else None
							
							if cat_name and cat_name == category_name:
								category_items.append(item)
								break
					elif item_categories:
						cat_name = str(item_categories) if not isinstance(item_categories, dict) else (item_categories.get("product_category") or item_categories.get("name"))
						if cat_name == category_name:
							category_items.append(item)
				
				category["count"] = len(category_items)
			
			filters["product_category_filters"] = [c for c in all_category_filters if c.get("count", 0) > 0]
		else:
			filters["product_category_filters"] = []
	else:
		# Hiç aktif filtre yoksa, normal filtreleri al (tüm ürünler için sayılar)
		filters["item_group_filters"] = all_item_group_filters
		filters["product_category_filters"] = all_category_filters
	
	# Field filters her zaman güncellenmiş olarak al
	filter_engine_for_fields = ProductFiltersBuilder(item_group=current_item_group) if current_item_group else ProductFiltersBuilder()
	filters["field_filters"] = filter_engine_for_fields.get_field_filters()

	settings_dict = {
		"enabled": engine.settings.enabled,
		"products_per_page": engine.page_length,
		"enable_attribute_filters": engine.settings.enable_attribute_filters,
		"enable_field_filters": engine.settings.enable_field_filters,
	}

	return {
		"items": items,
		"items_count": items_count,
		"filters": filters,
		"settings": settings_dict,
		"sub_categories": sub_categories,
	}



