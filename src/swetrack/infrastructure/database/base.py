"""SQLAlchemy engine/session setup for local persistence.

Defaults to a file-based SQLite database under ``var/`` (gitignored,
generated locally) so learning history survives across runs during
development, at $0 cost and with zero external services. Moving to
PostgreSQL later means setting ``SWETRACK_DATABASE_URL`` and adding a
driver dependency -- the ORM models and service layers built on top of
``Base``/``get_sessionmaker`` do not change.
"""

from __future__ import annotations

import os

from sqlalchemy import Engine, create_engine
from sqlalchemy.orm import DeclarativeBase, Session, sessionmaker

from swetrack.infrastructure.paths import find_repo_root

ROOT_DIR = find_repo_root()
DEFAULT_DATABASE_URL = f"sqlite:///{ROOT_DIR / 'var' / 'swetrack.db'}"


class Base(DeclarativeBase):
    """Declarative base shared by every ORM model in the project."""


def get_engine(database_url: str | None = None) -> Engine:
    """Create a SQLAlchemy engine, defaulting to the local SQLite file store.

    ``database_url`` overrides the ``SWETRACK_DATABASE_URL`` environment
    variable, which in turn overrides the local SQLite default. Pass
    ``"sqlite:///:memory:"`` for isolated, disk-free tests.
    """
    url = database_url or os.environ.get("SWETRACK_DATABASE_URL", DEFAULT_DATABASE_URL)
    connect_args = {"check_same_thread": False} if url.startswith("sqlite") else {}
    if url.startswith("sqlite") and ":memory:" not in url:
        (ROOT_DIR / "var").mkdir(parents=True, exist_ok=True)
    return create_engine(url, connect_args=connect_args)


def get_sessionmaker(engine: Engine) -> sessionmaker[Session]:
    return sessionmaker(bind=engine, expire_on_commit=False)


def register_all_domain_models() -> None:
    """Import every domain's ORM models module so Base.metadata is fully populated.

    SQLAlchemy only registers a table when its model *class* is actually
    imported somewhere in the process -- these imports exist purely for
    that side effect (class-body execution registers each table on
    ``Base.metadata``), not for any name they bind. A process that reaches
    the database only through api.py (which transitively imports every
    domain) never needs this explicitly; a standalone script that imports
    only ``infrastructure.database.*`` does, or ``init_db()``/table
    reflection silently sees zero tables. See scripts/export_data.py and
    scripts/import_data.py, and tests/conftest.py's equivalent explicit
    imports.
    """
    import swetrack.domains.applications.models  # noqa: F401
    import swetrack.domains.interviews.models  # noqa: F401
    import swetrack.domains.jobs.models  # noqa: F401
    import swetrack.domains.learning.models  # noqa: F401


def init_db(engine: Engine) -> None:
    """Create all tables from every imported model. Idempotent."""
    Base.metadata.create_all(engine)
