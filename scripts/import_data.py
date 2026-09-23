"""CLI: restore a database backup produced by scripts/export_data.py.

Job Radar Checkpoint 8. Inserts rows only -- intended to restore a backup
onto a fresh/empty database (e.g. SWETRACK_DATABASE_URL pointed at a new
file), not to merge with an already-populated one. Restoring on top of
existing rows with colliding primary keys will fail with an integrity
error rather than silently overwriting anything.

    SWETRACK_DATABASE_URL="sqlite:///var/swetrack-restored.db" \\
        python scripts/import_data.py --in var/backups/swetrack-export-20260115T120000Z.json
"""

from __future__ import annotations

import argparse
import json
from pathlib import Path

from swetrack.infrastructure.database.base import get_engine, init_db, register_all_domain_models
from swetrack.infrastructure.database.export import import_all


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    parser.add_argument("--in", dest="in_path", type=Path, required=True)
    args = parser.parse_args()

    if not args.in_path.exists():
        raise SystemExit(f"Backup file not found: {args.in_path}")

    data = json.loads(args.in_path.read_text(encoding="utf-8"))

    register_all_domain_models()
    engine = get_engine()
    init_db(engine)
    inserted = import_all(engine, data)

    print(f"Restored from {args.in_path}")
    for table_name, count in sorted(inserted.items()):
        if count:
            print(f"  {table_name}: {count} row(s)")


if __name__ == "__main__":
    main()
