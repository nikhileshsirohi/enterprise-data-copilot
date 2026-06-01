import os

import django
from django.apps import apps


def ensure_django_setup() -> None:
    os.environ.setdefault("DJANGO_SETTINGS_MODULE", "backend.django_app.config.settings")
    if not apps.ready:
        django.setup()
