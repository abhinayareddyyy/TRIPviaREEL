"""SQLite storage for generated trips (so a plan can be reopened by its id)."""
from __future__ import annotations

import json
import os
import secrets
import sqlite3
from datetime import datetime, timezone
from typing import Optional

SCHEMA = """
CREATE TABLE IF NOT EXISTS trips (
    id         TEXT PRIMARY KEY,
    created_at TEXT NOT NULL,
    request    TEXT NOT NULL,
    result     TEXT NOT NULL
)
"""


def _connect(path: str) -> sqlite3.Connection:
    conn = sqlite3.connect(path)
    conn.row_factory = sqlite3.Row
    return conn


def init_db(path: str) -> None:
    os.makedirs(os.path.dirname(os.path.abspath(path)), exist_ok=True)
    with _connect(path) as conn:
        conn.execute(SCHEMA)


def save_trip(path: str, request: dict, result: dict) -> str:
    trip_id = secrets.token_urlsafe(6)
    with _connect(path) as conn:
        conn.execute(
            "INSERT INTO trips (id, created_at, request, result) VALUES (?, ?, ?, ?)",
            (trip_id, datetime.now(timezone.utc).isoformat(timespec="seconds"), json.dumps(request), json.dumps(result)),
        )
    return trip_id


def load_trip(path: str, trip_id: str) -> Optional[dict]:
    with _connect(path) as conn:
        row = conn.execute("SELECT * FROM trips WHERE id = ?", (trip_id,)).fetchone()
    if not row:
        return None
    return {"id": row["id"], "created_at": row["created_at"],
            "request": json.loads(row["request"]), "result": json.loads(row["result"])}
