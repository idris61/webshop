"""
Override BlogPost to add translation support
"""
import frappe
import re
from frappe import _
from frappe.website.doctype.blog_post.blog_post import (
	BlogPost as OriginalBlogPost,
	get_blog_list as original_get_blog_list,
	get_list_context as original_get_list_context,
	get_html_content_based_on_type,
	strip_html_tags,
	find_first_image,
)
from frappe.utils import get_fullname, global_date_format
from webshop.webshop.utils.translation import get_translated_text


def translate_html_content(html_content, language):
	"""
	Translate HTML content while preserving HTML tags.
	Translates text nodes between HTML tags.
	"""
	if not html_content or not isinstance(html_content, str):
		return html_content
	
	# If language is "tr" (Turkish), return original content as it's already in Turkish
	if language == "tr":
		return html_content
	
	# First, try to translate complete paragraphs that are wrapped in <p> tags
	# This handles the most common case for blog content
	def translate_paragraph(match):
		"""Translate content inside paragraph tags"""
		full_tag = match.group(0)
		opening_tag = match.group(1)
		content = match.group(2)
		closing_tag = match.group(3)
		
		if content.strip():
			# Try to translate the whole paragraph first
			translated = get_translated_text(content.strip(), language)
			if translated and translated != content.strip():
				return opening_tag + translated + closing_tag
			else:
				# If whole paragraph doesn't have translation, try sentence by sentence
				sentences = re.split(r'([.!?]\s+)', content)
				translated_sentences = []
				
				for sentence in sentences:
					if sentence.strip() and not re.match(r'^[.!?]\s*$', sentence):
						translated_sent = get_translated_text(sentence.strip(), language)
						if translated_sent and translated_sent != sentence.strip():
							translated_sentences.append(translated_sent)
						else:
							translated_sentences.append(sentence)
					else:
						translated_sentences.append(sentence)
				
				return opening_tag + ''.join(translated_sentences) + closing_tag
		return full_tag
	
	# Translate paragraphs wrapped in <p> tags
	html_content = re.sub(r'(<p[^>]*>)(.*?)(</p>)', translate_paragraph, html_content, flags=re.DOTALL | re.IGNORECASE)
	
	# Now handle any remaining text that's not in paragraph tags
	# Split HTML into tags and text segments
	parts = re.split(r'(<[^>]+>)', html_content)
	translated_parts = []
	
	for part in parts:
		if part.startswith('<') and part.endswith('>'):
			# This is an HTML tag, keep it as is
			translated_parts.append(part)
		else:
			# This is text content, translate it
			if part.strip():
				# Try to translate the whole text block first
				translated_text = get_translated_text(part.strip(), language)
				if translated_text and translated_text != part.strip():
					# Preserve leading/trailing whitespace
					leading_ws = len(part) - len(part.lstrip())
					trailing_ws = len(part) - len(part.rstrip())
					translated_parts.append(' ' * leading_ws + translated_text + ' ' * trailing_ws)
				else:
					# If whole block translation failed, try sentence by sentence
					sentences = re.split(r'([.!?]\s+)', part)
					translated_sentences = []
					
					for sentence in sentences:
						if sentence.strip() and not re.match(r'^[.!?]\s*$', sentence):
							translated_sent = get_translated_text(sentence.strip(), language)
							if translated_sent and translated_sent != sentence.strip():
								translated_sentences.append(translated_sent)
							else:
								translated_sentences.append(sentence)
						else:
							translated_sentences.append(sentence)
					
					translated_parts.append(''.join(translated_sentences))
			else:
				translated_parts.append(part)
	
	return ''.join(translated_parts)


class BlogPost(OriginalBlogPost):
	def get_context(self, context):
		"""Override get_context to add translation support"""
		# Call original method first
		super().get_context(context)
		
		# Get current language
		current_language = frappe.local.lang or "en"
		
		# Translate title
		if hasattr(self, 'title') and self.title:
			translated_title = get_translated_text(self.title, current_language)
			if translated_title and translated_title != self.title:
				context.title = translated_title
				# Also update the doc for template access
				if hasattr(context, 'doc'):
					context.doc.title = translated_title
		
		# Translate blog_intro
		if hasattr(self, 'blog_intro') and self.blog_intro:
			translated_intro = get_translated_text(self.blog_intro, current_language)
			if translated_intro and translated_intro != self.blog_intro:
				context.blog_intro = translated_intro
				# Also update the doc for template access
				if hasattr(context, 'doc'):
					context.doc.blog_intro = translated_intro
		
		# Translate content
		if hasattr(context, 'content') and context.content:
			# Content is HTML, translate it while preserving HTML structure
			translated_content = translate_html_content(context.content, current_language)
			if translated_content and translated_content != context.content:
				context.content = translated_content
				# Also update the doc for template access
				if hasattr(context, 'doc'):
					context.doc.content = translated_content
		
		# Translate category title
		if hasattr(context, 'category') and context.category and context.category.get('title'):
			translated_category_title = get_translated_text(context.category['title'], current_language)
			if translated_category_title and translated_category_title != context.category['title']:
				context.category['title'] = translated_category_title
		
		# Translate meta description
		if hasattr(context, 'description') and context.description:
			translated_description = get_translated_text(context.description, current_language)
			if translated_description and translated_description != context.description:
				context.description = translated_description
				if hasattr(context, 'metatags'):
					context.metatags['description'] = translated_description
		
		return context


def get_blog_list(doctype, txt=None, filters=None, limit_start=0, limit_page_length=20, order_by=None):
	"""Override get_blog_list to add translation support"""
	# Call original function
	posts = original_get_blog_list(doctype, txt, filters, limit_start, limit_page_length, order_by)
	
	# Get current language
	current_language = frappe.local.lang or "en"
	
	# Translate each post
	for post in posts:
		# Translate title
		if post.get('title'):
			translated_title = get_translated_text(post['title'], current_language)
			if translated_title and translated_title != post['title']:
				post['title'] = translated_title
		
		# Translate intro
		if post.get('intro'):
			translated_intro = get_translated_text(post['intro'], current_language)
			if translated_intro and translated_intro != post['intro']:
				post['intro'] = translated_intro
		
		# Translate category title
		if post.get('category') and post['category'].get('title'):
			translated_category_title = get_translated_text(post['category']['title'], current_language)
			if translated_category_title and translated_category_title != post['category']['title']:
				post['category']['title'] = translated_category_title
	
	return posts


def get_list_context(context=None):
	"""Override get_list_context to add translation support"""
	# Call original function
	list_context = original_get_list_context(context)
	
	# Get current language
	current_language = frappe.local.lang or "en"
	
	# Translate blog title
	if list_context.get('blog_title'):
		translated_title = get_translated_text(list_context['blog_title'], current_language)
		if translated_title and translated_title != list_context['blog_title']:
			list_context['blog_title'] = translated_title
	
	# Translate blog introduction
	if list_context.get('blog_introduction'):
		translated_intro = get_translated_text(list_context['blog_introduction'], current_language)
		if translated_intro and translated_intro != list_context['blog_introduction']:
			list_context['blog_introduction'] = translated_intro
	
	# Translate blog categories
	if list_context.get('blog_categories'):
		for category in list_context['blog_categories']:
			if category.get('title'):
				translated_category_title = get_translated_text(category['title'], current_language)
				if translated_category_title and translated_category_title != category['title']:
					category['title'] = translated_category_title
	
	return list_context


# Monkey patch the original functions to use our overridden versions
def patch_blog_functions():
	"""Patch blog functions to use our translated versions"""
	import frappe.website.doctype.blog_post.blog_post as blog_post_module
	blog_post_module.get_blog_list = get_blog_list
	blog_post_module.get_list_context = get_list_context

