"""
ERP Item kartlarındaki açıklamaları Website Item'a aktarır.
Kullanım: bench --site culinary-test.local execute webshop.webshop.utils.sync_descriptions.sync_all_descriptions
"""
import frappe


def sync_all_descriptions():
	"""
	Tüm Website Item'lardaki description ve short_description fieldlarını
	Item'dan güncelleyerek senkronize eder.
	
	Item.description → Website Item.web_long_description
	Item.custom_short_description → Website Item.short_description
	"""
	print("\n" + "="*70)
	print("ERP ITEM AÇIKLAMALARINI WEBSITE ITEM'A SENKRONIZE ET")
	print("="*70 + "\n")
	
	# Tüm Website Item'ları al
	web_items = frappe.get_all(
		"Website Item",
		fields=["name", "item_code", "web_long_description", "short_description"]
	)
	
	print(f"📦 Toplam {len(web_items)} Website Item bulundu\n")
	
	updated_count = 0
	updated_fields = {"web_long_description": 0, "short_description": 0}
	
	for web_item in web_items:
		try:
			if not web_item.item_code:
				continue
				
			# Item'dan verileri al
			item_data = frappe.db.get_value(
				"Item",
				web_item.item_code,
				["description", "custom_short_description"],
				as_dict=True
			)
			
			if not item_data:
				continue
			
			updates = {}
			
			# Description → web_long_description
			if item_data.description:
				# HTML strip edip karşılaştır
				from frappe.utils import strip_html_tags
				item_desc = strip_html_tags(item_data.description) if item_data.description else ""
				web_desc = strip_html_tags(web_item.web_long_description) if web_item.web_long_description else ""
				
				if item_desc != web_desc:
					updates["web_long_description"] = item_data.description
					updated_fields["web_long_description"] += 1
			
			# custom_short_description → short_description
			if item_data.custom_short_description:
				if web_item.short_description != item_data.custom_short_description:
					updates["short_description"] = item_data.custom_short_description
					updated_fields["short_description"] += 1
			
			# Eğer güncelleme varsa kaydet
			if updates:
				for field, value in updates.items():
					frappe.db.set_value(
						"Website Item",
						web_item.name,
						field,
						value,
						update_modified=False
					)
				updated_count += 1
				print(f"✓ {web_item.name} ({web_item.item_code})")
				for field in updates.keys():
					field_label = "Web Sitesi Açıklaması" if field == "web_long_description" else "Kısa Açıklama"
					print(f"  └─ {field_label} güncellendi")
					
		except Exception as e:
			print(f"✗ Hata ({web_item.name}): {str(e)}")
	
	frappe.db.commit()
	
	print("\n" + "="*70)
	print("SENKRONIZASYON TAMAMLANDI")
	print("="*70)
	print(f"✅ Toplam {updated_count} Website Item güncellendi")
	print(f"   📝 Web Sitesi Açıklaması (web_long_description): {updated_fields['web_long_description']}")
	print(f"   📄 Kısa Açıklama (short_description): {updated_fields['short_description']}")
	print("="*70 + "\n")
	
	return {
		"total_updated": updated_count,
		"fields_updated": updated_fields
	}


def sync_single_item(item_code):
	"""
	Tek bir Item'ın açıklamalarını Website Item'a aktarır.
	
	Args:
		item_code: Item kodu
	"""
	try:
		# Website Item'ı bul
		web_item_name = frappe.db.get_value("Website Item", {"item_code": item_code}, "name")
		
		if not web_item_name:
			print(f"❌ {item_code} için Website Item bulunamadı")
			return False
		
		# Item'dan verileri al
		item = frappe.get_doc("Item", item_code)
		web_item = frappe.get_doc("Website Item", web_item_name)
		
		updates = {}
		
		# Description
		if hasattr(item, 'description') and item.description:
			if web_item.description != item.description:
				updates["description"] = item.description
		
		# Short Description
		if hasattr(item, 'custom_short_description') and item.custom_short_description:
			if web_item.short_description != item.custom_short_description:
				updates["short_description"] = item.custom_short_description
		
		if updates:
			for field, value in updates.items():
				frappe.db.set_value("Website Item", web_item_name, field, value, update_modified=False)
			
			frappe.db.commit()
			
			print(f"✓ {web_item_name} güncellendi")
			for field in updates.keys():
				print(f"  └─ {field} senkronize edildi")
			return True
		else:
			print(f"ℹ {web_item_name} zaten güncel")
			return True
			
	except Exception as e:
		print(f"✗ Hata: {str(e)}")
		return False

