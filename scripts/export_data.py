"""CLI: back up the entire local database to a portable JSON file.

Job Radar Checkpoint 8. Covers every table across every domain
(applications, interviews, learning, discovered jobs, skill mastery, ...)
via generic table reflection -- see infrastructure/database/export.py.

    python scripts/export_data.py
    python scripts/export_data.py --out var/backups/swetrack-2026-01-15.json
"""

from __future__ import annotations

import argparse
import json
from datetime import datetime, timezone
from pathlib import Path

from swetrack.infrastructure.database.base import get_engine, register_all_domain_models
from swetrack.infrastructure.database.export import export_all
from swetrack.infrastructure.paths import find_repo_root


def _default_out_path() -> Path:
    timestamp = datetime.now(timezone.utc).strftime("%Y%m%dT%H%M%SZ")
    return find_repo_root() / "var" / "backups" / f"swetrack-export-{timestamp}.json"


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    parser.add_argument("--out", type=Path, default=None)
    args = parser.parse_args()

    out_path = args.out or _default_out_path()
    out_path.parent.mkdir(parents=True, exist_ok=True)

    register_all_domain_models()
    engine = get_engine()
    data = export_all(engine)

    out_path.write_text(json.dumps(data, indent=2), encoding="utf-8")

    row_counts = {name: len(rows) for name, rows in data["tables"].items() if rows}
    print(f"Wrote backup to {out_path}")
    for table_name, count in sorted(row_counts.items()):
        print(f"  {table_name}: {count} row(s)")
    if not row_counts:
        print("  (database is currently empty)")


if __name__ == "__main__":
    main()
