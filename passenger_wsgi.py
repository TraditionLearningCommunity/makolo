import os
import sys

sys.path.insert(0, "/home/smnasar1/makolo")

os.environ.setdefault("DJANGO_SETTINGS_MODULE", "config.settings")

from django.core.wsgi import get_wsgi_application

application = get_wsgi_application()