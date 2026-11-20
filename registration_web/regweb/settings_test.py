"""Settings for pytest: no secrets or real data folder needed."""
import os
import tempfile

os.environ.setdefault("REGWEB_SECRET_KEY", "test-only-key")
os.environ.setdefault("REGWEB_DATA_DIR", tempfile.mkdtemp(prefix="regweb_test_"))

from .settings import *  # noqa: E402,F401,F403

ALLOWED_HOSTS = ["testserver"]
PASSWORD_HASHERS = ["django.contrib.auth.hashers.MD5PasswordHasher"]
