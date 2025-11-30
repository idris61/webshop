import frappe


def execute(doc, method=None):
    """
    Update Website Item if change in Item impacts it.
    
    Dinamik olarak tüm fetch_from ile eşleştirilmiş alanları günceller.
    Table field'lar için de otomatik sync yapar.
    """
    web_item = frappe.db.exists("Website Item", {"item_code": doc.item_code})

    if not web_item:
        return
    
    doc_before_save = doc.get_doc_before_save()
    if not doc_before_save:
        return
    
    changed = {}
    
    # 1. Website Item'ın tüm fetch_from mapping'lerini dinamik olarak al
    fetch_from_map = get_fetch_from_mappings()
    
    # 2. Item'da değişen fieldları kontrol et ve Website Item field'ına map et
    for item_field, web_item_field in fetch_from_map.items():
        # Eğer Item'da bu field varsa ve değiştiyse
        if hasattr(doc, item_field):
            old_value = doc_before_save.get(item_field)
            new_value = doc.get(item_field)
            
            if old_value != new_value:
                # Özel durumlar
                if item_field == "disabled":
                    changed["published"] = not new_value
                else:
                    changed[web_item_field] = new_value
    
    # 3. Table field'ları sync et (fetch_from çalışmaz, manuel sync gerekir)
    sync_table_fields(doc, web_item)
    
    # 4. Değişiklikler varsa Website Item'ı güncelle
    if changed:
        web_item_doc = frappe.get_doc("Website Item", web_item)
        web_item_doc.update(changed)
        web_item_doc.save()


def sync_table_fields(item_doc, web_item_name):
    """
    Item'daki table field değişikliklerini Website Item'a senkronize et.
    
    Item ve Website Item'da aynı fieldname'e sahip table field'ları bulur
    ve Item'daki değişiklikleri Website Item'a kopyalar.
    
    Args:
        item_doc: Item document
        web_item_name: Website Item name
    """
    # Item ve Website Item meta'larını al
    item_meta = frappe.get_meta("Item")
    web_item_meta = frappe.get_meta("Website Item")
    
    # Item'daki tüm table field'ları bul
    item_table_fields = [
        df.fieldname for df in item_meta.fields 
        if df.fieldtype == "Table"
    ]
    
    # Website Item'da da aynı fieldname'e sahip table field'ları bul
    web_item_table_fields = [
        df.fieldname for df in web_item_meta.fields 
        if df.fieldtype == "Table"
    ]
    
    # Her iki tarafta da olan table field'ları sync et
    for fieldname in item_table_fields:
        if fieldname in web_item_table_fields:
            # Field değişti mi kontrol et
            if item_doc.has_value_changed(fieldname):
                sync_single_table_field(item_doc, web_item_name, fieldname)


def sync_single_table_field(item_doc, web_item_name, fieldname):
    """
    Tek bir table field'ı Item'dan Website Item'a senkronize et.
    
    Args:
        item_doc: Item document
        web_item_name: Website Item name
        fieldname: Table field name (örn: product_badges, product_categories)
    """
    try:
        # Table field'ın child doctype'ını al
        item_meta = frappe.get_meta("Item")
        field_def = item_meta.get_field(fieldname)
        
        if not field_def or field_def.fieldtype != "Table":
            return
        
        child_doctype = field_def.options
        
        # Child doctype'ın geçerli olduğunu kontrol et
        if not frappe.db.exists("DocType", child_doctype):
            return
        
        # Mevcut child table kayıtlarını temizle (SQL ile)
        # Not: child_doctype meta'dan geldiği için güvenli, validate edildi
        frappe.db.sql(f"""
            DELETE FROM `tab{child_doctype}` 
            WHERE parent = %s AND parenttype = 'Website Item' AND parentfield = %s
        """, (web_item_name, fieldname))
        
        # Item'daki child table kayıtlarını kopyala
        if item_doc.get(fieldname):
            child_meta = frappe.get_meta(child_doctype)
            # Sistem field'larını hariç tut
            system_fields = ["name", "creation", "modified", "modified_by", "owner", "docstatus", "parent", "parenttype", "parentfield", "idx"]
            child_fields = [
                df.fieldname for df in child_meta.fields 
                if df.fieldname not in system_fields
            ]
            
            for idx, child_row in enumerate(item_doc.get(fieldname) or [], 1):
                # Child row'dan değerleri al
                values = {
                    "name": frappe.generate_hash(length=10),
                    "creation": frappe.utils.now(),
                    "modified": frappe.utils.now(),
                    "modified_by": frappe.session.user,
                    "owner": frappe.session.user,
                    "docstatus": 0,
                    "parent": web_item_name,
                    "parenttype": "Website Item",
                    "parentfield": fieldname,
                    "idx": idx
                }
                
                # Child row'daki tüm field'ları kopyala
                for child_field in child_fields:
                    if hasattr(child_row, child_field):
                        values[child_field] = getattr(child_row, child_field, None)
                
                # SQL ile insert (güvenli: child_doctype ve columns meta'dan geliyor)
                columns = ", ".join([f"`{k}`" for k in values.keys()])
                placeholders = ", ".join(["%s"] * len(values))
                
                frappe.db.sql(f"""
                    INSERT INTO `tab{child_doctype}` ({columns})
                    VALUES ({placeholders})
                """, list(values.values()))
        
        # Cache'i temizle
        frappe.clear_cache(doctype="Website Item")
        
    except Exception as e:
        # Hata logla ama Item save'ini engelleme
        frappe.log_error(
            f"Item: {item_doc.item_code} - Table field sync hatası ({fieldname}): {str(e)}", 
            "Website Item Table Field Sync Failed"
        )


def get_fetch_from_mappings():
    """
    Website Item'ın tüm fetch_from mapping'lerini döndürür.
    
    Returns:
        dict: {item_field: web_item_field} formatında mapping
        
    Örnek:
        {
            "description": "web_long_description",
            "custom_short_description": "short_description",
            "default_supplier": "supplier",
            "item_name": "item_name",
            ...
        }
    """
    mappings = {}
    
    # 1. Website Item JSON'dan fetch_from tanımlarını al
    web_item_meta = frappe.get_meta("Website Item", cached=False)
    
    for field in web_item_meta.fields:
        if field.fetch_from:
            # fetch_from formatı: "item_code.field_name" veya "link_field.field_name"
            fetch_parts = field.fetch_from.split(".")
            
            if len(fetch_parts) == 2:
                link_field, source_field = fetch_parts
                
                # Sadece item_code üzerinden gelen fetch'leri al
                if link_field == "item_code":
                    mappings[source_field] = field.fieldname
    
    # 2. Property Setter'lardan eklenen fetch_from'ları al
    property_setters = frappe.get_all(
        "Property Setter",
        filters={
            "doc_type": "Website Item",
            "property": "fetch_from"
        },
        fields=["field_name", "value"]
    )
    
    for ps in property_setters:
        if ps.value:
            fetch_parts = ps.value.split(".")
            
            if len(fetch_parts) == 2:
                link_field, source_field = fetch_parts
                
                if link_field == "item_code":
                    mappings[source_field] = ps.field_name
    
    # 3. Özel durumlar (manuel mapping)
    special_mappings = {
        "disabled": "published",  # Ters mantık: disabled=1 → published=0
        "short_description": "short_description",  # Item.short_description → Website Item.short_description
    }
    
    mappings.update(special_mappings)
    
    return mappings
