"""Application settings, read from environment variables and the `.env` file.

Variables follow DOCUMENTATION/18_DEPLOYMENT_PLAN.md §3, minus the ones that only
existed for authentication (JWT_SECRET, CV_API_KEY) or live camera URIs (FERNET_KEY):
decision D7 removed auth and decision D6 removed live cameras (see WORKFLOW.md).
"""

from functools import lru_cache
from pathlib import Path

from pydantic import Field
from pydantic_settings import BaseSettings, SettingsConfigDict

# backend/crowdcast/common/config.py -> repo root is three levels above `crowdcast/`.
REPO_ROOT = Path(__file__).resolve().parents[3]


class Settings(BaseSettings):
    model_config = SettingsConfigDict(
        env_file=(REPO_ROOT / ".env", REPO_ROOT / "backend" / ".env"),
        env_file_encoding="utf-8",
        extra="ignore",
    )

    database_url: str = Field(
        default="postgresql+psycopg://crowdcast:crowdcast@127.0.0.1:5432/crowdcast",
        description="SQLAlchemy URL of the PostgreSQL database.",
    )
    cors_origins: list[str] = Field(
        default=["http://localhost:5173"],
        description="Allowed frontend origins (Vite dev server by default).",
    )
    # No prediction-offset or model-directory setting: the cycle runs on event time taken from
    # the data (doc 10 §12), and model artefacts are always under <repo>/models (9.4 audit).
    retention_days_data: int = Field(default=365, ge=1)


@lru_cache
def get_settings() -> Settings:
    """Return the process-wide settings (cached; call `get_settings.cache_clear()` in tests)."""
    return Settings()
