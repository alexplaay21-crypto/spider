from functools import lru_cache
from pathlib import Path
import os

from pydantic_settings import BaseSettings, SettingsConfigDict


class Settings(BaseSettings):
    model_config = SettingsConfigDict(
        env_file=".env",
        env_file_encoding="utf-8",
        extra="ignore",
    )

    BACKEND_URL: str
    CORE_AUTH_TOKEN: str

    TELEGRAM_API_ID: int
    TELEGRAM_API_HASH: str

    STORE_BOT_USERNAME: str = ""

    LOG_LEVEL: str = "INFO"
    ENVIRONMENT: str = "development"

    MODULES_DIRECTORY: str = "./modules_data"
    DATA_DIRECTORY: str = "./data"

    HEARTBEAT_INTERVAL_SECONDS: int = 300
    DEVICE_NAME: str = "termux"

    AUTH_METHOD: str = "web"

    # Railway binds the application to 0.0.0.0:$PORT.
    LOCAL_AUTH_HOST: str = "127.0.0.1"
    LOCAL_AUTH_PORT: int = 8765

    # Public HTTPS address used for the login link.
    PUBLIC_BASE_URL: str = ""

    @property
    def railway_port(self) -> int:
        return int(os.getenv("PORT", str(self.LOCAL_AUTH_PORT)))

    @property
    def public_base_url(self) -> str:
        value = self.PUBLIC_BASE_URL.strip().rstrip("/")
        if value:
            return value

        # Useful fallback for Railway.
        domain = os.getenv("RAILWAY_PUBLIC_DOMAIN", "").strip()
        if domain:
            return f"https://{domain}"

        return ""

    @property
    def data_dir(self) -> Path:
        p = Path(self.DATA_DIRECTORY)
        p.mkdir(parents=True, exist_ok=True)
        return p

    @property
    def modules_dir(self) -> Path:
        p = Path(self.MODULES_DIRECTORY)
        p.mkdir(parents=True, exist_ok=True)
        return p


@lru_cache
def get_settings() -> Settings:
    return Settings()


settings = get_settings()
