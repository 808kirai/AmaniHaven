import hashlib
import hmac
import logging
import re

from cryptography.fernet import Fernet, InvalidToken

from app.config import get_settings

log = logging.getLogger(__name__)

# phone numbers are never stored in plain text
# each person is known by a keyed hash, so a leaked database can't be turned back into numbers without the pepper
# the number itself is kept encrypted, only so a counselor can reply or call back

# stand in key for local runs without DATA_ENCRYPTION_KEY
_dev_key = None


def _fernet():
    global _dev_key
    key = get_settings().data_encryption_key
    if key:
        return Fernet(key.encode())
    if _dev_key is None:
        log.warning("DATA_ENCRYPTION_KEY not set, using a throwaway key so stored data is unreadable after a restart")
        _dev_key = Fernet.generate_key()
    return Fernet(_dev_key)


def normalize_msisdn(phone):
    # one format for every number so the same person always gets the same hash
    # a kenyan local number like 0712 345 678 becomes +254712345678
    digits = re.sub(r"[^\d+]", "", phone or "")
    if digits.startswith("+"):
        return digits
    if digits.startswith("0") and len(digits) == 10:
        return "+254" + digits[1:]
    return "+" + digits


def hash_phone(phone):
    pepper = get_settings().phone_hash_pepper or "dev-only-pepper"
    return hmac.new(pepper.encode(), normalize_msisdn(phone).encode(), hashlib.sha256).hexdigest()


def encrypt(plaintext):
    return _fernet().encrypt(plaintext.encode()).decode()


def decrypt(token):
    # returns None instead of crashing when the key changed since the value was saved
    if not token:
        return None
    try:
        return _fernet().decrypt(token.encode()).decode()
    except InvalidToken:
        log.error("could not decrypt a stored value, the key may have changed")
        return None


def mask_phone(phone):
    # enough of the number for a counselor to tell people apart and no more
    if not phone:
        return "unknown"
    return phone[:6] + "*" * max(0, len(phone) - 9) + phone[-3:]
