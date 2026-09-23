from __future__ import annotations

import pytest
from sqlalchemy.orm import Session

from swetrack.infrastructure.database.base import get_engine, get_sessionmaker, init_db, register_all_domain_models

register_all_domain_models()


@pytest.fixture
def db_session() -> Session:
    """A fresh, isolated in-memory SQLite session for one test."""
    engine = get_engine("sqlite:///:memory:")
    init_db(engine)
    session = get_sessionmaker(engine)()
    try:
        yield session
    finally:
        session.close()
        engine.dispose()
