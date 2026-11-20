import pytest

from crowdcast.common.config import Settings


def test_defaults_point_to_local_postgres() -> None:
    s = Settings(_env_file=None)
    assert s.database_url.startswith("postgresql+psycopg://")
    assert s.prediction_offset_s == 10


def test_environment_overrides(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setenv("DATABASE_URL", "postgresql+psycopg://u:p@db:5432/x")
    monkeypatch.setenv("PREDICTION_OFFSET_S", "15")
    s = Settings(_env_file=None)
    assert s.database_url == "postgresql+psycopg://u:p@db:5432/x"
    assert s.prediction_offset_s == 15


def test_offset_out_of_range_rejected(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setenv("PREDICTION_OFFSET_S", "70")
    with pytest.raises(ValueError):
        Settings(_env_file=None)
