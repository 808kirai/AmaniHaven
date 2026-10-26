import json
import os
from dataclasses import dataclass, field
from functools import lru_cache

from dotenv import load_dotenv

# read .env when it exists so local runs pick up their settings
load_dotenv()


# one support line we can point people to
@dataclass(frozen=True)
class helpline:
    key: str
    name_en: str
    name_sw: str
    number: str
    free: bool = True


# kenya defaults, override them with HELPLINES_JSON for another country
# call every number before launch, a wrong crisis number is the worst bug this product could ship
default_helplines = [
    helpline("emergency", "Emergency", "Dharura", "999 / 112"),
    helpline("redcross", "Red Cross", "Red Cross", "1199"),
    helpline("gbv", "GBV line", "Simu ya GBV", "1195"),
    helpline("child", "Childline", "Childline", "116"),
    helpline("befrienders", "Befrienders Kenya", "Befrienders Kenya", "0722178177", free=False),
]


def _helplines():
    raw = os.getenv("HELPLINES_JSON")
    if not raw:
        return default_helplines
    return [helpline(**h) for h in json.loads(raw)]


def _counselor_tokens():
    # COUNSELOR_TOKENS looks like amina:longtoken,brian:othertoken
    # returns token to counselor name so a request token can be looked up directly
    out = {}
    for pair in filter(None, os.getenv("COUNSELOR_TOKENS", "").split(",")):
        name, _, token = pair.strip().partition(":")
        if name and token:
            out[token] = name
    return out


def _env(name, default=""):
    return lambda: os.getenv(name, default)


# every setting the app reads, loaded from environment variables
@dataclass(frozen=True)
class settings:
    env: str = field(default_factory=_env("APP_ENV", "development"))
    database_path: str = field(default_factory=_env("DATABASE_PATH", "amanihaven.db"))
    default_language: str = field(default_factory=_env("DEFAULT_LANGUAGE", "sw"))

    # privacy
    phone_hash_pepper: str = field(default_factory=_env("PHONE_HASH_PEPPER"))
    data_encryption_key: str = field(default_factory=_env("DATA_ENCRYPTION_KEY"))
    retention_days: int = field(default_factory=lambda: int(os.getenv("RETENTION_DAYS", "30")))

    # africa's talking gateway
    sms_gateway: str = field(default_factory=_env("SMS_GATEWAY", "console"))
    at_username: str = field(default_factory=_env("AT_USERNAME", "sandbox"))
    at_api_key: str = field(default_factory=_env("AT_API_KEY"))
    at_sender_id: str = field(default_factory=_env("AT_SENDER_ID"))
    ussd_code: str = field(default_factory=_env("USSD_CODE", "*384*123#"))
    sms_shortcode: str = field(default_factory=_env("SMS_SHORTCODE", "22123"))
    webhook_secret: str = field(default_factory=_env("WEBHOOK_SECRET"))

    # triage
    llm_enabled: bool = field(default_factory=lambda: os.getenv("LLM_ENABLED", "true").lower() == "true")
    llm_model: str = field(default_factory=_env("LLM_MODEL", "claude-opus-5-5"))
    llm_timeout_seconds: float = field(default_factory=lambda: float(os.getenv("LLM_TIMEOUT_SECONDS", "20")))

    # people and limits
    max_replies_per_hour: int = field(default_factory=lambda: int(os.getenv("MAX_REPLIES_PER_HOUR", "20")))
    counselor_alert_numbers: list = field(
        default_factory=lambda: [n.strip() for n in os.getenv("COUNSELOR_ALERT_NUMBERS", "").split(",") if n.strip()]
    )
    counselor_tokens: dict = field(default_factory=_counselor_tokens)
    admin_token: str = field(default_factory=_env("ADMIN_TOKEN"))
    helplines: list = field(default_factory=_helplines)

    # the public /demo page with a pretend phone, only for a sandbox demo server
    demo_enabled: bool = field(default_factory=lambda: os.getenv("DEMO_ENABLED", "false").lower() == "true")

    @property
    def is_production(self):
        return self.env == "production"

    def validate(self):
        # refuse to start in production with secrets missing
        if not self.is_production:
            return
        required = {
            "PHONE_HASH_PEPPER": self.phone_hash_pepper,
            "DATA_ENCRYPTION_KEY": self.data_encryption_key,
            "AT_API_KEY": self.at_api_key,
            "WEBHOOK_SECRET": self.webhook_secret,
            "ADMIN_TOKEN": self.admin_token,
        }
        missing = [name for name, value in required.items() if not value]
        if missing:
            raise RuntimeError(f"missing required production settings {', '.join(missing)}")
        if not self.counselor_tokens:
            raise RuntimeError("COUNSELOR_TOKENS must name at least one counselor in production")
        if self.sms_gateway != "africastalking":
            raise RuntimeError("SMS_GATEWAY must be africastalking in production")
        # demo visitors can open crisis cases, which must never page a real on call team
        if self.demo_enabled and self.at_username != "sandbox":
            raise RuntimeError("DEMO_ENABLED is only allowed with the africa's talking sandbox")


@lru_cache
def get_settings():
    # built once and reused, tests clear the cache to swap settings
    s = settings()
    s.validate()
    return s
