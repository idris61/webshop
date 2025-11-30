# Dinamik Çeviri Sistemi - Kullanım Kılavuzu

## Genel Bakış

Portal'da tüm ürün isimleri, açıklamaları ve filtre değerleri dinamik olarak çevrilir. Sistem ERPNext'in Translation DocType'ını kullanır.

## Nasıl Çalışır?

### 1. Çeviri Öncelik Sırası

Sistem çevirileri şu sırayla arar:

1. **Custom Field Çevirileri** (En Özel)
   - Item/Website Item'da `description_tr`, `description_de` gibi dil bazlı custom field'lar varsa bunlar kullanılır
   - Örnek: `description_tr` → Türkçe açıklama

2. **Context-Based Çeviriler** (Orta Özel)
   - Translation DocType'ında `context` field'ı kullanılarak
   - Format: `DocType::Name::Field`
   - Örnek: `Item::ITEM-001::description` → Bu Item'ın description'ı için özel çeviri

3. **Source Text Çevirileri** (Genel)
   - Translation DocType'ında `source_text` field'ı kullanılarak
   - Aynı metin tüm yerlerde aynı şekilde çevrilir
   - Örnek: "Produktdetails" → "Ürün Detayları"

4. **Frappe Translation System** (Fallback)
   - Frappe'nin kendi çeviri sistemi (tr.csv, de.csv dosyaları)

## Çeviri Ekleme Yöntemleri

### Yöntem 1: Source Text Bazlı (Önerilen - Dinamik)

**Avantajlar:**
- Item description değişse bile çeviri çalışır
- Aynı metin tüm ürünlerde otomatik çevrilir
- Bakımı kolay

**Nasıl Eklenir:**

1. ERPNext'te **Translation** DocType'ına gidin
2. Yeni kayıt oluşturun:
   - **Source Text**: Orijinal metin (örn: "Produktdetails PVAmicro...")
   - **Translated Text**: Çevrilmiş metin (örn: "PVAmicro ürün detayları...")
   - **Language**: Hedef dil (örn: Turkish)
   - **Context**: Boş bırakın (genel çeviri için)

**Örnek:**
```
Source Text: Produktdetails PVAmicro verbindet zwei Materialien...
Translated Text: PVAmicro iki malzemeyi benzersiz bir kompozisyonda birleştirir...
Language: Turkish
Context: (boş)
```

### Yöntem 2: Context-Based (Belirli Ürün İçin)

**Avantajlar:**
- Belirli bir ürün için özel çeviri
- Aynı metin farklı ürünlerde farklı çevrilebilir

**Nasıl Eklenir:**

1. ERPNext'te **Translation** DocType'ına gidin
2. Yeni kayıt oluşturun:
   - **Source Text**: Orijinal metin
   - **Translated Text**: Çevrilmiş metin
   - **Language**: Hedef dil
   - **Context**: `Item::ITEM-CODE::description` formatında

**Örnek:**
```
Source Text: Produktdetails PVAmicro...
Translated Text: PVAmicro ürün detayları...
Language: Turkish
Context: Item::ITEM-001::description
```

### Yöntem 3: Custom Field (En Özel)

**Avantajlar:**
- Item/Website Item'da direkt çeviri alanı
- En hızlı çözüm

**Nasıl Eklenir:**

1. Item veya Website Item DocType'ına custom field ekleyin
2. Field adı: `description_tr`, `description_de` gibi
3. Item kaydında bu field'a çeviriyi yazın

## Önemli Notlar

### Cache Yönetimi

- Çeviriler 5 dakika cache'lenir
- Item/Website Item güncellendiğinde cache otomatik temizlenir
- Translation DocType güncellendiğinde cache otomatik temizlenir

### Item Description Değiştiğinde

Eğer **Source Text** bazlı çeviri kullanıyorsanız:
- Item description değişse bile çeviri çalışır
- Sadece yeni metin için yeni çeviri eklemeniz gerekir

Eğer **Context-Based** çeviri kullanıyorsanız:
- Item description değiştiğinde Translation kaydını güncellemeniz gerekir
- Ya da yeni context ile yeni çeviri eklemeniz gerekir

## Örnek Senaryolar

### Senaryo 1: Tüm Ürünlerde Aynı Açıklama

**Durum:** Tüm ürünlerde "Produktdetails" kelimesi geçiyor

**Çözüm:** Source Text bazlı çeviri
```
Source Text: Produktdetails
Translated Text: Ürün Detayları
Language: Turkish
```

### Senaryo 2: Belirli Ürün İçin Özel Çeviri

**Durum:** Sadece "Vileda PVAmicro blau" ürünü için özel çeviri

**Çözüm:** Context-Based çeviri
```
Source Text: Vileda PVAmicro blau
Translated Text: Vileda PVAmicro mavi
Language: Turkish
Context: Item::ITEM-001::item_name
```

### Senaryo 3: Item Description Değişken

**Durum:** Item description sık sık değişiyor

**Çözüm:** Source Text bazlı çeviri (önerilen)
- Item description değişse bile çeviri çalışır
- Sadece yeni metin için yeni çeviri eklemeniz gerekir

## Teknik Detaylar

### Çeviri Fonksiyonları

- `get_translated_doc(doc, language, fields)`: Document çevirisi
- `get_translated_text(source_text, language)`: Metin çevirisi
- `get_translated_list(docs, language, fields)`: Liste çevirisi

### Cache Keys

- `translated_doc:{doctype}:{name}:{language}`
- `translated_text:{hash}:{language}`

### Hook'lar

- `Item.on_update` → Translation cache temizlenir
- `Website Item.on_update` → Translation cache temizlenir
- `Translation.on_update` → Translation cache temizlenir

## Sorun Giderme

### Çeviri Görünmüyor

1. Cache'i temizleyin: `bench --site site_name clear-cache`
2. Translation DocType'ında kayıt var mı kontrol edin
3. Language field'ı doğru mu kontrol edin (Turkish, German, etc.)
4. Source Text tam olarak eşleşiyor mu kontrol edin (boşluk, büyük/küçük harf)

### Item Description Değişti Ama Çeviri Çalışmıyor

1. Source Text bazlı çeviri kullanıyorsanız, yeni metin için yeni çeviri ekleyin
2. Context-Based çeviri kullanıyorsanız, Translation kaydını güncelleyin

### Performans Sorunları

- Cache 5 dakika tutulur, bu normal
- Çok fazla Translation kaydı varsa, source_text bazlı çeviri kullanın (daha hızlı)










