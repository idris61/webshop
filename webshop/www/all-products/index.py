import frappe
from frappe.utils import cint

from webshop.webshop.product_data_engine.filters import ProductFiltersBuilder

sitemap = 1


def get_context(context):
	context.body_class = "product-page"
	context.parents = [{"name": frappe._("Home"), "route": "/"}]

	filter_engine = ProductFiltersBuilder()
	context.field_filters = filter_engine.get_field_filters()
	context.attribute_filters = filter_engine.get_attribute_filters()
	context.item_group_filters = filter_engine.get_item_group_filters()
	context.product_category_filters = filter_engine.get_product_category_filters()

	items_per_page = cint(frappe.form_dict.get("items_per_page"))
	context.page_length = items_per_page or cint(frappe.db.get_single_value("Webshop Settings", "products_per_page")) or 20
	
	context.price_min = frappe.form_dict.get("price_min")
	context.price_max = frappe.form_dict.get("price_max")

	context.no_cache = 1
