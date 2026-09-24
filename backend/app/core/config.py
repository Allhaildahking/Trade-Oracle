"""Application configuration loaded from environment variables."""

from __future__ import annotations

from dataclasses import dataclass
import os


@dataclass(frozen=True, slots=True)
class Settings:
    app_env: str = "development"
    log_level: str = "INFO"
    twelve_data_api_key: str = ""
    alpha_vantage_api_key: str = ""
    fred_api_key: str = ""
    groq_api_key: str = ""
    trading_economics_api_key: str = ""
    telegram_bot_token: str = ""

    @classmethod
    def from_env(cls) -> Settings:
        return cls(
            app_env=os.getenv("APP_ENV", "development"),
            log_level=os.getenv("LOG_LEVEL", "INFO").upper(),
            twelve_data_api_key=os.getenv("TWELVE_DATA_API_KEY", ""),
            alpha_vantage_api_key=os.getenv("ALPHA_VANTAGE_API_KEY", ""),
            fred_api_key=os.getenv("FRED_API_KEY", ""),
            groq_api_key=os.getenv("GROQ_API_KEY", ""),
            trading_economics_api_key=os.getenv("TRADING_ECONOMICS_API_KEY", ""),
            telegram_bot_token=os.getenv("TELEGRAM_BOT_TOKEN", ""),
        )


settings = Settings.from_env()
