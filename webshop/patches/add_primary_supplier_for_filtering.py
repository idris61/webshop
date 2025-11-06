"""
Patch: Website Item'a primary_supplier field'ı ekler ve filtreleme için kullanır.

Bu patch:
1. Website Item'a primary_supplier field'ı ekler (filtreleme için)
2. Mevcut Website Item'ların ilk tedarikçisini primary_supplier'a kopyalar
3. Webshop Settings'te supplier filtresi primary_supplier'ı kullanır
"""

import frappe
from frappe.custom.doctype.custom_field.custom_field import create_custom_fields


def execute():
	"""
	Website Item'a primary_supplier field'ı ekler ve filtre düzenler.
	"""
	add_primary_supplier_field()
	sync_primary_supplier_data()
	update_webshop_filter()
	frappe.db.commit()


def add_primary_supplier_field():
	"""
	Website Item'a primary_supplier field'ı ekler.
	"""
	custom_fields = {
		"Website Item": [
			{
				"fieldname": "primary_supplier",
				"fieldtype": "Link",
				"label": "Ana Tedarikçi",
				"options": "Supplier",
				"insert_after": "supplier_items",
				"read_only": 1,
				"translatable": 0,
				"description": "Filtreleme için kullanılır. İlk tedarikçi otomatik atanır.",
			}
		]
	}
	
	try:
		create_custom_fields(custom_fields, update=True)
		frappe.logger().info("Website Item'a primary_supplier field'ı eklendi.")
	except Exception as e:
		frappe.logger().error(f"Primary supplier field eklenirken hata: {str(e)}")


def sync_primary_supplier_data():
	"""
	Mevcut Website Item'ların ilk tedarikçisini primary_supplier'a kopyalar.
	"""
	try:
		# Website Item'ları al
		website_items = frappe.db.sql("""
			SELECT DISTINCT wis.parent
			FROM `tabWebsite Item Supplier` wis
		""", as_dict=True)
		
		for item in website_items:
			try:
				# İlk tedarikçiyi al
				first_supplier = frappe.db.sql("""
					SELECT supplier
					FROM `tabWebsite Item Supplier`
					WHERE parent = %s
					ORDER BY idx ASC
					LIMIT 1
				""", item.parent)
				
				if first_supplier and first_supplier[0][0]:
					# primary_supplier'ı güncelle
					frappe.db.set_value(
						"Website Item",
						item.parent,
						"primary_supplier",
						first_supplier[0][0],
						update_modified=False
					)
					frappe.logger().info(f"Website Item {item.parent} primary_supplier güncellendi: {first_supplier[0][0]}")
			except Exception as e:
				frappe.logger().error(f"Website Item {item.parent} için primary_supplier güncellenirken hata: {str(e)}")
				continue
		
		frappe.logger().info("Tüm Website Item'lar için primary_supplier güncellendi.")
		
	except Exception as e:
		frappe.logger().error(f"Primary supplier verileri senkronize edilirken hata: {str(e)}")


def update_webshop_filter():
	"""
	Webshop Settings'te supplier filtresini primary_supplier'a günceller.
	"""
	try:
		settings = frappe.get_doc("Webshop Settings")
		
		# Mevcut supplier filtresini bul ve güncelle
		filter_updated = False
		for filter_field in settings.filter_fields:
			if filter_field.fieldname == "supplier":
				filter_field.fieldname = "primary_supplier"
				filter_updated = True
				frappe.logger().info("Webshop Settings'te supplier filtresi primary_supplier olarak güncellendi.")
				break
		
		# Eğer yoksa ekle
		if not filter_updated:
			existing_filters = [row.fieldname for row in settings.filter_fields]
			if "primary_supplier" not in existing_filters:
				settings.append("filter_fields", {
					"fieldname": "primary_supplier"
				})
				frappe.logger().info("Webshop Settings'e primary_supplier filtresi eklendi.")
		
		settings.save(ignore_permissions=True)
		frappe.logger().info("Webshop Settings başarıyla güncellendi.")
		
	except Exception as e:
		frappe.logger().error(f"Webshop Settings güncellenirken hata: {str(e)}")






