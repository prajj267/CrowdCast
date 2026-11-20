"""Database engine and session factory (M4)."""

from collections.abc import Iterator
from contextlib import contextmanager
from functools import lru_cache

from sqlalchemy import Engine, create_engine
from sqlalchemy.orm import Session, sessionmaker

from crowdcast.common.config import get_settings

# Session time zone UTC: timestamptz values come back in UTC, and date_trunc('minute', ...)
# in the bucket CHECK is evaluated in UTC, whatever the server default is.
UTC_CONNECT_ARGS = {"options": "-c TimeZone=UTC"}


@lru_cache
def get_engine() -> Engine:
    return create_engine(
        get_settings().database_url, pool_pre_ping=True, connect_args=UTC_CONNECT_ARGS
    )


@lru_cache
def _session_factory() -> sessionmaker[Session]:
    return sessionmaker(bind=get_engine(), expire_on_commit=False)


@contextmanager
def session_scope() -> Iterator[Session]:
    """Transactional session: commits on success, rolls back on error."""
    session = _session_factory()()
    try:
        yield session
        session.commit()
    except Exception:
        session.rollback()
        raise
    finally:
        session.close()
