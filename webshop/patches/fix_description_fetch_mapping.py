"""
Patch: Item.description'ı web_long_description'a fetch edecek şekilde düzeltir.

Bu patch:
1. Website Item'ın web_long_description field'ına fetch_from ekler (item_code.description)
2. Website Item'ın description field'ının fetch_from'unu kaldırır (gereksiz tekrar)
3. Mevcut Item.description verilerini Website Item.web_long_description'a kopyalar
"""

import frappe
from frappe.custom.doctype.property_setter.property_setter import make_property_setter


def execute():
	"""
	Description field mapping'ini düzeltir.
	"""
	print("\n" + "="*70)
	print("DESCRIPTION FIELD MAPPING DÜZELTİLİYOR")
	print("="*70 + "\n")
	
	# 1. web_long_description'a fetch_from ekle
	add_fetch_to_web_long_description()
	
	# 2. description'ın fetch_from'unu kaldır
	remove_fetch_from_description()
	
	# 3. Mevcut verileri migrate et
	migrate_description_data()
	
	frappe.db.commit()
	
	print("\n" + "="*70)
	print("✅ TAMAMLANDI")
	print("="*70 + "\n")


def add_fetch_to_web_long_description():
	"""
	Website Item'ın web_long_description field'ına fetch_from ekler.
	"""
	print("1️⃣  web_long_description field'ına fetch_from ekleniyor...\n")
	
	try:
		# fetch_from özelliği ekle
		make_property_setter(
			"Website Item",
			"web_long_description",
			"fetch_from",
			"item_code.description",
			"Text Editor",
			validate_fields_for_doctype=False
		)
		
		print("   ✓ web_long_description → fetch_from: item_code.description\n")
		
	except Exception as e:
		print(f"   ⚠ Uyarı: {str(e)}\n")


def remove_fetch_from_description():
	"""
	Website Item'ın description field'ının fetch_from'unu kaldırır.
	
	Not: Bu field artık gereksiz çünkü web_long_description kullanılacak.
	Ancak mevcut verileri korumak için field'ı silmiyoruz, sadece fetch_from'u kaldırıyoruz.
	"""
	print("2️⃣  description field'ının fetch_from'u kaldırılıyor...\n")
	
	try:
		# Property Setter'ı kontrol et
		ps = frappe.db.exists(
			"Property Setter",
			{
				"doc_type": "Website Item",
				"field_name": "description",
				"property": "fetch_from"
			}
		)
		
		if ps:
			frappe.delete_doc("Property Setter", ps, force=True)
			print("   ✓ description field'ının fetch_from'u kaldırıldı\n")
		else:
			# JSON'daki fetch_from'u kaldıramayız, sadece bilgi verelim
			print("   ℹ description field'ının fetch_from'u JSON'da tanımlı")
			print("   → Bu field artık kullanılmayacak, web_long_description kullanılacak\n")
			
	except Exception as e:
		print(f"   ⚠ Uyarı: {str(e)}\n")


def migrate_description_data():
	"""
	Item.description verilerini Website Item.web_long_description'a kopyalar.
	"""
	print("3️⃣  Mevcut veriler migrate ediliyor...\n")
	
	# Tüm Website Item'ları al
	web_items = frappe.get_all(
		"Website Item",
		fields=["name", "item_code", "web_long_description"]
	)
	
	updated_count = 0
	skipped_count = 0
	
	for web_item in web_items:
		try:
			if not web_item.item_code:
				continue
			
			# Item'dan description al
			item_desc = frappe.db.get_value("Item", web_item.item_code, "description")
			
			if not item_desc:
				skipped_count += 1
				continue
			
			# Eğer web_long_description boşsa, Item.description'ı kopyala
			if not web_item.web_long_description:
				frappe.db.set_value(
					"Website Item",
					web_item.name,
					"web_long_description",
					item_desc,
					update_modified=False
				)
				updated_count += 1
				print(f"   ✓ {web_item.name} güncellendi")
			else:
				# Zaten dolu, atla
				skipped_count += 1
				
		except Exception as e:
			print(f"   ✗ Hata ({web_item.name}): {str(e)}")
	
	print(f"\n   📊 Özet:")
	print(f"      Güncellenen: {updated_count}")
	print(f"      Atlanan: {skipped_count}")
	print(f"      Toplam: {len(web_items)}\n")


def sync_single_item_descriptions(item_code):
	"""
	Tek bir Item'ın description'ını Website Item'a senkronize eder.
	
	Args:
		item_code: Item kodu
	"""
	try:
		web_item_name = frappe.db.get_value("Website Item", {"item_code": item_code}, "name")
		
		if not web_item_name:
			print(f"❌ {item_code} için Website Item bulunamadı")
			return False
		
		# Item'dan description al
		item_desc = frappe.db.get_value("Item", item_code, "description")
		
		if not item_desc:
			print(f"⚠ {item_code} Item'ında description boş")
			return False
		
		# web_long_description'ı güncelle
		frappe.db.set_value(
			"Website Item",
			web_item_name,
			"web_long_description",
			item_desc,
			update_modified=False
		)
		
		frappe.db.commit()
		
		print(f"✓ {web_item_name} senkronize edildi")
		return True
		
	except Exception as e:
		print(f"✗ Hata: {str(e)}")
		return False







