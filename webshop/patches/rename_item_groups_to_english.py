import frappe
from frappe.model.rename_doc import rename_doc


ITEM_GROUP_RENAME_MAP = {
	"Tüm Ürün Grupları": "All Item Groups",
}


def execute():
	for old_name, new_name in ITEM_GROUP_RENAME_MAP.items():
		if not frappe.db.exists("Item Group", old_name):
			continue

		# Skip if already renamed
		if frappe.db.exists("Item Group", new_name):
			continue

		rename_doc(
			"Item Group",
			old_name,
			new_name,
			ignore_permissions=True,
			force=True,
		)

		# Ensure the item_group_name field matches the new title
		frappe.db.set_value(
			"Item Group",
			new_name,
			"item_group_name",
			new_name,
			update_modified=False,
		)

