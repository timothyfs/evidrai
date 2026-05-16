from __future__ import annotations

import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

from evidrai.config import database_url
from evidrai.db import run_migrations
from evidrai.reports import PostgresReportStore


def main() -> int:
    url = database_url()
    if not url:
        print("DATABASE_URL is not configured; no migrations applied.")
        return 1
    store = PostgresReportStore(url)
    applied = run_migrations(store._connect)
    if applied:
        print(f"Applied migrations: {', '.join(applied)}")
    else:
        print("No migrations to apply.")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
