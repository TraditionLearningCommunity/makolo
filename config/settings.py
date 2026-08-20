"""Django settings for Makolo.

The stable settings body lives in ``base_settings`` so new bounded contexts can
be registered without changing deployment entry points or maintaining a second
runtime settings module.
"""

from .base_settings import *  # noqa: F401,F403

INSTALLED_APPS = [*INSTALLED_APPS, "transport.apps.TransportConfig"]
