"""
Script to add translations for blog posts
"""
import frappe
from frappe.website.doctype.blog_post.blog_post import get_html_content_based_on_type

def get_blog_posts():
	"""Get all published blog posts"""
	return frappe.get_all(
		'Blog Post',
		fields=['name', 'title', 'blog_intro', 'content', 'content_type', 'content_html', 'content_md'],
		filters={'published': 1}
	)

def create_translation(language, source_text, translated_text, context=None):
	"""Create or update a translation record"""
	if not source_text or not isinstance(source_text, str) or not source_text.strip():
		return None
	
	# Check if translation already exists
	existing = frappe.db.get_value(
		"Translation",
		{
			"source_text": source_text.strip(),
			"language": language
		},
		"name"
	)
	
	if existing:
		# Update existing translation
		doc = frappe.get_doc("Translation", existing)
		doc.translated_text = translated_text
		doc.context = context
		doc.save(ignore_permissions=True)
		return existing
	else:
		# Create new translation
		doc = frappe.new_doc("Translation")
		doc.language = language
		doc.source_text = source_text.strip()
		doc.translated_text = translated_text
		if context:
			doc.context = context
		doc.insert(ignore_permissions=True)
		return doc.name

def add_blog_translations():
	"""Add translations for all blog posts"""
	posts = get_blog_posts()
	
	# Translation mappings for blog posts
	# Format: {source_text: {language: translated_text}}
	translations = {
		# Blog Post 1: COVID-19 zamanlarında canlandırma
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
		# Blog Post 2: Yeni AB Tıbbi Cihaz Yönetmeliği (MDR) geliyor
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
		# Blog Post 3: Koronavirüs önleme
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
		}
	}
	
	# Add translations
	for source_text, lang_translations in translations.items():
		for language, translated_text in lang_translations.items():
			try:
				create_translation(language, source_text, translated_text)
				print(f"✓ Added translation: {source_text[:50]}... -> {language}")
			except Exception as e:
				print(f"✗ Error adding translation for {source_text[:50]}... ({language}): {e}")
	
	# Process each blog post for content translation
	for post in posts:
		post_name = post['name']
		
		# Get HTML content
		html_content = get_html_content_based_on_type(
			frappe.get_doc("Blog Post", post_name),
			"content",
			post.get('content_type', 'Markdown')
		)
		
		# For now, we'll add translations for titles and intros
		# Content translations should be added manually or via a more sophisticated system
		# as blog content can be very long and complex
		
		print(f"\nProcessed blog post: {post_name}")
	
	print("\n✓ Blog translations added successfully!")
	frappe.db.commit()

if __name__ == "__main__":
	add_blog_translations()






