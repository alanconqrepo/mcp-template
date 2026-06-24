from __future__ import annotations

import logging
from collections.abc import Generator
from contextlib import contextmanager

import pyodbc
from pydantic import BaseModel

logger = logging.getLogger(__name__)


class SqlConnectionConfig(BaseModel):
    host: str
    port: int = 1433
    database: str
    username: str
    password: str
    driver: str = "ODBC Driver 18 for SQL Server"
    trust_server_certificate: bool = False


def _resolve_config(connection_name: str | None) -> SqlConnectionConfig:
    from mcp_server.config import get_settings

    settings = get_settings()
    name = connection_name or settings.SQL_DEFAULT_CONNECTION
    raw = settings.SQL_CONNECTIONS.get(name)
    if raw is None:
        available = list(settings.SQL_CONNECTIONS.keys())
        raise ValueError(f"SQL connection '{name}' not found. Available: {available}")
    return SqlConnectionConfig(**raw)


@contextmanager
def get_connection(
    connection_name: str | None = None,
    database: str | None = None,
) -> Generator[pyodbc.Connection, None, None]:
    """Open a named SQL Server connection, optionally overriding the database. Closes on exit."""
    cfg = _resolve_config(connection_name)
    db = database or cfg.database
    conn_str = (
        f"DRIVER={{{cfg.driver}}};"
        f"SERVER={cfg.host},{cfg.port};"
        f"DATABASE={db};"
        f"UID={cfg.username};"
        f"PWD={cfg.password};"
        f"TrustServerCertificate={'yes' if cfg.trust_server_certificate else 'no'};"
    )
    conn = pyodbc.connect(conn_str, autocommit=True)
    try:
        yield conn
    finally:
        conn.close()


def fetch_rows(cursor: pyodbc.Cursor) -> list[dict]:
    """Convert all cursor results to a list of dicts."""
    if cursor.description is None:
        return []
    cols = [d[0] for d in cursor.description]
    return [dict(zip(cols, row)) for row in cursor.fetchall()]
