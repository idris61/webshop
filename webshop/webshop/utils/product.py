import frappe
from frappe.utils import getdate, nowdate, fmt_money

from erpnext.stock.doctype.batch.batch import get_batch_qty
from erpnext.stock.doctype.warehouse.warehouse import get_child_warehouses


def get_web_item_qty_in_stock(item_code, item_warehouse_field, warehouse=None):
	in_stock, stock_qty = 0, ""
	template_item_code, is_stock_item = frappe.db.get_value(
		"Item", item_code, ["variant_of", "is_stock_item"]
	)

	if not warehouse:
		warehouse = frappe.db.get_value("Website Item", {"item_code": item_code}, item_warehouse_field)

	if not warehouse and template_item_code and template_item_code != item_code:
		warehouse = frappe.db.get_value(
			"Website Item", {"item_code": template_item_code}, item_warehouse_field
		)

	if warehouse and frappe.get_cached_value("Warehouse", warehouse, "is_group") == 1:
		warehouses = get_child_warehouses(warehouse)
	else:
		warehouses = [warehouse] if warehouse else []

	total_stock = 0.0
	if warehouses:
		for warehouse in warehouses:
			stock_qty = frappe.db.sql(
				"""
				select S.actual_qty / IFNULL(C.conversion_factor, 1)
				from tabBin S
				inner join `tabItem` I on S.item_code = I.Item_code
				left join `tabUOM Conversion Detail` C on I.sales_uom = C.uom and C.parent = I.Item_code
				where S.item_code=%s and S.warehouse=%s""",
				(item_code, warehouse),
			)

			if stock_qty:
				total_stock += adjust_qty_for_expired_items(item_code, stock_qty, warehouse)

		in_stock = total_stock > 0 and 1 or 0

	return frappe._dict(
		{"in_stock": in_stock, "stock_qty": total_stock, "is_stock_item": is_stock_item}
	)


def adjust_qty_for_expired_items(item_code, stock_qty, warehouse):
	batches = frappe.get_all("Batch", filters=[{"item": item_code}], fields=["expiry_date", "name"])
	expired_batches = get_expired_batches(batches)
	stock_qty = [list(item) for item in stock_qty]

	for batch in expired_batches:
		if warehouse:
			stock_qty[0][0] = max(0, stock_qty[0][0] - get_batch_qty(batch, warehouse))
		else:
			stock_qty[0][0] = max(0, stock_qty[0][0] - qty_from_all_warehouses(get_batch_qty(batch)))

		if not stock_qty[0][0]:
			break

	return stock_qty[0][0] if stock_qty else 0


def get_expired_batches(batches):
	return [b.name for b in batches if b.expiry_date and b.expiry_date <= getdate(nowdate())]


def qty_from_all_warehouses(batch_info):
	qty = 0
	for batch in batch_info:
		qty = qty + batch.qty
	return qty


def get_non_stock_item_status(item_code, item_warehouse_field):
	if frappe.db.exists("Product Bundle", item_code):
		items = frappe.get_doc("Product Bundle", item_code).get_all_children()
		bundle_warehouse = frappe.db.get_value(
			"Website Item", {"item_code": item_code}, item_warehouse_field
		)
		return all(
			get_web_item_qty_in_stock(d.item_code, item_warehouse_field, bundle_warehouse).in_stock
			for d in items
		)
	else:
		return 1


def get_uom_price_options(
	item_code: str, 
	price_obj: frappe._dict | None,
	price_list: str = None,
	customer_group: str = None,
	company: str = None
) -> list[dict]:
	if not price_obj:
		return []

	item_fields = frappe.db.get_value(
		"Item",
		item_code,
		["stock_uom", "sales_uom"],
		as_dict=True,
	)

	if not item_fields:
		return []

	stock_uom = item_fields.get("stock_uom")
	sales_uom = item_fields.get("sales_uom") or stock_uom

	if not stock_uom:
		return []

	conversions = frappe.db.get_all(
		"UOM Conversion Detail",
		fields=["uom", "conversion_factor"],
		filters={"parent": item_code},
		order_by="idx asc",
	)

	uom_list = [stock_uom]
	uom_factor_map = {stock_uom: 1}
	
	for row in conversions:
		uom = row.get("uom")
		factor = row.get("conversion_factor") or 0
		if not uom or factor <= 0:
			continue
		if uom not in uom_list:
			uom_list.append(uom)
		uom_factor_map[uom] = factor

	currency = price_obj.get("currency") or "EUR"
	
	if not price_list:
		price_list = frappe.db.get_value("Price List", {"currency": currency, "selling": 1}, "name")
		if not price_list:
			price_list = price_obj.get("price_list") if hasattr(price_obj, "price_list") else None

	item_prices = frappe.db.get_all(
		"Item Price",
		fields=["uom", "price_list_rate"],
		filters={
			"item_code": item_code,
			"price_list": price_list,
			"uom": ["in", uom_list]
		},
		order_by="uom asc"
	)

	uom_price_map = {ip.get("uom"): ip.get("price_list_rate") or 0 for ip in item_prices}
	base_rate = price_obj.get("price_list_rate") or 0
	default_uom = sales_uom or stock_uom
	
	if default_uom not in uom_price_map:
		uom_price_map[default_uom] = base_rate

	options: list[dict] = []
	for uom in uom_list:
		if not uom:  # UOM boş veya None ise atla
			continue
			
		if uom in uom_price_map:
			price_for_uom = uom_price_map[uom]
		else:
			factor = uom_factor_map.get(uom, 1)
			base_factor = uom_factor_map.get(default_uom, 1)
			if base_factor > 0:
				price_for_uom = (base_rate / base_factor) * factor
			else:
				price_for_uom = base_rate * factor
		
		# is_default: sales_uom varsa onu, yoksa stock_uom'u, yoksa ilk seçeneği işaretle
		is_default = 1 if uom == default_uom else 0
		
		options.append(
			{
				"uom": uom,
				"conversion_factor": uom_factor_map.get(uom, 1),
				"price": price_for_uom,
				"formatted_price": fmt_money(price_for_uom, currency=currency) if currency else str(price_for_uom),
				"is_default": is_default,
			}
		)

	# Eğer options boşsa ama stock_uom varsa, en azından onu ekle
	if not options and stock_uom:
		options.append(
			{
				"uom": stock_uom,
				"conversion_factor": 1,
				"price": base_rate,
				"formatted_price": fmt_money(base_rate, currency=currency) if currency else str(base_rate),
				"is_default": 1,
			}
		)

	# Default olanı en başa taşı ve eğer hiç default yoksa ilk seçeneği default yap
	if options:
		has_default = any(opt.get("is_default") == 1 for opt in options)
		if not has_default and len(options) > 0:
			options[0]["is_default"] = 1
		
		options.sort(key=lambda row: (0 if row.get("is_default") else 1, row.get("uom") or ""))
	
	return options

