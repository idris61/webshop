"""
Patch: Website Item'a supplier custom field ekler ve Webshop Settings'e dinamik filtreleri ekler.

Bu patch:
1. Website Item'a 'supplier' custom field ekler (Item'daki default_supplier'dan fetch eder)
2. Webshop Settings'e stock_uom ve supplier filtrelerini ekler (dinamik tedarikçi ve stok birimi için)
"""

import frappe
from frappe.custom.doctype.custom_field.custom_field import create_custom_fields


def execute():
	"""
	Website Item doctype'ına supplier field ekler ve Webshop Settings'e filtreleri ekler.
	"""
	add_supplier_custom_field_to_website_item()
	add_filters_to_webshop_settings()
	frappe.db.commit()


def add_supplier_custom_field_to_website_item():
	"""
	Website Item'a custom supplier field ekler.
	"""
	custom_fields = {
		"Website Item": [
			{
				"fieldname": "supplier",
				"fieldtype": "Link",
				"label": "Tedarikçi",
				"options": "Supplier",
				# fetch_from kaldırıldı çünkü Item'da default_supplier field'ı yok
				# Bu field Item Default child table'ında var ve doğrudan fetch edilemez
				"insert_after": "brand",
				"read_only": 0,  # Kullanıcı manuel seçebilsin
				"translatable": 0,
			}
		]
	}
	
	try:
		create_custom_fields(custom_fields, update=True)
		frappe.logger().info("Website Item'a supplier custom field eklendi.")
	except Exception as e:
		frappe.logger().error(f"Supplier custom field eklenirken hata: {str(e)}")


def add_filters_to_webshop_settings():
	"""
	Webshop Settings'e stock_uom ve supplier filtrelerini ekler.
	"""
	try:
		settings = frappe.get_doc("Webshop Settings")
		
		# Enable field filters if not already enabled
		if not settings.enable_field_filters:
			settings.enable_field_filters = 1
		
		# Mevcut filtreleri kontrol et
		existing_filters = [row.fieldname for row in settings.filter_fields]
		
		# stock_uom filtresi ekle (yoksa)
		if "stock_uom" not in existing_filters:
			settings.append("filter_fields", {
				"fieldname": "stock_uom"
			})
			frappe.logger().info("Webshop Settings'e stock_uom filtresi eklendi.")
		
		# supplier filtresi ekle (yoksa)
		if "supplier" not in existing_filters:
			settings.append("filter_fields", {
				"fieldname": "supplier"
			})
			frappe.logger().info("Webshop Settings'e supplier filtresi eklendi.")
		
		settings.save(ignore_permissions=True)
		frappe.logger().info("Webshop Settings başarıyla güncellendi.")
		
	except Exception as e:
		frappe.logger().error(f"Webshop Settings güncellenirken hata: {str(e)}")




