"""Shared fixtures.

Tests marked `db` need the PostgreSQL container (`docker compose up -d db`) with the
schema migrated (`uv run alembic upgrade head`). They are skipped, not failed, when the
database is unreachable, so the pure unit tests can always run.

Each db test runs inside a transaction that is rolled back afterwards: nothing persists.
"""

from collections.abc import Iterator

import pytest
from sqlalchemy import create_engine, text
from sqlalchemy.engine import Connection, Engine
from sqlalchemy.exc import OperationalError
from sqlalchemy.orm import Session

from crowdcast.common.config import get_settings
from crowdcast.storage.db import UTC_CONNECT_ARGS


@pytest.fixture(scope="session")
def db_engine() -> Iterator[Engine]:
    engine = create_engine(
        get_settings().database_url,
        connect_args={**UTC_CONNECT_ARGS, "connect_timeout": 3},
    )
    try:
        with engine.connect() as conn:
            has_schema = conn.execute(
                text("SELECT to_regclass('public.crowd_observations') IS NOT NULL")
            ).scalar_one()
    except OperationalError:
        pytest.skip("PostgreSQL not reachable: run `docker compose up -d db`")
    if not has_schema:
        pytest.skip("schema missing: run `uv run alembic upgrade head`")
    yield engine
    engine.dispose()


@pytest.fixture
def db_conn(db_engine: Engine) -> Iterator[Connection]:
    with db_engine.connect() as conn:
        outer = conn.begin()
        try:
            yield conn
        finally:
            outer.rollback()


@pytest.fixture
def db_session(db_conn: Connection) -> Iterator[Session]:
    # Session commits become savepoints inside the outer, rolled-back transaction.
    with Session(bind=db_conn, join_transaction_mode="create_savepoint") as session:
        yield session
