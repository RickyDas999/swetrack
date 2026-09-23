"""Generic, whole-database export/import: a JSON backup covering every table.

Job Radar Checkpoint 8 ("backups/export... export/import round trip
preserves application history"). Walks ``Base.metadata.sorted_tables``
(every model registered across every domain, in foreign-key dependency
order) via raw SQLAlchemy Core rather than per-domain ORM code -- new
tables added by future domains are backed up automatically, with no
per-domain export code to keep in sync.

``import_all`` is a restore-into-empty-database operation (inserts only,
no upsert/merge-with-existing-data logic): the intended use is restoring a
backup onto a fresh database, not reconciling two live ones.
"""

from __future__ import annotations

from datetime import datetime

from sqlalchemy import DateTime, Engine

from swetrack.infrastructure.database.base import Base

EXPORT_SCHEMA_VERSION = "swetrack-export-v1"


def export_all(engine: Engine) -> dict[str, object]:
    """Every row of every registered table, as JSON-safe plain data."""
    tables_data: dict[str, list[dict]] = {}
    with engine.connect() as conn:
        for table in Base.metadata.sorted_tables:
            rows = conn.execute(table.select()).mappings().all()
            tables_data[table.name] = [_row_to_json_safe(dict(row)) for row in rows]

    return {
        "schema_version": EXPORT_SCHEMA_VERSION,
        "tables": tables_data,
    }


def import_all(engine: Engine, data: dict[str, object]) -> dict[str, int]:
    """Insert every table's rows from an export_all() payload. Returns rows-inserted per table."""
    tables_data = data.get("tables", {})
    inserted: dict[str, int] = {}
    with engine.begin() as conn:
        for table in Base.metadata.sorted_tables:
            rows = tables_data.get(table.name, [])
            if not rows:
                inserted[table.name] = 0
                continue
            typed_rows = [_row_from_json(row, table) for row in rows]
            conn.execute(table.insert(), typed_rows)
            inserted[table.name] = len(typed_rows)
    return inserted


def _row_to_json_safe(row: dict) -> dict:
    return {key: (value.isoformat() if isinstance(value, datetime) else value) for key, value in row.items()}


def _row_from_json(row: dict, table) -> dict:
    result = dict(row)
    for column in table.columns:
        value = result.get(column.name)
        if isinstance(column.type, DateTime) and isinstance(value, str):
            result[column.name] = datetime.fromisoformat(value)
    return result
