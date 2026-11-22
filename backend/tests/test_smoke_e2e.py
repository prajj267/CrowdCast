"""Safety guard of the end-to-end smoke script (WORKFLOW 9.1): it may only touch *_smoke."""

from __future__ import annotations

import pytest

from tools.smoke_e2e import admin_dsn, smoke_url

BASE = "postgresql+psycopg://crowdcast:secret@127.0.0.1:5432/crowdcast"


def test_only_the_database_name_changes() -> None:
    assert smoke_url(BASE) == "postgresql+psycopg://crowdcast:secret@127.0.0.1:5432/crowdcast_smoke"


def test_refuses_a_non_smoke_database() -> None:
    with pytest.raises(ValueError, match="_smoke"):
        smoke_url(BASE, "crowdcast")


def test_admin_connection_uses_the_maintenance_database() -> None:
    dsn = admin_dsn(BASE)
    assert "dbname=postgres" in dsn and "host=127.0.0.1" in dsn and "port=5432" in dsn
