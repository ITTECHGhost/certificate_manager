"""registration_web settings.

Everything secret or machine-specific comes from environment variables:
  REGWEB_SECRET_KEY    required unless REGWEB_DEBUG=1
  REGWEB_DEBUG         "1" turns DEBUG on (off by default)
  REGWEB_ALLOWED_HOSTS comma separated, e.g. "192.168.1.10,regserver"
  REGWEB_DATA_DIR      folder for the SQLite DB and uploaded files (outside the repo)
"""
import os
from pathlib import Path

from django.core.exceptions import ImproperlyConfigured

BASE_DIR = Path(__file__).resolve().parent.parent
# Default data folder sits next to the repo (F:/CR_PY/registration_data), never inside it.
DATA_DIR = Path(os.environ.get("REGWEB_DATA_DIR", BASE_DIR.parent.parent / "registration_data"))
DATA_DIR.mkdir(parents=True, exist_ok=True)

DEBUG = os.environ.get("REGWEB_DEBUG", "") == "1"

# Server install (install_service.ps1): DATA_DIR/settings.json {"port", "allowed_hosts"}
# and DATA_DIR/secret_key.txt. Change the IP there, then restart the service.
_SERVER_SETTINGS = {}
if (DATA_DIR / "settings.json").exists():
    import json
    _SERVER_SETTINGS = json.loads((DATA_DIR / "settings.json").read_text(encoding="utf-8-sig"))
PORT = int(_SERVER_SETTINGS.get("port", 8080))

SECRET_KEY = os.environ.get("REGWEB_SECRET_KEY", "")
if not SECRET_KEY and (DATA_DIR / "secret_key.txt").exists():
    SECRET_KEY = (DATA_DIR / "secret_key.txt").read_text(encoding="utf-8").strip()
if not SECRET_KEY:
    if not DEBUG:
        raise ImproperlyConfigured("Set REGWEB_SECRET_KEY (or REGWEB_DEBUG=1 for local work).")
    SECRET_KEY = "dev-only-insecure-key"

ALLOWED_HOSTS = [h.strip() for h in os.environ.get("REGWEB_ALLOWED_HOSTS", "").split(",") if h.strip()]
if not ALLOWED_HOSTS:
    ALLOWED_HOSTS = list(_SERVER_SETTINGS.get("allowed_hosts", []))
if DEBUG and not ALLOWED_HOSTS:
    ALLOWED_HOSTS = ["localhost", "127.0.0.1"]

INSTALLED_APPS = [
    "django.contrib.admin",
    "django.contrib.auth",
    "django.contrib.contenttypes",
    "django.contrib.sessions",
    "django.contrib.messages",
    "django.contrib.staticfiles",
    "registry",
]

MIDDLEWARE = [
    "django.middleware.security.SecurityMiddleware",
    "django.contrib.sessions.middleware.SessionMiddleware",
    "django.middleware.common.CommonMiddleware",
    "django.middleware.csrf.CsrfViewMiddleware",
    "django.contrib.auth.middleware.AuthenticationMiddleware",
    "django.contrib.messages.middleware.MessageMiddleware",
    "django.middleware.clickjacking.XFrameOptionsMiddleware",
]

ROOT_URLCONF = "regweb.urls"
WSGI_APPLICATION = "regweb.wsgi.application"

TEMPLATES = [
    {
        "BACKEND": "django.template.backends.django.DjangoTemplates",
        "DIRS": [],
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

DATABASES = {
    "default": {
        "ENGINE": "django.db.backends.sqlite3",
        "NAME": DATA_DIR / "registration.sqlite3",
        "ATOMIC_REQUESTS": True,  # all or nothing: one transaction per request
    }
}

AUTH_PASSWORD_VALIDATORS = [
    {"NAME": "django.contrib.auth.password_validation.UserAttributeSimilarityValidator"},
    {"NAME": "django.contrib.auth.password_validation.MinimumLengthValidator"},
    {"NAME": "django.contrib.auth.password_validation.CommonPasswordValidator"},
    {"NAME": "django.contrib.auth.password_validation.NumericPasswordValidator"},
]

LANGUAGE_CODE = "ar"
TIME_ZONE = "Asia/Baghdad"
USE_I18N = True
USE_TZ = True

STATIC_URL = "static/"
STATIC_ROOT = DATA_DIR / "static"
MEDIA_URL = "media/"
MEDIA_ROOT = DATA_DIR / "media"
FILE_UPLOAD_MAX_MEMORY_SIZE = 5 * 1024 * 1024

DEFAULT_AUTO_FIELD = "django.db.models.BigAutoField"

SESSION_COOKIE_HTTPONLY = True
CSRF_COOKIE_HTTPONLY = True
X_FRAME_OPTIONS = "DENY"
