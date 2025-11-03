# Copyright (c) 2021, Frappe Technologies Pvt. Ltd. and Contributors
# License: GNU General Public License v3. See license.txt

import json

import frappe
from frappe.utils import cint, cstr
from redis.commands.search.query import Query

from webshop.webshop.redisearch_utils import (
	WEBSITE_ITEM_CATEGORY_AUTOCOMPLETE,
	WEBSITE_ITEM_INDEX,
	WEBSITE_ITEM_NAME_AUTOCOMPLETE,
	is_redisearch_enabled,
)
from webshop.webshop.shopping_cart.product_info import set_product_info_for_website
from webshop.webshop.doctype.override_doctype.item_group import get_item_for_list_in_html

no_cache = 1


def get_context(context):
	context.show_search = True


@frappe.whitelist(allow_guest=True)
def get_product_list(search=None, start=0, limit=12):
	data = get_product_data(search, start, limit)

	for item in data:
		set_product_info_for_website(item)

	return [get_item_for_list_in_html(r) for r in data]


def get_product_data(search=None, start=0, limit=12):
	"""Fetch product data with thumbnail fallback"""
	query = """
		SELECT
			web_item_name, item_name, item_code, brand, route,
			website_image, thumbnail, item_group,
			description, web_long_description as website_description,
			website_warehouse, ranking
		FROM `tabWebsite Item`
		WHERE published = 1
		"""

	if search:
		query += """ and (item_name like %(search)s
				or web_item_name like %(search)s
				or brand like %(search)s
				or web_long_description like %(search)s)"""
		search = "%" + cstr(search) + "%"

	query += """ ORDER BY ranking desc, modified desc limit %s offset %s""" % (
		cint(limit),
		cint(start),
	)

	results = frappe.db.sql(query, {"search": search}, as_dict=1)  # nosemgrep
	
	for item in results:
		if not item.get("thumbnail") and item.get("website_image"):
			item["thumbnail"] = item["website_image"]
		
		if item.get("thumbnail"):
			thumbnail = item["thumbnail"]
			if thumbnail and not thumbnail.startswith("http"):
				item["thumbnail"] = frappe.utils.get_url(thumbnail)
	
	return results


@frappe.whitelist(allow_guest=True)
def search(query):
	product_results = product_search(query)
	category_results = get_category_suggestions(query)

	return {
		"product_results": product_results.get("results") or [],
		"category_results": category_results.get("results") or [],
	}


@frappe.whitelist(allow_guest=True)
def product_search(query, limit=8, fuzzy_search=True):
	"""Search products using RediSearch with SQL fallback"""
	search_results = {"from_redisearch": True, "results": []}

	if not query or len(query) < 3:
		return search_results

	if not is_redisearch_enabled():
		search_results["from_redisearch"] = False
		search_results["results"] = get_product_data(query, 0, limit)
		return search_results

	try:
		redis = frappe.cache()
		cleaned_query = clean_up_query(query)

		redisearch = redis.ft(WEBSITE_ITEM_INDEX)
		suggestions = redisearch.sugget(
			WEBSITE_ITEM_NAME_AUTOCOMPLETE,
			cleaned_query,
			num=limit,
			fuzzy=fuzzy_search and len(query) > 3,
		)

		query_string = cleaned_query
		for s in suggestions:
			query_string += f"|('{clean_up_query(s.string)}')"

		q = Query(query_string)
		results = redisearch.search(q)

		search_results["results"] = list(map(convert_to_dict, results.docs))
		search_results["results"] = sorted(
			search_results["results"], key=lambda k: frappe.utils.cint(k["ranking"]), reverse=True
		)
	except Exception as e:
		frappe.log_error(f"Search error: {str(e)}", "Product Search")
		search_results["from_redisearch"] = False
		search_results["results"] = get_product_data(query, 0, limit)

	return search_results


def clean_up_query(query):
	return "".join(c for c in query if c.isalnum() or c.isspace())


def convert_to_dict(redis_search_doc):
	"""Convert Redis result to dict with thumbnail URL normalization"""
	doc_dict = redis_search_doc.__dict__
	
	if not doc_dict.get("thumbnail") and doc_dict.get("website_image"):
		doc_dict["thumbnail"] = doc_dict["website_image"]
	
	if doc_dict.get("thumbnail"):
		thumbnail = doc_dict["thumbnail"]
		if thumbnail and not thumbnail.startswith("http"):
			doc_dict["thumbnail"] = frappe.utils.get_url(thumbnail)
	
	return doc_dict


@frappe.whitelist(allow_guest=True)
def get_category_suggestions(query, limit=5):
	"""Get category suggestions using RediSearch with SQL fallback"""
	search_results = {"results": []}

	if not query or len(query) < 3:
		return search_results

	try:
		if not is_redisearch_enabled():
			categories = frappe.db.get_all(
				"Item Group",
				filters={"name": ["like", "%{0}%".format(query)], "show_in_website": 1},
				fields=["name", "route"],
				limit=limit,
			)
			search_results["results"] = categories
			return search_results

		ac = frappe.cache().ft()
		suggestions = ac.sugget(WEBSITE_ITEM_CATEGORY_AUTOCOMPLETE, query, num=limit, with_payloads=True)

		results = [json.loads(s.payload) for s in suggestions]
		search_results["results"] = results
	except Exception as e:
		frappe.log_error(f"Category search error: {str(e)}", "Category Search")
		search_results["results"] = []

	return search_results
