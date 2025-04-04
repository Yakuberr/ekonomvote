from django.templatetags.static import static
from django.urls import reverse
from django.contrib import messages
from django.utils import timezone
from jinja2 import Environment


def environment(**options):
    env = Environment(**options)
    env.globals.update(
        {
            "static": static,
            "url": reverse,
            'get_messages':messages.get_messages,
            'now':timezone.now,
        }
    )
    return env