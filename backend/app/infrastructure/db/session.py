"""Database engine and session management (SQLAlchemy 2).

Designed for scalable use: centralized engine/session factory, request/task
scoped sessions, and explicit transaction boundaries. Defaults to lazy init so
memory-only mode can run without a database.
"""

from __future__ import annotations

from contextlib import contextmanager
from typing import Generator

from sqlalchemy import Engine, create_engine
from sqlalchemy.orm import Session, sessionmaker

from app.core.config import settings

_engine: Engine | None = None
_session_factory: sessionmaker[Session] | None = None


def create_db_engine(database_url: str | None = None, *, echo: bool | None = None) -> Engine:
    url = database_url or settings.database_url
    kwargs: dict = {
        "echo": settings.db_echo if echo is None else echo,
        "future": True,
    }
    if url.startswith("sqlite"):
        # SQLite-friendly defaults for local dev/tests and threaded app servers
        kwargs["connect_args"] = {"check_same_thread": False}
        kwargs["pool_pre_ping"] = False
    else:
        kwargs["pool_pre_ping"] = settings.db_pool_pre_ping
    return create_engine(url, **kwargs)


def get_engine() -> Engine:
    global _engine
    if _engine is None:
        _engine = create_db_engine()
    return _engine


def get_session_factory(engine: Engine | None = None) -> sessionmaker[Session]:
    global _session_factory
    if engine is not None:
        return sessionmaker(bind=engine, autoflush=False, autocommit=False, expire_on_commit=False, future=True)
    if _session_factory is None:
        _session_factory = sessionmaker(
            bind=get_engine(), autoflush=False, autocommit=False, expire_on_commit=False, future=True
        )
    return _session_factory


SessionFactory = sessionmaker[Session]


def get_session() -> Generator[Session, None, None]:
    """FastAPI-compatible dependency/provider yielding a DB session."""
    session = get_session_factory()()
    try:
        yield session
    finally:
        session.close()


@contextmanager
def session_scope() -> Generator[Session, None, None]:
    """Transactional scope for scripts/workers/services."""
    session = get_session_factory()()
    try:
        yield session
        session.commit()
    except Exception:
        session.rollback()
        raise
    finally:
        session.close()


def reset_db_state() -> None:
    """Reset cached engine/session factory (tests/reconfiguration)."""
    global _engine, _session_factory
    if _engine is not None:
        try:
            _engine.dispose()
        except Exception:
            pass
    _engine = None
    _session_factory = None
