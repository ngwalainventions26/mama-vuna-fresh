"""Platform settings, read from environment variables (see .env.example)."""
import os
from pathlib import Path

BASE_DIR = Path(__file__).resolve().parent


def _bool(name: str, default: bool) -> bool:
    v = os.getenv(name)
    if v is None:
        return default
    return v.strip().lower() in ("1", "true", "yes", "on")


def _int(name: str, default: int) -> int:
    try:
        return int(os.getenv(name, default))
    except ValueError:
        return default


class Settings:
    APP_NAME = os.getenv("APP_NAME", "Mama Vuna Fresh")
    ORG_NAME = os.getenv("ORG_NAME", "Ngwala Inventions")
    ENV = os.getenv("APP_ENV", "development")  # development | production

    DATABASE_URL = os.getenv("DATABASE_URL", f"sqlite:///{BASE_DIR.parent / 'data' / 'mamavuna.db'}")
    SECRET_KEY = os.getenv("SECRET_KEY", "dev-only-change-me")
    SESSION_HTTPS_ONLY = _bool("SESSION_HTTPS_ONLY", False)

    # First admin account, created on start-up if no users exist
    ADMIN_EMAIL = os.getenv("ADMIN_EMAIL", "admin@example.org")
    ADMIN_PASSWORD = os.getenv("ADMIN_PASSWORD", "")
    ADMIN_NAME = os.getenv("ADMIN_NAME", "Platform Administrator")

    # Telecom gateway
    USSD_SERVICE_CODE = os.getenv("USSD_SERVICE_CODE", "*149*77#")
    WEBHOOK_TOKEN = os.getenv("WEBHOOK_TOKEN", "")  # if set, /ussd and /sms/* require ?token=
    SMS_PROVIDER = os.getenv("SMS_PROVIDER", "console")  # console | africastalking
    AT_USERNAME = os.getenv("AT_USERNAME", "sandbox")
    AT_API_KEY = os.getenv("AT_API_KEY", "")
    AT_SENDER_ID = os.getenv("AT_SENDER_ID", "")
    AT_SANDBOX = _bool("AT_SANDBOX", True)

    # Programme rules
    LEAD_DAYS = _int("ALERT_LEAD_DAYS", 21)            # alert helpers this many days before a risk window
    ALERT_TIMEOUT_HOURS = _int("ALERT_TIMEOUT_HOURS", 24)  # escalate to next helper after this
    RISK_START_WEEK = _int("RISK_START_WEEK", 28)       # start of protected period (third trimester)
    POSTPARTUM_DAYS = _int("POSTPARTUM_DAYS", 42)       # end of protected period after birth
    SCHEDULER_ENABLED = _bool("SCHEDULER_ENABLED", True)
    SCHEDULER_INTERVAL_MIN = _int("SCHEDULER_INTERVAL_MIN", 15)
    WEEKLY_TIPS_ENABLED = _bool("WEEKLY_TIPS_ENABLED", True)

    TIMEZONE = os.getenv("TZ", "Africa/Dar_es_Salaam")


settings = Settings()
