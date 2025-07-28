import bleach
from bleach.css_sanitizer import CSSSanitizer

ALLOWED_TAGS = [
    'a', 'b', 'strong', 'i', 'em', 'u', 'strike', 'blockquote',
    'ul', 'ol', 'li',
    'code', 'pre',
    'p', 'br', 'hr', 'span', 'div',
    'table', 'thead', 'tbody', 'tfoot', 'tr', 'th', 'td',  # dodane tagi tabel
]

ALLOWED_ATTRIBUTES = {
    'a': ['href', 'title', 'rel', 'target'],
    'span': ['style'],
    'div': ['style'],
    'p': ['style', 'align'],  # align czasem jest używany
    'table': ['border', 'cellpadding', 'cellspacing', 'style', 'width'],
    'th': ['style', 'colspan', 'rowspan', 'scope'],
    'td': ['style', 'colspan', 'rowspan'],
    'tr': ['style'],
}

ALLOWED_CSS_PROPERTIES = [
    'text-align', 'font-family', 'color', 'background-color',
    'font-size', 'line-height', 'border', 'border-collapse',
    'border-spacing', 'width', 'height', 'padding', 'margin'
]

css_sanitizer = CSSSanitizer(allowed_css_properties=ALLOWED_CSS_PROPERTIES)

def clean_html(html):
    return bleach.clean(
        html,
        tags=ALLOWED_TAGS,
        attributes=ALLOWED_ATTRIBUTES,
        css_sanitizer=css_sanitizer,
        strip=True
    )