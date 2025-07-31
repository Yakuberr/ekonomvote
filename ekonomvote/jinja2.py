from django.templatetags.static import static
from django.urls import reverse
from django.contrib import messages
from django.utils import timezone
from django.conf import settings
from jinja2 import Environment

def render_component_helper(component_name, **kwargs):
    """Helper do renderowania django-components z Jinja2"""
    return component.render_to_string(component_name, context=kwargs)

def environment(**options):
    env = Environment(**options)
    env.globals.update(
        {
            "static": static,
            "url": reverse,
            'get_messages':messages.get_messages,
            'now':timezone.now,
            'media_url':settings.MEDIA_URL,
            'static_url': settings.STATIC_URL,
        }
    )
    return env