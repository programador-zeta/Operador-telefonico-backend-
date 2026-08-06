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
        self.database_path = Path(os.getenv("DATABASE_PATH", "./data/mvp.db"))
        database_url = os.getenv("DATABASE_URL", "").strip()
        # Render may provide the legacy postgres:// prefix.
        if database_url.startswith("postgres://"):
            database_url = "postgresql://" + database_url.removeprefix("postgres://")
        self.database_url = database_url


@lru_cache
def get_settings() -> Settings:
    return Settings()
