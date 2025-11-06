"""
Website Item'lardaki supplier field'larını Item'dan fetch eder ve günceller.
Kullanım: bench --site culinary-test.local execute webshop.webshop.utils.update_filters.update_and_check
"""
import frappe


def update_and_check():
	"""
	Tüm Website Item'lardaki supplier field'larını günceller ve filtreleri kontrol eder.
	"""
	web_items = frappe.get_all("Website Item", fields=["name", "item_code"])
	
	print(f"\n{'='*50}")
	print(f"Toplam {len(web_items)} Website Item bulundu")
	print(f"{'='*50}\n")
	
	updated_count = 0
	
	for web_item in web_items:
		try:
			# Website Item'ı yükle
			doc = frappe.get_doc("Website Item", web_item.name)
			
			# Item'dan default_supplier'ı al
			if doc.item_code:
				item = frappe.get_doc("Item", doc.item_code)
				
				if hasattr(item, 'default_supplier') and item.default_supplier:
					# Supplier field'ını güncelle
					frappe.db.set_value("Website Item", doc.name, "supplier", item.default_supplier, update_modified=False)
					updated_count += 1
					print(f"✓ {doc.name} ({doc.item_code}) -> Tedarikçi: {item.default_supplier}")
		except Exception as e:
			print(f"✗ Hata ({web_item.name}): {str(e)}")
	
	frappe.db.commit()
	
	print(f"\n{'='*50}")
	print(f"Toplam {updated_count} Website Item başarıyla güncellendi")
	print(f"{'='*50}\n")
	
	# Filtreleri kontrol et
	print("\n=== WEBSHOP SETTINGS FİLTRELERİ ===")
	settings = frappe.get_doc("Webshop Settings")
	print(f"Field Filters Enabled: {settings.enable_field_filters}")
	print(f"\nAktif Filtreler:")
	for row in settings.filter_fields:
		print(f"  - {row.fieldname}")
	
	print("\n=== FİLTRE VERİLERİNİ TEST ET ===")
	from webshop.webshop.product_data_engine.filters import ProductFiltersBuilder
	
	filter_engine = ProductFiltersBuilder()
	field_filters = filter_engine.get_field_filters()
	
	if field_filters:
		print(f"\nToplam {len(field_filters)} filtre oluşturuldu:\n")
		for field_filter in field_filters:
			field_meta = field_filter[0]
			values = field_filter[1]
			print(f"  📋 {field_meta.label} ({field_meta.fieldname})")
			if values:
				print(f"     Değerler: {', '.join(str(v) for v in values[:5])}" + (" ..." if len(values) > 5 else ""))
			else:
				print(f"     Değerler: Yok")
	else:
		print("❌ Hiç filtre bulunamadı!")
	
	return {"updated": updated_count, "total": len(web_items)}







