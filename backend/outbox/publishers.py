"""The publishers configured in settings.PUBLISHERS, built once per process."""

from contextlib import contextmanager
from functools import cache

from django.conf import settings
from django.core.signals import setting_changed
from django.dispatch import receiver

from publishing.registry import build_publishers


@cache
def get_publishers():
    """Raises publishing.registry.ConfigurationError for a broken config;
    the system check (checks.py) reports the same errors at startup."""
    return build_publishers(getattr(settings, "PUBLISHERS", []))


@contextmanager
def opened_publishers():
    """Publishers of their own with their transports open, for work outside
    the worker, e.g. undoing from the admin."""
    publishers = build_publishers(getattr(settings, "PUBLISHERS", []))
    for publisher in publishers:
        publisher.open()
    try:
        yield publishers
    finally:
        for publisher in publishers:
            publisher.close()


@receiver(setting_changed)
def _reset(setting, **kwargs):
    # override_settings in tests
    if setting == "PUBLISHERS":
        get_publishers.cache_clear()
