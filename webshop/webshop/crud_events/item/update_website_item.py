import frappe


def execute(doc, method=None):
    """
    Update Website Item if change in Item impacts it.
    
    Dinamik olarak tüm fetch_from ile eşleştirilmiş alanları günceller.
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
    
    # 3. Değişiklikler varsa Website Item'ı güncelle
    if changed:
        web_item_doc = frappe.get_doc("Website Item", web_item)
        web_item_doc.update(changed)
        web_item_doc.save()


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
    }
    
    mappings.update(special_mappings)
    
    return mappings
