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


def _calculate_filter_counts(field_filters=None, attribute_filters=None, search_term=None, 
							item_group=None, price_min=None, price_max=None, items_before_price_filter=None):
	"""
	Her filtre seçeneği için veritabanından doğru sayıyı hesapla.
	Mantık: "Bu filtreyi seçersen mevcut diğer filtrelerle birlikte kaç ürün göreceksin"
	"""
	from webshop.webshop.doctype.override_doctype.item_group import get_child_groups_for_website
	
	filters = {}
	
	# Mevcut aktif filtreleri belirle (item_group ve product_category hariç - bunlar sayıları hesaplarken değişecek)
	has_other_filters = bool(
		search_term or 
		price_min or 
		price_max or 
		attribute_filters or 
		(field_filters and any(k not in ["item_group", "product_category"] for k in field_filters.keys()))
	)
	
	# Seçili item_group veya product_category filtresi var mı?
	has_item_group_filter = bool(field_filters and "item_group" in field_filters)
	has_product_category_filter = bool(field_filters and "product_category" in field_filters)
	
	# Eğer item_group veya product_category filtresi seçiliyse, sayıları hesaplamalıyız
	# Çünkü seçili filtre için sayı, o filtre seçiliyken kaç ürün olduğunu göstermeli
	has_active_filters = has_other_filters or has_item_group_filter or has_product_category_filter
	
	# Tüm filtre seçeneklerini al
	filter_engine = ProductFiltersBuilder()
	all_item_group_filters = filter_engine.get_item_group_filters()
	all_category_filters = filter_engine.get_product_category_filters()
	
	# Base filters - her zaman uygulanacak
	base_filters = {"published": 1, "variant_of": ["is", "not set"]}
	
	# Eğer hiç aktif filtre yoksa, orijinal sayıları kullan
	# ÖNEMLİ: Sadece gerçekten hiç filtre yoksa orijinal sayıları kullan
	# Eğer sadece item_group veya product_category seçiliyse, sayıları hesaplamalıyız
	if not has_active_filters:
		filters["item_group_filters"] = all_item_group_filters
		filters["product_category_filters"] = all_category_filters
		frappe.log_error("FILTER_COUNT: No active filters, using original counts", "FILTER_DEBUG")
		return filters
	
	# DEBUG: Aktif filtre durumunu logla
	frappe.log_error(
		f"FILTER_COUNT: Active filters detected - has_other_filters: {has_other_filters}, "
		f"has_item_group_filter: {has_item_group_filter}, "
		f"has_product_category_filter: {has_product_category_filter}, "
		f"field_filters: {field_filters}",
		"FILTER_DEBUG"
	)
	
	# Mevcut filtreleri hazırla (item_group ve product_category hariç)
	# Frappe'de filters hem dict hem de list olabilir
	# Base filters'i list formatına çevir
	current_filters = []
	for key, value in base_filters.items():
		if isinstance(value, list):
			# ["is", "not set"] veya ["in", [...]] formatı
			if len(value) == 2:
				current_filters.append([key] + value)
			elif len(value) == 3:
				# Zaten bir filter condition formatında
				current_filters.append([key] + value)
			else:
				current_filters.append([key, "=", value])
		else:
			current_filters.append([key, "=", value])
	
	current_or_filters = []
	
	# Search filter
	if search_term:
		search_term = search_term.strip()
		if search_term:
			current_or_filters.append(["item_code", "like", f"{search_term}%"])
			current_or_filters.append(["item_code", "=", search_term])
			search_pattern = f"%{search_term}%"
			for field in ["item_name", "web_long_description", "item_group"]:
				current_or_filters.append([field, "like", search_pattern])
	
	# Attribute filters
	if attribute_filters:
		item_codes = []
		for attribute, values in attribute_filters.items():
			if not isinstance(values, list):
				values = [values]
			attr_item_codes = frappe.get_all(
				"Item",
				filters=[
					["published_in_website", "=", 1],
					["Item Variant Attribute", "attribute", "=", attribute],
					["Item Variant Attribute", "attribute_value", "in", values],
				],
				pluck="item_code"
			)
			item_codes.append(set(attr_item_codes))
		
		if item_codes:
			item_codes = list(set.intersection(*item_codes))
			current_filters.append(["item_code", "in", item_codes])
	
	# Diğer field filters (item_group ve product_category hariç)
	if field_filters:
		meta = frappe.get_meta("Website Item", cached=True)
		for field, values in field_filters.items():
			if field in ["item_group", "product_category"] or not values or field == "discount" or field.startswith("_"):
				continue
			
			df = meta.get_field(field)
			if not df:
				continue
			
			if df.fieldtype == "Check":
				if isinstance(values, list):
					normalized_values = []
					for v in values:
						if v in ["Yes", "yes", "1", 1]:
							normalized_values.append(1)
						elif v in ["No", "no", "0", 0]:
							normalized_values.append(0)
						else:
							normalized_values.append(v)
					current_filters.append([field, "in", normalized_values])
				else:
					if values in ["Yes", "yes", "1", 1]:
						current_filters.append([field, "=", 1])
					elif values in ["No", "no", "0", 0]:
						current_filters.append([field, "=", 0])
					else:
						current_filters.append([field, "=", values])
			elif field == "primary_supplier":
				# Supplier filter için özel işlem
				base_filters_list = []
				for key, value in base_filters.items():
					if isinstance(value, list) and len(value) == 2:
						# ["in", [...]] veya ["is", "not set"] formatı
						base_filters_list.append([key] + value)
					else:
						base_filters_list.append([key, "=", value])
				
				website_items = frappe.get_all(
					"Website Item",
					filters=base_filters_list,
					pluck="name"
				)
				if website_items:
					suppliers = frappe.get_all(
						"Website Item Supplier",
						filters={"parent": ["in", website_items], "supplier": ["in", values if isinstance(values, list) else [values]]},
						pluck="parent",
						distinct=True
					)
					if suppliers:
						current_filters.append(["name", "in", suppliers])
					else:
						current_filters.append(["name", "=", "__no_item__"])
			elif df.fieldtype == "Table MultiSelect":
				child_doctype = df.options
				child_meta = frappe.get_meta(child_doctype, cached=True)
				child_fields = child_meta.get("fields")
				if child_fields:
					current_filters.append([child_doctype, child_fields[0].fieldname, "in", values if isinstance(values, list) else [values]])
			elif isinstance(values, list):
				current_filters.append([field, "in", values])
			else:
				current_filters.append([field, "=", values])
	
	# Item Group filtre sayılarını hesapla
	if all_item_group_filters:
		# Seçili item_group filtresini al
		selected_item_groups = []
		if has_item_group_filter and field_filters.get("item_group"):
			selected_item_groups = field_filters["item_group"] if isinstance(field_filters["item_group"], list) else [field_filters["item_group"]]
		
		# Seçili grupların tüm child gruplarını da topla (çünkü seçili grup child'ları da içeriyor olabilir)
		all_selected_groups = set(selected_item_groups)
		for selected_group in selected_item_groups:
			# Seçili grubun child'larını da ekle
			is_selected_group = frappe.db.get_value("Item Group", selected_group, "is_group")
			if is_selected_group:
				child_groups = get_child_groups_for_website(selected_group, include_self=False)
				all_selected_groups.update([cg.name for cg in child_groups])
		
		frappe.log_error(f"FILTER_COUNT: Calculating item_group counts with filters: {len(current_filters)}, or_filters: {len(current_or_filters)}, selected_groups: {selected_item_groups}, all_selected: {all_selected_groups}", "FILTER_DEBUG")
		
		for group in all_item_group_filters:
			group_name = group.get("name")
			is_group = group.get("is_group", False)
			is_selected = group_name in selected_item_groups
			
			# Bu grup için filtreleri hazırla
			group_filters = current_filters.copy()
			
			# Bu gruba ait tüm item_group'ları topla
			all_groups_for_count = [group_name]
			if is_group:
				child_groups = get_child_groups_for_website(group_name, include_self=False)
				all_groups_for_count.extend([cg.name for cg in child_groups])
			
			all_groups_for_count = list(set(all_groups_for_count))
			
			# Veritabanından say
			# ÖNEMLİ: frappe.db.count or_filters parametresini desteklemiyor!
			# Bu yüzden frappe.get_all kullanıp len() ile saymalıyız
			# Ayrıca, child table filtreleri için özel işlem yapmalıyız
			
			# İki yöntemle say: item_group field'ından ve Website Item Group child table'ından
			items_via_field = []
			items_via_child_table = []
			
			# 1. item_group field'ından say
			field_filters = group_filters.copy()
			field_filters.append(["item_group", "in", all_groups_for_count])
			# ÖNEMLİ: current_or_filters (search filtreleri) de uygulanmalı!
			
			# DEBUG: Önce direkt test sorgusu yap (basit)
			test_simple = frappe.get_all(
				"Website Item",
				filters=[
					["published", "=", 1],
					["variant_of", "is", "not set"],
					["item_group", "in", all_groups_for_count]
				],
				pluck="name",
				limit=10
			)
			
			# Şimdi bizim filtrelerle test et
			get_all_kwargs = {
				"doctype": "Website Item",
				"filters": field_filters,
				"pluck": "name",
				"distinct": True
			}
			if current_or_filters:
				get_all_kwargs["or_filters"] = current_or_filters
			
			try:
				items_via_field = frappe.get_all(**get_all_kwargs)
			except Exception as e:
				frappe.log_error(
					f"FILTER_QUERY_ERROR: Group '{group_name}' query failed. "
					f"Filters: {field_filters}, OR filters: {current_or_filters}, Error: {str(e)}",
					"FILTER_QUERY_ERROR"
				)
				items_via_field = []
			
			# DEBUG: Her zaman karşılaştır (sorun tespiti için)
			frappe.log_error(
				f"FILTER_COMPARE: Group '{group_name}' - Simple query: {len(test_simple)} items ({test_simple[:3] if test_simple else []}), "
				f"Our query: {len(items_via_field)} items ({items_via_field[:3] if items_via_field else []}). "
				f"Simple filters: [['published', '=', 1], ['variant_of', 'is', 'not set'], ['item_group', 'in', {all_groups_for_count}]]. "
				f"Our filters: {field_filters}. "
				f"Group filters (base): {group_filters}. "
				f"OR filters: {current_or_filters}",
				"FILTER_COMPARE"
			)
			
			# 2. Website Item Group child table'ından say
			# Önce base filtrelerle eşleşen Website Item'ları al (search filtreleri dahil)
			base_items_kwargs = {
				"doctype": "Website Item",
				"filters": group_filters,
				"pluck": "name"
			}
			if current_or_filters:
				base_items_kwargs["or_filters"] = current_or_filters
			base_items = frappe.get_all(**base_items_kwargs)
			
			if base_items:
				# Sonra bu item'ların Website Item Group child table'ında bu gruba ait olanlarını bul
				child_table_items = frappe.get_all(
					"Website Item Group",
					filters={
						"parent": ["in", base_items],
						"item_group": ["in", all_groups_for_count]
					},
					pluck="parent",
					distinct=True
				)
				items_via_child_table = child_table_items
			
			# İki listeyi birleştir ve unique count al
			all_items = set(items_via_field) | set(items_via_child_table)
			count = len(all_items)
			
			# DEBUG: Her zaman detaylı log (sorun tespiti için)
			# Özellikle seçili grup veya count 0 olan grup için detaylı log
			if is_selected or count == 0:
				# Sorguyu tekrar test et (debug için) - direkt test
				test_query_direct = frappe.get_all(
					"Website Item",
					filters=[
						["published", "=", 1],
						["variant_of", "is", "not set"],
						["item_group", "in", all_groups_for_count]
					],
					pluck="name",
					limit=5
				)
				
				# Sorguyu tekrar test et (debug için) - bizim filtrelerle
				test_query_with_filters = []
				try:
					test_query_with_filters = frappe.get_all(
						"Website Item",
						filters=field_filters,
						or_filters=current_or_filters if current_or_filters else None,
						pluck="name",
						limit=5
					)
				except Exception as e:
					test_query_with_filters = f"ERROR: {str(e)}"
				
				frappe.log_error(
					f"FILTER_COUNT_DETAIL: Group '{group_name}' -> {count} | "
					f"Selected: {is_selected} | "
					f"Has other filters: {has_other_filters} | "
					f"Groups: {all_groups_for_count} | "
					f"Via field: {len(items_via_field)} ({items_via_field[:3] if items_via_field else []}) | "
					f"Via child table: {len(items_via_child_table)} ({items_via_child_table[:3] if items_via_child_table else []}) | "
					f"Direct test query: {len(test_query_direct) if isinstance(test_query_direct, list) else 0} items ({test_query_direct[:3] if isinstance(test_query_direct, list) and test_query_direct else []}) | "
					f"Test query with filters: {len(test_query_with_filters) if isinstance(test_query_with_filters, list) else 'ERROR'} items | "
					f"Group filters: {group_filters} | "
					f"Field filters (final): {field_filters} | "
					f"OR filters: {current_or_filters}",
					"FILTER_COUNT_DETAIL"
				)
			
			group["count"] = count
			
			# Children için de say
			if group.get("children"):
				for child in group.get("children", []):
					child_name = child.get("name")
					child_is_selected = child_name in selected_item_groups
					
					child_filters = current_filters.copy()
					
					# Child grup için de aynı mantık: field ve child table'dan say
					child_items_via_field = []
					child_items_via_child_table = []
					
					# 1. item_group field'ından say
					child_field_filters = child_filters.copy()
					child_field_filters.append(["item_group", "=", child_name])
					# ÖNEMLİ: current_or_filters (search filtreleri) de uygulanmalı!
					child_get_all_kwargs = {
						"doctype": "Website Item",
						"filters": child_field_filters,
						"pluck": "name",
						"distinct": True
					}
					if current_or_filters:
						child_get_all_kwargs["or_filters"] = current_or_filters
					child_items_via_field = frappe.get_all(**child_get_all_kwargs)
					
					# 2. Website Item Group child table'ından say
					# Önce base filtrelerle eşleşen Website Item'ları al (search filtreleri dahil)
					child_base_items_kwargs = {
						"doctype": "Website Item",
						"filters": child_filters,
						"pluck": "name"
					}
					if current_or_filters:
						child_base_items_kwargs["or_filters"] = current_or_filters
					child_base_items = frappe.get_all(**child_base_items_kwargs)
					
					if child_base_items:
						child_table_items = frappe.get_all(
							"Website Item Group",
							filters={
								"parent": ["in", child_base_items],
								"item_group": ["=", child_name]
							},
							pluck="parent",
							distinct=True
						)
						child_items_via_child_table = child_table_items
					
					# İki listeyi birleştir ve unique count al
					child_all_items = set(child_items_via_field) | set(child_items_via_child_table)
					child_count = len(child_all_items)
					child["count"] = child_count
					
					frappe.log_error(f"FILTER_COUNT: Child Group '{child_name}' -> {child_count} (selected: {child_is_selected})", "FILTER_DEBUG")
		
		# Seçili grupları koru (count 0 olsa bile)
		# Parent ve child gruplar için seçili kontrolü yap
		def should_include_group(group):
			if group.get("count", 0) > 0:
				return True
			if group.get("name") in selected_item_groups:
				return True
			# Child gruplar için de kontrol et
			if group.get("children"):
				for child in group.get("children", []):
					if child.get("name") in selected_item_groups:
						return True
			return False
		
		filters["item_group_filters"] = [
			g for g in all_item_group_filters 
			if should_include_group(g)
		]
	else:
		filters["item_group_filters"] = []
	
	# Product Category filtre sayılarını hesapla (optimize edilmiş - tek sorguda tüm kategoriler)
	if all_category_filters:
		frappe.log_error(f"FILTER_COUNT: Calculating product_category counts with filters: {len(current_filters)}, or_filters: {len(current_or_filters)}", "FILTER_DEBUG")
		
		# Önce mevcut filtrelerle eşleşen tüm Website Item'ları al
		matching_web_items = frappe.get_all(
			"Website Item",
			filters=current_filters,
			or_filters=current_or_filters,
			pluck="name"
		)
		
		if matching_web_items:
			# Tüm kategoriler için tek sorguda say (performans optimizasyonu)
			category_names = [cat.get("name") for cat in all_category_filters]
			
			# Tüm kategoriler için eşleşen ürünleri tek sorguda al
			category_data = frappe.get_all(
				"Item Product Category",
				filters={
					"parent": ["in", matching_web_items],
					"parenttype": "Website Item",
					"parentfield": "product_categories",
					"product_category": ["in", category_names]
				},
				fields=["product_category", "parent"],
				distinct=True
			)
			
			# Her kategori için say
			for category in all_category_filters:
				category_name = category.get("name")
				category_count = len([item for item in category_data if item.product_category == category_name])
				category["count"] = category_count
				frappe.log_error(f"FILTER_COUNT: Category '{category_name}' -> {category_count}", "FILTER_DEBUG")
		else:
			# Eğer mevcut filtrelerle eşleşen ürün yoksa, tüm kategorilerin sayısı 0
			for category in all_category_filters:
				category["count"] = 0
		
		# Seçili kategorileri koru (count 0 olsa bile)
		selected_categories = []
		if field_filters and "product_category" in field_filters:
			selected_categories = field_filters["product_category"] if isinstance(field_filters["product_category"], list) else [field_filters["product_category"]]
		
		filters["product_category_filters"] = [
			c for c in all_category_filters 
			if c.get("count", 0) > 0 or c.get("name") in selected_categories
		]
	else:
		filters["product_category_filters"] = []
	
	return filters


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
	
	# Filtre sayılarını veritabanından doğru şekilde hesapla
	# Her filtre seçeneği için: "Bu filtreyi seçersen mevcut diğer filtrelerle birlikte kaç ürün göreceksin"
	calculated_filters = _calculate_filter_counts(
		field_filters=field_filters,
		attribute_filters=attribute_filters,
		search_term=search,
		item_group=item_group,
		price_min=price_min,
		price_max=price_max,
		items_before_price_filter=items_before_price_filter
	)
	
	# Discount filters
	filters = calculated_filters.copy()
	discounts = result.get("discounts", [])
	if discounts:
		filter_engine = ProductFiltersBuilder()
		filters["discount_filters"] = filter_engine.get_discount_filters(discounts)
	
	# Field filters her zaman güncellenmiş olarak al
	current_item_group = None
	if field_filters and "item_group" in field_filters:
		current_item_group = field_filters["item_group"]
		if isinstance(current_item_group, list) and current_item_group:
			current_item_group = current_item_group[0]
	elif item_group:
		current_item_group = item_group
	
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



