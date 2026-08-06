import json
import sqlite3
from contextlib import contextmanager
from datetime import UTC, datetime
from typing import Any, Iterator

from app.config import get_settings


TABLES = {"knowledge", "appointments", "notes", "metrics", "tool_events"}


def now_iso() -> str:
    return datetime.now(UTC).isoformat()


def using_postgres() -> bool:
    return get_settings().database_url.startswith(("postgresql://", "postgres://"))


@contextmanager
def connection() -> Iterator[Any]:
    settings = get_settings()
    if using_postgres():
        # Imported only in production; local development remains SQLite-only.
        import psycopg
        from psycopg.rows import dict_row

        db = psycopg.connect(settings.database_url, row_factory=dict_row)
    else:
        settings.database_path.parent.mkdir(parents=True, exist_ok=True)
        db = sqlite3.connect(settings.database_path)
        db.row_factory = sqlite3.Row
    try:
        yield db
        db.commit()
    except Exception:
        db.rollback()
        raise
    finally:
        db.close()


def init_db() -> None:
    id_column = "BIGSERIAL PRIMARY KEY" if using_postgres() else "INTEGER PRIMARY KEY AUTOINCREMENT"
    schema = f"""
        CREATE TABLE IF NOT EXISTS knowledge (
            id {id_column},
            category TEXT NOT NULL,
            question TEXT NOT NULL,
            answer TEXT NOT NULL,
            created_at TEXT NOT NULL
        );
        CREATE TABLE IF NOT EXISTS appointments (
            id {id_column},
            customer_name TEXT NOT NULL,
            customer_phone TEXT NOT NULL,
            service TEXT NOT NULL,
            starts_at TEXT NOT NULL,
            status TEXT NOT NULL DEFAULT 'scheduled',
            created_at TEXT NOT NULL
        );
        CREATE TABLE IF NOT EXISTS notes (
            id {id_column},
            customer_phone TEXT,
            content TEXT NOT NULL,
            created_at TEXT NOT NULL
        );
        CREATE TABLE IF NOT EXISTS metrics (
            id {id_column},
            event TEXT NOT NULL,
            value REAL NOT NULL DEFAULT 1,
            metadata TEXT NOT NULL DEFAULT '{{}}',
            created_at TEXT NOT NULL
        );
        CREATE TABLE IF NOT EXISTS tool_events (
            id {id_column},
            tool_call_id TEXT NOT NULL,
            tool_name TEXT NOT NULL,
            arguments TEXT NOT NULL,
            outcome TEXT NOT NULL,
            created_at TEXT NOT NULL
        );
    """
    with connection() as db:
        if using_postgres():
            for statement in schema.split(";"):
                if statement.strip():
                    db.execute(statement)
        else:
            db.executescript(schema)


def insert(table: str, values: dict[str, Any]) -> dict[str, Any]:
    if table not in TABLES:
        raise ValueError("Invalid table")
    values = {**values, "created_at": now_iso()}
    columns = ", ".join(values)
    placeholder = "%s" if using_postgres() else "?"
    placeholders = ", ".join(placeholder for _ in values)
    serialized = [json.dumps(v) if isinstance(v, (dict, list)) else v for v in values.values()]
    with connection() as db:
        if using_postgres():
            cursor = db.execute(
                f"INSERT INTO {table} ({columns}) VALUES ({placeholders}) RETURNING *",
                serialized,
            )
            row = cursor.fetchone()
        else:
            cursor = db.execute(
                f"INSERT INTO {table} ({columns}) VALUES ({placeholders})",
                serialized,
            )
            row = db.execute(f"SELECT * FROM {table} WHERE id = ?", (cursor.lastrowid,)).fetchone()
    return dict(row)


def list_rows(table: str) -> list[dict[str, Any]]:
    if table not in TABLES:
        raise ValueError("Invalid table")
    with connection() as db:
        rows = db.execute(f"SELECT * FROM {table} ORDER BY id DESC").fetchall()
    return [dict(row) for row in rows]


def log_tool_event(
    tool_call_id: str,
    tool_name: str,
    arguments: dict[str, Any],
    outcome: str,
) -> None:
    insert(
        "tool_events",
        {
            "tool_call_id": tool_call_id,
            "tool_name": tool_name,
            "arguments": json.dumps(arguments, ensure_ascii=False, separators=(",", ":")),
            "outcome": outcome,
        },
    )
