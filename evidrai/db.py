from __future__ import annotations

from dataclasses import dataclass
from pathlib import Path
from typing import Callable, Iterable, Protocol

from evidrai.errors import EvidraiError


MIGRATIONS_DIR = Path(__file__).resolve().parents[1] / "migrations"
MIGRATIONS_TABLE = "evidrai_schema_migrations"


class DatabaseMigrationError(EvidraiError):
    def __init__(self, message: str, *, developer_detail: str = "") -> None:
        super().__init__(message, code="database_migration_error", status_code=500, developer_detail=developer_detail)


class ConnectionFactory(Protocol):
    def __call__(self):
        ...


@dataclass(frozen=True)
class Migration:
    version: str
    name: str
    path: Path
    sql: str


def load_migrations(directory: Path = MIGRATIONS_DIR) -> list[Migration]:
    if not directory.exists():
        return []
    migrations: list[Migration] = []
    for path in sorted(directory.glob("*.sql")):
        version, _, name = path.stem.partition("_")
        if not version.isdigit() or not name:
            continue
        migrations.append(Migration(version=version, name=name, path=path, sql=path.read_text(encoding="utf-8")))
    return migrations


def ensure_migrations_table(cur) -> None:
    cur.execute(
        f"""
        CREATE TABLE IF NOT EXISTS {MIGRATIONS_TABLE} (
            version TEXT PRIMARY KEY,
            name TEXT NOT NULL,
            applied_at TIMESTAMPTZ NOT NULL DEFAULT now()
        )
        """
    )


def applied_versions(cur) -> set[str]:
    cur.execute(f"SELECT version FROM {MIGRATIONS_TABLE}")
    rows = cur.fetchall()
    versions: set[str] = set()
    for row in rows:
        if isinstance(row, dict):
            versions.add(str(row.get("version")))
        else:
            versions.add(str(row[0]))
    return versions


def run_migrations(connect: ConnectionFactory, migrations: Iterable[Migration] | None = None) -> list[str]:
    """Apply unapplied SQL migrations using the supplied connection factory.

    The app still works without a separate deployment step, but schema is now
    controlled by explicit SQL files and a migration ledger rather than ad-hoc
    table creation inside each store.
    """
    migration_list = list(migrations) if migrations is not None else load_migrations()
    if not migration_list:
        return []

    applied: list[str] = []
    try:
        with connect() as conn:
            with conn.cursor() as cur:
                ensure_migrations_table(cur)
                existing = applied_versions(cur)
                for migration in migration_list:
                    if migration.version in existing:
                        continue
                    cur.execute(migration.sql)
                    cur.execute(
                        f"INSERT INTO {MIGRATIONS_TABLE} (version, name) VALUES (%s, %s)",
                        (migration.version, migration.name),
                    )
                    applied.append(migration.version)
            conn.commit()
    except Exception as exc:
        raise DatabaseMigrationError("Could not apply database migrations.", developer_detail=str(exc))
    return applied
