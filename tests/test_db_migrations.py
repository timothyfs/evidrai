from pathlib import Path

from evidrai.db import MIGRATIONS_TABLE, Migration, load_migrations, run_migrations, split_sql_statements


class FakeCursor:
    def __init__(self):
        self.statements = []
        self.rows = []

    def execute(self, sql, params=None):
        self.statements.append((sql, params))
        if sql.strip().startswith("SELECT version"):
            self.rows = []

    def fetchall(self):
        return self.rows

    def __enter__(self):
        return self

    def __exit__(self, exc_type, exc, tb):
        return False


class FakeConnection:
    def __init__(self):
        self.cursor_obj = FakeCursor()
        self.committed = False

    def cursor(self):
        return self.cursor_obj

    def commit(self):
        self.committed = True

    def __enter__(self):
        return self

    def __exit__(self, exc_type, exc, tb):
        return False


def test_load_migrations_finds_initial_schema_file():
    migrations = load_migrations()

    assert migrations[0].version == "001"
    assert "CREATE TABLE IF NOT EXISTS assessments" in migrations[0].sql
    assert "CREATE TABLE IF NOT EXISTS feedback" in migrations[0].sql


def test_split_sql_statements_handles_migration_file():
    sql = """
    CREATE TABLE example (id text);
    CREATE INDEX example_idx ON example (id);
    """

    assert split_sql_statements(sql) == [
        "CREATE TABLE example (id text)",
        "CREATE INDEX example_idx ON example (id)",
    ]


def test_run_migrations_records_unapplied_versions():
    conn = FakeConnection()
    migration = Migration(version="001", name="test", path=Path("001_test.sql"), sql="CREATE TABLE example (id text)")

    applied = run_migrations(lambda: conn, migrations=[migration])

    assert applied == ["001"]
    assert conn.committed is True
    executed_sql = "\n".join(statement for statement, _params in conn.cursor_obj.statements)
    assert MIGRATIONS_TABLE in executed_sql
    assert "CREATE TABLE example" in executed_sql
    assert any(params == ("001", "test") for _statement, params in conn.cursor_obj.statements)
