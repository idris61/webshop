# Copyright (c) 2021, Frappe Technologies Pvt. Ltd. and Contributors
# License: GNU General Public License v3. See license.txt

import frappe

from webshop.webshop.doctype.webshop_settings.webshop_settings import (
    get_shopping_cart_settings,
    show_quantity_in_website,
)
from webshop.webshop.shopping_cart.cart import _get_cart_quotation, _set_price_list
from erpnext.utilities.product import (get_price)
from webshop.webshop.utils.product import (
    get_non_stock_item_status,
    get_web_item_qty_in_stock,
    get_uom_price_options,
)
from webshop.webshop.shopping_cart.cart import get_party


@frappe.whitelist(allow_guest=True)
def get_product_info_for_website(item_code, skip_quotation_creation=False):
	cart_settings = get_shopping_cart_settings()
	if not cart_settings.enabled:
		return frappe._dict({"product_info": {}, "cart_settings": cart_settings})

	cart_quotation = frappe._dict()
	if not skip_quotation_creation:
		cart_quotation = _get_cart_quotation()

	selling_price_list = (
		cart_quotation.get("selling_price_list")
		if cart_quotation
		else _set_price_list(cart_settings, None)
	)

	price = None
	if cart_settings.show_price:
		is_guest = frappe.session.user == "Guest"
		party = get_party()

		if not is_guest or not cart_settings.hide_price_for_guest:
			price = get_price(
				item_code,
				selling_price_list,
				cart_settings.default_customer_group,
				cart_settings.company,
				party=party,
			)

	stock_status = None

	if cart_settings.show_stock_availability:
		on_backorder = frappe.get_cached_value(
			"Website Item", {"item_code": item_code}, "on_backorder"
		)
		if on_backorder:
			stock_status = frappe._dict({"on_backorder": True})
		else:
			stock_status = get_web_item_qty_in_stock(item_code, "website_warehouse")

	stock_uom, sales_uom = frappe.db.get_value(
		"Item", item_code, ["stock_uom", "sales_uom"]
	) or (None, None)

	product_info = {
		"price": price,
		"qty": 0,
		"uom": stock_uom,
		"sales_uom": sales_uom,
	}

	if price:
		product_info["uom_options"] = get_uom_price_options(
			item_code, 
			price,
			price_list=selling_price_list,
			customer_group=cart_settings.default_customer_group if cart_settings else None,
			company=cart_settings.company if cart_settings else None
		)
		
		# Eğer uom_options boşsa ama stock_uom varsa, en azından onu ekle
		if not product_info.get("uom_options") and stock_uom:
			from frappe.utils import fmt_money
			currency = price.get("currency") or "EUR"
			base_rate = price.get("price_list_rate") or 0
			product_info["uom_options"] = [{
				"uom": stock_uom,
				"conversion_factor": 1,
				"price": base_rate,
				"formatted_price": fmt_money(base_rate, currency=currency) if currency else str(base_rate),
				"is_default": 1,
			}]
		if not product_info.get("sales_uom") and product_info.get("uom_options"):
			product_info["sales_uom"] = product_info["uom_options"][0]["uom"]

	if stock_status:
		if stock_status.on_backorder:
			product_info["on_backorder"] = True
		else:
			product_info["stock_qty"] = stock_status.stock_qty
			product_info["in_stock"] = (
				stock_status.in_stock
				if stock_status.is_stock_item
				else get_non_stock_item_status(item_code, "website_warehouse")
			)
			product_info["show_stock_qty"] = show_quantity_in_website()

	if product_info.get("price"):
		if frappe.session.user != "Guest":
			item = (
				cart_quotation.get({"item_code": item_code}) if cart_quotation else None
			)
			if item:
				product_info["qty"] = item[0].qty

	return frappe._dict({"product_info": product_info, "cart_settings": cart_settings})


def set_product_info_for_website(item):
	product_info = get_product_info_for_website(
		item.item_code, skip_quotation_creation=True
	).get("product_info")

	if product_info:
		item.update(product_info)
		item["stock_uom"] = product_info.get("uom")
		item["sales_uom"] = product_info.get("sales_uom")
		item["uom_options"] = product_info.get("uom_options") or []
		if product_info.get("price"):
			item["price_stock_uom"] = product_info.get("price").get("formatted_price")
			item["price_sales_uom"] = product_info.get("price").get(
				"formatted_price_sales_uom"
			)
		else:
			item["price_stock_uom"] = ""
			item["price_sales_uom"] = ""
