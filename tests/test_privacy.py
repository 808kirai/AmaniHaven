from app import db
from app.config import get_settings
from app.privacy import decrypt, encrypt, hash_phone, mask_phone, normalize_msisdn


def test_number_formats_hash_the_same():
    assert normalize_msisdn("0712 345 678") == "+254712345678"
    assert hash_phone("0712345678") == hash_phone("+254712345678") == hash_phone("254712345678")
    assert normalize_msisdn("712 345 678") == "+254712345678"
    assert normalize_msisdn("00254712345678") == "+254712345678"
    assert normalize_msisdn("0110 123 456") == "+254110123456"


def test_encryption_round_trip():
    token = encrypt("secret words")
    assert "secret" not in token
    assert decrypt(token) == "secret words"


def test_mask_phone():
    assert mask_phone("+254712345678") == "+25471****678"


def test_no_plain_phone_number_in_database_file():
    db.get_or_create_user("+254712345678")
    # closing the connection flushes everything to disk
    db.reset_for_tests()
    raw = open(get_settings().database_path, "rb").read()
    wal = get_settings().database_path + "-wal"
    try:
        raw += open(wal, "rb").read()
    except FileNotFoundError:
        pass
    assert b"712345678" not in raw
