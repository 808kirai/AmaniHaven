import asyncio

import pytest
from cryptography.fernet import Fernet

from app import db
from app.config import get_settings
from app.gateway import console_gateway, set_gateway

counselor_token = "test-counselor-token"
admin_token = "test-admin-token"
alert_number = "+254700000001"


@pytest.fixture(autouse=True)
def env(tmp_path, monkeypatch):
    # every test gets its own database, fresh keys and no network
    monkeypatch.setenv("APP_ENV", "test")
    monkeypatch.setenv("DATABASE_PATH", str(tmp_path / "test.db"))
    monkeypatch.setenv("LLM_ENABLED", "false")
    monkeypatch.setenv("SMS_GATEWAY", "console")
    monkeypatch.setenv("PHONE_HASH_PEPPER", "test-pepper")
    monkeypatch.setenv("DATA_ENCRYPTION_KEY", Fernet.generate_key().decode())
    monkeypatch.setenv("COUNSELOR_TOKENS", f"amina:{counselor_token}")
    monkeypatch.setenv("ADMIN_TOKEN", admin_token)
    monkeypatch.setenv("COUNSELOR_ALERT_NUMBERS", alert_number)
    monkeypatch.setenv("WEBHOOK_SECRET", "")
    monkeypatch.setenv("DEFAULT_LANGUAGE", "en")
    get_settings.cache_clear()
    db.reset_for_tests()
    yield
    db.reset_for_tests()
    get_settings.cache_clear()


@pytest.fixture
def gateway():
    # records every sms so tests can read what was sent
    gw = console_gateway()
    set_gateway(gw)
    yield gw
    set_gateway(None)


def run(coro):
    return asyncio.run(coro)


def reload_settings():
    get_settings.cache_clear()
