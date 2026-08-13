"""Django settings for Makolo."""

import os
from datetime import timedelta
from pathlib import Path
from urllib.parse import urlparse

from django.core.exceptions import ImproperlyConfigured


def env_bool(name: str, default: bool = False) -> bool:
    value = os.environ.get(name)
    if value is None:
        return default
    return value.strip().lower() in {"1", "true", "yes", "on"}


def env_list(name: str, default: str = "") -> list[str]:
    return [item.strip() for item in os.environ.get(name, default).split(",") if item.strip()]


BASE_DIR = Path(__file__).resolve().parent.parent
DJANGO_ENV = os.environ.get("DJANGO_ENV", "development").strip().lower()
VALID_ENVIRONMENTS = {"development", "test", "e2e", "production"}
if DJANGO_ENV not in VALID_ENVIRONMENTS:
    raise ImproperlyConfigured("DJANGO_ENV doit être development, test, e2e ou production.")

IS_DEVELOPMENT = DJANGO_ENV == "development"
IS_TEST = DJANGO_ENV == "test"
IS_E2E = DJANGO_ENV == "e2e"
IS_PRODUCTION = DJANGO_ENV == "production"
DEBUG = env_bool("DJANGO_DEBUG", default=IS_DEVELOPMENT)

SECRET_KEY = os.environ.get("DJANGO_SECRET_KEY", "").strip()
if not SECRET_KEY:
    if IS_PRODUCTION:
        raise ImproperlyConfigured("DJANGO_SECRET_KEY doit être définie en production.")
    SECRET_KEY = "django-insecure-makolo-local-development-only-do-not-use-this-key-in-production-2026"

if IS_PRODUCTION:
    ALLOWED_HOSTS = env_list("DJANGO_ALLOWED_HOSTS")
    if not ALLOWED_HOSTS:
        raise ImproperlyConfigured("DJANGO_ALLOWED_HOSTS doit être définie en production.")
else:
    ALLOWED_HOSTS = env_list("DJANGO_ALLOWED_HOSTS", "127.0.0.1,localhost,[::1]")

MAKOLO_PUBLIC_BASE_URL = os.environ.get(
    "MAKOLO_PUBLIC_BASE_URL",
    "http://127.0.0.1:8000" if not IS_PRODUCTION else "",
).rstrip("/")
if IS_PRODUCTION:
    if not MAKOLO_PUBLIC_BASE_URL:
        raise ImproperlyConfigured("MAKOLO_PUBLIC_BASE_URL doit être définie en production.")
    parsed_public_url = urlparse(MAKOLO_PUBLIC_BASE_URL)
    if parsed_public_url.scheme != "https" or not parsed_public_url.netloc:
        raise ImproperlyConfigured(
            "MAKOLO_PUBLIC_BASE_URL doit être une URL HTTPS absolue en production."
        )

if IS_PRODUCTION:
    CSRF_TRUSTED_ORIGINS = env_list("DJANGO_CSRF_TRUSTED_ORIGINS", MAKOLO_PUBLIC_BASE_URL)
else:
    CSRF_TRUSTED_ORIGINS = env_list("DJANGO_CSRF_TRUSTED_ORIGINS")

AUTH_USER_MODEL = "accounts.User"

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
    "authorization.apps.AuthorizationConfig",
    "organizations",
    "groups.apps.GroupsConfig",
    "events",
    "tickets",
    "scanner",
    "payments",
    "notifications",
    "automation",
    "partners",
    "crm",
    "promotions.apps.PromotionsConfig",
    "loyalty.apps.LoyaltyConfig",
    "analytics_app",
    "operations.apps.OperationsConfig",
    "discovery.apps.DiscoveryConfig",
    "growth.apps.GrowthConfig",
]
INSTALLED_APPS = [*DJANGO_APPS, *THIRD_PARTY_APPS, *LOCAL_APPS]

MIDDLEWARE = [
    "django.middleware.security.SecurityMiddleware",
    "core.security_headers.FrontendSecurityHeadersMiddleware",
    "whitenoise.middleware.WhiteNoiseMiddleware",
    "django.contrib.sessions.middleware.SessionMiddleware",
    "django.middleware.common.CommonMiddleware",
    "django.middleware.csrf.CsrfViewMiddleware",
    "django.contrib.auth.middleware.AuthenticationMiddleware",
    "growth.middleware.MarketingSessionUserMiddleware",
    "django.contrib.messages.middleware.MessageMiddleware",
    "django.middleware.clickjacking.XFrameOptionsMiddleware",
]

ROOT_URLCONF = "config.urls"
WSGI_APPLICATION = "config.wsgi.application"
ASGI_APPLICATION = "config.asgi.application"

TEMPLATES = [
    {
        "BACKEND": "django.template.backends.django.DjangoTemplates",
        "DIRS": [BASE_DIR / "templates"],
        "APP_DIRS": True,
        "OPTIONS": {
            "context_processors": [
                "django.template.context_processors.request",
                "django.contrib.auth.context_processors.auth",
                "django.contrib.messages.context_processors.messages",
                "notifications.context_processors.notifications_summary",
            ],
        },
    },
]

DATABASE_ENGINE = os.environ.get("DJANGO_DATABASE_ENGINE", "sqlite").strip().lower()
if DATABASE_ENGINE == "sqlite":
    DATABASES = {
        "default": {
            "ENGINE": "django.db.backends.sqlite3",
            "NAME": Path(os.environ.get("DJANGO_DB_PATH", BASE_DIR / "db.sqlite3")),
            "OPTIONS": {
                "timeout": int(os.environ.get("DJANGO_SQLITE_TIMEOUT_SECONDS", "20")),
            },
        }
    }
elif DATABASE_ENGINE in {"postgresql", "postgres"}:
    DATABASES = {
        "default": {
            "ENGINE": "django.db.backends.postgresql",
            "NAME": os.environ.get("DJANGO_DATABASE_NAME", "").strip(),
            "USER": os.environ.get("DJANGO_DATABASE_USER", "").strip(),
            "PASSWORD": os.environ.get("DJANGO_DATABASE_PASSWORD", ""),
            "HOST": os.environ.get("DJANGO_DATABASE_HOST", "").strip(),
            "PORT": os.environ.get("DJANGO_DATABASE_PORT", "5432").strip(),
            "CONN_MAX_AGE": int(os.environ.get("DJANGO_DATABASE_CONN_MAX_AGE", "60")),
            "OPTIONS": {
                "connect_timeout": int(
                    os.environ.get("DJANGO_DATABASE_CONNECT_TIMEOUT_SECONDS", "5")
                ),
            },
        }
    }
    missing_database_settings = [
        name
        for name, value in (
            ("DJANGO_DATABASE_NAME", DATABASES["default"]["NAME"]),
            ("DJANGO_DATABASE_USER", DATABASES["default"]["USER"]),
            ("DJANGO_DATABASE_HOST", DATABASES["default"]["HOST"]),
        )
        if not value
    ]
    if missing_database_settings:
        raise ImproperlyConfigured(
            "Configuration PostgreSQL incomplète: "
            + ", ".join(missing_database_settings)
            + "."
        )
else:
    raise ImproperlyConfigured("DJANGO_DATABASE_ENGINE doit être sqlite ou postgresql.")

AUTH_PASSWORD_VALIDATORS = [
    {"NAME": "django.contrib.auth.password_validation.UserAttributeSimilarityValidator"},
    {"NAME": "django.contrib.auth.password_validation.MinimumLengthValidator"},
    {"NAME": "django.contrib.auth.password_validation.CommonPasswordValidator"},
    {"NAME": "django.contrib.auth.password_validation.NumericPasswordValidator"},
]
PASSWORD_RESET_TIMEOUT = int(os.environ.get("DJANGO_PASSWORD_RESET_TIMEOUT_SECONDS", "3600"))

LANGUAGE_CODE = "fr"
TIME_ZONE = "Africa/Lubumbashi"
USE_I18N = True
USE_TZ = True

STATIC_URL = "/static/"
STATIC_ROOT = Path(os.environ.get("DJANGO_STATIC_ROOT", BASE_DIR / "staticfiles"))
STATICFILES_DIRS = []
LOCAL_STATIC_DIR = BASE_DIR / "static"
if LOCAL_STATIC_DIR.exists():
    STATICFILES_DIRS.append(LOCAL_STATIC_DIR)

STORAGES = {
    "default": {"BACKEND": "django.core.files.storage.FileSystemStorage"},
    "staticfiles": {
        "BACKEND": (
            "django.contrib.staticfiles.storage.StaticFilesStorage"
            if IS_TEST
            else "whitenoise.storage.CompressedManifestStaticFilesStorage"
        )
    },
}
WHITENOISE_USE_FINDERS = IS_DEVELOPMENT
WHITENOISE_MANIFEST_STRICT = IS_PRODUCTION or IS_E2E

MAKOLO_CONTENT_SECURITY_POLICY = "; ".join(
    [
        "default-src 'self'",
        "base-uri 'self'",
        "connect-src 'self'",
        "font-src 'self'",
        "form-action 'self'",
        "frame-ancestors 'none'",
        "frame-src 'none'",
        "img-src 'self' data: blob:",
        "media-src 'self' blob:",
        "object-src 'none'",
        "script-src 'self'",
        "style-src 'self' 'unsafe-inline'",
        "worker-src 'self' blob:",
    ]
)
MAKOLO_PERMISSIONS_POLICY = "camera=(self), microphone=(), geolocation=()"

MEDIA_URL = "/media/"
MEDIA_ROOT = Path(os.environ.get("DJANGO_MEDIA_ROOT", BASE_DIR / "media"))
MAKOLO_BACKUP_DIR = Path(os.environ.get("MAKOLO_BACKUP_DIR", BASE_DIR / "backups"))
DATA_UPLOAD_MAX_MEMORY_SIZE = int(
    os.environ.get("DJANGO_DATA_UPLOAD_MAX_MEMORY_SIZE", str(12 * 1024 * 1024))
)
FILE_UPLOAD_MAX_MEMORY_SIZE = int(
    os.environ.get("DJANGO_FILE_UPLOAD_MAX_MEMORY_SIZE", str(3 * 1024 * 1024))
)
DEFAULT_AUTO_FIELD = "django.db.models.BigAutoField"

LOGIN_URL = "accounts:login"
LOGIN_REDIRECT_URL = "core:dashboard"
LOGOUT_REDIRECT_URL = "accounts:login"

REST_FRAMEWORK = {
    "DEFAULT_AUTHENTICATION_CLASSES": (
        "rest_framework_simplejwt.authentication.JWTAuthentication",
        "rest_framework.authentication.SessionAuthentication",
    ),
    "DEFAULT_PERMISSION_CLASSES": ("rest_framework.permissions.IsAuthenticated",),
    "DEFAULT_PAGINATION_CLASS": "rest_framework.pagination.PageNumberPagination",
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
    "EXCEPTION_HANDLER": "core.api.exceptions.custom_exception_handler",
}

SIMPLE_JWT = {
    "ACCESS_TOKEN_LIFETIME": timedelta(minutes=15),
    "REFRESH_TOKEN_LIFETIME": timedelta(days=7),
    "ROTATE_REFRESH_TOKENS": True,
    "BLACKLIST_AFTER_ROTATION": True,
    "CHECK_REVOKE_TOKEN": True,
    "UPDATE_LAST_LOGIN": False,
    "ALGORITHM": "HS256",
    "SIGNING_KEY": SECRET_KEY,
    "AUTH_HEADER_TYPES": ("Bearer",),
    "AUTH_HEADER_NAME": "HTTP_AUTHORIZATION",
    "USER_ID_FIELD": "id",
    "USER_ID_CLAIM": "user_id",
    "TOKEN_TYPE_CLAIM": "token_type",
}

if IS_E2E:
    EMAIL_BACKEND = "django.core.mail.backends.filebased.EmailBackend"
    EMAIL_FILE_PATH = Path(
        os.environ.get("DJANGO_EMAIL_FILE_PATH", BASE_DIR / ".e2e-emails")
    )
    EMAIL_FILE_PATH.mkdir(parents=True, exist_ok=True)
elif IS_DEVELOPMENT or IS_TEST:
    EMAIL_BACKEND = "django.core.mail.backends.console.EmailBackend"
else:
    EMAIL_BACKEND = os.environ.get(
        "DJANGO_EMAIL_BACKEND",
        "django.core.mail.backends.console.EmailBackend",
    )
    EMAIL_HOST = os.environ.get("DJANGO_EMAIL_HOST", "").strip()
    EMAIL_PORT = int(os.environ.get("DJANGO_EMAIL_PORT", "587"))
    EMAIL_USE_TLS = env_bool("DJANGO_EMAIL_USE_TLS", True)
    EMAIL_USE_SSL = env_bool("DJANGO_EMAIL_USE_SSL", False)
    EMAIL_HOST_USER = os.environ.get("DJANGO_EMAIL_HOST_USER", "").strip()
    EMAIL_HOST_PASSWORD = os.environ.get("DJANGO_EMAIL_HOST_PASSWORD", "")
    if EMAIL_USE_TLS and EMAIL_USE_SSL:
        raise ImproperlyConfigured(
            "DJANGO_EMAIL_USE_TLS et DJANGO_EMAIL_USE_SSL ne peuvent pas être activés ensemble."
        )
    if EMAIL_BACKEND == "django.core.mail.backends.smtp.EmailBackend" and not EMAIL_HOST:
        raise ImproperlyConfigured(
            "DJANGO_EMAIL_HOST doit être défini quand le backend SMTP est activé."
        )
DEFAULT_FROM_EMAIL = os.environ.get("DJANGO_DEFAULT_FROM_EMAIL", "Makolo <noreply@localhost>")

PAYMENTS_SANDBOX_ENABLED = env_bool(
    "PAYMENTS_SANDBOX_ENABLED",
    default=IS_DEVELOPMENT or IS_TEST or IS_E2E,
)
PAYMENTS_WEBHOOK_SECRET = os.environ.get(
    "PAYMENTS_WEBHOOK_SECRET",
    "makolo-local-webhook-secret" if not IS_PRODUCTION else "",
)
if IS_PRODUCTION and PAYMENTS_SANDBOX_ENABLED and not PAYMENTS_WEBHOOK_SECRET:
    raise ImproperlyConfigured(
        "PAYMENTS_WEBHOOK_SECRET doit être défini quand le sandbox paiement est activé en production."
    )

SESSION_COOKIE_NAME = "makolo_sessionid"
CSRF_COOKIE_NAME = "makolo_csrftoken"
SESSION_COOKIE_HTTPONLY = True
CSRF_COOKIE_HTTPONLY = False
SESSION_COOKIE_SAMESITE = "Lax"
CSRF_COOKIE_SAMESITE = "Lax"
SESSION_COOKIE_AGE = int(
    os.environ.get("DJANGO_SESSION_COOKIE_AGE_SECONDS", str(14 * 24 * 3600))
)
SESSION_SAVE_EVERY_REQUEST = False
SESSION_EXPIRE_AT_BROWSER_CLOSE = env_bool("DJANGO_SESSION_EXPIRE_AT_BROWSER_CLOSE", False)

SECURE_CONTENT_TYPE_NOSNIFF = True
X_FRAME_OPTIONS = "DENY"
SECURE_REFERRER_POLICY = "same-origin"

if IS_PRODUCTION:
    if DEBUG:
        raise ImproperlyConfigured("DJANGO_DEBUG ne doit pas être activé en production.")
    SESSION_COOKIE_SECURE = True
    CSRF_COOKIE_SECURE = True
    SECURE_CONTENT_TYPE_NOSNIFF = True
    X_FRAME_OPTIONS = "DENY"
    SECURE_REFERRER_POLICY = "same-origin"
    SECURE_PROXY_SSL_HEADER = ("HTTP_X_FORWARDED_PROTO", "https")
    SECURE_SSL_REDIRECT = env_bool("DJANGO_SECURE_SSL_REDIRECT", True)
    SECURE_HSTS_SECONDS = int(os.environ.get("DJANGO_SECURE_HSTS_SECONDS", "31536000"))
    SECURE_HSTS_INCLUDE_SUBDOMAINS = env_bool("DJANGO_SECURE_HSTS_INCLUDE_SUBDOMAINS", False)
    SECURE_HSTS_PRELOAD = env_bool("DJANGO_SECURE_HSTS_PRELOAD", False)
else:
    SESSION_COOKIE_SECURE = False
    CSRF_COOKIE_SECURE = False
    SECURE_SSL_REDIRECT = False
    SECURE_HSTS_SECONDS = 0
    SECURE_HSTS_INCLUDE_SUBDOMAINS = False
    SECURE_HSTS_PRELOAD = False

LOG_LEVEL = os.environ.get("DJANGO_LOG_LEVEL", "INFO" if DEBUG else "WARNING").upper()
LOG_DIR = Path(os.environ.get("DJANGO_LOG_DIR", BASE_DIR / "logs"))
LOG_DIR.mkdir(parents=True, exist_ok=True)
LOGGING = {
    "version": 1,
    "disable_existing_loggers": False,
    "filters": {
        "redact_sensitive": {
            "()": "core.logging_filters.SensitiveDataFilter",
        },
    },
    "formatters": {
        "verbose": {
            "format": "{levelname} {asctime} {name} {process:d} {thread:d} {message}",
            "style": "{",
        },
        "simple": {"format": "{levelname} {name}: {message}", "style": "{"},
    },
    "handlers": {
        "console": {
            "class": "logging.StreamHandler",
            "formatter": "simple",
            "filters": ["redact_sensitive"],
        },
        "django_file": {
            "class": "logging.handlers.RotatingFileHandler",
            "filename": LOG_DIR / "django.log",
            "maxBytes": int(os.environ.get("DJANGO_LOG_MAX_BYTES", str(5 * 1024 * 1024))),
            "backupCount": int(os.environ.get("DJANGO_LOG_BACKUP_COUNT", "5")),
            "formatter": "verbose",
            "filters": ["redact_sensitive"],
        },
        "security_file": {
            "class": "logging.handlers.RotatingFileHandler",
            "filename": LOG_DIR / "security.log",
            "maxBytes": int(os.environ.get("DJANGO_LOG_MAX_BYTES", str(5 * 1024 * 1024))),
            "backupCount": int(os.environ.get("DJANGO_LOG_BACKUP_COUNT", "5")),
            "formatter": "verbose",
            "filters": ["redact_sensitive"],
        },
    },
    "loggers": {
        "django": {
            "handlers": ["console", "django_file"],
            "level": LOG_LEVEL,
            "propagate": False,
        },
        "django.security": {
            "handlers": ["console", "security_file"],
            "level": "WARNING",
            "propagate": False,
        },
        "makolo": {
            "handlers": ["console", "django_file"],
            "level": LOG_LEVEL,
            "propagate": False,
        },
        "core": {
            "handlers": ["console", "django_file"],
            "level": LOG_LEVEL,
            "propagate": False,
        },
    },
}

INTERNAL_IPS = ["127.0.0.1"]

if IS_TEST or IS_E2E:
    PASSWORD_HASHERS = ["django.contrib.auth.hashers.MD5PasswordHasher"]
if IS_TEST:
    EMAIL_BACKEND = "django.core.mail.backends.locmem.EmailBackend"
