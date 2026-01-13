from __future__ import annotations

import os


class Settings:
    NEWS_PROVIDER: str = os.environ.get("NEWS_PROVIDER", "none")
    NEWSAPI_KEY: str | None = os.environ.get("NEWSAPI_KEY")
    WIZARD_BASE_URL: str = os.environ.get("WIZARD_BASE_URL", "http://127.0.0.1:11434/api/chat")
    CACHE_TTL_SECONDS: int = int(os.environ.get("CACHE_TTL_SECONDS", "900"))


settings = Settings()
