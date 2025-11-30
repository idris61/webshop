"""
Script to add translations for blog posts - Fixed version
"""
import frappe

def add_blog_translations():
	"""Add translations for all blog posts"""
	frappe.init(site='north_medical.local')
	frappe.connect()
	
	def create_translation(language, source_text, translated_text):
		"""Create or update a translation record"""
		if not source_text or not isinstance(source_text, str) or not source_text.strip():
			return None
		
		source_text = source_text.strip()
		
		# Check if translation already exists
		existing = frappe.db.get_value(
			"Translation",
			{
				"source_text": source_text,
				"language": language
			},
			"name"
		)
		
		if existing:
			doc = frappe.get_doc("Translation", existing)
			doc.translated_text = translated_text
			doc.save(ignore_permissions=True)
			return existing
		else:
			doc = frappe.new_doc("Translation")
			doc.language = language
			doc.source_text = source_text
			doc.translated_text = translated_text
			doc.insert(ignore_permissions=True)
			return doc.name
	
	# Blog translations
	translations = {
		"COVID-19 zamanlarında canlandırma": {
			"en": "Resuscitation in times of COVID-19",
			"de": "Wiederbelebung in Zeiten von COVID-19",
			"it": "Rianimazione ai tempi del COVID-19",
			"fr": "Réanimation en temps de COVID-19"
		},
		"COVID-19 salgını son haftalarda hayatın her alanında önemli değişikliklere yol açtı.": {
			"en": "The COVID-19 pandemic has led to significant changes in all areas of life in recent weeks.",
			"de": "Die COVID-19-Pandemie hat in den letzten Wochen zu erheblichen Veränderungen in allen Lebensbereichen geführt.",
			"it": "La pandemia di COVID-19 ha portato a cambiamenti significativi in tutti gli ambiti della vita nelle ultime settimane.",
			"fr": "La pandémie de COVID-19 a entraîné des changements importants dans tous les domaines de la vie ces dernières semaines."
		},
		"Yeni AB Tıbbi Cihaz Yönetmeliği (MDR) geliyor": {
			"en": "New EU Medical Device Regulation (MDR) is coming",
			"de": "Neue EU-Medizinprodukteverordnung (MDR) kommt",
			"it": "Arriva il nuovo Regolamento UE sui Dispositivi Medici (MDR)",
			"fr": "Le nouveau Règlement UE sur les Dispositifs Médicaux (MDR) arrive"
		},
		"Üç yıllık geçiş süreci sona ermek üzere.": {
			"en": "The three-year transition period is coming to an end.",
			"de": "Die dreijährige Übergangsphase geht zu Ende.",
			"it": "Il periodo di transizione di tre anni sta volgendo al termine.",
			"fr": "La période de transition de trois ans touche à sa fin."
		},
		"Koronavirüs önleme": {
			"en": "Coronavirus prevention",
			"de": "Coronavirus-Prävention",
			"it": "Prevenzione del coronavirus",
			"fr": "Prévention du coronavirus"
		},
		"Sınırlı virüs öldürücü dezenfektanlar*, bir virüse karşı koruma sağlar": {
			"en": "Limited virucidal disinfectants* provide protection against a virus",
			"de": "Begrenzt viruzide Desinfektionsmittel* bieten Schutz vor einem Virus",
			"it": "Disinfettanti virucidi limitati* forniscono protezione contro un virus",
			"fr": "Les désinfectants virucides limités* offrent une protection contre un virus"
		},
		"Sağlık hizmetleri ve resüsitasyon özellikle etkilendi.": {
			"en": "Health services and resuscitation were particularly affected.",
			"de": "Gesundheitsdienste und Wiederbelebung waren besonders betroffen.",
			"it": "I servizi sanitari e la rianimazione sono stati particolarmente colpiti.",
			"fr": "Les services de santé et la réanimation ont été particulièrement touchés."
		},
		"Alman Resüsitasyon Konseyi (GRC), resüsitasyon prosedürlerini bu nedenle uyarladı.": {
			"en": "The German Resuscitation Council (GRC) has therefore adapted resuscitation procedures.",
			"de": "Der Deutsche Rat für Wiederbelebung (GRC) hat daher die Wiederbelebungsverfahren angepasst.",
			"it": "Il Consiglio tedesco per la rianimazione (GRC) ha quindi adattato le procedure di rianimazione.",
			"fr": "Le Conseil allemand de réanimation (GRC) a donc adapté les procédures de réanimation."
		},
		"Covid-19 döneminde resüsitasyona ilişkin bilgi formu": {
			"en": "Information form on resuscitation during the Covid-19 period",
			"de": "Informationsformular zur Wiederbelebung während der Covid-19-Periode",
			"it": "Modulo informativo sulla rianimazione durante il periodo Covid-19",
			"fr": "Formulaire d'information sur la réanimation pendant la période Covid-19"
		}
	}
	
	# Add translations
	count = 0
	for source_text, lang_translations in translations.items():
		for language, translated_text in lang_translations.items():
			try:
				create_translation(language, source_text, translated_text)
				count += 1
			except Exception as e:
				print(f"Error: {e}")
	
	frappe.db.commit()
	print(f"✓ Added {count} blog translations!")
	return count

if __name__ == "__main__":
	add_blog_translations()




