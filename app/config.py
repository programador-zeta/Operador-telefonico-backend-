from functools import lru_cache
from pathlib import Path

from dotenv import load_dotenv

load_dotenv()


class Settings:
    def __init__(self) -> None:
        import os

        self.app_name = os.getenv("APP_NAME", "Operador Telefonico MVP")
        self.app_env = os.getenv("APP_ENV", "development")
        self.api_key = os.getenv("API_KEY", "")
        self.dashboard_user = os.getenv("DASHBOARD_USER", "admin")
        self.dashboard_password = os.getenv("DASHBOARD_PASSWORD", "") or self.api_key
        self.twilio_account_sid = os.getenv("TWILIO_ACCOUNT_SID", "").strip()
        self.twilio_auth_token = os.getenv("TWILIO_AUTH_TOKEN", "").strip()
        self.twilio_whatsapp_from = os.getenv(
            "TWILIO_WHATSAPP_FROM", "whatsapp:+14155238886"
        ).strip()
        self.twilio_appointment_content_sid = os.getenv(
            "TWILIO_APPOINTMENT_CONTENT_SID",
            "HXb5b62575e6e4ff6129ad7c8efe1f983e",
        ).strip()
        self.database_path = Path(os.getenv("DATABASE_PATH", "./data/mvp.db"))
        database_url = os.getenv("DATABASE_URL", "").strip()
        # Render may provide the legacy postgres:// prefix.
        if database_url.startswith("postgres://"):
            database_url = "postgresql://" + database_url.removeprefix("postgres://")
        self.database_url = database_url


@lru_cache
def get_settings() -> Settings:
    return Settings()
