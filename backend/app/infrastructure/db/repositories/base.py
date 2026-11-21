"""Shared helpers for SQLAlchemy repositories."""

from __future__ import annotations

from contextlib import contextmanager
from typing import Iterator

from sqlalchemy.orm import Session, sessionmaker


class SessionProvider:
    """Provides sessions for repositories.

    Repositories can operate on an externally-managed session (transaction/unit of work)
    or create short-lived sessions from a factory for standalone operations.
    """

    def __init__(self, session: Session | None = None, session_factory: sessionmaker[Session] | None = None):
        self._session = session
        self._session_factory = session_factory

    @contextmanager
    def scope(self) -> Iterator[Session]:
        if self._session is not None:
            yield self._session
            return
        if self._session_factory is None:
            raise RuntimeError("No session or session_factory configured")
        session = self._session_factory()
        try:
            yield session
            session.commit()
        except Exception:
            session.rollback()
            raise
        finally:
            session.close()
