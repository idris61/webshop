# Copyright (c) 2021, Frappe Technologies Pvt. Ltd. and Contributors
# License: GNU General Public License v3. See license.txt

import frappe
from frappe.utils import flt

from webshop.webshop.doctype.item_review.item_review import get_customer
from webshop.webshop.shopping_cart.product_info import get_product_info_for_website
from webshop.webshop.utils.product import get_non_stock_item_status


class ProductQuery:
	"""Query engine for product listing

	Attributes:
	        fields (list): Fields to fetch in query
	        conditions (string): Conditions for query building
	        or_conditions (string): Search conditions
	        page_length (Int): Length of page for the query
	        settings (Document): Webshop Settings DocType
	"""

	def __init__(self):
		self.settings = frappe.get_doc("Webshop Settings")
		self.page_length = self.settings.products_per_page or 20
		self.order_by = "ranking desc"  # Default sorting

		self.or_filters = []
		self.filters = [["published", "=", 1]]
		self.fields = [
			"web_item_name",
			"web_item_name_tr",
			"web_item_name_en",
			"web_item_name_de",
			"name",
			"item_name",
			"item_code",
		"website_image",
		"variant_of",
		"has_variants",
		"item_group",
		"web_long_description",
		"web_long_description_tr",
		"web_long_description_en",
		"web_long_description_de",
		"short_description",
			"description",
		"route",
		"website_warehouse",
		"ranking",
			"on_backorder",
			"brand",
			"stock_uom",
			"thumbnail",
		]

	def query(self, attributes=None, fields=None, search_term=None, start=0, item_group=None):
		"""
		Args:
		        attributes (dict, optional): Item Attribute filters
		        fields (dict, optional): Field level filters
		        search_term (str, optional): Search term to lookup
		        start (int, optional): Page start

		Returns:
		        dict: Dict containing items, item count & discount range
		"""
		# track if discounts included in field filters
		self.filter_with_discount = bool(fields and fields.get("discount"))
		result, discount_list, website_item_groups, cart_items, count = [], [], [], [], 0

		if fields:
			self.build_fields_filters(fields)
		if item_group:
			self.build_item_group_filters(item_group)
		if search_term:
			self.build_search_filters(search_term)
		# Always hide variants in product listing - count only template items
		self.filters.append(["variant_of", "is", "not set"])

		# query results
		if attributes:
			result, count = self.query_items_with_attributes(attributes, start)
		else:
			result, count = self.query_items(start=start)

		if self.settings.enabled:
			cart_items = self.get_cart_items()

		result, discount_list = self.add_display_details(result, discount_list, cart_items)
		result = sorted(result, key=lambda x: x.get("ranking", 0), reverse=True)

		discounts = []
		if discount_list:
			discounts = [min(discount_list), max(discount_list)]

		result = self.filter_results_by_discount(fields, result)

		return {"items": result, "items_count": count, "discounts": discounts}

	def query_items(self, start=0):
		"""Build a query to fetch Website Items based on field filters."""
		# MySQL does not support offset without limit,
		# frappe does not accept two parameters for limit
		# https://dev.mysql.com/doc/refman/8.0/en/select.html#id4651989
		count_items = frappe.db.get_all(
			"Website Item",
			filters=self.filters,
			or_filters=self.or_filters,
			limit_page_length=184467440737095516,
			limit_start=start,  # get all items from this offset for total count ahead
			order_by="ranking desc",
		)
		count = len(count_items)

		# If discounts included, return all rows.
		# Slice after filtering rows with discount (See `filter_results_by_discount`).
		# Slicing before hand will miss discounted items on the 3rd or 4th page.
		# Discounts are fetched on computing Pricing Rules so we cannot query them directly.
		page_length = 184467440737095516 if self.filter_with_discount else self.page_length

		items = frappe.db.get_all(
			"Website Item",
			fields=self.fields,
			filters=self.filters,
			or_filters=self.or_filters,
			limit_page_length=page_length,
			limit_start=start,
			order_by=self.order_by,
		)

		return items, count

	def query_items_with_attributes(self, attributes, start=0):
		"""Build a query to fetch Website Items based on field & attribute filters."""
		item_codes = []

		for attribute, values in attributes.items():
			if not isinstance(values, list):
				values = [values]

			# get items that have selected attribute & value
			item_code_list = frappe.db.get_all(
				"Item",
				fields=["item_code"],
				filters=[
					["published_in_website", "=", 1],
					["Item Variant Attribute", "attribute", "=", attribute],
					["Item Variant Attribute", "attribute_value", "in", values],
				],
			)
			item_codes.append({x.item_code for x in item_code_list})

		if item_codes:
			item_codes = list(set.intersection(*item_codes))
			self.filters.append(["item_code", "in", item_codes])

		items, count = self.query_items(start=start)

		return items, count

	def build_fields_filters(self, filters):
		if not filters:
			return
		
		meta = frappe.get_meta("Website Item", cached=True)
		
		for field, values in filters.items():
			if not values or field == "discount" or field.startswith("_"):
				continue

			if field == "item_group":
				from webshop.webshop.doctype.override_doctype.item_group import get_child_groups_for_website
				
				all_groups = []
				if not isinstance(values, list):
					values = [values]
				
				for item_group in values:
					all_groups.append(item_group)
					is_group = frappe.db.get_value("Item Group", item_group, "is_group")
					if is_group:
						child_groups = get_child_groups_for_website(item_group, include_self=False)
						all_groups.extend([cg.name for cg in child_groups])
				
				all_groups = list(set(all_groups))
				item_group_filters = [
					["item_group", "in", all_groups],
					["Website Item Group", "item_group", "in", all_groups]
				]
				self.or_filters.extend(item_group_filters)
				continue

			if field == "product_category":
				if not isinstance(values, list):
					values = [values]
				
				web_items_with_category = frappe.get_all(
					"Item Product Category",
					filters={
						"product_category": ["in", values],
						"parenttype": "Website Item",
						"parentfield": "product_categories"
					},
					pluck="parent",
					distinct=True
				)
				
				if web_items_with_category:
					self.filters.append(["name", "in", web_items_with_category])
				else:
					self.filters.append(["name", "=", "__no_item__"])
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
					self.filters.append([field, "in", normalized_values])
				else:
					if values in ["Yes", "yes", "1", 1]:
						self.filters.append([field, "=", 1])
					elif values in ["No", "no", "0", 0]:
						self.filters.append([field, "=", 0])
					else:
						self.filters.append([field, "=", values])
			elif field == "primary_supplier":
				self.filters.append(["Website Item Supplier", "supplier", "in", values])
			elif df.fieldtype == "Table MultiSelect":
				child_doctype = df.options
				child_meta = frappe.get_meta(child_doctype, cached=True)
				fields = child_meta.get("fields")
				if fields:
					self.filters.append([child_doctype, fields[0].fieldname, "IN", values])
			elif isinstance(values, list):
				self.filters.append([field, "in", values])
			else:
				self.filters.append([field, "=", values])

	def build_item_group_filters(self, item_group):
		from webshop.webshop.doctype.override_doctype.item_group import get_child_groups_for_website

		item_group_filters = []
		item_group_filters.append(["Website Item", "item_group", "=", item_group])
		item_group_filters.append(["Website Item Group", "item_group", "=", item_group])

		if frappe.db.get_value("Item Group", item_group, "include_descendants"):
			include_groups = get_child_groups_for_website(item_group, include_self=True)
			include_groups = [x.name for x in include_groups]
			item_group_filters.append(["Website Item", "item_group", "in", include_groups])

		self.or_filters.extend(item_group_filters)

	def build_search_filters(self, search_term):
		"""Build optimized search filters with item_code priority"""
		if not search_term:
			return
		
		search_term = search_term.strip()
		
		# Get search fields
		default_fields = {"item_code", "item_name", "web_long_description", "item_group"}
		meta = frappe.get_meta("Website Item")
		meta_fields = set(meta.get_search_fields())
		search_fields = default_fields.union(meta_fields)
		if frappe.db.count("Website Item", cache=True) > 50000:
			search_fields.discard("web_long_description")

		# Öncelik 1: Item code için prefix match (en hızlı ve spesifik)
		# Prefix match daha hızlı çalışır çünkü indeks kullanılabilir
		if search_term and len(search_term) >= 1:
			self.or_filters.append(["item_code", "like", f"{search_term}%"])
			# Ayrıca tam match için exact match (daha spesifik sonuçlar)
			self.or_filters.append(["item_code", "=", search_term])

		# Öncelik 2: Diğer alanlar için normal LIKE araması
		search_pattern = "%{}%".format(search_term)
		for field in search_fields:
			if field != "item_code":  # item_code zaten yukarıda eklendi
				self.or_filters.append([field, "like", search_pattern])

	def add_display_details(self, result, discount_list, cart_items):
		"""Add price, availability, and cart quantity details in result."""
		from webshop.webshop.doctype.webshop_settings.webshop_settings import get_shopping_cart_settings
		from webshop.webshop.shopping_cart.cart import _set_price_list
		from erpnext.utilities.product import get_price
		from frappe.utils import fmt_money
		
		cart_settings = get_shopping_cart_settings()
		price_list = _set_price_list(cart_settings, None)
		
		for item in result:
			has_variants = item.get("has_variants") if isinstance(item, dict) else getattr(item, 'has_variants', False)
			item_code = item.get("item_code") if isinstance(item, dict) else getattr(item, 'item_code', None)
			
			if has_variants and item_code:
				try:
					self.calculate_variant_price_range(item, price_list, cart_settings)
					formatted_price_range = item.get("formatted_price_range") if isinstance(item, dict) else getattr(item, 'formatted_price_range', None)
					if not formatted_price_range:
						product_info = get_product_info_for_website(item_code, skip_quotation_creation=True).get(
							"product_info"
						)
						if product_info and product_info.get("price") and product_info["price"].get("formatted_price"):
							self.get_price_discount_info(item, product_info["price"], discount_list)
				except Exception as e:
					frappe.log_error(f"Error calculating variant price range for {item_code}: {str(e)}", "Variant Price Range Error")
			
			if not item.has_variants:
				product_info = get_product_info_for_website(item.item_code, skip_quotation_creation=True).get(
					"product_info"
				)

				if product_info and product_info.get("price") and product_info["price"].get("formatted_price"):
					self.get_price_discount_info(item, product_info["price"], discount_list)

			self.get_stock_availability(item)

			item.in_cart = item.item_code in cart_items
			item.qty = cart_items.get(item.item_code, 0) if cart_items else 0

			item.wished = False
			if frappe.db.exists(
				"Wishlist Item", {"item_code": item.item_code, "parent": frappe.session.user}
			):
				item.wished = True
			
			# Eğer item'ın resmi yoksa, thumbnail'i kullan
			if not item.get("website_image") and item.get("thumbnail"):
				item.website_image = item.get("thumbnail")
			
			# Eğer varyant ürünün resmi hala yoksa, ana ürünün resmini kullan
			if not item.get("website_image") and item.get("variant_of"):
				template_item_code = item.get("variant_of")
				template_web_item = frappe.db.get_value(
					"Website Item",
					{"item_code": template_item_code},
					["website_image", "thumbnail"],
					as_dict=True
				)
				if template_web_item:
					# Önce website_image, yoksa thumbnail kullan
					if template_web_item.website_image:
						item.website_image = template_web_item.website_image
					elif template_web_item.thumbnail:
						item.website_image = template_web_item.thumbnail
			
			web_item_name = item.get("name")
			if web_item_name:
				product_categories = frappe.db.get_values(
					"Item Product Category",
					{"parent": web_item_name, "parenttype": "Website Item", "parentfield": "product_categories"},
					["product_category"],
					as_dict=True,
					order_by="idx asc"
				) or []
				item.product_categories = [pc.product_category for pc in product_categories]
				
				product_badges = frappe.db.get_values(
					"Product Badge",
					{"parent": web_item_name, "parenttype": "Website Item", "parentfield": "product_badges"},
					["badge_name", "badge_image", "badge_link", "badge_alt_text", "display_order"],
					as_dict=True,
					order_by="display_order asc, idx asc"
				) or []
				item.product_badges = product_badges
			
			try:
				from webshop.webshop.utils.translation import get_translated_doc
				translated_item = get_translated_doc(item)
				for key, value in translated_item.items():
					if key in ["item_name", "web_item_name", "description", "website_description", "item_group", "brand"]:
						item[key] = value
			except Exception as e:
				frappe.log_error(f"Translation error for item {item.get('item_code', 'Unknown')}: {str(e)}", "Translation Error")

		return result, discount_list

	def calculate_variant_price_range(self, item, price_list, cart_settings):
		from erpnext.utilities.product import get_price
		from frappe.utils import fmt_money
		
		has_variants = item.get("has_variants") if isinstance(item, dict) else getattr(item, 'has_variants', False)
		if not has_variants:
			return
		
		item_code = item.get("item_code") if isinstance(item, dict) else getattr(item, 'item_code', None)
		if not item_code:
			return
		
		variants = frappe.get_all(
			"Item",
			filters={"variant_of": item_code, "disabled": 0},
			fields=["item_code"],
			pluck="item_code"
		)
		
		if not variants:
			return
		
		published_variants = frappe.get_all(
			"Website Item",
			filters={"item_code": ["in", variants], "published": 1},
			fields=["item_code"],
			pluck="item_code"
		)
		
		if not published_variants:
			return
		
		variant_prices = []
		for variant_code in published_variants:
			if cart_settings.show_price:
				price_data = get_price(
					variant_code,
					price_list,
					cart_settings.default_customer_group,
					cart_settings.company,
				)
				if price_data and price_data.get("price_list_rate"):
					variant_prices.append(price_data.get("price_list_rate"))
		
		if not variant_prices:
			return
		
		min_price = min(variant_prices)
		max_price = max(variant_prices)
		currency = frappe.db.get_value("Price List", price_list, "currency") if price_list else "EUR"
		
		price_range_dict = {
			"min": min_price,
			"max": max_price,
			"min_formatted": fmt_money(min_price, currency=currency),
			"max_formatted": fmt_money(max_price, currency=currency),
			"currency": currency,
			"has_range": len(set(variant_prices)) > 1
		}
		
		item["price_range"] = price_range_dict
		if price_range_dict["has_range"]:
			formatted_range = f"{price_range_dict['min_formatted']} – {price_range_dict['max_formatted']}"
			item["formatted_price_range"] = formatted_range
		else:
			item["formatted_price_range"] = price_range_dict['min_formatted']

	def get_price_discount_info(self, item, price_object, discount_list):
		"""Modify item object and add price details."""
		fields = ["formatted_mrp", "formatted_price", "price_list_rate"]
		for field in fields:
			item[field] = price_object.get(field)

		if price_object.get("discount_percent"):
			item.discount_percent = flt(price_object.discount_percent)
			discount_list.append(price_object.discount_percent)

		if item.formatted_mrp:
			item.discount = price_object.get("formatted_discount_percent") or price_object.get(
				"formatted_discount_rate"
			)

	def get_stock_availability(self, item):
		"""Modify item object and add stock details."""
		from webshop.templates.pages.wishlist import (
			get_stock_availability as get_stock_availability_from_template,
		)

		item.in_stock = False
		warehouse = item.get("website_warehouse")
		is_stock_item = frappe.get_cached_value("Item", item.item_code, "is_stock_item")

		if item.get("on_backorder"):
			return

		if not is_stock_item:
			if warehouse:
				# product bundle case
				item.in_stock = get_non_stock_item_status(item.item_code, "website_warehouse")
			else:
				item.in_stock = True
		elif warehouse:
			# stock item and has warehouse
			item.in_stock = get_stock_availability_from_template(item.item_code, warehouse)

	def get_cart_items(self):
		customer = get_customer(silent=True)
		if customer:
			quotation = frappe.get_all(
				"Quotation",
				fields=["name"],
				filters={
					"party_name": customer,
					"contact_email": frappe.session.user,
					"order_type": "Shopping Cart",
					"docstatus": 0,
				},
				order_by="modified desc",
				limit_page_length=1,
			)
			if quotation:
				items = frappe.get_all(
					"Quotation Item", 
					fields=["item_code", "qty"], 
					filters={"parent": quotation[0].get("name")}
				)
				return {row.item_code: row.qty for row in items}

		return {}

	def filter_results_by_discount(self, fields, result):
		if fields and fields.get("discount"):
			discount_percent = frappe.utils.flt(fields["discount"][0])
			result = [
				row
				for row in result
				if row.get("discount_percent") and row.discount_percent <= discount_percent
			]

		if self.filter_with_discount:
			result = result[: self.page_length]

		return result
