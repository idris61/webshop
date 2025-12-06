# Copyright (c) 2021, Frappe Technologies Pvt. Ltd. and Contributors
# License: GNU General Public License v3. See license.txt
import frappe
from frappe import _
from frappe.utils import floor


# Translation mapping for filter values (ERPNext value -> English translation key)
FILTER_VALUE_TRANSLATIONS = {
	# Product Categories
	"Genel": "General",
	"Einweghandschuhe": "Disposable Gloves",
	"Zubehör für Reinigungsmittel": "Cleaning Accessories",
	"Oberfläche, Reinigung": "Surface Cleaning",
	"Wipes/Vliestücher": "Wipes",
	"Desinfektion": "Disinfection",
	"Haut&Hände": "Skin & Hands",
	"Allzweckreiniger": "All-Purpose Cleaner",
	"Duschgel": "Shower Gel",
	# Product Groups (already in English, but keep for consistency)
	"Cleaning": "Cleaning",
	"Hygiene Products": "Hygiene Products",
	"Personal Protective Equipment": "Personal Protective Equipment",
	"Disinfection": "Disinfection",
	# Brands (keep original names as they are brand names)
	"Dreiturm": "Dreiturm",
	"Meditrade": "Meditrade",
	"Dr. Schnell": "Dr. Schnell",
	"BeeSana": "BeeSana",
	"Gentle Med": "Gentle Med",
}


def get_translated_label(value):
	"""Convert database value to English translation key for i18n"""
	# First check if we have a direct mapping
	english_key = FILTER_VALUE_TRANSLATIONS.get(value, value)
	# Return the English key so it can be translated via _() in templates
	return english_key


class ProductFiltersBuilder:
	def __init__(self, item_group=None):
		if not item_group:
			self.doc = frappe.get_doc("Webshop Settings")
		else:
			self.doc = frappe.get_doc("Item Group", item_group)

		self.item_group = item_group

	def _get_root_item_group(self):
		cache_key = "root_item_group"
		root_group = frappe.cache().get_value(cache_key)
		
		if not root_group:
			root_groups = frappe.get_all(
				"Item Group",
				filters={"parent_item_group": ["in", [None, ""]], "is_group": 1},
				fields=["name"],
				order_by="lft asc",
				limit=1
			)
			
			if root_groups:
				root_group = root_groups[0].name
				frappe.cache().set_value(cache_key, root_group, expires_in_sec=3600)
			else:
				return None
		
		return root_group

	def _get_base_filters(self):
		# Her zaman sadece template items say (variants hariç)
		# Çünkü product listing sayfası her zaman sadece template items gösteriyor
		filters = {"published": 1, "variant_of": ["is", "not set"]}
		return filters

	def _get_item_group_or_filters(self, item_group):
		from webshop.webshop.doctype.override_doctype.item_group import get_child_groups_for_website
		
		or_filters = []
		
		if not item_group:
			return or_filters
		
		include_child = frappe.db.get_value("Item Group", item_group, "include_descendants")
		
		if include_child:
			include_groups = get_child_groups_for_website(item_group, include_self=True)
			include_groups = [x.name for x in include_groups]
			or_filters.extend([
				["item_group", "in", include_groups],
				["Website Item Group", "item_group", "in", include_groups]
			])
		else:
			or_filters.extend([
				["item_group", "=", item_group],
				["Website Item Group", "item_group", "=", item_group]
			])
		
		return or_filters

	def _count_products_in_group(self, item_group_name, child_group_names=None):
		"""Count products in an item group, including those in Website Item Group child table"""
		base_filters = self._get_base_filters()
		
		# Collect all item groups to check (parent + children)
		all_item_groups = [item_group_name]
		if child_group_names:
			all_item_groups.extend(child_group_names)
		
		# Get all Website Items that match this group via item_group field
		items_via_field = frappe.get_all(
			"Website Item",
			filters={**base_filters, "item_group": ["in", all_item_groups]},
			pluck="name"
		)
		
		# Get all Website Items that match this group via Website Item Group child table
		items_via_child_table = []
		if all_item_groups:
			# First get all parent Website Items that are published
			published_web_items = frappe.get_all(
				"Website Item",
				filters=base_filters,
				pluck="name"
			)
			
			if published_web_items:
				items_via_child_table = frappe.get_all(
					"Website Item Group",
					filters={
						"item_group": ["in", all_item_groups],
						"parent": ["in", published_web_items]
					},
					pluck="parent",
					distinct=True
				)
		
		# Combine and get unique count (avoid double counting)
		all_items = set(items_via_field) | set(items_via_child_table)
		count = len(all_items)
		
		# DEBUG: Sayı hesaplama detayları (kısa format)
		frappe.log_error(
			f"COUNT: {item_group_name} -> {count} (field:{len(items_via_field)}, child:{len(items_via_child_table)})",
			"FILTER_COUNT"
		)
		
		return count

	def get_item_group_filters(self):
		from webshop.webshop.doctype.override_doctype.item_group import get_child_groups_for_website
		
		cache_key = f"item_group_filters:{self.item_group or 'all'}"
		cached_result = frappe.cache().get_value(cache_key)
		if cached_result:
			return cached_result
		
		root_group = self._get_root_item_group()
		if not root_group:
			return []
		
		parent_item_groups = frappe.get_all(
			"Item Group",
			filters={"parent_item_group": root_group, "is_group": 1, "show_in_website": 1},
			fields=["name", "parent_item_group", "is_group", "route"],
			order_by="lft asc"
		)
		
		if not parent_item_groups:
			return []
		
		parent_group_names = [ig.name for ig in parent_item_groups]
		child_item_groups = frappe.get_all(
			"Item Group",
			filters={"parent_item_group": ["in", parent_group_names], "show_in_website": 1},
			fields=["name", "parent_item_group", "is_group", "route"],
			order_by="lft asc"
		)
		
		item_groups = list(parent_item_groups) + list(child_item_groups)
		if not item_groups:
			return []
		
		category_map = {}
		for ig in item_groups:
			if ig.is_group:
				child_groups = get_child_groups_for_website(ig.name, include_self=False)
				child_group_names = [cg.name for cg in child_groups]
				count = self._count_products_in_group(ig.name, child_group_names)
			else:
				count = self._count_products_in_group(ig.name)
			
			# DEBUG: Her grup için sayı (kısa format)
			frappe.log_error(
				f"GROUP: {ig.name} -> {count} (is_group:{ig.is_group}, param:{self.item_group or 'all'})",
				"FILTER_COUNT"
			)
			
			if count > 0:
				translated_label = get_translated_label(ig.name)
				category_map[ig.name] = {
					"name": ig.name,
					"label": translated_label,
					"route": ig.route or f"/{ig.name.lower().replace(' ', '-')}",
					"count": count,
					"parent": ig.parent_item_group,
					"is_group": ig.is_group,
					"children": []
				}
		
		if not category_map:
			return []
		
		category_tree = []
		
		for name, data in category_map.items():
			if data["parent"] and data["parent"] in category_map and data["count"] > 0:
				parent_data = category_map[data["parent"]]
				parent_data["children"].append({
					"name": data["name"],
					"label": data["label"],
					"route": data["route"],
					"count": data["count"]
				})
		
		for name, data in category_map.items():
			if not data["parent"] or data["parent"] not in category_map:
				category_tree.append(data)
		
		category_tree.sort(key=lambda x: (
			len(x.get("children", [])) == 0,
			-x["count"],
			x["name"]
		))
		
		frappe.cache().set_value(cache_key, category_tree, expires_in_sec=300)
		
		return category_tree
	
	def get_field_filters(self):
		from webshop.webshop.doctype.override_doctype.item_group import get_child_groups_for_website

		if not self.item_group and not self.doc.enable_field_filters:
			return

		filter_fields = [row.fieldname for row in self.doc.filter_fields]
		if not filter_fields:
			return []

		web_item_meta = frappe.get_meta("Website Item", cached=True)
		fields = [
			web_item_meta.get_field(field) 
			for field in filter_fields 
			if web_item_meta.has_field(field)
		]

		if not fields:
			return []

		filter_data = []
		item_filters = self._get_base_filters()
		item_or_filters = self._get_item_group_or_filters(self.item_group)

		for df in fields:
			link_doctype_values = self.get_filtered_link_doctype_records(df)

			if df.fieldtype == "Link":
				if df.fieldname == "primary_supplier":
					values = self.get_supplier_filter_values(item_filters, item_or_filters, link_doctype_values)
				else:
					item_values = frappe.get_all(
						"Website Item",
						fields=[df.fieldname],
						filters=item_filters,
						or_filters=item_or_filters,
						distinct=True,
						pluck=df.fieldname,
					)
					values = list(set(item_values) & link_doctype_values)
					
			elif df.fieldtype == "Check":
				check_count = frappe.db.count(
					"Website Item",
					filters={**item_filters, df.fieldname: ["in", ["Yes", 1, "1"]]}
				)
				values = [] if check_count > 0 else None
				
			elif df.fieldtype == "Select":
				item_values = frappe.get_all(
					"Website Item",
					fields=[df.fieldname],
					filters=item_filters,
					or_filters=item_or_filters,
					distinct=True,
					pluck=df.fieldname,
				)
				values = [v for v in item_values if v and v not in ["No", "Hayır", "Hayir"]]
			else:
				# Table MultiSelect
				values = list(link_doctype_values)

			if values and None in values:
				values.remove(None)

			if df.fieldtype == "Check":
				if values is not None:
					filter_data.append([df, values])
			elif values:
				filter_data.append([df, values])

		return filter_data

	def get_supplier_filter_values(self, item_filters, item_or_filters, link_doctype_values):
		from webshop.webshop.doctype.override_doctype.item_group import get_child_groups_for_website
		
		parent_filters = [["published", "=", 1]]
		parent_filters.extend(self._get_item_group_or_filters(self.item_group))
		
		if frappe.db.get_single_value("Webshop Settings", "hide_variants"):
			parent_filters.append(["variant_of", "is", "not set"])
		
		website_items = frappe.get_all(
			"Website Item",
			filters=parent_filters,
			pluck="name"
		)
		
		if not website_items:
			return []
		
		suppliers = frappe.get_all(
			"Website Item Supplier",
			filters={"parent": ["in", website_items]},
			pluck="supplier",
			distinct=True
		)
		
		return list(set(suppliers) & link_doctype_values)
	
	def get_filtered_link_doctype_records(self, field):
		link_doctype = field.get_link_doctype()
		if not link_doctype:
			return set()
		
		meta = frappe.get_meta(link_doctype, cached=True)
		filters = self.get_link_doctype_filters(meta)
		
		records = frappe.get_all(link_doctype, filters=filters, pluck="name")
		return set(records)

	def get_link_doctype_filters(self, meta):
		if not meta:
			return {}

		filters = {}
		if meta.has_field("enabled"):
			filters["enabled"] = 1
		if meta.has_field("disabled"):
			filters["disabled"] = 0
		if meta.has_field("show_in_website"):
			filters["show_in_website"] = 1

		return filters

	def get_product_category_filters(self):
		cache_key = f"product_category_filters:{self.item_group or 'all'}"
		cached_result = frappe.cache().get_value(cache_key)
		if cached_result:
			return cached_result
		
		item_filters = self._get_base_filters()
		item_or_filters = self._get_item_group_or_filters(self.item_group)
		
		published_web_items = frappe.get_all(
			"Website Item",
			filters=item_filters,
			or_filters=item_or_filters,
			fields=["name"],
			pluck="name"
		)
		
		if not published_web_items:
			return []
		
		categories = frappe.get_all(
			"Item Product Category",
			filters={
				"parent": ["in", published_web_items],
				"parenttype": "Website Item",
				"parentfield": "product_categories"
			},
			fields=["product_category"],
			distinct=True,
			pluck="product_category"
		)
		
		if not categories:
			return []
		
		category_data = []
		for category_name in categories:
			web_items_with_category = frappe.get_all(
				"Item Product Category",
				filters={
					"parent": ["in", published_web_items],
					"parenttype": "Website Item",
					"parentfield": "product_categories",
					"product_category": category_name
				},
				pluck="parent",
				distinct=True
			)
			
			count = len(web_items_with_category)
			if count > 0:
				translated_label = get_translated_label(category_name)
				category_data.append({
					"name": category_name,
					"label": translated_label,
					"count": count
				})
		
		category_data.sort(key=lambda x: (-x["count"], x["name"]))
		frappe.cache().set_value(cache_key, category_data, expires_in_sec=300)
		
		return category_data

	def get_attribute_filters(self):
		from webshop.webshop.doctype.override_doctype.item_group import get_child_groups_for_website
		
		if not self.item_group and not self.doc.enable_attribute_filters:
			return

		attributes = [row.attribute for row in self.doc.filter_attributes]
		if not attributes:
			return []
		
		cache_key = f"attribute_filters:{self.item_group or 'all'}:{':'.join(sorted(attributes))}"
		cached_result = frappe.cache().get_value(cache_key)
		if cached_result:
			return cached_result

		item_filters = self._get_base_filters()
		item_or_filters = self._get_item_group_or_filters(self.item_group)
		
		published_items = frappe.get_all(
			"Website Item",
			filters=item_filters,
			or_filters=item_or_filters,
			fields=["item_code"],
			pluck="item_code"
		)
		
		if not published_items:
			return []
		
		result = frappe.get_all(
			"Item Variant Attribute",
			filters={
				"parent": ["in", published_items],
				"attribute": ["in", attributes],
				"attribute_value": ["is", "set"]
			},
			fields=["attribute", "attribute_value"],
			distinct=True,
		)

		attribute_value_map = {}
		for d in result:
			attribute_value_map.setdefault(d.attribute, []).append(d.attribute_value)

		out = []
		for attribute in attributes:
			if attribute not in attribute_value_map:
				continue

			values = sorted(list(set(attribute_value_map[attribute])))
			out.append(frappe._dict(name=attribute, item_attribute_values=values))

		frappe.cache().set_value(cache_key, out, expires_in_sec=300)

		return out

	def get_discount_filters(self, discounts):
		if not discounts or len(discounts) < 2:
			return []
		
		discount_filters = []
		min_discount, max_discount = discounts[0], discounts[1]
		min_range_absolute, max_range_absolute = floor(min_discount), floor(max_discount)

		min_range = int(min_discount - (min_range_absolute % 10))
		max_range = int(max_discount - (max_range_absolute % 10))

		min_range = (min_range + 10) if min_range != min_range_absolute else min_range
		max_range = (max_range + 10) if max_range != max_range_absolute else max_range

		for discount in range(min_range, (max_range + 1), 10):
			label = _("{0}% and below").format(discount)
			discount_filters.append([discount, label])

		return discount_filters


def clear_filter_cache(doc=None, method=None):
	frappe.cache().delete_value("root_item_group")
	
	try:
		frappe.cache().delete_keys("item_group_filters:*")
		frappe.cache().delete_keys("product_category_filters:*")
		frappe.cache().delete_keys("attribute_filters:*")
	except Exception:
		pass
	
	try:
		frappe.cache().delete_keys("product_filter:*")
	except Exception:
		pass
