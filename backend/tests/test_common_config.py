import pytest

from crowdcast.common.config import Settings


def test_defaults_point_to_local_postgres() -> None:
    s = Settings(_env_file=None)
    assert s.database_url.startswith("postgresql+psycopg://")
    assert s.retention_days_data == 365


def test_environment_overrides(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setenv("DATABASE_URL", "postgresql+psycopg://u:p@db:5432/x")
    monkeypatch.setenv("RETENTION_DAYS_DATA", "30")
    s = Settings(_env_file=None)
    assert s.database_url == "postgresql+psycopg://u:p@db:5432/x"
    assert s.retention_days_data == 30


def test_out_of_range_value_rejected(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setenv("RETENTION_DAYS_DATA", "0")
    with pytest.raises(ValueError):
        Settings(_env_file=None)
