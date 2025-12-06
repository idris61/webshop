"""
Webshop Installation Setup
Migration işlemleri ve settings yapılandırması
Custom field'lar ve property setter'lar fixture'lardan yüklenir
"""
import frappe
from frappe import _

# Default filter fields to add during installation
DEFAULT_FILTER_FIELDS = ["stock_uom", "primary_supplier"]


def after_install():
	"""App kurulumundan sonra çalışır"""
	try:
		setup_webshop_settings()
		navbar_add_products_link()
		frappe.db.commit()
	except Exception as e:
		frappe.log_error(
			title="Webshop Installation Error",
			message=f"Error during webshop installation: {str(e)}"
		)
		# Install sırasında hata olsa bile devam et
		pass


def setup_webshop_settings():
	"""Webshop Settings'i yapılandır - field filtrelerini ekle"""
	try:
		settings = frappe.get_doc("Webshop Settings")
		needs_save = False
		
		# Field filters'ı etkinleştir
		if not settings.enable_field_filters:
			settings.enable_field_filters = 1
			needs_save = True
		
		# Mevcut filtreleri kontrol et
		existing_filters = [row.fieldname for row in settings.filter_fields or []]
		
		# Default filtreleri ekle (yoksa)
		for filter_name in DEFAULT_FILTER_FIELDS:
			if filter_name not in existing_filters:
				settings.append("filter_fields", {"fieldname": filter_name})
				needs_save = True
		
		# Eski supplier filtresini primary_supplier'a güncelle (bir kez yapılmalı)
		# Bu migration logic'i patch'e taşınmalı, şimdilik burada kalıyor
		for filter_field in settings.filter_fields or []:
			if filter_field.fieldname == "supplier":
				filter_field.fieldname = "primary_supplier"
				needs_save = True
				break
		
		if needs_save:
			settings.flags.ignore_permissions = True
			settings.save()
			frappe.db.commit()
	except frappe.DoesNotExistError:
		# Webshop Settings henüz oluşturulmamış, normal
		pass
	except Exception as e:
		frappe.log_error(
			title="Webshop Settings Setup Error",
			message=f"Error setting up webshop settings: {str(e)}"
		)


def navbar_add_products_link():
	"""Website Settings'e Products link'i ekle (yoksa)"""
	try:
		website_settings = frappe.get_doc("Website Settings")
		
		# Zaten link var mı kontrol et
		existing_links = [item.url for item in website_settings.top_bar_items or []]
		if "/all-products" in existing_links:
			return
		
		website_settings.append(
			"top_bar_items",
			{
				"label": _("Shop"),
				"url": "/all-products",
				"right": False,
			},
		)
		website_settings.flags.ignore_permissions = True
		website_settings.save()
		frappe.db.commit()
	except frappe.DoesNotExistError:
		# Website Settings henüz oluşturulmamış, normal
		pass
	except Exception as e:
		frappe.log_error(
			title="Navbar Setup Error",
			message=f"Error adding products link to navbar: {str(e)}"
		)


