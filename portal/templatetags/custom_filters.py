from django import template

register = template.Library()

@register.filter
def is_pdf(file_url):
    return file_url.lower().endswith('.pdf')

@register.filter
def is_audio(file_url):
    return any(file_url.lower().endswith(ext) for ext in ['.mp3', '.wav'])

@register.filter
def is_video(file_url):
    return any(file_url.lower().endswith(ext) for ext in ['.mp4', '.webm'])