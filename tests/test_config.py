import pytest
from cryptography.fernet import Fernet

from app.config import get_settings

from .conftest import reload_settings


@pytest.fixture
def production(monkeypatch):
    # a complete production setup, each test then breaks one thing
    for name, value in {"APP_ENV": "production", "AT_USERNAME": "amanihaven", "AT_API_KEY": "k",
                        "WEBHOOK_SECRET": "w", "SMS_GATEWAY": "africastalking",
                        "DATA_ENCRYPTION_KEY": Fernet.generate_key().decode()}.items():
        monkeypatch.setenv(name, value)
    reload_settings()


def test_complete_production_settings_start(production):
    assert get_settings().is_production


def test_production_needs_alert_numbers(production, monkeypatch):
    monkeypatch.setenv("COUNSELOR_ALERT_NUMBERS", "")
    reload_settings()
    with pytest.raises(RuntimeError, match="COUNSELOR_ALERT_NUMBERS"):
        get_settings()


def test_production_checks_the_encryption_key(production, monkeypatch):
    monkeypatch.setenv("DATA_ENCRYPTION_KEY", "not-a-real-key")
    reload_settings()
    with pytest.raises(RuntimeError, match="DATA_ENCRYPTION_KEY"):
        get_settings()
