import bleach

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
