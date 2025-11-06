"""
Patch: custom_short_description verilerini standart short_description field'ına taşır.

Bu patch:
1. Website Item'daki custom_short_description verilerini short_description'a kopyalar
2. Custom field'ı siler
3. Item'daki custom_short_description'ı Website Item'ın short_description'ına fetch edecek şekilde ayarlar
"""

import frappe


def execute():
	"""
	custom_short_description'dan short_description'a veri migrasyonu yapar.
	"""
	migrate_custom_to_standard_description()
	update_website_item_short_description_field()
	delete_custom_short_description_field()
	frappe.db.commit()


def migrate_custom_to_standard_description():
	"""
	Website Item'daki custom_short_description verilerini short_description'a kopyalar.
	"""
	print("\n=== VERİ MİGRASYONU BAŞLIYOR ===\n")
	
	# Custom short description'ı olan Website Item'ları bul
	web_items = frappe.db.sql("""
		SELECT name, custom_short_description, short_description
		FROM `tabWebsite Item`
		WHERE custom_short_description IS NOT NULL 
		AND custom_short_description != ''
	""", as_dict=True)
	
	updated_count = 0
	
	for item in web_items:
		try:
			# Eğer short_description boşsa custom_short_description'ı kopyala
			if not item.short_description:
				frappe.db.set_value(
					"Website Item",
					item.name,
					"short_description",
					item.custom_short_description,
					update_modified=False
				)
				updated_count += 1
				print(f"✓ {item.name}: custom_short_description -> short_description")
			else:
				# İkisi de doluysa, kullanıcıya göster
				print(f"⚠ {item.name}: Her iki alan da dolu, short_description korundu")
		except Exception as e:
			print(f"✗ Hata ({item.name}): {str(e)}")
	
	print(f"\n✅ Toplam {updated_count} Website Item güncellendi\n")


def update_website_item_short_description_field():
	"""
	Website Item'ın short_description field'ına fetch_from ekler.
	"""
	print("\n=== WEBSITE ITEM SHORT_DESCRIPTION FIELD GÜNCELLEME ===\n")
	
	try:
		# Website Item'ın short_description field'ını Item'ın custom_short_description'ından fetch et
		from frappe.custom.doctype.property_setter.property_setter import make_property_setter
		
		# fetch_from özelliği ekle
		make_property_setter(
			"Website Item",
			"short_description",
			"fetch_from",
			"item_code.custom_short_description",
			"Small Text",
			validate_fields_for_doctype=False
		)
		
		print("✅ Website Item short_description field'ı Item'dan fetch edecek şekilde güncellendi")
		
	except Exception as e:
		print(f"⚠ Uyarı: {str(e)}")


def delete_custom_short_description_field():
	"""
	Website Item'daki custom_short_description custom field'ını siler.
	"""
	print("\n=== CUSTOM FIELD SİLME ===\n")
	
	try:
		if frappe.db.exists("Custom Field", "Website Item-custom_short_description"):
			frappe.delete_doc("Custom Field", "Website Item-custom_short_description", force=True)
			print("✅ Website Item'daki custom_short_description custom field'ı silindi")
		else:
			print("ℹ Website Item'da custom_short_description custom field'ı bulunamadı")
			
	except Exception as e:
		print(f"⚠ Uyarı: {str(e)}")
	
	print("\n=== ITEM CUSTOM FIELD DURUMU ===")
	print("ℹ Item'daki custom_short_description field'ı korundu.")
	print("  Bu field artık Website Item'ın short_description field'ına fetch ediliyor.")

