# =============================================================================
# password_hashing.py — Password hashing for personnel accounts
#
# Stored format (fits personnel.password_hash VARCHAR(255)):
#     pbkdf2_sha256$<iterations>$<salt>$<hash>      (salt/hash: URL-safe base64)
# Older records may still hold the plain password (or its SHA-256 hex); they are
# accepted by verify_password() and upgraded to the hashed format on the next
# successful online login (needs_upgrade()).
#
# The SAME file exists in utils/ (client) and certificate_manager_api/ (server),
# because the server folder is deployed on its own. Keep both copies identical.
# =============================================================================

import base64
import hashlib
import hmac
import os

ALGORITHM = "pbkdf2_sha256"
ITERATIONS = 200_000
DISABLED_VALUES = {"", "disabled"}


def _b64(data: bytes) -> str:
    return base64.urlsafe_b64encode(data).decode("ascii").rstrip("=")


def _unb64(text: str) -> bytes:
    return base64.urlsafe_b64decode(text + "=" * (-len(text) % 4))


def is_hashed(stored: str | None) -> bool:
    return str(stored or "").startswith(ALGORITHM + "$")


def is_disabled(stored: str | None) -> bool:
    """Accounts with no password or 'disabled' (e.g. signers) cannot log in."""
    return str(stored or "").strip().lower() in DISABLED_VALUES


def hash_password(password: str) -> str:
    salt = os.urandom(16)
    digest = hashlib.pbkdf2_hmac("sha256", password.encode("utf-8"), salt, ITERATIONS)
    return f"{ALGORITHM}${ITERATIONS}${_b64(salt)}${_b64(digest)}"


def verify_password(password: str, stored: str | None) -> bool:
    """Check a typed password against the stored value (hashed, or legacy plain / SHA-256)."""
    if not password or is_disabled(stored):
        return False
    stored = str(stored).strip()
    if is_hashed(stored):
        try:
            _algo, iterations, salt, expected = stored.split("$", 3)
            digest = hashlib.pbkdf2_hmac("sha256", password.encode("utf-8"), _unb64(salt), int(iterations))
            return hmac.compare_digest(_b64(digest), expected)
        except (ValueError, TypeError):
            return False
    # Legacy records: plain text or unsalted SHA-256 hex
    legacy_sha = hashlib.sha256(password.encode("utf-8")).hexdigest()
    return hmac.compare_digest(stored, password) or hmac.compare_digest(stored.lower(), legacy_sha)


def needs_upgrade(stored: str | None) -> bool:
    """True for a legacy (not yet hashed) password that should be re-saved as a hash."""
    return not is_disabled(stored) and not is_hashed(stored)


def prepare_for_storage(password: str | None) -> str:
    """Value to write into personnel.password_hash for a password typed by a person."""
    value = str(password or "")
    if is_disabled(value) or is_hashed(value):
        return value.strip()
    return hash_password(value)
