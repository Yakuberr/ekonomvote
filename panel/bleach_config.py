import bleach
from bleach.css_sanitizer import CSSSanitizer

ALLOWED_TAGS = [
    'a', 'b', 'strong', 'i', 'em', 'u', 'strike', 'blockquote',
    'ul', 'ol', 'li',
    'code', 'pre',
    'p', 'br', 'hr', 'span', 'div'
]

ALLOWED_ATTRIBUTES = {
    'a': ['href', 'title', 'rel', 'target'],
    'span': ['style'],
    'div': ['style'],
    'p': ['style'],
}

ALLOWED_CSS_PROPERTIES = ['text-align', 'font-family', 'color', 'background-color', 'font-size', 'line-height']

css_sanitizer = CSSSanitizer(allowed_css_properties=ALLOWED_CSS_PROPERTIES)
