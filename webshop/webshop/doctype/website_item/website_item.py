# -*- coding: utf-8 -*-
# Copyright (c) 2022, Frappe Technologies Pvt. Ltd. and contributors
# For license information, please see license.txt

import json
from typing import TYPE_CHECKING

if TYPE_CHECKING:
    from erpnext.stock.doctype.item.item import Item

import frappe
from frappe import _
from frappe.utils import cint, cstr, flt, random_string, fmt_money
from frappe.website.doctype.website_slideshow.website_slideshow import get_slideshow
from frappe.website.website_generator import WebsiteGenerator

from webshop.webshop.doctype.item_review.item_review import get_item_reviews
from webshop.webshop.redisearch_utils import (
    delete_item_from_index,
    insert_item_to_index,
    update_index_for_item,
)
from webshop.webshop.shopping_cart.cart import _set_price_list
from webshop.webshop.doctype.override_doctype.item_group import (
    get_parent_item_groups,
    invalidate_cache_for,
)
from erpnext.stock.doctype.item.item import Item
from erpnext.utilities.product import get_price
from webshop.webshop.shopping_cart.cart import get_party
from webshop.webshop.variant_selector.item_variants_cache import (
    ItemVariantsCacheManager,
)


class WebsiteItem(WebsiteGenerator):
	website = frappe._dict(
		page_title_field="web_item_name",
		condition_field="published",
		template="templates/generators/item/item.html",
		no_cache=1,
	)

	def autoname(self):
		# use naming series to accomodate items with same name (different item code)
		from frappe.model.naming import get_default_naming_series, make_autoname

		naming_series = get_default_naming_series("Website Item")
		if not self.name and naming_series:
			self.name = make_autoname(naming_series, doc=self)

	def onload(self):
		super(WebsiteItem, self).onload()

	def validate(self):
		super(WebsiteItem, self).validate()

		if not self.item_code:
			frappe.throw(_("Item Code is required"), title=_("Mandatory"))

		self.validate_duplicate_website_item()
		self.validate_website_image()
		self.make_thumbnail()
		self.update_primary_supplier()
		self.sync_product_categories_from_item()
		self.publish_unpublish_desk_item(publish=True)

		if not self.get("__islocal"):
			wig = frappe.qb.DocType("Website Item Group")
			query = (
				frappe.qb.from_(wig)
				.select(wig.item_group)
				.where(
					(wig.parentfield == "website_item_groups")
					& (wig.parenttype == "Website Item")
					& (wig.parent == self.name)
				)
			)
			result = query.run(as_list=True)

			self.old_website_item_groups = [x[0] for x in result]

	def on_update(self):
		invalidate_cache_for_web_item(self)
		self.update_template_item()

	def on_trash(self):
		super(WebsiteItem, self).on_trash()
		delete_item_from_index(self)
		self.publish_unpublish_desk_item(publish=False)

	def validate_duplicate_website_item(self):
		existing_web_item = frappe.db.exists(
			"Website Item", {"item_code": self.item_code}
		)
		if existing_web_item and existing_web_item != self.name:
			message = _("Website Item already exists against Item {0}").format(
				frappe.bold(self.item_code)
			)
			frappe.throw(message, title=_("Already Published"))

	def publish_unpublish_desk_item(self, publish=True):
		if (
			frappe.db.get_value("Item", self.item_code, "published_in_website")
			and publish
		):
			return  # if already published don't publish again
		frappe.db.set_value("Item", self.item_code, "published_in_website", publish)

	def make_route(self):
		"""Called from set_route in WebsiteGenerator."""
		if not self.route:
			return (
				cstr(frappe.db.get_value("Item Group", self.item_group, "route"))
				+ "/"
				+ self.scrub(
					(self.item_name if self.item_name else self.item_code)
					+ "-"
					+ random_string(5)
				)
			)

	def update_template_item(self):
		"""Publish Template Item if Variant is published."""
		if self.variant_of:
			if self.published:
				# show template
				template_item = frappe.get_doc("Item", self.variant_of)

				if not template_item.published_in_website:
					template_item.flags.ignore_permissions = True
					make_website_item(template_item)
	
	def sync_product_categories_from_item(self):
		"""Product categories'i Item'dan fetch et"""
		if self.item_code and frappe.db.exists("Item", self.item_code):
			item_doc = frappe.get_doc("Item", self.item_code)
			
			# Mevcut kategorileri temizle
			self.product_categories = []
			
			# Item'daki kategorileri kopyala
			for cat_row in item_doc.product_categories:
				self.append("product_categories", {
					"product_category": cat_row.product_category
				})
	
	def update_primary_supplier(self):
		"""Update primary_supplier field with first supplier from supplier_items."""
		supplier_items = self.get("supplier_items", [])
		if supplier_items and len(supplier_items) > 0:
			# İlk tedarikçiyi primary_supplier olarak ata
			self.primary_supplier = supplier_items[0].supplier
		else:
			# Tedarikçi yoksa temizle
			self.primary_supplier = None

	def validate_website_image(self):
		if frappe.flags.in_import:
			return

		"""Validate if the website image is a public file"""
		if not self.website_image:
			return

		# find if website image url exists as public
		file_doc = frappe.get_all(
			"File",
			filters={"file_url": self.website_image},
			fields=["name", "is_private"],
			order_by="is_private asc",
			limit_page_length=1,
		)

		if file_doc:
			file_doc = file_doc[0]

		if not file_doc:
			frappe.msgprint(
				_("Website Image {0} attached to Item {1} cannot be found").format(
					self.website_image, self.name
				)
			)

			self.website_image = None

		elif file_doc.is_private:
			frappe.msgprint(_("Website Image should be a public file or website URL"))

			self.website_image = None

	def make_thumbnail(self):
		"""Make a thumbnail of `website_image`"""
		if frappe.flags.in_import or frappe.flags.in_migrate:
			return

		import requests.exceptions

		db_website_image = frappe.db.get_value(self.doctype, self.name, "website_image")
		if not self.is_new() and self.website_image != db_website_image:
			self.thumbnail = None

		if self.website_image and not self.thumbnail:
			file_doc = None

			try:
				file_doc = frappe.get_doc(
					"File",
					{
						"file_url": self.website_image,
						"attached_to_doctype": "Website Item",
						"attached_to_name": self.name,
					},
				)
			except frappe.DoesNotExistError:
				pass
				# cleanup
				frappe.local.message_log.pop()

			except requests.exceptions.HTTPError:
				frappe.msgprint(
					_("Warning: Invalid attachment {0}").format(self.website_image)
				)
				self.website_image = None

			except requests.exceptions.SSLError:
				frappe.msgprint(
					_("Warning: Invalid SSL certificate on attachment {0}").format(
						self.website_image
					)
				)
				self.website_image = None

			# for CSV import
			if self.website_image and not file_doc:
				try:
					file_doc = frappe.get_doc(
						{
							"doctype": "File",
							"file_url": self.website_image,
							"attached_to_doctype": "Website Item",
							"attached_to_name": self.name,
						}
					).save()

				except IOError:
					self.website_image = None

			if file_doc:
				if not file_doc.thumbnail_url:
					file_doc.make_thumbnail()

				self.thumbnail = file_doc.thumbnail_url

	def get_context(self, context):
		context.show_search = True
		context.search_link = "/search"
		context.body_class = "product-page"

		context.parents = get_parent_item_groups(self.item_group, from_item=True)
		self.attributes = frappe.get_all(
			"Item Variant Attribute",
			fields=["attribute", "attribute_value"],
			filters={"parent": self.item_code},
		)

		# Varyant seçildiğinde varyantın resim ve badge'lerini kontrol et
		variant_item_code = frappe.request.args.get('variant') if frappe.request else None
		variant_web_item = None
		variant_image = None
		variant_badges = []
		
		if variant_item_code and variant_item_code != self.item_code:
			# Varyantın Website Item'ını bul
			variant_web_item_name = frappe.db.exists("Website Item", {"item_code": variant_item_code})
			if variant_web_item_name:
				variant_web_item = frappe.get_doc("Website Item", variant_web_item_name)
				# Varyantın resmini al (varsa)
				if variant_web_item.website_image:
					variant_image = variant_web_item.website_image
				# Varyantın badge'lerini al
				variant_badges = frappe.db.get_values(
					"Product Badge",
					{"parent": variant_web_item_name, "parenttype": "Website Item", "parentfield": "product_badges"},
					"*",
					as_dict=True,
					order_by="display_order asc, idx asc"
				) or []

		# Varyantın resmi varsa onu kullan, yoksa template item'ın resmini kullan
		if variant_image:
			context.variant_image = variant_image
		else:
			context.variant_image = self.website_image

		# Varyantın badge'leri varsa onları kullan, yoksa template item'ın badge'lerini kullan
		if variant_badges:
			self.product_badges = variant_badges
		else:
			if not hasattr(self, 'product_badges') or not self.product_badges:
				# Child table'ı doğrudan yükle
				badges = frappe.db.get_values(
					"Product Badge",
					{"parent": self.name, "parenttype": "Website Item", "parentfield": "product_badges"},
					"*",
					as_dict=True,
					order_by="display_order asc, idx asc"
				) or []
				self.product_badges = badges
		
		# Product Categories'i context'e ekle
		if not hasattr(self, 'product_categories') or not self.product_categories:
			# Child table'ı doğrudan yükle
			categories = frappe.db.get_values(
				"Item Product Category",
				{"parent": self.name, "parenttype": "Website Item", "parentfield": "product_categories"},
				"*",
				as_dict=True,
				order_by="idx asc"
			) or []
			self.product_categories = categories
		
		# Context'e product_categories ekle
		context.product_categories = self.product_categories

		if self.slideshow:
			context.update(get_slideshow(self))

		self.set_metatags(context)
		self.set_shopping_cart_data(context)

		settings = context.shopping_cart.cart_settings
		
		# has_variants'i context'e ekle (template'te kullanılmak için)
		context.has_variants = self.has_variants
		
		# Varyant bilgilerini yükle (has_variants ise)
		if self.has_variants and settings.enable_variants:
			self.set_variant_context(context)
		
		self.get_product_details_section(context)

		if settings.get("enable_reviews"):
			reviews_data = get_item_reviews(self.name)
			context.update(reviews_data)
			context.reviews = context.reviews[:4]

		context.wished = False
		if frappe.db.exists(
			"Wishlist Item",
			{"item_code": self.item_code, "parent": frappe.session.user},
		):
			context.wished = True

		context.user_is_customer = check_if_user_is_customer()

		context.recommended_items = None
		if settings and settings.enable_recommendations:
			context.recommended_items = self.get_recommended_items(settings)

		# short_description artık doğrudan Website Item'da mevcut (Item'dan fetch ediliyor)
		
		# Apply translations for portal content
		from webshop.webshop.utils.translation import get_translated_doc, get_translated_text
		# Get current language explicitly to ensure it's up-to-date
		current_language = frappe.local.lang or "en"
		
		if hasattr(context, 'doc') and context.doc:
			# Translate Website Item
			translated_doc = get_translated_doc(context.doc, language=current_language)
			if not isinstance(translated_doc, dict):
				if hasattr(translated_doc, "as_dict"):
					translated_doc = translated_doc.as_dict()
				else:
					translated_doc = frappe._dict(translated_doc.__dict__)
			
			# Also translate the underlying Item DocType (description comes from Item)
			if hasattr(context.doc, 'item_code') and context.doc.item_code:
				try:
					item_doc = frappe.get_cached_doc("Item", context.doc.item_code)
					translated_item = get_translated_doc(item_doc, language=current_language, 
						fields=["item_name", "description", "item_group", "brand"])
					if isinstance(translated_item, dict):
						# Update Website Item fields from translated Item
						if "description" in translated_item and translated_item["description"]:
							# Item.description -> Website Item.web_long_description or description
							if not translated_doc.get("web_long_description"):
								translated_doc["web_long_description"] = translated_item["description"]
							if not translated_doc.get("description"):
								translated_doc["description"] = translated_item["description"]
						if "item_name" in translated_item and translated_item["item_name"]:
							if not translated_doc.get("item_name"):
								translated_doc["item_name"] = translated_item["item_name"]
							if not translated_doc.get("web_item_name"):
								translated_doc["web_item_name"] = translated_item["item_name"]
				except Exception as e:
					frappe.log_error(f"Error translating Item for Website Item: {str(e)}")
			
			# Update context.doc with translated fields
			for key, value in translated_doc.items():
				if key in ["item_name", "web_item_name", "description", "website_description", 
				          "web_long_description", "item_group", "brand", "short_description"]:
					setattr(context.doc, key, value)
					# Also update context dict for template access
					context[key] = value
			
			# Translate product categories
			if hasattr(context, "product_categories") and context.product_categories:
				for category_row in context.product_categories:
					category_name = None
					if isinstance(category_row, dict):
						category_name = category_row.get("product_category")
					elif hasattr(category_row, "product_category"):
						category_name = getattr(category_row, "product_category")
					if not category_name:
						continue
					translated_category = get_translated_text(category_name, language=current_language)
					if translated_category and translated_category != category_name:
						if isinstance(category_row, dict):
							category_row["product_category"] = translated_category
						else:
							setattr(category_row, "product_category", translated_category)

		return context

	def set_variant_context(self, context):
		"""Varyant bilgilerini context'e ekle"""
		from webshop.webshop.variant_selector.utils import get_attributes_and_values
		from webshop.webshop.shopping_cart.cart import _set_price_list
		from webshop.webshop.doctype.webshop_settings.webshop_settings import get_shopping_cart_settings
		from erpnext.utilities.product import get_price
		
		# Varyant attribute'larını al
		attributes = get_attributes_and_values(self.item_code)
		
		# Varyant cache'den varyant bilgilerini al
		item_cache = ItemVariantsCacheManager(self.item_code)
		item_attribute_value_map = item_cache.get_item_attribute_value_map()
		
		# Varyantları oluştur (sadece published Website Item'lar)
		variants = []
		variant_map = {}
		published_web_items = frappe.get_all(
			"Website Item",
			filters={"item_code": ["in", list(item_attribute_value_map.keys())], "published": 1},
			fields=["item_code"],
			pluck="item_code"
		)
		
		# Fiyat aralığı hesaplama için cart settings
		cart_settings = get_shopping_cart_settings()
		price_list = _set_price_list(cart_settings, None)
		variant_prices = []
		
		# Varyantları sıralı olarak oluştur (Size'a göre)
		for item_code in published_web_items:
			if item_code in item_attribute_value_map:
				variant_attrs = []
				size_value = None
				for attr_name, attr_value in item_attribute_value_map[item_code].items():
					variant_attrs.append({
						"attribute": attr_name,
						"attribute_value": attr_value
					})
					if attr_name == "Size":
						try:
							size_value = float(attr_value)
						except (ValueError, TypeError):
							size_value = 0
				
				# Varyant fiyatını al
				variant_price = None
				if cart_settings.show_price:
					price_data = get_price(
						item_code,
						price_list,
						cart_settings.default_customer_group,
						cart_settings.company,
					)
					if price_data and price_data.get("price_list_rate"):
						variant_price = price_data.get("price_list_rate")
						variant_prices.append(variant_price)
				
				variant_map[item_code] = {
					"name": item_code,
					"attributes": variant_attrs,
					"price": variant_price,
					"_size_value": size_value if size_value is not None else 0
				}
				variants.append(variant_map[item_code])
		
		# Varyantları Size'a göre sırala
		variants.sort(key=lambda v: v.get("_size_value", 0))
		
		# Fiyat aralığını hesapla
		if variant_prices:
			min_price = min(variant_prices)
			max_price = max(variant_prices)
			currency = frappe.db.get_value("Price List", price_list, "currency") if price_list else "EUR"
			
			context.price_range = {
				"min": min_price,
				"max": max_price,
				"min_formatted": fmt_money(min_price, currency=currency),
				"max_formatted": fmt_money(max_price, currency=currency),
				"currency": currency,
				"has_range": len(set(variant_prices)) > 1  # Birden fazla farklı fiyat varsa
			}
		else:
			context.price_range = None
		
		context.variant_info = variants
		context.attributes = attributes
		
		# Seçili varyant (varsa)
		variant_item_code = frappe.request.args.get('variant') if frappe.request else None
		if variant_item_code and variant_item_code in variant_map:
			context.variant = variant_map[variant_item_code]
		elif variants:
			# İlk varyantı varsayılan olarak seç
			context.variant = variants[0]
		else:
			context.variant = frappe._dict({"name": self.item_code, "attributes": []})
		
		context.selected_attributes = frappe._dict()
		attribute_values_available = frappe._dict()
		context.attribute_values = frappe._dict()  # Önce başlat
		self.set_selected_attributes(variants, context, attribute_values_available)
		self.set_attribute_values(attributes, context, attribute_values_available)
		# attribute_values_available'daki değerleri context.attribute_values'a kopyala
		for attr_name, values in attribute_values_available.items():
			context.attribute_values[attr_name] = values

	def set_selected_attributes(self, variants, context, attribute_values_available):
		"""Varyant attribute'larını işle ve seçili attribute'ları belirle"""
		for variant in variants:
			# variant bir dict, name'i al
			variant_name = variant.get("name")
			
			# Eğer attributes yoksa, Item Variant Attribute'dan çek
			if not variant.get("attributes"):
				variant["attributes"] = frappe.get_all(
					"Item Variant Attribute",
					filters={"parent": variant_name},
					fields=["attribute", "attribute_value as value"],
				)

			# Attribute-value map oluştur
			variant_attrs = variant.get("attributes", [])
			variant["attribute_map"] = frappe._dict(
				{attr.get("attribute"): attr.get("attribute_value") or attr.get("value") for attr in variant_attrs}
			)

			# Her attribute için değerleri topla
			for attr in variant_attrs:
				attr_name = attr.get("attribute")
				attr_value = attr.get("attribute_value") or attr.get("value")
				
				if attr_name and attr_value:
					values = attribute_values_available.setdefault(attr_name, [])
					if attr_value not in values:
						values.append(attr_value)

					# Seçili varyantın attribute'larını işaretle
					context_variant_name = context.variant.get("name") if isinstance(context.variant, dict) else getattr(context.variant, "name", None)
					if variant_name == context_variant_name:
						context.selected_attributes[attr_name] = attr_value

	def set_attribute_values(self, attributes, context, attribute_values_available):
		for attr in attributes:
			values = context.attribute_values.setdefault(attr.attribute, [])

			if cint(
				frappe.db.get_value("Item Attribute", attr.attribute, "numeric_values")
			):
				for val in sorted(
					attribute_values_available.get(attr.attribute, []), key=flt
				):
					values.append(val)
			else:
				# get list of values defined (for sequence)
				for attr_value in frappe.db.get_all(
					"Item Attribute Value",
					fields=["attribute_value"],
					filters={"parent": attr.attribute},
					order_by="idx asc",
				):

					if attr_value.attribute_value in attribute_values_available.get(
						attr.attribute, []
					):
						values.append(attr_value.attribute_value)

	def set_metatags(self, context):
		context.metatags = frappe._dict({})

		safe_description = frappe.utils.to_markdown(self.description)

		context.metatags.url = frappe.utils.get_url() + "/" + context.route

		if context.website_image:
			if context.website_image.startswith("http"):
				url = context.website_image
			else:
				url = frappe.utils.get_url() + context.website_image
			context.metatags.image = url

		context.metatags.description = safe_description[:300]

		context.metatags.title = self.web_item_name or self.item_name or self.item_code

		context.metatags["og:type"] = "product"
		context.metatags["og:site_name"] = "ERPNext"

	def set_shopping_cart_data(self, context):
		from webshop.webshop.shopping_cart.product_info import (
			get_product_info_for_website,
		)

		# skip_quotation_creation=False yaparak sepetteki güncel miktarı alıyoruz
		# Böylece sayfa yüklendiğinde doğru qty gösterilir (flash-of-content yok)
		context.shopping_cart = get_product_info_for_website(
			self.item_code, skip_quotation_creation=False
		)

	@frappe.whitelist()
	def copy_specification_from_item_group(self):
		self.set("website_specifications", [])
		if self.item_group:
			for label, desc in frappe.db.get_values(
				"Item Website Specification",
				{"parent": self.item_group},
				["label", "description"],
			):
				row = self.append("website_specifications")
				row.label = label
				row.description = desc

	def get_product_details_section(self, context):
		"""Get section with tabs or website specifications."""
		context.show_tabs = self.show_tabbed_section
		if self.show_tabbed_section and (self.tabs or self.website_specifications):
			context.tabs = self.get_tabs()
		else:
			context.website_specifications = self.website_specifications

	def get_tabs(self):
		tab_values = {}
		tab_values["tab_1_title"] = _("Product Details")
		tab_values["tab_1_content"] = frappe.render_template(
			"templates/generators/item/item_specifications.html",
			{
				"website_specifications": self.website_specifications,
				"show_tabs": self.show_tabbed_section,
			},
		)

		for row in self.tabs:
			tab_values[f"tab_{row.idx + 1}_title"] = _(row.label)
			tab_values[f"tab_{row.idx + 1}_content"] = row.content

		return tab_values

	def get_recommended_items(self, settings):
		ri = frappe.qb.DocType("Recommended Items")
		wi = frappe.qb.DocType("Website Item")

		query = (
			frappe.qb.from_(ri)
			.join(wi)
			.on(ri.item_code == wi.item_code)
			.select(
				ri.item_code, ri.route, ri.website_item_name, ri.website_item_thumbnail
			)
			.where((ri.parent == self.name) & (wi.published == 1))
			.orderby(ri.idx)
		)
		items = query.run(as_dict=True)

		if settings.show_price:
			is_guest = frappe.session.user == "Guest"
			# Show Price if logged in.
			# If not logged in and price is hidden for guest, skip price fetch.
			if is_guest and settings.hide_price_for_guest:
				return items

			selling_price_list = _set_price_list(settings, None)
			party = get_party()

			for item in items:
				item.price_info = get_price(
					item.item_code,
					selling_price_list,
					settings.default_customer_group,
					settings.company,
					party=party,
				)

		return items


def invalidate_item_variants_cache_for_website(doc):
	"""
	Rebuild ItemVariantsCacheManager via Item or Website Item

	Args:
		doc (Item): item of which cache should be cleared
	"""
	item_code = None
	is_web_item = doc.get("published_in_website") or doc.get("published")

	if doc.has_variants and is_web_item:
		item_code = doc.item_code
	elif doc.variant_of and frappe.db.get_value(
		"Item", doc.variant_of, "published_in_website"
	):
		item_code = doc.variant_of

	if not item_code:
		return

	item_cache = ItemVariantsCacheManager(item_code)
	item_cache.rebuild_cache()


def invalidate_cache_for_web_item(doc):
	"""
	Invalidate Website Item Group cache and rebuild ItemVariantsCacheManager
	Args:
		doc (Item): document against which cache should be cleared
	"""
	invalidate_cache_for(doc, doc.item_group)

	website_item_groups = list(
		set(
			(doc.get("old_website_item_groups") or [])
			+ [
				d.item_group
				for d in doc.get({"doctype": "Website Item Group"})
				if d.item_group
			]
		)
	)

	for item_group in website_item_groups:
		invalidate_cache_for(doc, item_group)

	# Update Search Cache
	update_index_for_item(doc)

	invalidate_item_variants_cache_for_website(doc)


def on_doctype_update():
	# since route is a Text column, it needs a length for indexing
	frappe.db.add_index("Website Item", ["route(500)"])


def check_if_user_is_customer(user=None):
	from frappe.contacts.doctype.contact.contact import get_contact_name

	if not user:
		user = frappe.session.user

	contact_name = get_contact_name(user)
	customer = None

	if contact_name:
		contact = frappe.get_doc("Contact", contact_name)
		for link in contact.links:
			if link.link_doctype == "Customer":
				customer = link.link_name
				break

	return True if customer else False


@frappe.whitelist()
def make_website_item(doc, save=True):
	"""
	Make Website Item from Item. Used via Form UI or patch.
	"""
	if not doc:
		return

	if isinstance(doc, str):
		doc = json.loads(doc)

	if frappe.db.exists("Website Item", {"item_code": doc.get("item_code")}):
		message = _("Website Item already exists against {0}").format(
			frappe.bold(doc.get("item_code"))
		)
		frappe.throw(message, title=_("Already Published"))

	website_item = frappe.new_doc("Website Item")
	website_item.web_item_name = doc.get("item_name")

	fields_to_map = [
		"item_code",
		"item_name",
		"item_group",
		"stock_uom",
		"brand",
		"has_variants",
		"variant_of",
		"description",
	]
	for field in fields_to_map:
		website_item.update({field: doc.get(field)})

	# Needed for publishing/mapping via Form UI only
	if not frappe.flags.in_migrate and (
		doc.get("image") and not website_item.website_image
	):
		website_item.website_image = doc.get("image")
	
	# Copy supplier items from Item to Website Item
	if doc.get("supplier_items"):
		for idx, supplier_item in enumerate(doc.get("supplier_items")):
			website_item.append("supplier_items", {
				"supplier": supplier_item.get("supplier"),
				"supplier_part_no": supplier_item.get("supplier_part_no")
			})
			# İlk tedarikçiyi primary_supplier olarak ata (filtreleme için)
			if idx == 0:
				website_item.primary_supplier = supplier_item.get("supplier")

	if not save:
		return website_item

	website_item.save()

	# Add to search cache
	insert_item_to_index(website_item)

	return [website_item.name, website_item.web_item_name]

@frappe.whitelist()
def has_website_permission_for_website_item(doc, ptype, user, verbose=False):
	# Check item group permissions for website

	if user == "Administrator":
		return True

	if frappe.has_permission("Website Item", ptype=ptype, doc=doc, user=user):
		return True

	if not frappe.db.get_single_value("Webshop Settings", "login_required_to_view_products"):
		return True

	return False

@frappe.whitelist()
def has_website_permission_for_item_group(doc, ptype, user, verbose=False):
	# Check item group permissions for website
	if user == "Administrator":
		return True

	if frappe.has_permission("Item Group", ptype=ptype, doc=doc, user=user):
		return True

	if not frappe.db.get_single_value("Webshop Settings", "login_required_to_view_products"):
		return True

	return False
