"""Engine y sesión. Unit of Work: una transacción por solicitud (ver api/deps.py)."""

from collections.abc import Iterator
from contextlib import contextmanager
from functools import lru_cache

from sqlalchemy import Engine, create_engine
from sqlalchemy.orm import Session

from app.config import get_settings


@lru_cache
def get_engine() -> Engine:
    return create_engine(get_settings().database_url, pool_pre_ping=True)


@contextmanager
def transaccion() -> Iterator[Session]:
    """Commit al salir; rollback ante cualquier error, para no dejar registros parciales."""
    with Session(get_engine()) as session, session.begin():
        yield session
