from .settings import *  # noqa: F401,F403

# Task 12 registers the new vertical without duplicating the base settings module.
INSTALLED_APPS = [*INSTALLED_APPS, "transport.apps.TransportConfig"]
