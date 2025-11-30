import frappe
from frappe import _


def add_translation_helpers(context):
	from webshop.webshop.utils.translation import get_translated_text, get_translated_doc
	context.translate_text = get_translated_text
	context.translate_doc = get_translated_doc


def get_translated_doc(doc, language=None, fields=None):
	if not doc:
		return doc
	
	if not language:
		language = frappe.local.lang or "en"
	
	if not isinstance(doc, dict):
		if hasattr(doc, "as_dict"):
			try:
				doc = doc.as_dict()
			except:
				if hasattr(doc, "__dict__"):
					doc = dict(doc.__dict__)
		elif hasattr(doc, "__dict__"):
			doc = dict(doc)
	
	if fields is None:
		fields = [
			"item_name", "web_item_name", "description", "website_description",
			"web_long_description", "short_description", "website_specifications", 
			"item_group", "brand"
		]
	
	cache_key = f"translated_doc:{doc.get('doctype', 'Unknown')}:{doc.get('name', 'Unknown')}:{language}"
	cached = frappe.cache().get_value(cache_key)
	if cached:
		return cached
	
	translated_doc = doc.copy()
	language_key = (language or "").lower().replace("-", "_")
	if language_key not in ["tr", "en", "de"]:
		language_key = "en"

	for field in fields:
		if field not in translated_doc:
			continue
		
		value = translated_doc[field]
		if not value or not isinstance(value, str):
			continue
		
		translated_value = None

		if language_key in ["tr", "en", "de"]:
			if field == "web_item_name":
				lang_field = f"web_item_name_{language_key}"
				if lang_field in translated_doc and translated_doc.get(lang_field):
					lang_value = (translated_doc.get(lang_field) or "").strip()
					if lang_value:
						translated_value = lang_value
			elif field == "web_long_description":
				lang_field = f"web_long_description_{language_key}"
				if lang_field in translated_doc and translated_doc.get(lang_field):
					lang_value = (translated_doc.get(lang_field) or "").strip()
					if lang_value:
						translated_value = lang_value
			else:
				lang_field = f"{field}_{language_key}"
				if lang_field in translated_doc and translated_doc.get(lang_field):
					lang_value = (translated_doc.get(lang_field) or "").strip()
					if lang_value:
						translated_value = lang_value

		if not translated_value or not translated_value.strip():
			translated_value = (value or "").strip()

		if not translated_value or (translated_value == value and value):
			context_key = f"{doc.get('doctype')}::{doc.get('name')}::{field}"
			text_translation = frappe.db.get_value(
				"Translation",
				{"language": language, "context": context_key},
				"translated_text"
			)
			if text_translation:
				translated_value = text_translation
			else:
				text_translation = frappe.db.get_value(
					"Translation",
					{"source_text": value.strip(), "language": language},
					"translated_text"
				)
				if text_translation:
					translated_value = text_translation
				else:
					text_translation = get_translated_text(value, language)
					if text_translation and text_translation != value:
						translated_value = text_translation
		
		if translated_value and translated_value.strip():
			translated_doc[field] = translated_value
		elif value:
			translated_doc[field] = value
	
	frappe.cache().set_value(cache_key, translated_doc, expires_in_sec=300)
	
	return translated_doc


def get_translated_text(source_text, language=None):
	if not source_text or not isinstance(source_text, str):
		return source_text
	
	if not language:
		language = frappe.local.lang or "en"
	
	cache_key = f"translated_text:{hash(source_text)}:{language}"
	cached = frappe.cache().get_value(cache_key)
	if cached is not None:
		return cached
	
	translation = frappe.db.get_value(
		"Translation",
		{"source_text": source_text.strip(), "language": language},
		"translated_text"
	)
	
	if translation:
		result = translation
	else:
		result = _(source_text)
		if result == source_text:
			result = source_text
	
	frappe.cache().set_value(cache_key, result, expires_in_sec=300)
	
	return result


def get_translated_list(docs, language=None, fields=None):
	if not docs:
		return docs
	return [get_translated_doc(doc, language, fields) for doc in docs]


def clear_translation_cache(doc=None, method=None):
	try:
		frappe.cache().delete_keys("translated_doc:*")
		frappe.cache().delete_keys("translated_text:*")
	except:
		pass

