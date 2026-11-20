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
    prediction_offset_s: int = Field(
        default=10,
        ge=0,
        le=50,
        description="Seconds after a minute boundary before the prediction cycle runs "
        "(grace period for late observations, 07 §5).",
    )
    model_dir: Path = Field(
        default=REPO_ROOT / "models",
        description="Directory of the model registry (git-ignored).",
    )
    retention_days_data: int = Field(default=365, ge=1)


@lru_cache
def get_settings() -> Settings:
    """Return the process-wide settings (cached; call `get_settings.cache_clear()` in tests)."""
    return Settings()
