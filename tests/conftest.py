from __future__ import annotations

import pytest
from sqlalchemy.orm import Session

from swetrack.domains.applications import models as _applications_models  # noqa: F401 -- registers tables
from swetrack.domains.interviews import models as _interviews_models  # noqa: F401 -- registers tables
from swetrack.domains.jobs import models as _jobs_models  # noqa: F401 -- registers tables
from swetrack.domains.learning import models as _learning_models  # noqa: F401 -- registers tables
from swetrack.infrastructure.database.base import get_engine, get_sessionmaker, init_db


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
