# -*- coding: utf-8 -*-
"""
Item'daki is_kitchen_item ve supplier değişikliklerini Website Item'a senkronize et.

Bu hook, Item save edildiğinde otomatik olarak çalışır.
Sadece değişiklik olduğunda Website Item güncellenir (performans optimizasyonu).
"""

import frappe


def execute(doc, method=None):
	"""
	Item kaydedildiğinde is_kitchen_item ve supplier değerlerini 
	Website Item'a otomatik kopyala.
	
	Performance:
	- Sadece değişiklik varsa çalışır
	- Bulk update kullanır (db.set_value)
	- Gereksiz commit yok
	
	Args:
		doc: Item document
		method: Hook method (on_update)
	"""
	if doc.doctype != "Item":
		return
	
	# Website Item var mı kontrol et
	web_item_name = frappe.db.exists("Website Item", {"item_code": doc.item_code})
	if not web_item_name:
		return
	
	# Güncellenecek alanları hazırla
	updates = {}
	
	# is_kitchen_item kontrolü (sadece değişmişse)
	if doc.has_value_changed("is_kitchen_item"):
		# Format: "Evet" veya "Hayır" (filtre uyumluluğu için)
		updates["is_kitchen_item"] = "Evet" if doc.is_kitchen_item else "Hayır"
	
	# supplier kontrolü (sadece değişmişse veya ilk supplier eklenmişse)
	if doc.has_value_changed("supplier_items") or "is_kitchen_item" in updates:
		supplier = None
		if doc.get("supplier_items") and len(doc.supplier_items) > 0:
			supplier = doc.supplier_items[0].supplier
		
		# Sadece supplier değiştiyse güncelle
		current_supplier = frappe.db.get_value("Website Item", web_item_name, "supplier")
		if current_supplier != supplier:
			updates["supplier"] = supplier
	
	# Eğer güncellenecek bir şey varsa güncelle
	if updates:
		try:
			frappe.db.set_value(
				"Website Item",
				web_item_name,
				updates,
				update_modified=True
			)
			# Frappe otomatik commit yapar, manuel commit gereksiz ve zararlı
		except Exception as e:
			# Hata logla ama Item save'ini engelleme
			frappe.log_error(
				f"Item: {doc.item_code}, Error: {str(e)}", 
				"Website Item Sync Failed"
			)
