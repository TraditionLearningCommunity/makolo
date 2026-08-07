"""
Configuration Django du projet Makolo.

Environnements pris en charge :
- development : développement local
- test        : tests automatisés
- production  : déploiement réel

Variables d'environnement principales :
- DJANGO_ENV
- DJANGO_SECRET_KEY
- DJANGO_DEBUG
- DJANGO_ALLOWED_HOSTS
- DJANGO_CSRF_TRUSTED_ORIGINS
- DJANGO_SECURE_SSL_REDIRECT
"""

import os
from pathlib import Path

from django.core.exceptions import ImproperlyConfigured


# ============================================================
# UTILITAIRES
# ============================================================

def env_bool(name: str, default: bool = False) -> bool:
    """
    Convertit proprement une variable d'environnement en booléen.

    Valeurs considérées comme vraies :
    1, true, yes, on
    """
    value = os.environ.get(name)

    if value is None:
        return default

    return value.strip().lower() in {
        "1",
        "true",
        "yes",
        "on",
    }


def env_list(name: str, default: str = "") -> list[str]:
    """
    Transforme une variable séparée par des virgules en liste Python.
    """
    value = os.environ.get(name, default)

    return [
        item.strip()
        for item in value.split(",")
        if item.strip()
    ]


# ============================================================
# BASE
# ============================================================

BASE_DIR = Path(__file__).resolve().parent.parent


# ============================================================
# ENVIRONNEMENT
# ============================================================

DJANGO_ENV = os.environ.get(
    "DJANGO_ENV",
    "development",
).strip().lower()

VALID_ENVIRONMENTS = {
    "development",
    "test",
    "production",
}

if DJANGO_ENV not in VALID_ENVIRONMENTS:
    raise ImproperlyConfigured(
        "DJANGO_ENV doit être l'une des valeurs suivantes : "
        "development, test, production."
    )

IS_DEVELOPMENT = DJANGO_ENV == "development"
IS_TEST = DJANGO_ENV == "test"
IS_PRODUCTION = DJANGO_ENV == "production"


# ============================================================
# SÉCURITÉ DE BASE
# ============================================================

# En développement, DEBUG est actif par défaut.
# En production, DEBUG est désactivé par défaut.
DEBUG = env_bool(
    "DJANGO_DEBUG",
    default=IS_DEVELOPMENT,
)

SECRET_KEY = os.environ.get("DJANGO_SECRET_KEY", "").strip()

if not SECRET_KEY:
    if IS_PRODUCTION:
        raise ImproperlyConfigured(
            "DJANGO_SECRET_KEY doit obligatoirement être définie "
            "en environnement de production."
        )

    # Clé réservée exclusivement au développement local et aux tests.
    SECRET_KEY = (
        "django-insecure-makolo-local-development-only-"
        "do-not-use-this-key-in-production-2026"
    )


# ============================================================
# HÔTES ET ORIGINES
# ============================================================

DEFAULT_ALLOWED_HOSTS = (
    "127.0.0.1,"
    "localhost,"
    "[::1]"
)

if IS_PRODUCTION:
    DEFAULT_ALLOWED_HOSTS = (
        "makolo.smnasarl.com,"
        "www.makolo.smnasarl.com"
    )

ALLOWED_HOSTS = env_list(
    "DJANGO_ALLOWED_HOSTS",
    DEFAULT_ALLOWED_HOSTS,
)

DEFAULT_CSRF_TRUSTED_ORIGINS = ""

if IS_PRODUCTION:
    DEFAULT_CSRF_TRUSTED_ORIGINS = (
        "https://makolo.smnasarl.com,"
        "https://www.makolo.smnasarl.com"
    )

CSRF_TRUSTED_ORIGINS = env_list(
    "DJANGO_CSRF_TRUSTED_ORIGINS",
    DEFAULT_CSRF_TRUSTED_ORIGINS,
)


# ============================================================
# MODÈLE UTILISATEUR
# ============================================================

AUTH_USER_MODEL = "accounts.User"


# ============================================================
# APPLICATIONS
# ============================================================

DJANGO_APPS = [
    "django.contrib.admin",
    "django.contrib.auth",
    "django.contrib.contenttypes",
    "django.contrib.sessions",
    "django.contrib.messages",
    "django.contrib.staticfiles",
]

THIRD_PARTY_APPS = [
    "rest_framework",
    "rest_framework_simplejwt",
    "rest_framework_simplejwt.token_blacklist",
]

LOCAL_APPS = [
    "core",
    "accounts",
    "events",
    "tickets",
    "scanner",
    "partners",
    "analytics_app",
    "payments",
    "notifications",
]

INSTALLED_APPS = [
    *DJANGO_APPS,
    *THIRD_PARTY_APPS,
    *LOCAL_APPS,
]


# ============================================================
# MIDDLEWARE
# ============================================================

MIDDLEWARE = [
    "django.middleware.security.SecurityMiddleware",

    # WhiteNoise doit rester immédiatement après SecurityMiddleware.
    "whitenoise.middleware.WhiteNoiseMiddleware",

    "django.contrib.sessions.middleware.SessionMiddleware",
    "django.middleware.common.CommonMiddleware",
    "django.middleware.csrf.CsrfViewMiddleware",
    "django.contrib.auth.middleware.AuthenticationMiddleware",
    "django.contrib.messages.middleware.MessageMiddleware",
    "django.middleware.clickjacking.XFrameOptionsMiddleware",
]


# ============================================================
# URLS / WSGI / ASGI
# ============================================================

ROOT_URLCONF = "config.urls"

WSGI_APPLICATION = "config.wsgi.application"

# À conserver si config/asgi.py existe.
ASGI_APPLICATION = "config.asgi.application"


# ============================================================
# TEMPLATES
# ============================================================

TEMPLATES = [
    {
        "BACKEND": "django.template.backends.django.DjangoTemplates",

        "DIRS": [
            BASE_DIR / "templates",
        ],

        "APP_DIRS": True,

        "OPTIONS": {
            "context_processors": [
                "django.template.context_processors.request",
                "django.contrib.auth.context_processors.auth",
                "django.contrib.messages.context_processors.messages",
            ],
        },
    },
]


# ============================================================
# BASE DE DONNÉES
# ============================================================

DATABASES = {
    "default": {
        "ENGINE": "django.db.backends.sqlite3",
        "NAME": BASE_DIR / "db.sqlite3",
    }
}


# ============================================================
# VALIDATION DES MOTS DE PASSE
# ============================================================

AUTH_PASSWORD_VALIDATORS = [
    {
        "NAME": (
            "django.contrib.auth.password_validation."
            "UserAttributeSimilarityValidator"
        ),
    },
    {
        "NAME": (
            "django.contrib.auth.password_validation."
            "MinimumLengthValidator"
        ),
    },
    {
        "NAME": (
            "django.contrib.auth.password_validation."
            "CommonPasswordValidator"
        ),
    },
    {
        "NAME": (
            "django.contrib.auth.password_validation."
            "NumericPasswordValidator"
        ),
    },
]


# ============================================================
# INTERNATIONALISATION
# ============================================================

LANGUAGE_CODE = "fr"

TIME_ZONE = "Africa/Lubumbashi"

USE_I18N = True

USE_TZ = True


# ============================================================
# FICHIERS STATIQUES
# ============================================================

STATIC_URL = "/static/"

STATIC_ROOT = BASE_DIR / "staticfiles"

STATICFILES_DIRS = []

LOCAL_STATIC_DIR = BASE_DIR / "static"

if LOCAL_STATIC_DIR.exists():
    STATICFILES_DIRS.append(LOCAL_STATIC_DIR)


# Django moderne utilise STORAGES plutôt que STATICFILES_STORAGE.
STORAGES = {
    "default": {
        "BACKEND": (
            "django.core.files.storage.FileSystemStorage"
        ),
    },
    "staticfiles": {
        "BACKEND": (
            "whitenoise.storage."
            "CompressedManifestStaticFilesStorage"
        ),
    },
}

# Pendant le développement local, WhiteNoise peut servir les fichiers
# statiques même lorsque DEBUG=True.
WHITENOISE_USE_FINDERS = IS_DEVELOPMENT

# Évite qu'un fichier source-map manquant bloque collectstatic.
WHITENOISE_MANIFEST_STRICT = IS_PRODUCTION


# ============================================================
# FICHIERS MÉDIA
# ============================================================

MEDIA_URL = "/media/"

MEDIA_ROOT = BASE_DIR / "media"


# ============================================================
# CLÉ PRIMAIRE PAR DÉFAUT
# ============================================================

DEFAULT_AUTO_FIELD = "django.db.models.BigAutoField"


# ============================================================
# AUTHENTIFICATION WEB
# ============================================================

LOGIN_URL = "accounts:login"

LOGIN_REDIRECT_URL = "core:dashboard"

LOGOUT_REDIRECT_URL = "accounts:login"


# ============================================================
# DJANGO REST FRAMEWORK
# ============================================================

REST_FRAMEWORK = {
    "DEFAULT_AUTHENTICATION_CLASSES": (
        # JWT pour les clients API.
        "rest_framework_simplejwt.authentication.JWTAuthentication",

        # Sessions Django pour l'API navigable et l'application web.
        "rest_framework.authentication.SessionAuthentication",
    ),

    "DEFAULT_PERMISSION_CLASSES": (
        "rest_framework.permissions.IsAuthenticated",
    ),

    "DEFAULT_PAGINATION_CLASS": (
        "rest_framework.pagination.PageNumberPagination"
    ),

    "PAGE_SIZE": 20,

    "DEFAULT_RENDERER_CLASSES": (
        "rest_framework.renderers.JSONRenderer",
        "rest_framework.renderers.BrowsableAPIRenderer",
    ),

    "DEFAULT_PARSER_CLASSES": (
        "rest_framework.parsers.JSONParser",
        "rest_framework.parsers.FormParser",
        "rest_framework.parsers.MultiPartParser",
    ),

    "DEFAULT_FILTER_BACKENDS": (
        "rest_framework.filters.SearchFilter",
        "rest_framework.filters.OrderingFilter",
    ),
}


# ============================================================
# SIMPLE JWT
# ============================================================

from datetime import timedelta  # noqa: E402


SIMPLE_JWT = {
    "ACCESS_TOKEN_LIFETIME": timedelta(minutes=15),
    "REFRESH_TOKEN_LIFETIME": timedelta(days=7),

    "ROTATE_REFRESH_TOKENS": True,
    "BLACKLIST_AFTER_ROTATION": True,

    "UPDATE_LAST_LOGIN": False,

    "ALGORITHM": "HS256",
    "SIGNING_KEY": SECRET_KEY,

    "AUTH_HEADER_TYPES": (
        "Bearer",
    ),

    "AUTH_HEADER_NAME": "HTTP_AUTHORIZATION",

    "USER_ID_FIELD": "id",
    "USER_ID_CLAIM": "user_id",

    "TOKEN_TYPE_CLAIM": "token_type",
}


# ============================================================
# E-MAIL
# ============================================================

if IS_DEVELOPMENT or IS_TEST:
    EMAIL_BACKEND = (
        "django.core.mail.backends.console.EmailBackend"
    )
else:
    EMAIL_BACKEND = os.environ.get(
        "DJANGO_EMAIL_BACKEND",
        "django.core.mail.backends.smtp.EmailBackend",
    )

    EMAIL_HOST = os.environ.get("DJANGO_EMAIL_HOST", "")
    EMAIL_PORT = int(
        os.environ.get("DJANGO_EMAIL_PORT", "587")
    )
    EMAIL_USE_TLS = env_bool(
        "DJANGO_EMAIL_USE_TLS",
        True,
    )
    EMAIL_USE_SSL = env_bool(
        "DJANGO_EMAIL_USE_SSL",
        False,
    )
    EMAIL_HOST_USER = os.environ.get(
        "DJANGO_EMAIL_HOST_USER",
        "",
    )
    EMAIL_HOST_PASSWORD = os.environ.get(
        "DJANGO_EMAIL_HOST_PASSWORD",
        "",
    )

DEFAULT_FROM_EMAIL = os.environ.get(
    "DJANGO_DEFAULT_FROM_EMAIL",
    "Makolo <noreply@localhost>",
)


# ============================================================
# SESSIONS ET COOKIES
# ============================================================

SESSION_COOKIE_NAME = "makolo_sessionid"

CSRF_COOKIE_NAME = "makolo_csrftoken"

SESSION_COOKIE_HTTPONLY = True

CSRF_COOKIE_HTTPONLY = False

SESSION_COOKIE_SAMESITE = "Lax"

CSRF_COOKIE_SAMESITE = "Lax"


# ============================================================
# SÉCURITÉ PRODUCTION
# ============================================================

if IS_PRODUCTION:
    if DEBUG:
        raise ImproperlyConfigured(
            "DJANGO_DEBUG ne doit pas être activé en production."
        )

    SESSION_COOKIE_SECURE = True
    CSRF_COOKIE_SECURE = True

    SECURE_CONTENT_TYPE_NOSNIFF = True

    X_FRAME_OPTIONS = "DENY"

    SECURE_REFERRER_POLICY = "same-origin"

    SECURE_PROXY_SSL_HEADER = (
        "HTTP_X_FORWARDED_PROTO",
        "https",
    )

    SECURE_SSL_REDIRECT = env_bool(
        "DJANGO_SECURE_SSL_REDIRECT",
        True,
    )

    SECURE_HSTS_SECONDS = int(
        os.environ.get(
            "DJANGO_SECURE_HSTS_SECONDS",
            "31536000",
        )
    )

    SECURE_HSTS_INCLUDE_SUBDOMAINS = env_bool(
        "DJANGO_SECURE_HSTS_INCLUDE_SUBDOMAINS",
        False,
    )

    SECURE_HSTS_PRELOAD = env_bool(
        "DJANGO_SECURE_HSTS_PRELOAD",
        False,
    )

else:
    SESSION_COOKIE_SECURE = False
    CSRF_COOKIE_SECURE = False
    SECURE_SSL_REDIRECT = False
    SECURE_HSTS_SECONDS = 0
    SECURE_HSTS_INCLUDE_SUBDOMAINS = False
    SECURE_HSTS_PRELOAD = False


# ============================================================
# JOURNALISATION
# ============================================================

LOG_LEVEL = os.environ.get(
    "DJANGO_LOG_LEVEL",
    "INFO" if DEBUG else "WARNING",
).upper()

LOG_DIR = BASE_DIR / "logs"
LOG_DIR.mkdir(parents=True, exist_ok=True)

LOGGING = {
    "version": 1,
    "disable_existing_loggers": False,

    "formatters": {
        "verbose": {
            "format": (
                "{levelname} {asctime} "
                "{name} {process:d} {thread:d} "
                "{message}"
            ),
            "style": "{",
        },
        "simple": {
            "format": "{levelname} {name}: {message}",
            "style": "{",
        },
    },

    "handlers": {
        "console": {
            "class": "logging.StreamHandler",
            "formatter": "simple",
        },

        "django_file": {
            "class": "logging.handlers.RotatingFileHandler",
            "filename": LOG_DIR / "django.log",
            "maxBytes": 5 * 1024 * 1024,
            "backupCount": 5,
            "formatter": "verbose",
        },

        "security_file": {
            "class": "logging.handlers.RotatingFileHandler",
            "filename": LOG_DIR / "security.log",
            "maxBytes": 5 * 1024 * 1024,
            "backupCount": 5,
            "formatter": "verbose",
        },
    },

    "loggers": {
        "django": {
            "handlers": [
                "console",
                "django_file",
            ],
            "level": LOG_LEVEL,
            "propagate": False,
        },

        "django.security": {
            "handlers": [
                "console",
                "security_file",
            ],
            "level": "WARNING",
            "propagate": False,
        },

        "makolo": {
            "handlers": [
                "console",
                "django_file",
            ],
            "level": LOG_LEVEL,
            "propagate": False,
        },
    },
}


# ============================================================
# DÉVELOPPEMENT LOCAL
# ============================================================

INTERNAL_IPS = [
    "127.0.0.1",
]


# ============================================================
# TESTS
# ============================================================

if IS_TEST:
    PASSWORD_HASHERS = [
        "django.contrib.auth.hashers.MD5PasswordHasher",
    ]

    EMAIL_BACKEND = (
        "django.core.mail.backends.locmem.EmailBackend"
    )