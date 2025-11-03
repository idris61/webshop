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
	"""Apply price filtering and sorting in single pass"""
	if not items:
		return []
	
	min_price = flt(price_min) if price_min else None
	max_price = flt(price_max) if price_max else None
	price_sort = sort_by in ["price_asc", "price_desc"]
	
	if not (price_min or price_max or price_sort):
		return items
	
	processed_items = []
	for item in items:
		price_val = flt(item.get("price_list_rate", 0))
		
		if min_price and price_val > 0 and price_val < min_price:
			continue
		if max_price and price_val > 0 and price_val > max_price:
			continue
		if (min_price or max_price) and price_val == 0:
			continue
		
		if price_sort:
			processed_items.append((price_val, item))
		else:
			processed_items.append(item)
	
	if price_sort:
		sort_key, reverse = SORT_OPTIONS[sort_by]
		processed_items.sort(key=lambda x: x[0], reverse=reverse)
		return [item for _, item in processed_items]
	
	return processed_items


def _generate_cache_key(query_args):
	"""Generate MD5 cache key from query arguments"""
	key_parts = []
	for k in sorted(query_args.keys()):
		val = query_args[k]
		if isinstance(val, dict):
			val = json.dumps(val, sort_keys=True)
		key_parts.append(f"{k}:{val}")
	
	cache_string = "|".join(key_parts)
	cache_hash = hashlib.md5(cache_string.encode()).hexdigest()
	return f"product_filter:{cache_hash}"


@frappe.whitelist(allow_guest=True)
def get_product_filter_data(query_args=None):
	"""Returns filtered products with caching and sorting support"""
	if isinstance(query_args, str):
		query_args = json.loads(query_args)

	query_args = frappe._dict(query_args or {})
	cache_key = _generate_cache_key(query_args)
	
	cached_result = frappe.cache().get_value(cache_key)
	if cached_result and not frappe.conf.developer_mode:
		return json.loads(cached_result)

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

	items = _apply_price_filter_and_sort(
		result.get("items", []),
		price_min=price_min,
		price_max=price_max,
		sort_by=sort_by
	)
	
	items_count = len(items) if (price_min or price_max) else result.get("items_count", 0)

	filters = {}
	discounts = result.get("discounts", [])
	if discounts:
		filter_engine = ProductFiltersBuilder()
		filters["discount_filters"] = filter_engine.get_discount_filters(discounts)

	response = {
		"items": items,
		"filters": filters,
		"settings": engine.settings,
		"sub_categories": sub_categories,
		"items_count": items_count,
	}
	
	if not frappe.conf.developer_mode:
		frappe.cache().set_value(cache_key, json.dumps(response, default=str), expires_in_sec=300)
	
	return response


@frappe.whitelist(allow_guest=True)
def get_guest_redirect_on_action():
	return frappe.db.get_single_value("Webshop Settings", "redirect_on_action")
