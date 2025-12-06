"""
ERP Item kartlarındaki açıklamaları Website Item'a aktarır.
Kullanım: bench --site site_name execute webshop.webshop.utils.sync_descriptions.sync_all_descriptions
"""
import frappe
from frappe.utils import strip_html_tags, cstr


def sync_all_descriptions():
	"""
	Tüm Website Item'lardaki web_long_description field'ını
	Item'daki description field'ından güncelleyerek senkronize eder.
	
	Item.description → Website Item.web_long_description
	"""
	print("\n" + "="*70)
	print("ERP ITEM AÇIKLAMALARINI WEBSITE ITEM'A SENKRONIZE ET")
	print("="*70 + "\n")
	
	# Tüm Website Item'ları al
	web_items = frappe.get_all(
		"Website Item",
		fields=["name", "item_code", "web_long_description"]
	)
	
	print(f"📦 Toplam {len(web_items)} Website Item bulundu\n")
	
	updated_count = 0
	skipped_count = 0
	error_count = 0
	
	for web_item in web_items:
		try:
			if not web_item.item_code:
				skipped_count += 1
				continue
				
			# Item'dan description'ı al
			item_description = frappe.db.get_value(
				"Item",
				web_item.item_code,
				"description"
			)
			
			if not item_description:
				skipped_count += 1
				continue
			
			# Mevcut web_long_description ile karşılaştır
			current_web_desc = cstr(web_item.web_long_description or "").strip()
			new_item_desc = cstr(item_description or "").strip()
			
			# HTML'den arındırılmış içeriklerle karşılaştır
			current_clean = strip_html_tags(current_web_desc) if current_web_desc else ""
			new_clean = strip_html_tags(new_item_desc) if new_item_desc else ""
			
			# Eğer farklıysa güncelle
			if current_clean != new_clean:
				frappe.db.set_value(
					"Website Item",
					web_item.name,
					"web_long_description",
					item_description,
					update_modified=False
				)
				updated_count += 1
				print(f"✓ {web_item.item_code} - {web_item.name}")
			else:
				skipped_count += 1
					
		except Exception as e:
			error_count += 1
			frappe.log_error(
				title=f"Description Sync Hatası: {web_item.name}",
				message=f"Item Code: {web_item.item_code}\nHata: {str(e)}"
			)
			print(f"✗ Hata ({web_item.item_code}): {str(e)}")
	
	frappe.db.commit()
	
	# Cache temizle
	frappe.clear_cache()
	
	print("\n" + "="*70)
	print("SENKRONIZASYON TAMAMLANDI")
	print("="*70)
	print(f"✅ Güncellenen: {updated_count} Website Item")
	print(f"⏭️  Atlanan: {skipped_count} Website Item")
	print(f"❌ Hata: {error_count} Website Item")
	print("="*70 + "\n")
	
	return {
		"total_updated": updated_count,
		"skipped": skipped_count,
		"errors": error_count
	}


def sync_single_item(item_code):
	"""
	Tek bir Item'ın açıklamasını Website Item'a aktarır.
	
	Args:
		item_code: Item kodu
	"""
	try:
		# Website Item'ı bul
		web_item_name = frappe.db.get_value("Website Item", {"item_code": item_code}, "name")
		
		if not web_item_name:
			print(f"❌ {item_code} için Website Item bulunamadı")
			return False
		
		# Item'dan description'ı al
		item_description = frappe.db.get_value("Item", item_code, "description")
		
		if not item_description:
			print(f"ℹ {item_code} için Item'da description yok")
			return False
		
		# Website Item'ı al
		web_item = frappe.get_cached_doc("Website Item", web_item_name)
		
		# Mevcut web_long_description ile karşılaştır
		current_web_desc = cstr(web_item.web_long_description or "").strip()
		new_item_desc = cstr(item_description or "").strip()
		
		# HTML'den arındırılmış içeriklerle karşılaştır
		current_clean = strip_html_tags(current_web_desc) if current_web_desc else ""
		new_clean = strip_html_tags(new_item_desc) if new_item_desc else ""
		
		# Eğer farklıysa güncelle
		if current_clean != new_clean:
			frappe.db.set_value(
				"Website Item",
				web_item_name,
				"web_long_description",
				item_description,
				update_modified=False
			)
			frappe.db.commit()
			
			print(f"✓ {web_item_name} güncellendi")
			print(f"  └─ Web Sitesi Açıklaması senkronize edildi")
			return True
		else:
			print(f"ℹ {web_item_name} zaten güncel")
			return True
			
	except Exception as e:
		frappe.log_error(
			title=f"Description Sync Hatası: {item_code}",
			message=f"Hata: {str(e)}"
		)
		print(f"✗ Hata: {str(e)}")
		return False

