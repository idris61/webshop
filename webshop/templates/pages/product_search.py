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

no_cache = 1


def get_context(context):
	context.show_search = True


def get_product_data(search=None, start=0, limit=15):
	"""Fetch product data with thumbnail fallback - improved search with item code and word-by-word matching"""
	query = """
		SELECT
			wi.web_item_name, wi.item_name, wi.item_code, wi.brand, wi.route,
			wi.website_image, wi.thumbnail, wi.item_group,
			wi.description as website_description,
			wi.website_warehouse, wi.ranking
		FROM `tabWebsite Item` wi
		WHERE wi.published = 1
		"""

	if search:
		search = cstr(search).strip()
		search_words = search.split()
		
		if search_words:
			# Her kelime için ayrı arama koşulları oluştur
			word_conditions = []
			search_params = []
			
			for word in search_words:
				word_pattern = f"%{word}%"
				# Her kelimeyi tüm alanlarda ara (item_code dahil)
				word_conditions.append("""(
					wi.item_name LIKE %s
					OR wi.web_item_name LIKE %s
					OR wi.item_code LIKE %s
					OR wi.brand LIKE %s
					OR wi.description LIKE %s
				)""")
				# Her kelime için 5 parametre ekle
				search_params.extend([word_pattern] * 5)
			
			# Tüm kelimelerin eşleşmesi için AND kullan (daha doğru sonuçlar)
			if word_conditions:
				query += " AND " + " AND ".join(word_conditions)
				query += f" ORDER BY wi.ranking desc, wi.modified desc limit {cint(limit)} offset {cint(start)}"
				results = frappe.db.sql(query, tuple(search_params), as_dict=1)  # nosemgrep
			else:
				query += f" ORDER BY wi.ranking desc, wi.modified desc limit {cint(limit)} offset {cint(start)}"
				results = frappe.db.sql(query, {}, as_dict=1)  # nosemgrep
		else:
			query += f" ORDER BY wi.ranking desc, wi.modified desc limit {cint(limit)} offset {cint(start)}"
			results = frappe.db.sql(query, {}, as_dict=1)  # nosemgrep
	else:
		query += f" ORDER BY wi.ranking desc, wi.modified desc limit {cint(limit)} offset {cint(start)}"
		results = frappe.db.sql(query, {}, as_dict=1)  # nosemgrep
	
	for item in results:
		# Eğer website_image yoksa, thumbnail'i kullan
		if not item.get("website_image") and item.get("thumbnail"):
			item["website_image"] = item["thumbnail"]
		
		# Eğer thumbnail yoksa, website_image'i kullan
		if not item.get("thumbnail") and item.get("website_image"):
			item["thumbnail"] = item["website_image"]
		
		# Eğer varyant ürünün resmi hala yoksa, ana ürünün resmini kullan
		if not item.get("website_image") and not item.get("thumbnail"):
			# variant_of field'ını Item'dan al
			variant_of = frappe.db.get_value("Item", item.get("item_code"), "variant_of")
			if variant_of:
				template_web_item = frappe.db.get_value(
					"Website Item",
					{"item_code": variant_of},
					["website_image", "thumbnail"],
					as_dict=True
				)
				if template_web_item:
					if template_web_item.website_image:
						item["website_image"] = template_web_item.website_image
						item["thumbnail"] = template_web_item.website_image
					elif template_web_item.thumbnail:
						item["website_image"] = template_web_item.thumbnail
						item["thumbnail"] = template_web_item.thumbnail
		
		# URL'leri normalize et
		if item.get("thumbnail"):
			thumbnail = item["thumbnail"]
			if thumbnail and not thumbnail.startswith("http"):
				item["thumbnail"] = frappe.utils.get_url(thumbnail)
		if item.get("website_image"):
			website_image = item["website_image"]
			if website_image and not website_image.startswith("http"):
				item["website_image"] = frappe.utils.get_url(website_image)
	
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
def product_search(query, limit=15, fuzzy_search=True):
	"""Search products using RediSearch with SQL fallback"""
	search_results = {"from_redisearch": True, "results": []}

	if not query or len(query) < 1:
		return search_results

	if not is_redisearch_enabled():
		search_results["from_redisearch"] = False
		search_results["results"] = get_product_data(query, 0, limit)
		return search_results

	try:
		redis = frappe.cache()
		cleaned_query = clean_up_query(query)

		redisearch = redis.ft(WEBSITE_ITEM_INDEX)
		
		# Daha esnek fuzzy search - 1 karakterden itibaren çalışır
		suggestions = redisearch.sugget(
			WEBSITE_ITEM_NAME_AUTOCOMPLETE,
			cleaned_query,
			num=limit * 2,  # Daha fazla öneri al
			fuzzy=fuzzy_search and len(query) > 1,  # 1 karakterden sonra fuzzy
		)

		query_string = cleaned_query
		for s in suggestions:
			query_string += f"|('{clean_up_query(s.string)}')"
		
		# Item code için de arama ekle
		if cleaned_query:
			query_string += f"|(@item_code:{cleaned_query}*)"

		q = Query(query_string)
		results = redisearch.search(q, limit=limit)  # Sonuç limitini belirle

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
	
	# Eğer website_image yoksa, thumbnail'i kullan
	if not doc_dict.get("website_image") and doc_dict.get("thumbnail"):
		doc_dict["website_image"] = doc_dict["thumbnail"]
	
	# Eğer thumbnail yoksa, website_image'i kullan
	if not doc_dict.get("thumbnail") and doc_dict.get("website_image"):
		doc_dict["thumbnail"] = doc_dict["website_image"]
	
	# Eğer varyant ürünün resmi hala yoksa, ana ürünün resmini kullan
	if not doc_dict.get("website_image") and not doc_dict.get("thumbnail"):
		# variant_of field'ını Item'dan al
		item_code = doc_dict.get("item_code")
		if item_code:
			variant_of = frappe.db.get_value("Item", item_code, "variant_of")
			if variant_of:
				template_web_item = frappe.db.get_value(
					"Website Item",
					{"item_code": variant_of},
					["website_image", "thumbnail"],
					as_dict=True
				)
				if template_web_item:
					if template_web_item.website_image:
						doc_dict["website_image"] = template_web_item.website_image
						doc_dict["thumbnail"] = template_web_item.website_image
					elif template_web_item.thumbnail:
						doc_dict["website_image"] = template_web_item.thumbnail
						doc_dict["thumbnail"] = template_web_item.thumbnail
	
	# URL'leri normalize et
	if doc_dict.get("thumbnail"):
		thumbnail = doc_dict["thumbnail"]
		if thumbnail and not thumbnail.startswith("http"):
			doc_dict["thumbnail"] = frappe.utils.get_url(thumbnail)
	if doc_dict.get("website_image"):
		website_image = doc_dict["website_image"]
		if website_image and not website_image.startswith("http"):
			doc_dict["website_image"] = frappe.utils.get_url(website_image)
	
	return doc_dict


@frappe.whitelist(allow_guest=True)
def get_category_suggestions(query, limit=5):
	"""Get category suggestions using RediSearch with SQL fallback"""
	search_results = {"results": []}

	if not query or len(query) < 1:
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
