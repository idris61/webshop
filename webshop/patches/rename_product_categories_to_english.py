import frappe
from frappe.model.rename_doc import rename_doc


CATEGORY_RENAME_MAP = {
	"Haut&Hände": "Skin & Hands",
	"Allzweckreiniger": "All-Purpose Cleaner",
	"Desinfektion": "Disinfection",
	"Duschgel": "Shower Gel",
	"Wipes/Vliestücher": "Wipes",
	"Zubehör für Reinigungsmittel": "Cleaning Accessories",
	"Oberfläche, Reinigung": "Surface Cleaning",
	"Einweghandschuhe": "Disposable Gloves",
	"Genel": "General",
}


def execute():
	for old_name, new_name in CATEGORY_RENAME_MAP.items():
		try:
			if not frappe.db.exists("Product Category", old_name):
				continue

			# Already renamed
			if old_name == new_name or frappe.db.exists("Product Category", new_name):
				# If target exists, only delete old doc if duplicate? safer skip
				if old_name != new_name and frappe.db.exists("Product Category", new_name):
					frappe.logger().info(
						f"[webshop] Product Category rename skipped: target '{new_name}' already exists."
					)
				continue

			rename_doc(
				"Product Category",
				old_name,
				new_name,
				ignore_permissions=True,
				force=True,
			)
		except Exception as exc:
			frappe.log_error(
				title="Product Category Rename Failed",
				message=f"Could not rename '{old_name}' to '{new_name}': {str(exc)}",
			)

