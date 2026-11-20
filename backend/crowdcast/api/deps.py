"""Shared FastAPI dependencies."""

from __future__ import annotations

from collections.abc import Iterator
from typing import Annotated

from fastapi import Depends
from sqlalchemy.orm import Session

from crowdcast.storage.interfaces import session_scope


def get_session() -> Iterator[Session]:
    """One transaction per request: committed on success, rolled back on error.

    Overridden in tests with a session that is always rolled back.
    """
    with session_scope() as session:
        yield session


SessionDep = Annotated[Session, Depends(get_session)]
