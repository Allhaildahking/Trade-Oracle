"""Application configuration.

This module intentionally contains configuration only. Provider-specific logic,
credentials, and trading rules should live in their respective modules.
"""

from __future__ import annotations

import os
from dataclasses import dataclass


@dataclass(frozen=True, slots=True)
class Settings:
    app_env: str = "development"
    log_level: str = "INFO"

    @classmethod
    def from_env(cls) -> Settings:
        return cls(
            app_env=os.getenv("APP_ENV", "development"),
            log_level=os.getenv("LOG_LEVEL", "INFO").upper(),
        )


settings = Settings.from_env()
