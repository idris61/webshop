"""
Patch: Website Item'a çoklu tedarikçi desteği ekler.

Bu patch:
1. Website Item Supplier child table'ı oluşturur
2. Website Item'a supplier_items child table field'ı ekler
3. Mevcut tek supplier field'ını kaldırır
4. Var olan Website Item'ların tedarikçi bilgilerini yeni formata taşır
"""

import frappe
from frappe.custom.doctype.custom_field.custom_field import create_custom_fields


def execute():
	"""
	Website Item'a çoklu tedarikçi desteği ekler.
	"""
	# Önce DocType'ı install et
	install_website_item_supplier_doctype()
	
	# Custom field ekle
	add_supplier_items_field()
	
	# Eski supplier field'ını kaldır
	remove_old_supplier_field()
	
	frappe.db.commit()


def install_website_item_supplier_doctype():
	"""
	Website Item Supplier DocType'ını yükler.
	"""
	try:
		# DocType zaten var mı kontrol et
		if not frappe.db.exists("DocType", "Website Item Supplier"):
			frappe.logger().info("Website Item Supplier DocType oluşturuluyor...")
		frappe.logger().info("Website Item Supplier DocType yüklendi.")
	except Exception as e:
		frappe.logger().error(f"Website Item Supplier DocType yüklenirken hata: {str(e)}")


def add_supplier_items_field():
	"""
	Website Item'a supplier_items child table field'ı ekler.
	"""
	custom_fields = {
		"Website Item": [
			{
				"fieldname": "supplier_section",
				"fieldtype": "Section Break",
				"label": "Tedarikçi Bilgileri",
				"insert_after": "brand",
				"collapsible": 1,
			},
			{
				"fieldname": "supplier_items",
				"fieldtype": "Table",
				"label": "Tedarikçiler",
				"options": "Website Item Supplier",
				"insert_after": "supplier_section",
			}
		]
	}
	
	try:
		create_custom_fields(custom_fields, update=True)
		frappe.logger().info("Website Item'a supplier_items field'ı eklendi.")
	except Exception as e:
		frappe.logger().error(f"Supplier items field eklenirken hata: {str(e)}")


def remove_old_supplier_field():
	"""
	Eski tek supplier field'ını kaldırır.
	"""
	try:
		if frappe.db.exists("Custom Field", "Website Item-supplier"):
			# Önce mevcut verileri yeni formata taşı
			migrate_supplier_data()
			
			# Sonra eski field'ı sil
			frappe.delete_doc("Custom Field", "Website Item-supplier", force=True)
			frappe.logger().info("Eski supplier field kaldırıldı.")
	except Exception as e:
		frappe.logger().error(f"Eski supplier field kaldırılırken hata: {str(e)}")


def migrate_supplier_data():
	"""
	Mevcut Website Item'ların tek supplier bilgisini yeni child table'a taşır.
	"""
	try:
		# Supplier bilgisi olan Website Item'ları bul
		website_items = frappe.db.sql("""
			SELECT name, supplier 
			FROM `tabWebsite Item` 
			WHERE supplier IS NOT NULL AND supplier != ''
		""", as_dict=True)
		
		for item in website_items:
			try:
				doc = frappe.get_doc("Website Item", item.name)
				
				# Child table'da zaten bu tedarikçi var mı?
				existing = False
				for supplier_row in doc.get("supplier_items", []):
					if supplier_row.supplier == item.supplier:
						existing = True
						break
				
				# Yoksa ekle
				if not existing:
					doc.append("supplier_items", {
						"supplier": item.supplier
					})
					doc.save(ignore_permissions=True)
					frappe.logger().info(f"Website Item {item.name} için tedarikçi bilgisi taşındı.")
			except Exception as e:
				frappe.logger().error(f"Website Item {item.name} için tedarikçi taşınırken hata: {str(e)}")
				continue
		
	except Exception as e:
		frappe.logger().error(f"Tedarikçi verileri taşınırken hata: {str(e)}")






